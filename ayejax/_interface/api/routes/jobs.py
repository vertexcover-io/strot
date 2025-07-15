"""
Job routes for creating new API patterns
"""

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

import boto3
import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from playwright.async_api import Browser
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select

import ayejax
from ayejax._interface.api.auth import AuthDependency
from ayejax._interface.api.database import DBSessionDependency, sessionmanager
from ayejax._interface.api.database.models.job import Job
from ayejax._interface.api.database.models.output import Output
from ayejax._interface.api.settings import settings
from ayejax.logging import get_logger
from ayejax.logging.handlers import S3HandlerConfig
from ayejax.pagination.strategy import LimitOffsetInfo, NextCursorInfo, PageOffsetInfo, PageOnlyInfo
from ayejax.tag import TagLiteral
from ayejax.types import Output as AyejaxOutput

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


boto3_session = boto3.Session(
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)


class CreateJobRequest(BaseModel):
    url: HttpUrl
    """Target URL to analyze"""
    tag: TagLiteral
    """Kind of information to look for (e.g. reviews)"""


class CreateJobResponse(BaseModel):
    job_id: UUID


JobStatus = Literal["pending", "ready", "failed"]


class GetJobResponse(BaseModel):
    status: JobStatus
    job_id: UUID
    url: str
    tag: TagLiteral
    message: str
    result: dict[str, Any] | None


@router.post("/", response_model=CreateJobResponse)
async def create_job(
    raw_request: Request,
    request: CreateJobRequest,
    db: DBSessionDependency,
    background_tasks: BackgroundTasks,
    _: AuthDependency,
):
    """Create a new job for API pattern generation"""
    job_id = uuid4()

    job = Job(
        id=job_id,
        url=str(request.url),
        tag=request.tag,
        status="pending",
        message="Analyzing the webpage",
        created_at=datetime.now(timezone.utc),
    )

    db.add(job)
    await db.commit()

    background_tasks.add_task(process_job_request, job_id, request, raw_request.app.state.browser)

    return CreateJobResponse(job_id=job_id)


@router.get("/{job_id}", response_model=GetJobResponse)
async def get_job(
    job_id: UUID,
    db: DBSessionDependency,
    _: AuthDependency,
    limit: int = 5,
    offset: int = 0,
):
    """Get job details"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    result = None
    if job.status == "ready" and job.output_id:
        try:
            result = await execute_api_request(job.output_id, limit, offset)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to execute API request: {e}") from e

    return GetJobResponse(
        status=job.status,
        job_id=job.id,
        url=job.url,
        tag=job.tag,
        message=job.message,
        result=result,
    )


async def create_output(request: CreateJobRequest, output: AyejaxOutput, db: DBSessionDependency):
    existing_output_result = await db.execute(
        select(Output).where(Output.url == str(request.url), Output.tag == request.tag)
    )
    existing_output = existing_output_result.scalar_one_or_none()

    output_id = None
    if existing_output:
        existing_output.value = output.model_dump()
        existing_output.updated_at = datetime.now(timezone.utc)
        output_id = existing_output.id
    else:
        output_id = uuid4()
        new_output = Output(
            id=output_id,
            url=str(request.url),
            tag=request.tag,
            value=output.model_dump(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(new_output)
        await db.flush()

    return output_id


async def process_job_request(job_id: UUID, request: CreateJobRequest, browser: Browser):
    """Background task to process job request"""

    s3_handler_config = S3HandlerConfig(
        boto3_session=boto3_session,
        bucket_name=settings.AWS_S3_LOG_BUCKET,
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
    )

    logger = get_logger(f"job-{job_id!s}", s3_handler_config, job_id=str(job_id))

    async with sessionmanager.session() as db:
        try:
            logger.info("Starting job analysis", url=str(request.url), tag=request.tag)

            # Use the job-aware logger for ayejax.analyze to capture ALL logs in S3
            output, metadata = await ayejax.analyze(str(request.url), request.tag, browser=browser, logger=logger)

            result = await db.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if not job:
                logger.error("Job not found in database")
                return

            job.completed_at = datetime.now(timezone.utc)
            job.analysis_metadata = metadata.model_dump() if metadata else None

            if output is not None:
                logger.info("Creating output", has_output=True)
                job.output_id = await create_output(request, output, db)
                job.status = "ready"
                job.message = "Output created successfully"
                logger.info("Job completed successfully", status="ready")
            else:
                job.status = "failed"
                job.message = "No relevant request found"
                logger.info("Job failed - no relevant request found", status="failed")

            await db.commit()

        except Exception as e:
            logger.error("bg-process", exception=e)
            result = await db.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                job.status = "failed"
                job.completed_at = datetime.now(timezone.utc)
                job.message = str(e)
                await db.commit()


def prepare_pagination_states(
    pagination_strategy: PageOnlyInfo | PageOffsetInfo | LimitOffsetInfo,
    limit: int,
    offset: int,
    initial_page_size: int,
) -> list[dict[str, str]]:
    """Prepare the API requests needed to fulfill limit/offset requirements."""
    requests = []

    if isinstance(pagination_strategy, LimitOffsetInfo):
        # For limit/offset, we need to determine how many API calls to make
        # based on the API's original limit (initial_page_size)
        api_limit = initial_page_size
        current_offset = offset
        remaining_items = limit

        while remaining_items > 0:
            # Calculate how many items to request from this API call
            items_to_request = min(remaining_items, api_limit)

            requests.append({
                pagination_strategy.limit_key: str(items_to_request),
                pagination_strategy.offset_key: str(current_offset),
            })

            current_offset += items_to_request
            remaining_items -= items_to_request

    elif isinstance(pagination_strategy, PageOnlyInfo):
        # Calculate which pages we need to fetch
        start_page = (offset // initial_page_size) + 1
        end_item = offset + limit
        end_page = ((end_item - 1) // initial_page_size) + 1

        for page in range(start_page, end_page + 1):
            requests.append({pagination_strategy.page_key: str(page)})

    elif isinstance(pagination_strategy, PageOffsetInfo):
        # Calculate which pages we need to fetch
        start_page = (offset // initial_page_size) + 1
        end_item = offset + limit
        end_page = ((end_item - 1) // initial_page_size) + 1

        for page in range(start_page, end_page + 1):
            requests.append({
                pagination_strategy.page_key: str(page),
                pagination_strategy.offset_key: str(pagination_strategy.base_offset * page),
            })

    return requests


async def make_request(output: AyejaxOutput, pagination_state: dict[str, str]) -> str:
    """Execute a single API request with the given parameters."""
    if output.request.method.lower() == "post" and isinstance(output.request.post_data, dict):
        output.request.post_data.update(pagination_state)
    else:
        output.request.queries.update(pagination_state)

    async with httpx.AsyncClient(timeout=settings.EXTERNAL_API_REQUEST_TIMEOUT) as client:
        response = await client.request(
            output.request.method,
            output.request.url,
            params=output.request.queries,
            headers=output.request.headers,
            data=output.request.post_data,
        )
        response.raise_for_status()
        return response.text


async def execute_api_request(output_id: UUID, limit: int, offset: int) -> dict[str, str]:  # noqa: C901
    async with sessionmanager.session() as db:
        result = await db.execute(select(Output).where(Output.id == output_id))
        output_record = result.scalar_one_or_none()

        if not output_record:
            raise Exception(f"Output {output_id!s} not found")

        output = AyejaxOutput.model_validate(output_record.value)

        if isinstance(output.pagination_strategy, NextCursorInfo):
            raise TypeError("Limit/offset pagination not supported for cursor-based pagination")

        try:
            if not output.pagination_strategy:
                # If no pagination strategy, just return the first call
                pagination_requests = [{}]
            else:
                # Calculate all the requests we need to make
                pagination_requests = prepare_pagination_states(
                    output.pagination_strategy, limit, offset, output.items_count_on_first_extraction
                )

            data_list = []
            successful_pagination_requests = []
            last_response = None

            # Execute all requests
            for pagination_state in pagination_requests:
                response_text = await make_request(output, pagination_state)

                # Check for duplicate responses (pagination end)
                if last_response is not None and last_response == response_text:
                    break

                successful_pagination_requests.append(pagination_state)
                last_response = response_text

                # Extract data if schema extractor is available
                if output.schema_extractor_code:
                    namespace = {}
                    exec(output.schema_extractor_code, namespace)  # noqa: S102
                    if data := namespace["extract_data"](response_text):
                        data_list.extend(data)
                    else:
                        break
                else:
                    # If no schema extractor, return raw response
                    data_list.append(response_text)

            # Apply final slicing for exact limit/offset
            if output.schema_extractor_code:
                # If we fetched multiple pages, we need to calculate the correct slice
                if len(successful_pagination_requests) > 1:
                    # Calculate the global start index within our fetched results
                    global_start = 0
                    for i, pagination_state in enumerate(successful_pagination_requests):
                        if isinstance(output.pagination_strategy, (PageOnlyInfo, PageOffsetInfo)):
                            page_num = int(pagination_state[output.pagination_strategy.page_key])
                            if page_num == ((offset // output.items_count_on_first_extraction) + 1):
                                global_start = i * output.items_count_on_first_extraction
                                break
                        elif isinstance(output.pagination_strategy, LimitOffsetInfo):
                            request_offset = int(pagination_state[output.pagination_strategy.offset_key])
                            if request_offset <= offset:
                                global_start = sum(
                                    int(req[output.pagination_strategy.limit_key])
                                    for req in successful_pagination_requests[:i]
                                )

                    start_idx = global_start + (offset % output.items_count_on_first_extraction)
                else:
                    # For structured data, we need to slice based on the original offset within our fetched data
                    start_idx = offset % output.items_count_on_first_extraction if offset else 0

                data_list = data_list[start_idx : start_idx + limit]

            output_record.usage_count += 1
            output_record.last_used_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(output_record)

            return {output_record.tag: data_list}  # noqa: TRY300
        except Exception as e:
            return {"error": f"Pagination processing failed: {e}"}
