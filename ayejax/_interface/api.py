from contextlib import asynccontextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

import requests
from fastapi import BackgroundTasks, FastAPI, HTTPException
from pydantic import BaseModel, HttpUrl

from ayejax import Tag, create_browser, find
from ayejax.logging import FileHandlerConfig, get_logger, setup_logging
from ayejax.pagination.strategy import NextCursorInfo
from ayejax.types import Metadata, Output

LOG_DIR = Path.home() / ".ayejax" / "logs" / "api"

setup_logging()

service_logger = get_logger(
    f"service-{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}",
    file_handler_config=FileHandlerConfig(directory=LOG_DIR / "service"),
)


class JobStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class CreateJobRequest(BaseModel):
    url: HttpUrl
    tag: Literal["reviews"]


class CreateJobResponse(BaseModel):
    job_id: UUID


class GetJobResponse(BaseModel):
    status: JobStatus
    data: dict[str, Any] | None = None


class PaginationState(BaseModel):
    request_number: int = 0
    cursor: str | None = None


class JobEntry(BaseModel):
    request: CreateJobRequest
    status: JobStatus
    created_at: datetime

    completed_at: datetime | None = None
    output: Output | None = None
    metadata: Metadata | None = None
    error: str | None = None

    pagination_state: PaginationState | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with create_browser("headed") as browser:  # TODO: change to headless
        app.state.browser = browser
        yield


app = FastAPI(title="Ayejax API", lifespan=lifespan)
jobs: dict[UUID, JobEntry] = {}


async def process_job_request(job_id: UUID, request: CreateJobRequest):
    try:
        logger = get_logger(f"job-{job_id!s}", file_handler_config=FileHandlerConfig(directory=LOG_DIR / "jobs"))

        output, metadata = await find(
            str(request.url), Tag._member_map_[request.tag], browser=app.state.browser, logger=logger
        )

        jobs[job_id].completed_at = datetime.now()
        jobs[job_id].metadata = metadata

        if output is not None:
            jobs[job_id].output = output
            if output.pagination_strategy is not None:
                if isinstance(output.pagination_strategy, NextCursorInfo):
                    pagination_state = PaginationState(cursor=output.pagination_strategy.first_cursor)
                else:
                    pagination_state = PaginationState(request_number=1)
                jobs[job_id].pagination_state = pagination_state
            jobs[job_id].status = JobStatus.SUCCESS
        else:
            jobs[job_id].status = JobStatus.FAILED
            jobs[job_id].error = "No relevant request found"

    except Exception as e:
        jobs[job_id].status = JobStatus.FAILED
        jobs[job_id].completed_at = datetime.now()
        jobs[job_id].error = str(e)


@app.post("/v1/jobs", response_model=CreateJobResponse)
async def create_job(request: CreateJobRequest, background_tasks: BackgroundTasks):
    """Create a new job and start processing in background"""
    job_id = uuid4()

    jobs[job_id] = JobEntry(request=request, status=JobStatus.PENDING, created_at=datetime.now())

    background_tasks.add_task(process_job_request, job_id, request)
    service_logger.info(
        "create-job", job_id=job_id, url=str(request.url), tag=request.tag, created_at=jobs[job_id].created_at
    )
    return CreateJobResponse(job_id=job_id)


@app.get("/v1/jobs/{job_id}", response_model=GetJobResponse)
async def get_job(job_id: UUID):  # noqa: C901
    """Get the job response"""

    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job_entry = jobs[job_id]
    service_logger.info(
        "get-job",
        job_id=job_id,
        url=str(job_entry.request.url),
        tag=job_entry.request.tag,
    )

    data = {}
    if job_entry.status == JobStatus.SUCCESS:
        if job_entry.pagination_state is not None:

            def update_entries(entries: dict[str, Any]):
                if isinstance(job_entry.output.pagination_strategy, NextCursorInfo):
                    if job_entry.pagination_state.cursor:
                        job_entry.output.pagination_strategy.update_entries(entries, job_entry.pagination_state.cursor)
                else:
                    job_entry.output.pagination_strategy.update_entries(
                        entries, job_entry.pagination_state.request_number
                    )

            if job_entry.output.request.method.lower() == "post" and (
                isinstance(job_entry.output.request.post_data, dict)
            ):
                update_entries(job_entry.output.request.post_data)
            else:
                update_entries(job_entry.output.request.queries)

        try:
            response = requests.request(  # noqa: S113
                job_entry.output.request.method,
                job_entry.output.request.url,
                params=job_entry.output.request.queries,
                headers=job_entry.output.request.headers,
                data=job_entry.output.request.post_data,
            )
            response.raise_for_status()
            if job_entry.pagination_state is not None:
                if isinstance(job_entry.output.pagination_strategy, NextCursorInfo):
                    next_cursor = job_entry.output.pagination_strategy.extract_cursor(response.text)
                    job_entry.pagination_state.cursor = next_cursor
                    if next_cursor is None:
                        data["error"] = "No more data available"
                else:
                    job_entry.pagination_state.request_number += 1

            data[job_entry.request.tag] = response.text
        except Exception as e:
            data["error"] = str(e)
            job_entry.status = JobStatus.FAILED

    elif job_entry.status == JobStatus.FAILED:
        data["error"] = job_entry.error

    return GetJobResponse(status=job_entry.status, data=data)
