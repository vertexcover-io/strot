import re
from typing import Any

from pydantic import BaseModel

from ayejax.pagination.pattern_builder import Pattern


class PageOnlyInfo(BaseModel):
    page_key: str

    def update_entries(self, entries: dict[str, Any], request_number: int):
        entries[self.page_key] = request_number


class PageOffsetInfo(BaseModel):
    page_key: str
    offset_key: str
    base_offset: int

    def update_entries(self, entries: dict[str, Any], request_number: int):
        entries[self.page_key] = request_number
        entries[self.offset_key] = self.base_offset * request_number


class LimitOffsetInfo(BaseModel):
    limit_key: str
    offset_key: str

    def update_entries(self, entries: dict[str, Any], request_number: int):
        entries[self.offset_key] = int(entries[self.limit_key]) * (request_number - 1)


class NextCursorInfo(BaseModel):
    cursor_key: str
    first_cursor: str | None
    patterns: list[Pattern]

    def update_entries(self, entries: dict[str, Any], cursor: str):
        entries[self.cursor_key] = cursor

    def extract_cursor(self, response_text: str) -> str | None:
        for pattern in self.patterns:
            match = re.search(re.escape(pattern.before) + r"(.*?)" + re.escape(pattern.after), response_text)
            if match:
                return match.group(1)
        return None


StrategyInfo = PageOnlyInfo | PageOffsetInfo | LimitOffsetInfo | NextCursorInfo
