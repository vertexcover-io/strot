from collections.abc import Callable
from typing import Any, TypedDict

from pydantic import BaseModel, model_validator

from strot.analyzer.schema import Pattern, Response
from strot.analyzer.schema.request import Request, RequestException
from strot.analyzer.utils import LimitOffsetTracker, extract_potential_cursor_values, generate_patterns

__all__ = ("PaginationStrategy", "IndexPaginationParameter", "IndexInfo", "CursorPaginationParameter", "CursorInfo")


class IndexPaginationParameter(TypedDict):
    key: str
    default_value: int


class CursorPaginationParameter(TypedDict):
    key: str
    default_value: str  # string representation of the default value
    pattern_map: dict[str, list[Pattern]]


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


class IndexInfo(PaginationStrategy):
    page: IndexPaginationParameter | None = None
    limit: IndexPaginationParameter | None = None
    offset: IndexPaginationParameter | None = None

    @model_validator(mode="after")
    def validate_required_fields(self):
        if not self.page and not self.offset:
            raise ValueError("Either page or offset parameter is required")
        return self

    @property
    def name(self) -> str:
        return "index-based"

    def _get_gen_fn(self):
        """Return the pagination combination in priority order"""
        if self.limit and self.offset:
            return self._generate_limit_offset_data
        elif self.page and self.limit:
            return self._generate_page_limit_data
        elif self.page and self.offset:
            return self._generate_page_offset_data
        else:
            return self._generate_page_limit_data

    async def _detect_page_base(self, request: Request) -> int:
        """Detect if API uses 0-based or 1-based page numbering by testing page 0"""
        try:
            await (await request.make(state={self.page["key"]: "0"})).text()
        except RequestException:
            return 1  # Page 0 failed, API is 1-based
        else:
            return 0  # Page 0 works, API is 0-based

    async def generate_data(
        self, request: Request, tracker: LimitOffsetTracker, extract_fn: Callable[[str], list], default_limit: int = 1
    ):
        gen_fn = self._get_gen_fn()
        async for data in gen_fn(request, tracker, extract_fn, default_limit):
            yield data

    async def _generate_limit_offset_data(
        self,
        request: Request,
        tracker: LimitOffsetTracker,
        extract_fn: Callable[[str], list],
        default_limit: int,
    ):
        """Generate data using limit/offset pagination"""
        current_offset = tracker.offset
        page_size = tracker.limit if self.limit else default_limit

        first_request = True
        last_response = None
        used_fallback = False  # Track if we've already used the default limit fallback

        # Initialize tracker's global position to start at the beginning of our first request
        tracker.global_position = tracker.offset

        while tracker.remaining_items > 0:
            state = {
                self.offset["key"]: str(current_offset),
            }
            if self.limit:
                state[self.limit["key"]] = str(page_size)

            try:
                response = await (await request.make(state=state)).text()
            except RequestException as e:
                # On first 400 error, try default limit if limit key is available and we haven't used fallback yet
                if e.status_code == 400 and self.limit and not used_fallback:
                    page_size = default_limit
                    state[self.limit["key"]] = str(page_size)
                    used_fallback = True
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
                elif self.limit and len(data) < page_size:
                    page_size = len(data)
                first_request = False

            if slice_data := tracker.slice(data):
                yield slice_data
                # Move to next page by incrementing offset by the full data length
                current_offset += len(data)
            else:
                break

    async def _generate_page_limit_data(  # noqa: C901
        self,
        request: Request,
        tracker: LimitOffsetTracker,
        extract_fn: Callable[[str], list],
        default_limit: int,
    ):
        """Generate data using page/limit pagination"""
        page_base = await self._detect_page_base(request)

        # Determine the page size (items per page)
        page_size = default_limit
        if self.limit:
            # Try to use user's requested limit as page size, fall back to default
            try:
                test_state = {self.page["key"]: str(page_base), self.limit["key"]: str(tracker.limit)}
                response = await (await request.make(state=test_state)).text()
                test_data = extract_fn(response)
                if test_data:
                    page_size = min(len(test_data), tracker.limit)
            except RequestException:
                page_size = default_limit

        # Calculate which pages we need to fetch
        start_page = page_base + (tracker.offset // page_size)
        end_item = tracker.offset + tracker.limit
        end_page = page_base + ((end_item - 1) // page_size)

        current_page = start_page
        last_response = None
        used_fallback = False  # Track if we've already used the default limit fallback

        # Set initial global position for tracker based on the starting page
        tracker.global_position = (start_page - page_base) * page_size

        while tracker.remaining_items > 0 and current_page <= end_page:
            # Prepare request state
            state = {self.page["key"]: str(current_page)}
            if self.limit:
                state[self.limit["key"]] = str(page_size)

            try:
                response = await (await request.make(state=state)).text()
            except RequestException as e:
                # On first 400 error, try default limit if limit key is available and we haven't used fallback yet
                if e.status_code == 400 and self.limit and not used_fallback:
                    page_size = default_limit
                    state[self.limit["key"]] = str(page_size)
                    used_fallback = True
                    response = await (await request.make(state=state)).text()
                else:
                    break

            # Check for identical responses (end of data)
            if response == last_response:
                if current_page == 1:  # both page 0 and 1 can return the same response
                    current_page += 1
                    continue
                break

            last_response = response
            data = extract_fn(response)
            if not data:
                break

            # Use tracker.slice to handle offset/limit logic
            if slice_data := tracker.slice(data):
                yield slice_data
            else:
                break

            current_page += 1

    async def _generate_page_offset_data(
        self,
        request: Request,
        tracker: LimitOffsetTracker,
        extract_fn: Callable[[str], list],
        default_limit: int,
    ):
        """Generate data using page/offset pagination"""
        page_base = await self._detect_page_base(request)

        # This is tricky - we need to figure out how page and offset interact
        # Common patterns:
        # 1. page=N, offset=M means "start at page N, then skip M items within that page"
        # 2. page=N, offset=M means "page N of results, starting from global offset M"

        # We'll assume pattern 1 (offset within page) for now
        # In a real implementation, you'd need to test the API behavior

        # Calculate starting page based on user offset and estimated page size
        estimated_page_size = default_limit
        start_page = page_base + (tracker.offset // estimated_page_size)
        end_item = tracker.offset + tracker.limit
        end_page = page_base + ((end_item - 1) // estimated_page_size)
        offset_within_page = tracker.offset % estimated_page_size

        current_page = start_page
        last_response = None

        # Set initial global position for tracker based on the starting page
        tracker.global_position = (start_page - page_base) * estimated_page_size

        while tracker.remaining_items > 0 and current_page <= end_page:
            state = {
                self.page["key"]: str(current_page),
                self.offset["key"]: str(self.offset["default_value"] + offset_within_page),
            }

            try:
                response = await (await request.make(state=state)).text()
            except RequestException:
                break

            if response == last_response:
                if current_page == 1:  # both page 0 and 1 can return the same response
                    current_page += 1
                    continue
                break
            last_response = response

            data = extract_fn(response)
            if not data:
                break

            # Use tracker.slice to handle offset/limit logic
            if slice_data := tracker.slice(data):
                yield slice_data
            else:
                break

            # For subsequent pages, no offset within page
            if current_page > start_page:
                offset_within_page = 0

            current_page += 1


class CursorInfo(PaginationStrategy):
    cursor: CursorPaginationParameter
    limit: IndexPaginationParameter | None = None

    @property
    def name(self) -> str:
        return "cursor-based"

    @classmethod
    def create_pattern_map(cls, cursor_value: Any, relevant_responses: list[Response]) -> dict[str, list[Pattern]]:
        """Create pattern map by extracting cursor values and searching in captured responses"""
        extracted_values = extract_potential_cursor_values(cursor_value)
        if not extracted_values:
            return {}

        # Find the response with the most matching values (not necessarily all)
        best_response = None
        best_match_count = 0

        for response in relevant_responses:
            response_text = response.value

            # Count how many extracted values are found in this response
            match_count = sum(1 for value in extracted_values if value in response_text)

            # Keep track of the response with the most matches
            if match_count >= best_match_count:
                best_match_count = match_count
                best_response = response

        # If we found a response with at least some matches, generate patterns
        if best_response and best_match_count > 0:
            pattern_map = {}
            response_text = best_response.value

            for value in extracted_values:
                patterns = generate_patterns(response_text, value)
                if patterns:
                    pattern_map[value] = patterns

            return pattern_map

        return {}

    def extract_cursor(self, response_text: str) -> str | None:
        """Extract next cursor from response using pattern map"""
        cursor_values = {}

        for value, patterns in self.cursor["pattern_map"].items():
            if not patterns:
                # Constant value that doesn't need updating
                cursor_values[value] = value
                continue

            for pattern in patterns:
                if (output := pattern.test(response_text)) and len(output) == len(value):
                    cursor_values[value] = output
                    break
            else:
                # If we can't find a pattern for this value, cursor extraction failed
                return None

        if not cursor_values:
            return None

        # Reconstruct cursor with new values
        new_cursor = self.cursor["default_value"]
        for old_value, new_value in cursor_values.items():
            new_cursor = new_cursor.replace(old_value, new_value)

        return new_cursor

    async def get_start_cursor(self, request: Request) -> str | None:
        """Determine the starting cursor value for pagination."""

        # Try 1: No cursor (some APIs support starting without cursor)
        try:
            _ = await (await request.make(state={self.cursor["key"]: None})).text()
        except RequestException:
            pass
        else:
            return None

        # Try 2: Replace cursor values with null to create a "first page" cursor
        try:
            cursor = self.cursor["default_value"]
            for value in self.cursor["pattern_map"]:
                # Replace the cursor value with "null", handling quoted values properly
                pos = cursor.find(value)
                if pos != -1:
                    # Check for quotes around the value
                    if pos > 0 and cursor[pos - 1] == '"':
                        value = f'"{value}"'
                        i = 2
                        while pos >= i and cursor[pos - i] == "\\":
                            value = f"\\{value}\\"
                            i += 1

                    cursor = cursor.replace(value, "null")

            _ = await (await request.make(state={self.cursor["key"]: cursor})).text()
        except RequestException:
            pass
        else:
            return cursor

        # Try 3: Use original default cursor as fallback
        return self.cursor["default_value"]

    async def generate_data(
        self,
        request: Request,
        tracker: LimitOffsetTracker,
        extract_fn: Callable[[str], list],
        default_limit: int = 1,
    ):
        state = {self.cursor["key"]: await self.get_start_cursor(request)}
        if self.limit:
            state[self.limit["key"]] = str(tracker.limit)

        first_request = True
        last_response = None
        while tracker.remaining_items > 0:
            try:
                response = await (await request.make(state=state)).text()
            except RequestException as e:
                if e.status_code == 400 and self.limit and first_request:
                    state[self.limit["key"]] = str(default_limit)
                    response = await (await request.make(state=state)).text()
                else:
                    raise
            if response == last_response:
                break
            last_response = response
            data = extract_fn(response)

            # Detect API's actual limit on first request
            if self.limit and first_request and len(data) < tracker.limit:
                state[self.limit["key"]] = str(len(data))
                first_request = False

            if slice_data := tracker.slice(data):
                yield slice_data
            else:
                # For cursor pagination, update global_position even when no slice is returned
                tracker.global_position += len(data)

            next_cursor = self.extract_cursor(response)
            if next_cursor is None or next_cursor == state[self.cursor["key"]]:
                break
            state[self.cursor["key"]] = next_cursor
