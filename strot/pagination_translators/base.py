from typing import Any

from strot.schema.request import RequestDetail
from strot.schema.response import ResponseDetail

__all__ = ("BasePaginationTranslator",)


class BasePaginationTranslator:
    async def _fetch_data(
        self, request_detail: RequestDetail, response_detail: ResponseDetail, parameters: dict[str, Any]
    ) -> list:
        response = await request_detail.make_request(parameters=parameters)
        return response_detail.extract_data(await response.text())

    async def detect_start_page(self, request_detail: RequestDetail, response_detail: ResponseDetail) -> int:
        pg_info = request_detail.pagination_info
        if pg_info is None:
            raise ValueError("Pagination info not found")
        if pg_info.page is None:
            raise ValueError("Pagination info must have a page parameter")

        data = await self._fetch_data(request_detail, response_detail, parameters={pg_info.page.key: "0"})
        return 0 if data else 1

    async def detect_start_cursor(self, request_detail: RequestDetail, response_detail: ResponseDetail) -> str | None:
        pg_info = request_detail.pagination_info
        if pg_info is None:
            raise ValueError("Pagination info not found")
        if pg_info.cursor is None:
            raise ValueError("Pagination info must have a cursor parameter")

        # Try 1: No cursor (some APIs support starting without cursor)
        try:
            if await self._fetch_data(request_detail, response_detail, parameters={pg_info.cursor.key: None}):
                return None
        except Exception:  # noqa: S110
            pass

        # Try 2: Replace sub cursors with null to create a "first page" cursor
        try:
            nullable_cursor = pg_info.cursor.get_nullable_cursor()
            if await self._fetch_data(
                request_detail, response_detail, parameters={pg_info.cursor.key: nullable_cursor}
            ):
                return nullable_cursor
        except Exception:  # noqa: S110
            pass

        # Fallback: Use default cursor as starting cursor
        return pg_info.cursor.default_value

    async def generate_data(
        self,
        *,
        request_detail: RequestDetail,
        response_detail: ResponseDetail,
        **dynamic_parameters,
    ):
        raise NotImplementedError
