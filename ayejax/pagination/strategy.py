import re

from pydantic import BaseModel

from ayejax.pagination.pattern_builder import Pattern


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

    def extract_cursor(self, response_text: str) -> str | None:
        for pattern in self.patterns:
            match = re.search(re.escape(pattern.before) + r"(.*?)" + re.escape(pattern.after), response_text)
            if match:
                return match.group(1)
        return None


StrategyInfo = PageOnlyInfo | PageOffsetInfo | LimitOffsetInfo | NextCursorInfo
