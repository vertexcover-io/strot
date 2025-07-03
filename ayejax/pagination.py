from typing import Any

from pydantic import BaseModel

PAGE_KEY_CANDIDATES = {
    "page",
    "pageno",
    "page_no",
    "page_number",
    "pagenum",
    "pagenumber",
    "pageindex",
    "page_index",
    "data_page",
}

LIMIT_KEY_CANDIDATES = {"limit", "take", "page_size", "per_page"}

OFFSET_KEY_CANDIDATES = {"offset"}


class PageOnlyStrategy(BaseModel):
    page_key: str


class PageOffsetStrategy(BaseModel):
    page_key: str
    offset_key: str
    base_offset: int


class LimitOffsetStrategy(BaseModel):
    limit_key: str
    offset_key: str


Strategy = PageOnlyStrategy | PageOffsetStrategy | LimitOffsetStrategy


def determine_strategy(entries: dict[str, Any]) -> Strategy | None:
    def get_key(candidates: set[str]) -> str | None:
        return next((k for k in candidates if k in entries), None)

    page_key = get_key(PAGE_KEY_CANDIDATES)
    offset_key = get_key(OFFSET_KEY_CANDIDATES)
    limit_key = get_key(LIMIT_KEY_CANDIDATES)

    if page_key and offset_key:
        return PageOffsetStrategy(
            page_key=page_key, offset_key=offset_key, base_offset=int(entries[offset_key]) // int(entries[page_key])
        )
    elif limit_key and offset_key:
        return LimitOffsetStrategy(
            limit_key=limit_key,
            offset_key=offset_key,
        )
    elif page_key:
        return PageOnlyStrategy(page_key=page_key)

    return None
