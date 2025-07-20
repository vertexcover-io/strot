from .strategy import StrategyInfo

__all__ = ("StrategyInfo",)

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

NEXT_CURSOR_KEY_CANDIDATES = {"page_after", "cursor", "next_cursor", "nextcursor", "next", "after", "pageafter"}
