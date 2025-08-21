from collections.abc import Callable
from typing import TypedDict

from pydantic import BaseModel, model_validator

from strot.analyzer.schema import Pattern, ResponsePreprocessorT
from strot.analyzer.schema.request import Request, RequestException
from strot.analyzer.utils import LimitOffsetTracker

__all__ = ("PaginationStrategy", "NumberParameter", "CursorParameter")


class NumberParameter(TypedDict):
    key: str
    default_value: int


class CursorParameter(TypedDict):
    key: str
    default_value: str
    pattern_map: dict[str, list[Pattern]]


class PaginationStrategy(BaseModel):
    page: NumberParameter | None = None
    cursor: CursorParameter | None = None
    limit: NumberParameter | None = None
    offset: NumberParameter | None = None

    @model_validator(mode="after")
    def validate_required_fields(self):
        if not self.page and not self.offset and not self.cursor:
            raise ValueError("Either page, offset or cursor parameter is required")
        return self

    async def generate_data(
        self,
        *,
        request: Request,
        tracker: LimitOffsetTracker,
        response_preprocessor: ResponsePreprocessorT | None = None,
        extract_fn: Callable[[str], list],
        default_limit: int = 1,
    ):
        gen_fn = self._get_gen_fn()
        async for data in gen_fn(request, tracker, response_preprocessor, extract_fn, default_limit):
            yield data

    def _get_gen_fn(self):
        """Return the pagination combination in priority order"""
        if self.limit and self.offset:
            return self._generate_limit_offset_data
        elif self.page and self.limit:
            return self._generate_page_limit_data
        elif self.page and self.offset:
            return self._generate_page_offset_data
        elif self.cursor:
            return self._generate_cursor_data
        else:
            return self._generate_page_limit_data

    @staticmethod
    async def _make_request(
        request: Request,
        state: dict,
        response_preprocessor: ResponsePreprocessorT | None,
    ) -> tuple[str, str | None]:
        response = await request.make(state=state)
        original_text = await response.text()
        if response_preprocessor:
            return original_text, response_preprocessor.run(original_text)
        return original_text, original_text

    async def _generate_limit_offset_data(
        self,
        request: Request,
        tracker: LimitOffsetTracker,
        response_preprocessor: ResponsePreprocessorT | None,
        extract_fn: Callable[[str], list],
        default_limit: int,
    ):
        """Generate data using limit/offset pagination"""
        page_size = tracker.limit if self.limit else default_limit

        first_request = True
        last_response = None
        used_fallback = False  # Track if we've already used the default limit fallback

        # Initialize tracker's global position to start at the beginning of our first request
        tracker.global_position = tracker.offset

        while tracker.remaining_items > 0:
            state = {
                self.offset["key"]: str(tracker.global_position),
            }
            if self.limit:
                state[self.limit["key"]] = str(page_size)

            try:
                _, response = await self._make_request(request, state, response_preprocessor)
            except RequestException as e:
                # On first 400 error, try default limit if limit key is available and we haven't used fallback yet
                if e.status_code == 400 and self.limit and not used_fallback:
                    page_size = default_limit
                    state[self.limit["key"]] = str(page_size)
                    used_fallback = True
                    _, response = await self._make_request(request, state, response_preprocessor)
                else:
                    raise

            if not response or response == last_response:
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
            else:
                break

    async def _generate_page_limit_data(  # noqa: C901
        self,
        request: Request,
        tracker: LimitOffsetTracker,
        response_preprocessor: ResponsePreprocessorT | None,
        extract_fn: Callable[[str], list],
        default_limit: int,
    ):
        """Generate data using page/limit pagination"""
        page_base = await self._detect_page_base(self.page, request, response_preprocessor, extract_fn)

        # Determine the page size (items per page)
        page_size = default_limit
        if self.limit:
            # Try to use user's requested limit as page size, fall back to default
            try:
                test_state = {self.page["key"]: str(page_base), self.limit["key"]: str(tracker.limit)}
                _, response = await self._make_request(request, test_state, response_preprocessor)
                if response and (test_data := extract_fn(response)):
                    page_size = min(len(test_data), tracker.limit)
            except RequestException:
                page_size = default_limit

        # Calculate which pages we need to fetch
        start_page = page_base + (tracker.offset // page_size)

        current_page = start_page
        last_response = None
        used_fallback = False  # Track if we've already used the default limit fallback

        tracker.global_position = tracker.offset
        while tracker.remaining_items > 0:
            # Prepare request state
            state = {self.page["key"]: str(current_page)}
            if self.limit:
                state[self.limit["key"]] = str(page_size)

            try:
                _, response = await self._make_request(request, state, response_preprocessor)
            except RequestException as e:
                # On first 400 error, try default limit if limit key is available and we haven't used fallback yet
                if e.status_code == 400 and self.limit and not used_fallback:
                    page_size = default_limit
                    state[self.limit["key"]] = str(page_size)
                    used_fallback = True
                    _, response = await self._make_request(request, state, response_preprocessor)
                else:
                    break

            # Check for identical responses (end of data)
            if not response or response == last_response:
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
        response_preprocessor: ResponsePreprocessorT | None,
        extract_fn: Callable[[str], list],
        default_limit: int,
    ):
        """Generate data using page/offset pagination"""
        page_base = await self._detect_page_base(self.page, request, response_preprocessor, extract_fn)

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
                _, response = await self._make_request(request, state, response_preprocessor)
            except RequestException:
                break

            if not response or response == last_response:
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

    async def _generate_cursor_data(  # noqa: C901
        self,
        request: Request,
        tracker: LimitOffsetTracker,
        response_preprocessor: ResponsePreprocessorT | None,
        extract_fn: Callable[[str], list],
        default_limit: int = 1,
    ):
        all_cursors = []
        start_cursor = await get_start_cursor(request, self.cursor)
        if start_cursor:
            all_cursors.append(start_cursor)
        state = {self.cursor["key"]: start_cursor}
        if self.page:
            state[self.page["key"]] = str(
                await self._detect_page_base(self.page, request, response_preprocessor, extract_fn)
            )
        if self.limit:
            state[self.limit["key"]] = str(tracker.limit)

        first_request = True
        last_response = None
        if self.offset:
            tracker.global_position = tracker.offset
        while tracker.remaining_items > 0:
            if self.offset:
                state[self.offset["key"]] = str(tracker.global_position)
            try:
                orig, response = await self._make_request(request, state, response_preprocessor)
            except RequestException as e:
                if e.status_code == 400 and self.limit and first_request:
                    state[self.limit["key"]] = str(default_limit)
                    orig, response = await self._make_request(request, state, response_preprocessor)
                else:
                    raise
            if not response or response == last_response:
                if self.page:
                    current_page = int(state[self.page["key"]])
                    if current_page == 1:  # both page 0 and 1 can return the same response
                        state[self.page["key"]] = str(current_page + 1)
                        continue
                break
            last_response = response
            data = extract_fn(response)

            # Detect API's actual limit on first request
            if self.limit and first_request and len(data) < tracker.limit:
                state[self.limit["key"]] = str(len(data))
                first_request = False

            if slice_data := tracker.slice(data):
                yield slice_data

            next_cursor = extract_cursor(orig, self.cursor)
            if next_cursor is None or next_cursor in all_cursors:
                break
            all_cursors.append(next_cursor)
            state[self.cursor["key"]] = next_cursor
            if self.page:
                state[self.page["key"]] = str(int(state[self.page["key"]]) + 1)

    async def _detect_page_base(
        self,
        page_parameter: NumberParameter,
        request: Request,
        response_preprocessor: ResponsePreprocessorT | None,
        extract_fn: Callable[[str], list],
    ) -> int:
        """Detect if API uses 0-based or 1-based page numbering by testing page 0"""
        try:
            _, response = await self._make_request(request, {page_parameter["key"]: "0"}, response_preprocessor)
            if response and extract_fn(response):
                return 0  # Page 0 works, API is 0-based
        except RequestException:
            pass
        return 1  # Page 0 failed, API is 1-based


async def get_start_cursor(request: Request, cursor_parameter: CursorParameter) -> str | None:
    """Determine the starting cursor value for pagination."""

    # Try 1: No cursor (some APIs support starting without cursor)
    try:
        _ = await (await request.make(state={cursor_parameter["key"]: None})).text()
    except RequestException:
        pass
    else:
        return None

    # Try 2: Replace sub cursors with null to create a "first page" cursor
    try:
        cursor = cursor_parameter["default_value"]
        for value in cursor_parameter["pattern_map"]:
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

        _ = await (await request.make(state={cursor_parameter["key"]: cursor})).text()
    except RequestException:
        pass
    else:
        return cursor

    # Fallback: Use default cursor as starting cursor
    return cursor_parameter["default_value"]


def extract_cursor(response_text: str, cursor_parameter: CursorParameter) -> str | None:
    """Extract cursor from response using pattern map"""
    cursor_values = {}

    for value, patterns in cursor_parameter["pattern_map"].items():
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
    new_cursor = cursor_parameter["default_value"]
    for old_value in sorted(cursor_values.keys(), key=len, reverse=True):
        new_cursor = new_cursor.replace(old_value, cursor_values[old_value])

    return new_cursor
