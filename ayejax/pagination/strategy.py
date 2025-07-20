from typing import Any

from pydantic import BaseModel

from ayejax.pagination.pattern import Pattern


class PageInfo(BaseModel):
    page_key: str

    @property
    def name(self) -> str:
        return "page-based"


class PageOffsetInfo(BaseModel):
    page_key: str
    offset_key: str
    base_offset: int

    @property
    def name(self) -> str:
        return "page-offset"


class LimitOffsetInfo(BaseModel):
    limit_key: str
    offset_key: str

    @property
    def name(self) -> str:
        return "limit-offset"


class StringCursorInfo(BaseModel):
    cursor_key: str
    start_cursor: str | None
    patterns: list[Pattern]

    @property
    def name(self) -> str:
        return "cursor-based"

    @classmethod
    def generate_patterns(cls, response_text: str, cursor: str) -> list[Pattern]:
        return Pattern.generate_list(response_text, cursor)

    def extract_cursor(self, response_text: str) -> str | None:
        for pattern in self.patterns:
            if output := pattern.test(response_text):
                return output
        return None


class DictCursorInfo(BaseModel):
    cursor_key: str
    start_cursor: dict[str, Any] | None
    pattern_map: dict[str, list[Pattern]]

    @property
    def name(self) -> str:
        return "cursor-based"

    @classmethod
    def generate_pattern_map(cls, response_text: str, cursor: dict[str, Any]) -> dict[str, list[Pattern]]:
        pattern_map: dict[str, list[Pattern]] = {}
        for key, value in cursor.items():
            pattern_map[key] = Pattern.generate_list(response_text, str(value))
        return pattern_map

    def extract_cursor(self, response_text: str) -> dict[str, Any] | None:
        cursor = {}
        for key, patterns in self.pattern_map.items():
            for pattern in patterns:
                if output := pattern.test(response_text):
                    cursor[key] = output
                    break
        return cursor or None


StrategyInfo = PageInfo | PageOffsetInfo | LimitOffsetInfo | StringCursorInfo | DictCursorInfo
