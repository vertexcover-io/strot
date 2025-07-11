from typing import Any

from pydantic import BaseModel


class ReviewSchema(BaseModel):
    title: str | None = None
    username: str | None = None
    rating: float | None = None
    comment: str | None = None
    location: str | None = None
    date: str | None = None
    extra: dict[str, Any] | None = None
