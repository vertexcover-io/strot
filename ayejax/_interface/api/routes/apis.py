from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ayejax._interface.api.database import DBSessionDependency
from ayejax._interface.api.database.models.output import Output
from ayejax._interface.api.database.models.session import Session as SessionModel
from ayejax.pagination.strategy import NextCursorInfo
from ayejax.tag import TagLiteral
from ayejax.types import Output as AyejaxOutput

router = APIRouter(prefix="/v1/apis", tags=["apis"])


class SearchRequest(BaseModel):
    url: HttpUrl
    """Target URL to analyze"""
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


class CreateSessionRequest(BaseModel):
    output_id: UUID


class CreateSessionResponse(BaseModel):
    session_id: UUID
    output_id: UUID
    created_at: datetime


class SessionExecuteResponse(BaseModel):
    data: dict[str, Any]


@router.post("/search", response_model=SearchResponse)
async def search_apis(request: SearchRequest, db: DBSessionDependency):
    """Search for existing API patterns by URL and tag"""
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


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest, db: DBSessionDependency):
    """Create execution session from API pattern"""
    result = await db.execute(select(Output).where(Output.id == request.output_id))
    output = result.scalar_one_or_none()

    if not output:
        raise HTTPException(status_code=404, detail="Output not found")

    session_id = uuid4()
    session = SessionModel(id=session_id, output_id=request.output_id, request_number=0, created_at=datetime.now())

    # Initialize cursor if output has NextCursorInfo pagination
    output_data = AyejaxOutput.model_validate(output.value)
    if output_data.pagination_strategy and isinstance(output_data.pagination_strategy, NextCursorInfo):
        session.cursor = output_data.pagination_strategy.first_cursor

    db.add(session)
    await db.commit()
    await db.refresh(session)

    return CreateSessionResponse(session_id=session_id, output_id=request.output_id, created_at=session.created_at)


@router.post("/sessions/{session_id}/execute", response_model=SessionExecuteResponse)
async def execute_session(session_id: UUID, db: DBSessionDependency):
    """Execute API request through session"""
    result = await db.execute(
        select(SessionModel).options(selectinload(SessionModel.output)).where(SessionModel.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    output = AyejaxOutput.model_validate(session.output.value)

    if output.pagination_strategy:

        def update_state(entries: dict[str, Any]):
            if isinstance(output.pagination_strategy, NextCursorInfo):
                if session.cursor:
                    output.pagination_strategy.update_entries(entries, session.cursor)
            else:
                output.pagination_strategy.update_entries(entries, session.request_number)

        if output.request.method.lower() == "post" and isinstance(output.request.post_data, dict):
            update_state(output.request.post_data)
        else:
            update_state(output.request.queries)

    try:
        response = requests.request(
            output.request.method,
            output.request.url,
            params=output.request.queries,
            headers=output.request.headers,
            data=output.request.post_data,
            timeout=30,
        )
        response.raise_for_status()

        if output.pagination_strategy:
            if isinstance(output.pagination_strategy, NextCursorInfo):
                next_cursor = output.pagination_strategy.extract_cursor(response.text)
                session.cursor = next_cursor
            else:
                session.request_number += 1

        session.last_executed_at = datetime.now()

        session.output.usage_count += 1
        session.output.last_used_at = datetime.now()

        await db.commit()
        await db.refresh(session)

        return SessionExecuteResponse(data={session.output.tag: response.text})

    except Exception as e:
        return SessionExecuteResponse(data={"error": str(e)})
