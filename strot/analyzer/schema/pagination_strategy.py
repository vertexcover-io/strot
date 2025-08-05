from collections.abc import Callable
from json import dumps as json_dumps
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, PrivateAttr

from strot.analyzer.schema import Pattern
from strot.analyzer.schema.request import Request, RequestException
from strot.analyzer.utils import LimitOffsetTracker, generate_patterns

__all__ = ("PaginationStrategy", "PageInfo", "PageOffsetInfo", "LimitOffsetInfo", "StringCursorInfo", "MapCursorInfo")


CursorT = TypeVar("CursorT")


class PaginationStrategy(BaseModel):
    @property
    def name(self) -> str:
        raise NotImplementedError("Subclasses must implement this property")

    async def generate_data(
        self,
        request: Request,
        tracker: LimitOffsetTracker,
        extract_fn: Callable[[str], list],
        default_limit: int = 1,
    ):
        raise NotImplementedError("Subclasses must implement this method")


class PageInfo(PaginationStrategy):
    page_key: str
    limit_key: str | None = None

    @property
    def name(self) -> str:
        return "page-based"

    async def generate_data(  # noqa: C901
        self,
        request: Request,
        tracker: LimitOffsetTracker,
        extract_fn: Callable[[str], list],
        default_limit: int = 1,
    ):
        actual_limit = default_limit
        state = {}

        # If limit_key exists, detect actual API limit first
        if self.limit_key:
            state[self.limit_key] = str(tracker.limit)
            state[self.page_key] = "1"

            try:
                response = await (await request.make(state=state)).text()
            except RequestException as e:
                if e.status_code == 400:
                    state[self.limit_key] = str(actual_limit)
                    response = await (await request.make(state=state)).text()
                else:
                    raise

            data = extract_fn(response)

            # If the first request with the requested limit returns no data,
            # it likely means the API doesn't support that limit - stop here
            if len(data) == 0:
                return

            # Use detected limit or original tracker limit
            actual_limit = len(data) if len(data) < tracker.limit else tracker.limit
            state[self.limit_key] = str(actual_limit)

            # If this first page contains our target data, yield it
            tracker.global_position = 0
            if slice_data := tracker.slice(data):
                yield slice_data
                if tracker.remaining_items <= 0:
                    return

            # Start from page 2 for remaining iterations
            start_page = 2
        else:
            start_page = 1

        # Now calculate pages with the actual limit
        if start_page == 1:
            start_page = (tracker.offset // actual_limit) + 1

        end_item = tracker.offset + tracker.limit
        end_page = ((end_item - 1) // actual_limit) + 1

        if start_page == 1:
            tracker.global_position = 0
        else:
            tracker.global_position = (start_page - 1) * actual_limit

        last_response = None
        for page in range(start_page, end_page + 1):
            state[self.page_key] = str(page)
            response = await (await request.make(state=state)).text()
            if response == last_response:
                break
            last_response = response
            data = extract_fn(response)

            if slice_data := tracker.slice(data):
                yield slice_data
                if tracker.remaining_items <= 0:
                    break
            else:
                break


class PageOffsetInfo(PaginationStrategy):
    page_key: str
    offset_key: str
    base_offset: int

    @property
    def name(self) -> str:
        return "page-offset"

    async def generate_data(
        self,
        request: Request,
        tracker: LimitOffsetTracker,
        extract_fn: Callable[[str], list],
        default_limit: int = 1,
    ):
        # Use default_limit but ensure it's at least 1 for division
        safe_limit = max(default_limit, 1)
        start_page = (tracker.offset // safe_limit) + 1
        end_item = tracker.offset + tracker.limit
        end_page = ((end_item - 1) // safe_limit) + 1

        tracker.global_position = (start_page - 1) * safe_limit
        last_response = None
        for page in range(start_page, end_page + 1):
            state = {
                self.page_key: str(page),
                self.offset_key: str(self.base_offset * page),
            }
            response = await (await request.make(state=state)).text()
            if response == last_response:
                break
            last_response = response
            data = extract_fn(response)

            if slice_data := tracker.slice(data):
                yield slice_data
                if tracker.remaining_items <= 0:
                    break
            else:
                break


class LimitOffsetInfo(PaginationStrategy):
    limit_key: str
    offset_key: str

    @property
    def name(self) -> str:
        return "limit-offset"

    async def generate_data(
        self,
        request: Request,
        tracker: LimitOffsetTracker,
        extract_fn: Callable[[str], list],
        default_limit: int = 1,
    ):
        state = {
            self.limit_key: str(tracker.limit),
            self.offset_key: str(tracker.offset),
        }

        first_request = True
        last_response = None
        while tracker.remaining_items > 0:
            try:
                response = await (await request.make(state=state)).text()
            except RequestException as e:
                if e.status_code == 400 and first_request:
                    state[self.limit_key] = str(default_limit)
                    response = await (await request.make(state=state)).text()
                else:
                    raise
            if response == last_response:
                break
            last_response = response
            data = extract_fn(response)

            # Detect API's actual limit on first request
            if first_request:
                if len(data) == 0:
                    # If first request returns no data, API doesn't support this limit
                    break
                elif len(data) < tracker.limit:
                    state[self.limit_key] = str(len(data))
                first_request = False

            if slice_data := tracker.slice(data):
                yield slice_data
                state[self.offset_key] = str(int(state[self.offset_key]) + len(slice_data))
            else:
                break


class BaseCursorInfo(PaginationStrategy, Generic[CursorT]):
    cursor_key: str
    limit_key: str | None = None
    default_cursor: CursorT

    _repr_fn: Callable[[CursorT], str] = PrivateAttr(default=lambda c, x: x)

    @property
    def name(self) -> str:
        return "cursor-based"

    def extract_cursor(self, response_text: str) -> CursorT | None:
        raise NotImplementedError("Subclasses must implement this method")

    async def generate_data(
        self,
        request: Request,
        tracker: LimitOffsetTracker,
        extract_fn: Callable[[str], list],
        default_limit: int = 1,
    ):
        state = {self.cursor_key: None}
        if self.limit_key:
            state[self.limit_key] = str(tracker.limit)

        first_request = True
        last_response = None
        while tracker.remaining_items > 0:
            try:
                response = await (await request.make(state=state)).text()
            except RequestException as e:
                if e.status_code == 400 and self.limit_key and first_request:
                    state[self.limit_key] = str(default_limit)
                    response = await (await request.make(state=state)).text()
                else:
                    raise
            if response == last_response:
                break
            last_response = response
            data = extract_fn(response)

            # Detect API's actual limit on first request
            if self.limit_key and first_request and len(data) < tracker.limit:
                state[self.limit_key] = str(len(data))
                first_request = False

            if slice_data := tracker.slice(data):
                yield slice_data
            else:
                # For cursor pagination, update global_position even when no slice is returned
                # so we can eventually reach the offset
                tracker.global_position += len(data)

            next_cursor = self.extract_cursor(response)
            if next_cursor is None or self._repr_fn(next_cursor) == state[self.cursor_key]:
                break
            state[self.cursor_key] = self._repr_fn(next_cursor)


class StringCursorInfo(BaseCursorInfo[str]):
    patterns: list[Pattern]

    @classmethod
    def generate_patterns(cls, response_text: str, cursor: str) -> list[Pattern]:
        return generate_patterns(response_text, cursor)

    def extract_cursor(self, response_text: str) -> str | None:
        for pattern in self.patterns:
            if output := pattern.test(response_text):
                return output
        return None


class MapCursorInfo(BaseCursorInfo[dict[str, Any]]):
    patterns_map: dict[str, list[Pattern]]

    _repr_fn: Callable[[dict[str, Any]], str] = PrivateAttr(default=lambda c, x: json_dumps(x))

    @classmethod
    def generate_patterns_map(cls, response_text: str, cursor: dict[str, Any]) -> dict[str, list[Pattern]]:
        patterns_map: dict[str, list[Pattern]] = {}
        for key, value in cursor.items():
            patterns_map[key] = generate_patterns(response_text, str(value))
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
