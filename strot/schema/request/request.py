from typing import Any, Literal

from strot.schema.base import BaseSchema

__all__ = ("Request",)

RequestType = Literal["ajax", "ssr"]


class Request(BaseSchema):
    method: str
    url: str
    type: RequestType = "ajax"
    queries: dict[str, str]
    headers: dict[str, str]
    post_data: dict[str, Any] | str | None = None
