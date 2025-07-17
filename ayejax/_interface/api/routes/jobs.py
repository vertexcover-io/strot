"""
Job routes for creating new API patterns
"""

import contextlib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

import boto3
import botocore.exceptions
import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from playwright.async_api import Browser
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from starlette.responses import HTMLResponse

import ayejax
from ayejax._interface.api.auth import AuthDependency
from ayejax._interface.api.database import DBSessionDependency, sessionmanager
from ayejax._interface.api.database.models.job import Job
from ayejax._interface.api.database.models.output import Output
from ayejax._interface.api.settings import settings
from ayejax.logging import get_logger
from ayejax.logging.handlers import S3HandlerConfig
from ayejax.pagination.strategy import LimitOffsetInfo, NextCursorInfo, PageOffsetInfo, PageOnlyInfo
from ayejax.report_generation import generate_report
from ayejax.tag import TagLiteral
from ayejax.types import Output as AyejaxOutput

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


boto3_session = boto3.Session(
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)

s3_handler_config = S3HandlerConfig(
    boto3_session=boto3_session,
    bucket_name=settings.AWS_S3_LOG_BUCKET,
    endpoint_url=settings.AWS_S3_ENDPOINT_URL,
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
    created_at: datetime
    completed_at: datetime | None
    url: str
    tag: TagLiteral
    message: str
    result: dict[str, Any] | None


@router.post("/", response_model=CreateJobResponse, status_code=202)
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
        created_at=job.created_at,
        completed_at=job.completed_at,
        url=job.url,
        tag=job.tag,
        message=job.message,
        result=result,
    )


@router.get("/{job_id}/report", response_class=HTMLResponse)
async def generate_job_report(
    job_id: UUID,
    db: DBSessionDependency,
    _: AuthDependency,
):
    """Generate job report"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        return HTMLResponse(content=f"<h1>Job {job_id!s} not found</h1>", status_code=404)

    s3_client = boto3_session.client(
        "s3",
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
    )
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        local_path = tmp.name

    try:
        s3_client.download_file(settings.AWS_S3_LOG_BUCKET, f"job-{job_id!s}.log", local_path)
        content = generate_report(Path(local_path).read_text())
    except botocore.exceptions.BotoCoreError as e:
        return HTMLResponse(content=f"<h1>Log download error: {e!s}</h1>", status_code=500)
    except Exception as e:
        return HTMLResponse(content=f"<h1>Report generation failed: {e!s}</h1>", status_code=500)
    finally:
        with contextlib.suppress(OSError):
            os.remove(local_path)

    return HTMLResponse(content=content, status_code=200)


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

    async with sessionmanager.session() as db:
        try:
            output = await ayejax.analyze(
                str(request.url),
                request.tag,
                browser=browser,
                logger=get_logger(f"job-{job_id!s}", s3_handler_config, job_id=str(job_id)),
            )

            result = await db.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if not job:
                return

            job.completed_at = datetime.now(timezone.utc)

            if output is not None:
                job.output_id = await create_output(request, output, db)
                job.status = "ready"
                job.message = "Output created successfully"
            else:
                job.status = "failed"
                job.message = "No relevant request found"

            await db.commit()

        except Exception as e:
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

        strategy = output.pagination_strategy
        try:
            if not strategy or isinstance(strategy, NextCursorInfo):
                # If pagination strategy is not available or is cursor-based, just return the first call
                pagination_requests = [{}]
            else:
                # Calculate all the requests we need to make
                pagination_requests = prepare_pagination_states(
                    strategy, limit, offset, output.items_count_on_first_extraction
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
                        if isinstance(strategy, (PageOnlyInfo, PageOffsetInfo)):
                            page_num = int(pagination_state[strategy.page_key])
                            if page_num == ((offset // output.items_count_on_first_extraction) + 1):
                                global_start = i * output.items_count_on_first_extraction
                                break
                        elif isinstance(strategy, LimitOffsetInfo):
                            request_offset = int(pagination_state[strategy.offset_key])
                            if request_offset <= offset:
                                global_start = sum(
                                    int(req[strategy.limit_key]) for req in successful_pagination_requests[:i]
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

            result = {output_record.tag: data_list}
            if strategy and isinstance(strategy, NextCursorInfo):
                result["error"] = (
                    "Limit/offset pagination not supported for cursor-based pagination. Returning data from first page."
                )
        except Exception as e:
            return {"error": f"Pagination processing failed: {e}"}

        return result
