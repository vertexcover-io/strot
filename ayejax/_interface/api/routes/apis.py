from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select

from ayejax._interface.api.auth import AuthDependency
from ayejax._interface.api.database import DBSessionDependency
from ayejax._interface.api.database.models.output import Output
from ayejax.tag import TagLiteral
from ayejax.types import Output as AyejaxOutput

router = APIRouter(prefix="/v1/apis", tags=["apis"])


class SearchRequest(BaseModel):
    url: HttpUrl
    """Target URL to search"""
    tag: TagLiteral
    """Kind of information to look for (e.g. reviews)"""


class SearchResponse(BaseModel):
    id: UUID
    url: str
    tag: TagLiteral
    output: AyejaxOutput
    usage_count: int
    last_used_at: datetime | None
    created_at: datetime


@router.post("/search", response_model=SearchResponse)
async def search_apis(request: SearchRequest, db: DBSessionDependency, _: AuthDependency):
    """Search for existing API outputs by URL and tag"""
    result = await db.execute(
        select(Output)
        .where(Output.tag == request.tag, Output.url == str(request.url))
        .order_by(Output.usage_count.desc(), Output.last_used_at.desc())
    )
    output = result.scalar_one_or_none()

    if not output:
        raise HTTPException(status_code=404, detail="No output found")

    return SearchResponse(
        id=output.id,
        url=output.url,
        tag=output.tag,
        output=AyejaxOutput.model_validate(output.value),
        usage_count=output.usage_count,
        last_used_at=output.last_used_at,
        created_at=output.created_at,
    )
