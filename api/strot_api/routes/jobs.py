from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

import boto3
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from json_schema_to_pydantic import create_model
from patchright.async_api import Browser
from pydantic import BaseModel, HttpUrl
from sqlalchemy import func, select

import strot
from strot.logging import get_logger, handlers, setup_logging
from strot.schema.source import OldSource, Source
from strot.type_adapter import TypeAdapter
from strot_api.database import DBSessionDependency, sessionmanager
from strot_api.database.schema import Job, Label
from strot_api.settings import settings

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])

setup_logging()

boto3_session = boto3.Session(
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)

s3_handler_config = handlers.S3HandlerConfig(
    boto3_session=boto3_session,
    bucket_name=settings.AWS_S3_LOG_BUCKET,
    endpoint_url=settings.AWS_S3_ENDPOINT_URL,
    flush_interval=15,
)


class CreateJobRequest(BaseModel):
    url: HttpUrl
    """Target URL to analyze"""
    label: str
    """Label to use for analysis"""


class CreateJobResponse(BaseModel):
    job_id: UUID


JobStatus = Literal["pending", "ready", "failed"]


class GetJobResponse(BaseModel):
    url: str
    label: str
    job_id: UUID
    initiated_at: datetime
    status: JobStatus
    completed_at: datetime | None = None
    # if the bg process fails
    error: str | None = None
    # when job is ready
    source: Source | OldSource | None = None
    result: dict[str, Any] | None = None


class JobListItem(BaseModel):
    id: UUID
    url: str
    label_name: str
    status: JobStatus
    initiated_at: datetime
    completed_at: datetime | None = None
    usage_count: int
    last_used_at: datetime | None = None
    error: str | None = None


class JobListResponse(BaseModel):
    jobs: list[JobListItem]
    total: int
    limit: int
    offset: int
    has_next: bool


@router.post("", response_model=CreateJobResponse, status_code=202)
async def create_job(
    raw_request: Request,
    request: CreateJobRequest,
    db: DBSessionDependency,
    background_tasks: BackgroundTasks,
):
    result = await db.execute(select(Label).where(Label.name == request.label))
    label = result.scalar_one_or_none()
    if not label:
        raise HTTPException(status_code=404, detail=f"Label {request.label!r} not found")

    job_id = uuid4()

    job = Job(
        id=job_id,
        url=str(request.url),
        label_id=label.id,
        status="pending",
        initiated_at=datetime.now(UTC),
    )

    db.add(job)
    await db.commit()
    await db.refresh(label)

    background_tasks.add_task(
        process_job_request,
        job_id,
        str(request.url),
        label.requirement,
        create_model(label.output_schema),
        raw_request.app.state.browser,
    )

    return CreateJobResponse(job_id=job_id)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    db: DBSessionDependency,
    limit: int = Query(20, ge=1, le=100, description="Maximum number of jobs to return"),
    offset: int = Query(0, ge=0, description="Number of jobs to skip"),
    status: str | None = Query(None, description="Filter by job status"),
    label: str | None = Query(None, description="Filter by label name"),
    search: str | None = Query(None, description="Search by URL"),
):
    """list all jobs with pagination and optional filters."""
    from sqlalchemy.orm import selectinload

    # Build base query with proper eager loading of label relationship
    query = select(Job).options(selectinload(Job.label))

    # Apply filters
    if status:
        query = query.where(Job.status == status)

    if label:
        # Join with Label table for filtering
        query = query.join(Label).where(Label.name == label)

    if search:
        query = query.where(Job.url.ilike(f"%{search}%"))

    # Get total count
    count_query = select(func.count(Job.id))
    if status:
        count_query = count_query.where(Job.status == status)
    if label:
        count_query = count_query.join(Label).where(Label.name == label)
    if search:
        count_query = count_query.where(Job.url.ilike(f"%{search}%"))

    count_result = await db.execute(count_query)
    total = count_result.scalar()

    # Apply pagination and ordering
    paginated_query = query.order_by(Job.initiated_at.desc()).offset(offset).limit(limit)

    result = await db.execute(paginated_query)
    jobs = result.scalars().all()

    job_responses = []
    for job in jobs:
        job_responses.append(
            JobListItem(
                id=job.id,
                url=job.url,
                label_name=job.label.name,
                status=job.status,
                initiated_at=job.initiated_at,
                completed_at=job.completed_at,
                usage_count=job.usage_count or 0,
                last_used_at=job.last_used_at,
                error=job.error,
            )
        )

    has_next = offset + limit < total

    return JobListResponse(jobs=job_responses, total=total, limit=limit, offset=offset, has_next=has_next)


@router.get("/{job_id}", response_model=GetJobResponse)
async def get_job(  # noqa: C901
    raw_request: Request,
    job_id: UUID,
    db: DBSessionDependency,
    limit: int | None = Query(None, ge=1, description="Limit for data extraction (optional)"),
    offset: int | None = Query(None, ge=0, description="Offset for data extraction (optional)"),
):
    from sqlalchemy.orm import selectinload

    # Eagerly load the label relationship
    db_result = await db.execute(select(Job).options(selectinload(Job.label)).where(Job.id == job_id))
    job = db_result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if pending job has timed out (no log activity for 60 seconds)
    if job.status == "pending":
        current_time = datetime.now(UTC)
        time_since_initiation = (current_time - job.initiated_at).total_seconds()

        # Only check for timeout after job has been running for at least 60 seconds
        if time_since_initiation > 60:
            try:
                # Check if logs exist in S3 and get last modified time
                s3_client = boto3_session.client("s3", endpoint_url=settings.AWS_S3_ENDPOINT_URL)

                response = s3_client.head_object(Bucket=settings.AWS_S3_LOG_BUCKET, Key=f"job-{job_id!s}.log")

                last_modified = response["LastModified"].replace(tzinfo=UTC)
                time_since_last_log = (current_time - last_modified).total_seconds()

                # If no log activity for 60 seconds, mark as failed
                if time_since_last_log > 60:
                    job.status = "failed"
                    job.error = "Job timed out - no log activity detected for over 60 seconds"
                    job.completed_at = current_time
                    await db.commit()
                    await db.refresh(job)

            except Exception:  # noqa: S110
                # If S3 check fails, silently continue (don't fail the request)
                pass

    result = None
    label_name = job.label.name

    dynamic_parameters = {}
    if raw_request.query_params:
        for k, v in raw_request.query_params.items():
            if k in ["limit", "offset"]:
                continue
            dynamic_parameters[k] = v

    # Only extract data if limit/offset are explicitly provided
    if job.status == "ready" and job.source and limit is not None:
        source = TypeAdapter(OldSource | Source).validate_python(job.source)
        result = {label_name: []}
        try:
            async for data in source.generate_data(limit=limit, offset=offset or 0, **dynamic_parameters):
                result[label_name].extend(data)

            result["count"] = len(result[label_name])
        except Exception as e:
            result["error"] = f"Source request failed: {e}"

        job.usage_count += 1
        job.last_used_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(job)

    return GetJobResponse(
        url=job.url,
        label=label_name,
        job_id=job.id,
        initiated_at=job.initiated_at,
        status=job.status,
        completed_at=job.completed_at,
        error=job.error,
        source=job.source,
        result=result,
    )


@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: UUID, db: DBSessionDependency):
    """Delete a job. Cannot delete jobs in pending state."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == "pending":
        raise HTTPException(
            status_code=400, detail="Cannot delete job in pending state. Wait for it to complete or fail."
        )

    await db.delete(job)
    await db.commit()


async def process_job_request(
    job_id: UUID, url: str, requirement: str, output_schema: type[BaseModel], browser: Browser
):
    """Background task to process job request"""

    async with sessionmanager.session() as db:
        error, source = None, None
        try:
            source = await strot.analyze(
                url=url,
                query=requirement,
                output_schema=output_schema,
                browser=browser,
                logger=get_logger(f"job-{job_id!s}", s3_handler_config, job_id=str(job_id)),
            )
            if source is None:
                error = "No relevant source found"
        except Exception as e:
            error = str(e)

        result = await db.execute(select(Job).where(Job.id == job_id))
        if not (job := result.scalar_one_or_none()):
            return

        job.completed_at = datetime.now(UTC)

        if source is not None:
            job.source = source.model_dump()
            job.status = "ready"
        elif error is not None:
            job.status = "failed"
            job.error = error

        await db.commit()
