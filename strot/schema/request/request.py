from typing import Any, Literal

from pydantic import Field

from strot.schema.base import BaseSchema

__all__ = ("Request",)

RequestType = Literal["ajax", "ssr"]


class Request(BaseSchema):
    method: str
    url: str
    type: RequestType = "ajax"
    queries: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    post_data: dict[str, Any] | str | None = None
