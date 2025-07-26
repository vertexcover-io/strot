from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select

from strot_api.database import DBSessionDependency
from strot_api.database.schema.job import Job
from strot_api.database.schema.label import Label

router = APIRouter(prefix="/labels", tags=["labels"])


class LabelCreate(BaseModel):
    name: str
    requirement: str
    output_schema: dict


class LabelUpdate(BaseModel):
    requirement: str | None = None
    output_schema: dict | None = None


class LabelResponse(BaseModel):
    id: UUID
    name: str
    requirement: str
    output_schema: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LabelListResponse(BaseModel):
    labels: list[LabelResponse]
    total: int
    limit: int
    offset: int
    has_next: bool


@router.post("", response_model=LabelResponse, status_code=201)
async def create_label(label: LabelCreate, db: DBSessionDependency):
    """Create a new label (query + output schema combination)."""

    result = await db.execute(select(Label).where(Label.name == label.name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Label name already exists")

    new_label = Label(name=label.name, requirement=label.requirement, output_schema=label.output_schema)

    db.add(new_label)
    await db.commit()
    await db.refresh(new_label)

    return new_label


@router.get("", response_model=LabelListResponse)
async def list_labels(
    db: DBSessionDependency,
    limit: int = Query(20, ge=1, le=100, description="Maximum number of labels to return"),
    offset: int = Query(0, ge=0, description="Number of labels to skip"),
    search: str | None = Query(None, description="Search by name or requirement"),
):
    """list all labels with pagination and optional search."""
    query = select(Label)

    # Apply search filter
    if search:
        query = query.where(or_(Label.name.ilike(f"%{search}%"), Label.requirement.ilike(f"%{search}%")))

    # Get total count for pagination
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar()

    # Apply pagination
    paginated_query = query.offset(offset).limit(limit)

    result = await db.execute(paginated_query)
    labels = result.scalars().all()

    # Add job count for each label
    label_responses = []
    for label in labels:
        label_responses.append(
            LabelResponse(
                id=label.id,
                name=label.name,
                requirement=label.requirement,
                output_schema=label.output_schema,
                created_at=label.created_at,
                updated_at=label.updated_at,
            )
        )

    has_next = offset + limit < total

    return LabelListResponse(labels=label_responses, total=total, limit=limit, offset=offset, has_next=has_next)


@router.get("/{label_id}", response_model=LabelResponse)
async def get_label(label_id: UUID, db: DBSessionDependency):
    """Get a specific label by ID."""
    result = await db.execute(select(Label).where(Label.id == label_id))
    label = result.scalar_one_or_none()

    if not label:
        raise HTTPException(status_code=404, detail="Label not found")

    return LabelResponse(
        id=label.id,
        name=label.name,
        requirement=label.requirement,
        output_schema=label.output_schema,
        created_at=label.created_at,
        updated_at=label.updated_at,
    )


@router.put("/{label_id}", response_model=LabelResponse)
async def update_label(label_id: UUID, label_update: LabelUpdate, db: DBSessionDependency):
    """Update a label. Only provided fields will be updated."""
    result = await db.execute(select(Label).where(Label.id == label_id))
    label = result.scalar_one_or_none()
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")

    update_data = label_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(label, field, value)

    await db.commit()
    await db.refresh(label)

    return LabelResponse(
        id=label.id,
        name=label.name,
        requirement=label.requirement,
        output_schema=label.output_schema,
        created_at=label.created_at,
        updated_at=label.updated_at,
    )


@router.delete("/{label_id}", status_code=204)
async def delete_label(
    db: DBSessionDependency,
    label_id: UUID,
    force: bool = Query(False, description="Force delete even if label has associated jobs"),
):
    """Delete a label. Fails if label has associated jobs unless force=true."""
    result = await db.execute(select(Label).where(Label.id == label_id))
    label = result.scalar_one_or_none()

    if not label:
        raise HTTPException(status_code=404, detail="Label not found")

    job_count_result = await db.execute(select(func.count()).select_from(Job).where(Job.label_id == label.id))
    job_count = job_count_result.scalar()

    if job_count > 0 and not force:
        raise HTTPException(
            status_code=400, detail=f"Label has {job_count} associated jobs. Use force=true to delete anyway."
        )

    await db.delete(label)
    await db.commit()

    return None
