from pydantic import BaseModel

from .pattern_builder import Pattern


class PageOnlyInfo(BaseModel):
    page_key: str


class PageOffsetInfo(BaseModel):
    page_key: str
    offset_key: str
    base_offset: int


class LimitOffsetInfo(BaseModel):
    limit_key: str
    offset_key: str


class NextCursorInfo(BaseModel):
    cursor_key: str
    first_cursor: str | None
    patterns: list[Pattern]


StrategyInfo = PageOnlyInfo | PageOffsetInfo | LimitOffsetInfo | NextCursorInfo
