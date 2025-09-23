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

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Request):
            return False

        return (
            self.method == other.method
            and self.url == other.url
            and self.type == other.type
            and self.queries == other.queries
            and self.headers == other.headers
            and self.post_data == other.post_data
        )
