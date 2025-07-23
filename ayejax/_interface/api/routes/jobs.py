import contextlib
import os
import tempfile
from datetime import datetime, timezone
from json import dumps as json_dumps
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
from ayejax.pagination.strategy import LimitOffsetInfo, MapCursorInfo, PageInfo, PageOffsetInfo, StringCursorInfo
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
            result = await execute_output(job.output_id, limit, offset)
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


async def make_request(output: AyejaxOutput, pagination_state: dict[str, str]) -> str:
    """Execute a single API request with the given pagination state."""
    if output.request.method.lower() == "post" and isinstance(output.request.post_data, dict):
        for key, value in pagination_state.items():
            if value is None:
                output.request.post_data.pop(key, None)
            else:
                output.request.post_data[key] = value
    else:
        for key, value in pagination_state.items():
            if value is None:
                output.request.queries.pop(key, None)
            else:
                output.request.queries[key] = value

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


async def generate_data(output: AyejaxOutput, limit: int, offset: int):  # noqa: C901
    namespace = {}
    if output.schema_extractor_code:
        exec(output.schema_extractor_code, namespace)  # noqa: S102

    last_response = None

    def extract_data(response_text: str) -> list:
        nonlocal last_response
        if last_response == response_text:
            return []

        last_response = response_text
        if "extract_data" in namespace:
            return namespace["extract_data"](response_text)
        return [response_text]

    global_position = 0
    remaining_items = limit
    initial_page_size = output.items_count_on_first_extraction

    def _slice(data: list) -> list:
        if not data:
            return []

        nonlocal global_position
        nonlocal remaining_items

        chunk_start = max(0, offset - global_position)
        chunk_end = min(len(data), chunk_start + remaining_items)

        if chunk_start < len(data):
            slice_data = data[chunk_start:chunk_end]
            if slice_data:
                remaining_items -= len(slice_data)
                global_position += len(data)
                return slice_data

        return []

    pagination_strategy = output.pagination_strategy
    if isinstance(pagination_strategy, LimitOffsetInfo):
        state = {
            pagination_strategy.limit_key: str(limit),
            pagination_strategy.offset_key: str(offset),
        }
        first_request = True

        while remaining_items > 0:
            data = extract_data(await make_request(output, state))

            # Detect API's actual limit on first request
            if first_request and len(data) < limit:
                state[pagination_strategy.limit_key] = str(len(data))
                first_request = False

            if slice_data := _slice(data):
                yield slice_data
                state[pagination_strategy.offset_key] = str(
                    int(state[pagination_strategy.offset_key]) + len(slice_data)
                )
            else:
                break

    elif isinstance(pagination_strategy, PageInfo):
        start_page = (offset // initial_page_size) + 1
        end_item = offset + limit
        end_page = ((end_item - 1) // initial_page_size) + 1

        global_position = (start_page - 1) * initial_page_size
        state, first_request = {}, True
        if pagination_strategy.limit_key:
            state[pagination_strategy.limit_key] = str(limit)

        for page in range(start_page, end_page + 1):
            state[pagination_strategy.page_key] = str(page)
            data = extract_data(await make_request(output, state))

            # Detect API's actual limit on first request
            if pagination_strategy.limit_key and first_request and len(data) < limit:
                state[pagination_strategy.limit_key] = str(len(data))
                first_request = False

            if slice_data := _slice(data):
                yield slice_data
                if remaining_items <= 0:
                    break
            else:
                break

    elif isinstance(pagination_strategy, PageOffsetInfo):
        start_page = (offset // initial_page_size) + 1
        end_item = offset + limit
        end_page = ((end_item - 1) // initial_page_size) + 1

        global_position = (start_page - 1) * initial_page_size

        for page in range(start_page, end_page + 1):
            data = extract_data(
                await make_request(
                    output,
                    {
                        pagination_strategy.page_key: str(page),
                        pagination_strategy.offset_key: str(pagination_strategy.base_offset * page),
                    },
                )
            )

            if slice_data := _slice(data):
                yield slice_data
                if remaining_items <= 0:
                    break
            else:
                break

    elif isinstance(pagination_strategy, (StringCursorInfo, MapCursorInfo)):
        state = {pagination_strategy.cursor_key: None}
        if pagination_strategy.limit_key:
            state[pagination_strategy.limit_key] = limit

        repr_fn = lambda x: json_dumps(x) if isinstance(pagination_strategy, MapCursorInfo) else x
        first_request = True

        while remaining_items > 0:
            current_response = await make_request(output, state)
            data = extract_data(current_response)

            # Detect API's actual limit on first request
            if pagination_strategy.limit_key and first_request and len(data) < limit:
                state[pagination_strategy.limit_key] = str(len(data))
                first_request = False

            if slice_data := _slice(data):
                yield slice_data
            else:
                break

            next_cursor = pagination_strategy.extract_cursor(current_response)
            if next_cursor is None or repr_fn(next_cursor) == state[pagination_strategy.cursor_key]:
                break
            state[pagination_strategy.cursor_key] = repr_fn(next_cursor)
    else:
        yield _slice(extract_data(await make_request(output, {})))


async def execute_output(output_id: UUID, limit: int, offset: int) -> dict[str, str]:
    async with sessionmanager.session() as db:
        result = await db.execute(select(Output).where(Output.id == output_id))
        output_record = result.scalar_one_or_none()

        if not output_record:
            raise Exception(f"Output {output_id!s} not found")

        output = AyejaxOutput.model_validate(output_record.value)

        data_list = []
        error_message = None
        try:
            async for data in generate_data(output, limit, offset):
                data_list.extend(data)
        except Exception as e:
            error_message = f"External API request failed: {e}"

        output_record.usage_count += 1
        output_record.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(output_record)

        result = {output_record.tag: data_list, "count": len(data_list)}
        if error_message:
            result["error"] = error_message

        return result
