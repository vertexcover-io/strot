"""
Job routes for creating new API patterns
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

import requests
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from playwright.async_api import Browser
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import selectinload

import ayejax
from ayejax._interface.api.auth import AuthDependency
from ayejax._interface.api.database import DBSessionDependency, sessionmanager
from ayejax._interface.api.database.models.execution_state import ExecutionState
from ayejax._interface.api.database.models.job import Job
from ayejax._interface.api.database.models.output import Output
from ayejax._interface.api.settings import settings
from ayejax.logging import FileHandlerConfig, get_logger
from ayejax.pagination.strategy import NextCursorInfo
from ayejax.tag import TagLiteral
from ayejax.types import Output as AyejaxOutput

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


class GetJobResponse(BaseModel):
    status: JobStatus
    job_id: UUID
    url: str
    tag: TagLiteral
    message: str
    execution_result: dict[str, Any] | None


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
async def get_job(job_id: UUID, db: DBSessionDependency, _: AuthDependency):
    """Get job details"""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    execution_result = None
    if job.status == "ready" and job.execution_state_id:
        try:
            execution_result = await execute_api_request(job.execution_state_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to execute API request: {e}") from e

    return GetJobResponse(
        status=job.status,
        job_id=job.id,
        url=job.url,
        tag=job.tag,
        message=job.message,
        execution_result=execution_result,
    )


async def create_execution_state(request: CreateJobRequest, output: AyejaxOutput, db: DBSessionDependency):
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

    execution_state_id = uuid4()
    execution_state = ExecutionState(id=execution_state_id, output_id=output_id, created_at=datetime.now(timezone.utc))
    db.add(execution_state)
    await db.flush()
    return execution_state_id


async def process_job_request(job_id: UUID, request: CreateJobRequest, browser: Browser):
    """Background task to process job request"""
    logger = get_logger(f"job-{job_id!s}", file_handler_config=FileHandlerConfig(directory=LOG_DIR / "jobs"))
    async with sessionmanager.session() as db:
        try:
            output, metadata = await ayejax.analyze(str(request.url), request.tag, browser=browser, logger=logger)

            result = await db.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if not job:
                return

            job.completed_at = datetime.now(timezone.utc)
            job.analysis_metadata = metadata.model_dump() if metadata else None

            if output is not None:
                job.execution_state_id = await create_execution_state(request, output, db)
                job.status = "ready"
                job.message = "Output created successfully"
            else:
                job.status = "failed"
                job.message = "No relevant request found"

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


async def execute_api_request(execution_state_id: UUID) -> dict[str, str]:  # noqa: C901
    async with sessionmanager.session() as db:
        result = await db.execute(
            select(ExecutionState)
            .options(selectinload(ExecutionState.output))
            .where(ExecutionState.id == execution_state_id)
        )
        execution_state = result.scalar_one_or_none()

        if not execution_state:
            raise Exception("Execution state not found")

        output = AyejaxOutput.model_validate(execution_state.output.value)

        if output.pagination_strategy:

            def update_state(entries: dict[str, Any]):
                if isinstance(output.pagination_strategy, NextCursorInfo):
                    if execution_state.last_response and (
                        cursor := output.pagination_strategy.extract_cursor(execution_state.last_response)
                    ):
                        output.pagination_strategy.update_entries(entries, cursor)
                    else:
                        return False
                else:
                    output.pagination_strategy.update_entries(entries, execution_state.request_number)

                return True

            if output.request.method.lower() == "post" and isinstance(output.request.post_data, dict):
                state_updated = update_state(output.request.post_data)
            else:
                state_updated = update_state(output.request.queries)

            if not state_updated:
                return {"error": "No more pagination"}

        try:
            response = requests.request(
                output.request.method,
                output.request.url,
                params=output.request.queries,
                headers=output.request.headers,
                data=output.request.post_data,
                timeout=settings.EXTERNAL_API_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            response_text = response.text

            if execution_state.last_response and (execution_state.last_response == response_text):
                return {"error": "No more pagination"}

            if output.pagination_strategy:
                execution_state.request_number += 1
                execution_state.last_response = response_text

            execution_state.last_executed_at = datetime.now(timezone.utc)
            execution_state.output.usage_count += 1
            execution_state.output.last_used_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(execution_state)

        except requests.RequestException as e:
            return {"error": f"External API request failed: {e!s}"}

        else:
            if output.schema_extractor_code:
                namespace = {}
                exec(output.schema_extractor_code, namespace)  # noqa: S102
                if data := namespace["extract_data"](response_text):
                    return {execution_state.output.tag: data}

            return {execution_state.output.tag: response_text}
