from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from ayejax.pagination.pattern import Pattern

CursorT = TypeVar("CursorT")


class PageInfo(BaseModel):
    page_key: str
    limit_key: str | None = None

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


class BaseCursorInfo(BaseModel, Generic[CursorT]):
    cursor_key: str
    limit_key: str | None = None
    default_cursor: CursorT

    @property
    def name(self) -> str:
        return "cursor-based"

    def extract_cursor(self, response_text: str) -> CursorT | None:
        raise NotImplementedError


class StringCursorInfo(BaseCursorInfo[str]):
    patterns: list[Pattern]

    @classmethod
    def generate_patterns(cls, response_text: str, cursor: str) -> list[Pattern]:
        return Pattern.generate_list(response_text, cursor)

    def extract_cursor(self, response_text: str) -> str | None:
        for pattern in self.patterns:
            if output := pattern.test(response_text):
                return output
        return None


class MapCursorInfo(BaseCursorInfo[dict[str, Any]]):
    patterns_map: dict[str, list[Pattern]]

    @classmethod
    def generate_patterns_map(cls, response_text: str, cursor: dict[str, Any]) -> dict[str, list[Pattern]]:
        patterns_map: dict[str, list[Pattern]] = {}
        for key, value in cursor.items():
            patterns_map[key] = Pattern.generate_list(response_text, str(value))
        return patterns_map

    def extract_cursor(self, response_text: str) -> dict[str, Any] | None:
        cursor = {}
        for key, patterns in self.patterns_map.items():
            if not patterns:
                # we assume it is a constant value that does not needs to be updated
                cursor[key] = self.default_cursor[key]
                continue

            for pattern in patterns:
                if output := pattern.test(response_text):
                    cursor[key] = output
                    break
            else:
                return None
        return cursor


StrategyInfo = PageInfo | PageOffsetInfo | LimitOffsetInfo | StringCursorInfo | MapCursorInfo
