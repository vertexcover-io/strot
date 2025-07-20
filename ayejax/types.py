import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ayejax.pagination.strategy import StrategyInfo

__all__ = ("AnalysisResult", "Request", "Response", "Output")


class PydanticModel(BaseModel):
    @classmethod
    def load_from_file(cls, path: str | Path):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path!r}")

        return cls.model_validate_json(path.read_bytes())

    def save_to_file(self, path: str | Path) -> None:
        path = Path(path)
        path.write_text(self.model_dump_json(indent=3, exclude_none=True))


class Point(BaseModel):
    x: float
    y: float


class AnalysisResult(PydanticModel):
    close_overlay_popup_coords: Point | None = Field(
        None,
        description="Coordinates of dismiss button for overlay popups (cookie banners, modals, ads) that block content. Only set if popup is NOT related to user requirements.",
    )
    skip_to_content_coords: Point | None = Field(
        None, description="Coordinates of element or button which might lead to the required content."
    )
    load_more_content_coords: Point | None = Field(
        None,
        description="Coordinates of pagination controls (Next, More, page numbers, arrows) that load additional relevant content.",
    )
    text_sections: list[str] | None = Field(
        None,
        description="List of exact text strings visible in screenshot that match user requirements (product names, prices, descriptions, etc.).",
    )


class PaginationKeys(PydanticModel):
    """
    Pagination keys identified from API request entries.
    """

    page_number_key: str | None = Field(
        None,
        description="The key used to specify the page number for page-based pagination (e.g., 'page', 'page_no', 'page_number')",
    )
    limit_key: str | None = Field(
        None,
        description="The key used to specify the maximum number of items to return per page (e.g., 'limit', 'take', 'page_size', 'per_page')",
    )
    offset_key: str | None = Field(
        None, description="The key used to specify the starting position or number of items to skip (e.g., 'offset')"
    )
    cursor_key: str | None = Field(
        None,
        description="The key used for cursor-based pagination to continue from a specific point (e.g., 'cursor', 'next_cursor', 'page_after')",
    )

    def strategy_available(self) -> bool:
        if self.page_number_key and self.offset_key:
            return True

        if self.limit_key and self.offset_key:
            return True

        if self.page_number_key:
            return True

        return bool(self.cursor_key)


class Request(PydanticModel):
    method: str
    url: str
    queries: dict[str, str]
    headers: dict[str, str]
    post_data: dict[str, Any] | str | None = None

    @property
    def parameters(self) -> dict[str, Any]:
        def _load_value(value: Any) -> Any:
            if isinstance(value, str):
                try:
                    return _load_value(json.loads(value))
                except (json.JSONDecodeError, ValueError):
                    return value
            elif isinstance(value, dict):
                return {k: _load_value(v) for k, v in value.items()}
            else:
                return value

        if self.method.lower() == "post" and isinstance(self.post_data, dict):
            return _load_value(self.post_data)

        return _load_value(self.queries)


class Response(PydanticModel):
    value: str
    request: Request


class Output(PydanticModel):
    request: Request
    pagination_strategy: StrategyInfo | None = None
    schema_extractor_code: str | None = None
    items_count_on_first_extraction: int
