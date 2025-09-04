from strot.exceptions import RequestException
from strot.pagination_translators.base import BasePaginationTranslator
from strot.schema.request import RequestDetail
from strot.schema.response import ResponseDetail

__all__ = ("LimitOffsetTranslator",)


class LimitOffsetTranslator(BasePaginationTranslator):
    def __init__(self, limit: int, offset: int):
        self.offset = offset
        self.limit = limit
        self.global_position = 0
        self.remaining_items = limit

    def slice(self, data: list) -> list:
        if not data:
            return []

        chunk_start = max(0, self.offset - self.global_position)
        chunk_end = min(len(data), chunk_start + self.remaining_items)
        self.global_position += len(data)

        if chunk_start < len(data):
            slice_data = data[chunk_start:chunk_end]
            if slice_data:
                self.remaining_items -= len(slice_data)
                return slice_data

        return []

    async def generate_data(
        self,
        *,
        request_detail: RequestDetail,
        response_detail: ResponseDetail,
        **dynamic_parameters,
    ):
        pg_info = request_detail.pagination_info
        if not pg_info:
            data = await self._fetch_data(request_detail, response_detail, parameters=dynamic_parameters)
            if slice_data := self.slice(data):
                yield slice_data
            return

        if pg_info.limit and pg_info.offset:
            gen_fn = self._generate_limit_offset_data
        elif pg_info.page and pg_info.limit:
            gen_fn = self._generate_page_limit_data
        elif pg_info.page and pg_info.offset:
            gen_fn = self._generate_page_offset_data
        elif pg_info.cursor:
            gen_fn = self._generate_cursor_data
        else:
            gen_fn = self._generate_page_limit_data

        async for data in gen_fn(request_detail, response_detail, **dynamic_parameters):
            yield data

    async def _generate_limit_offset_data(
        self,
        request_detail: RequestDetail,
        response_detail: ResponseDetail,
        **dynamic_parameters,
    ):
        """Generate data using limit/offset pagination"""
        page_size = self.limit if request_detail.pagination_info.limit else response_detail.default_entity_count

        first_request = True
        last_response_text = None
        used_fallback = False  # Track if we've already used the default limit fallback

        # Initialize tracker's global position to start at the beginning of our first request
        self.global_position = self.offset

        pg_info = request_detail.pagination_info
        while self.remaining_items > 0:
            state = dynamic_parameters | {
                pg_info.offset.key: str(self.global_position),
            }
            if pg_info.limit:
                state[pg_info.limit.key] = str(page_size)

            try:
                response = await request_detail.make_request(parameters=state)
            except RequestException as e:
                # On first 400 error, try default limit if limit key is available and we haven't used fallback yet
                if e.status_code == 400 and pg_info.limit and not used_fallback:
                    page_size = response_detail.default_entity_count
                    state[pg_info.limit.key] = str(page_size)
                    used_fallback = True
                    response = await request_detail.make_request(parameters=state)
                else:
                    raise

            response_text = await response.text()
            if not response_text or response_text == last_response_text:
                break
            last_response_text = response_text
            data = response_detail.extract_data(response_text)

            # Detect API's actual limit on first request
            if first_request:
                if len(data) == 0:
                    # If first request returns no data, API doesn't support this limit
                    break
                elif pg_info.limit and len(data) < page_size:
                    page_size = len(data)
                first_request = False

            if slice_data := self.slice(data):
                yield slice_data
            else:
                break

    async def _generate_page_limit_data(  # noqa: C901
        self,
        request_detail: RequestDetail,
        response_detail: ResponseDetail,
        **dynamic_parameters,
    ):
        """Generate data using page/limit pagination"""
        start_page = await self.detect_start_page(request_detail, response_detail)

        # Determine the page size (items per page)
        pg_info = request_detail.pagination_info
        page_size = response_detail.default_entity_count
        if pg_info.limit:
            # Try to use user's requested limit as page size, fall back to default
            try:
                test_state = dynamic_parameters | {
                    pg_info.page.key: str(start_page),
                    pg_info.limit.key: str(self.limit),
                }
                if test_data := await self._fetch_data(request_detail, response_detail, parameters=test_state):
                    page_size = min(len(test_data), self.limit)
            except RequestException:
                page_size = response_detail.default_entity_count

        # Calculate which pages we need to fetch
        start_page = start_page + (self.offset // page_size)

        current_page = start_page
        last_response_text = None
        used_fallback = False  # Track if we've already used the default limit fallback

        self.global_position = self.offset
        pg_info = request_detail.pagination_info
        while self.remaining_items > 0:
            # Prepare request state
            state = dynamic_parameters | {pg_info.page.key: str(current_page)}
            if pg_info.limit:
                state[pg_info.limit.key] = str(page_size)

            try:
                response = await request_detail.make_request(parameters=state)
            except RequestException as e:
                # On first 400 error, try default limit if limit key is available and we haven't used fallback yet
                if e.status_code == 400 and pg_info.limit and not used_fallback:
                    page_size = response_detail.default_entity_count
                    state[pg_info.limit.key] = str(page_size)
                    used_fallback = True
                    response = await request_detail.make_request(parameters=state)
                else:
                    raise

            response_text = await response.text()
            # Check for identical responses (end of data)
            if not response_text or response_text == last_response_text:
                if current_page == 1:  # both page 0 and 1 can return the same response
                    current_page += 1
                    continue
                break

            last_response_text = response_text
            data = response_detail.extract_data(response_text)
            if not data:
                break

            # Use tracker.slice to handle offset/limit logic
            if slice_data := self.slice(data):
                yield slice_data
            else:
                break

            current_page += 1

    async def _generate_page_offset_data(
        self,
        request_detail: RequestDetail,
        response_detail: ResponseDetail,
        **dynamic_parameters,
    ):
        """Generate data using page/offset pagination"""
        start_page = await self.detect_start_page(request_detail, response_detail)

        # This is tricky - we need to figure out how page and offset interact
        # Common patterns:
        # 1. page=N, offset=M means "start at page N, then skip M items within that page"
        # 2. page=N, offset=M means "page N of results, starting from global offset M"

        # We'll assume pattern 1 (offset within page) for now
        # In a real implementation, you'd need to test the API behavior

        # Calculate starting page based on user offset and estimated page size
        estimated_page_size = response_detail.default_entity_count
        start_page = start_page + (self.offset // estimated_page_size)
        end_item = self.offset + self.limit
        end_page = start_page + ((end_item - 1) // estimated_page_size)
        offset_within_page = self.offset % estimated_page_size

        current_page = start_page
        last_response_text = None

        # Set initial global position for tracker based on the starting page
        self.global_position = (start_page - start_page) * estimated_page_size

        pg_info = request_detail.pagination_info
        while self.remaining_items > 0 and current_page <= end_page:
            state = dynamic_parameters | {
                pg_info.page.key: str(current_page),
                pg_info.offset.key: str(pg_info.offset.default_value + offset_within_page),
            }

            response = await request_detail.make_request(parameters=state)

            response_text = await response.text()
            if not response_text or response_text == last_response_text:
                if current_page == 1:  # both page 0 and 1 can return the same response
                    current_page += 1
                    continue
                break
            last_response_text = response_text

            data = response_detail.extract_data(response_text)
            if not data:
                break

            # Use tracker.slice to handle offset/limit logic
            if slice_data := self.slice(data):
                yield slice_data
            else:
                break

            # For subsequent pages, no offset within page
            if current_page > start_page:
                offset_within_page = 0

            current_page += 1

    async def _generate_cursor_data(  # noqa: C901
        self,
        request_detail: RequestDetail,
        response_detail: ResponseDetail,
        **dynamic_parameters,
    ):
        all_cursors = []
        pg_info = request_detail.pagination_info
        start_cursor = await self.detect_start_cursor(request_detail, response_detail)
        if start_cursor:
            all_cursors.append(start_cursor)
        state = dynamic_parameters | {pg_info.cursor.key: start_cursor}
        if pg_info.page:
            state[pg_info.page.key] = str(await self.detect_start_page(request_detail, response_detail))
        if pg_info.limit:
            state[pg_info.limit.key] = str(self.limit)

        first_request = True
        last_response_text = None
        if pg_info.offset:
            self.global_position = pg_info.offset.default_value
        while self.remaining_items > 0:
            if pg_info.offset:
                state[pg_info.offset.key] = str(self.global_position)
            try:
                response = await request_detail.make_request(parameters=state)
            except RequestException as e:
                if e.status_code == 400 and pg_info.limit and first_request:
                    state[pg_info.limit.key] = str(response_detail.default_entity_count)
                    response = await request_detail.make_request(parameters=state)
                else:
                    raise

            response_text = await response.text()
            if not response_text or response_text == last_response_text:
                if pg_info.page:
                    current_page = int(state[pg_info.page.key])
                    if current_page == 1:  # both page 0 and 1 can return the same response
                        state[pg_info.page.key] = str(current_page + 1)
                        continue
                break
            last_response_text = response_text
            data = response_detail.extract_data(response_text)

            # Detect API's actual limit on first request
            if pg_info.limit and first_request and len(data) < self.limit:
                state[pg_info.limit.key] = str(len(data))
                first_request = False

            if slice_data := self.slice(data):
                yield slice_data

            next_cursor = pg_info.cursor.extract_cursor(response_text)
            if next_cursor is None or next_cursor in all_cursors:
                break
            all_cursors.append(next_cursor)
            state[pg_info.cursor.key] = next_cursor
            if pg_info.page:
                state[pg_info.page.key] = str(int(state[pg_info.page.key]) + 1)
