"""
Job routes for creating new API patterns
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from playwright.async_api import Browser
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select

import ayejax
from ayejax._interface.api.database import DBSessionDependency
from ayejax._interface.api.database.models.job import Job
from ayejax._interface.api.database.models.output import Output
from ayejax.logging import FileHandlerConfig, get_logger
from ayejax.tag import TagLiteral

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])

LOG_DIR = Path.home() / ".ayejax" / "logs" / "api"


class CreateJobRequest(BaseModel):
    url: HttpUrl
    """Target URL to analyze"""
    tag: TagLiteral
    """Kind of information to look for (e.g. reviews)"""


class CreateJobResponse(BaseModel):
    job_id: UUID


JobStatus = Literal["pending", "ready", "failed"]


class JobStatusResponse(BaseModel):
    status: JobStatus
    job_id: UUID
    url: str
    tag: TagLiteral
    output_id: UUID | None
    message: str | None


async def process_job_request(job_id: UUID, request: CreateJobRequest, db: DBSessionDependency, browser: Browser):
    """Background task to process job request"""
    try:
        logger = get_logger(f"job-{job_id!s}", file_handler_config=FileHandlerConfig(directory=LOG_DIR / "jobs"))

        output, metadata = await ayejax.analyze(str(request.url), request.tag, browser=browser, logger=logger)

        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if not job:
            return

        job.completed_at = datetime.now(timezone.utc)
        job.analysis_metadata = metadata.model_dump() if metadata else None

        if output is not None:
            # Check if output already exists
            existing_output_result = await db.execute(
                select(Output).where(Output.url == str(request.url), Output.tag == request.tag)
            )
            existing_output = existing_output_result.scalar_one_or_none()

            if existing_output:
                # Update existing output with new analysis
                existing_output.value = output.model_dump()
                existing_output.updated_at = datetime.now(timezone.utc)
            else:
                db.add(
                    Output(
                        id=uuid4(),
                        url=str(request.url),
                        tag=request.tag,
                        value=output.model_dump(),
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
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


@router.post("/", response_model=CreateJobResponse)
async def create_job(
    raw_request: Request, request: CreateJobRequest, db: DBSessionDependency, background_tasks: BackgroundTasks
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

    background_tasks.add_task(process_job_request, job_id, request, db, raw_request.app.state.browser)

    return CreateJobResponse(job_id=job_id)


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: UUID, db: DBSessionDependency):
    """Get job status and details"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    output_id = None
    if job.status == "ready":
        output_result = await db.execute(select(Output).where(Output.url == job.url, Output.tag == job.tag))
        output = output_result.scalar_one_or_none()
        if output:
            output_id = output.id

    return JobStatusResponse(
        status=job.status, job_id=job.id, url=job.url, tag=job.tag, output_id=output_id, message=job.message
    )
