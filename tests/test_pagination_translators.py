"""Tests for pagination translators with real business logic."""

from unittest.mock import AsyncMock

import pytest

from strot.exceptions import RequestException
from strot.pagination_translators.base import BasePaginationTranslator
from strot.pagination_translators.limit_offset import LimitOffsetTranslator
from strot.schema.request import Request
from strot.schema.request.detail import RequestDetail
from strot.schema.request.pagination_info import CursorParameter, NumberParameter, PaginationInfo
from strot.schema.response.detail import ResponseDetail


class TestBasePaginationTranslator:
    """Test the base pagination translator."""

    @pytest.fixture
    def base_translator(self):
        """Create base pagination translator instance."""
        return BasePaginationTranslator()

    @pytest.fixture
    def request_detail_no_pagination(self):
        """Create RequestDetail without pagination info."""
        return RequestDetail(
            request=Request(
                method="GET", url="https://api.example.com/data", type="ajax", queries={}, headers={}, post_data=None
            ),
            dynamic_parameters={},
            pagination_info=None,
            apply_parameters_code="def apply_parameters(request, **params): return request",
        )

    @pytest.fixture
    def response_detail(self):
        """Create ResponseDetail with JSON extraction code."""
        return ResponseDetail(
            preprocessor=None,
            code_to_extract_data="def extract_data(response_text): import json; return json.loads(response_text)['data']",
            default_entity_count=10,
        )

    @pytest.mark.asyncio
    async def test_fetch_data(self, base_translator, request_detail_no_pagination, response_detail, mocker):
        """Test data fetching with mocked HTTP client."""
        # Mock the rnet HTTP client at module level
        mock_rnet_response = AsyncMock()
        mock_rnet_response.status = 200
        mock_rnet_response.text = AsyncMock(return_value='{"data": [{"id": 1}, {"id": 2}]}')

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_rnet_response)

        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        result = await base_translator._fetch_data(request_detail_no_pagination, response_detail, {"page": "1"})

        assert result == [{"id": 1}, {"id": 2}]
        mock_client.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_detect_start_page_no_pagination_info(
        self, base_translator, request_detail_no_pagination, response_detail
    ):
        """Test detect_start_page raises error when pagination info is missing."""
        with pytest.raises(ValueError, match="Pagination info not found"):
            await base_translator.detect_start_page(request_detail_no_pagination, response_detail)

    @pytest.mark.asyncio
    async def test_detect_start_page_no_page_param(
        self, base_translator, request_detail_no_pagination, response_detail
    ):
        """Test detect_start_page raises error when page parameter is missing."""
        request_detail_no_pagination.pagination_info = PaginationInfo(
            page=None,
            limit=None,
            offset=NumberParameter(key="offset", default_value=0),  # Need at least offset to satisfy validation
            cursor=None,
        )

        with pytest.raises(ValueError, match="Pagination info must have a page parameter"):
            await base_translator.detect_start_page(request_detail_no_pagination, response_detail)

    @pytest.mark.asyncio
    async def test_detect_start_page_zero_based(
        self, base_translator, request_detail_no_pagination, response_detail, mocker
    ):
        """Test detect_start_page detects zero-based pagination by testing page 0."""
        request_detail_no_pagination.pagination_info = PaginationInfo(
            page=NumberParameter(key="page", default_value=1), limit=None, offset=None, cursor=None
        )

        # Mock rnet client to return data for page 0
        mock_rnet_response = AsyncMock()
        mock_rnet_response.status = 200
        mock_rnet_response.text = AsyncMock(return_value='{"data": [{"id": 1}]}')

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_rnet_response)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        result = await base_translator.detect_start_page(request_detail_no_pagination, response_detail)
        assert result == 0

    @pytest.mark.asyncio
    async def test_detect_start_page_one_based(
        self, base_translator, request_detail_no_pagination, response_detail, mocker
    ):
        """Test detect_start_page detects one-based pagination when page 0 returns empty data."""
        request_detail_no_pagination.pagination_info = PaginationInfo(
            page=NumberParameter(key="page", default_value=1), limit=None, offset=None, cursor=None
        )

        # Mock rnet client to return empty data for page 0
        mock_rnet_response = AsyncMock()
        mock_rnet_response.status = 200
        mock_rnet_response.text = AsyncMock(return_value='{"data": []}')

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_rnet_response)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        result = await base_translator.detect_start_page(request_detail_no_pagination, response_detail)
        assert result == 1

    @pytest.mark.asyncio
    async def test_detect_start_cursor_no_pagination(
        self, base_translator, request_detail_no_pagination, response_detail
    ):
        """Test detect_start_cursor raises error when pagination info is missing."""
        with pytest.raises(ValueError, match="Pagination info not found"):
            await base_translator.detect_start_cursor(request_detail_no_pagination, response_detail)

    @pytest.mark.asyncio
    async def test_detect_start_cursor_no_cursor_param(
        self, base_translator, request_detail_no_pagination, response_detail
    ):
        """Test detect_start_cursor raises error when cursor parameter is missing."""
        request_detail_no_pagination.pagination_info = PaginationInfo(
            page=NumberParameter(key="page", default_value=1), limit=None, offset=None, cursor=None
        )

        with pytest.raises(ValueError, match="Pagination info must have a cursor parameter"):
            await base_translator.detect_start_cursor(request_detail_no_pagination, response_detail)

    @pytest.mark.asyncio
    async def test_detect_start_cursor_none_supported(
        self, base_translator, request_detail_no_pagination, response_detail, mocker
    ):
        """Test detect_start_cursor returns None when API supports null cursor values."""
        request_detail_no_pagination.pagination_info = PaginationInfo(
            page=None,
            limit=None,
            offset=None,
            cursor=CursorParameter(key="cursor", default_value="default_cursor", pattern_map={}),
        )

        # Mock rnet client to return data when cursor is None
        mock_rnet_response = AsyncMock()
        mock_rnet_response.status = 200
        mock_rnet_response.text = AsyncMock(return_value='{"data": [{"id": 1}]}')

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_rnet_response)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        result = await base_translator.detect_start_cursor(request_detail_no_pagination, response_detail)
        assert result is None

    @pytest.mark.asyncio
    async def test_detect_start_cursor_fallback_to_default(
        self, base_translator, request_detail_no_pagination, response_detail, mocker
    ):
        """Test detect_start_cursor falls back to default value when API requests fail."""
        request_detail_no_pagination.pagination_info = PaginationInfo(
            page=None,
            limit=None,
            offset=None,
            cursor=CursorParameter(key="cursor", default_value="fallback_cursor", pattern_map={}),
        )

        # Mock rnet client to always fail
        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=Exception("API Error"))
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        result = await base_translator.detect_start_cursor(request_detail_no_pagination, response_detail)
        assert result == "fallback_cursor"


class TestLimitOffsetTranslator:
    """Test LimitOffsetTranslator with comprehensive business logic coverage."""

    @pytest.fixture
    def response_detail(self):
        """Create ResponseDetail with JSON extraction logic."""
        return ResponseDetail(
            preprocessor=None,
            code_to_extract_data="def extract_data(response_text): import json; return json.loads(response_text)['items']",
            default_entity_count=10,
        )

    def test_initialization(self):
        """Test LimitOffsetTranslator initializes with correct limit, offset, and tracking values."""
        translator = LimitOffsetTranslator(limit=25, offset=5)
        assert translator.limit == 25
        assert translator.offset == 5
        assert translator.global_position == 0
        assert translator.remaining_items == 25

    def test_slice_empty_data(self):
        """Test slice method returns empty list when input data is empty."""
        translator = LimitOffsetTranslator(limit=10, offset=5)
        result = translator.slice([])
        assert result == []
        assert translator.global_position == 0

    def test_slice_data_before_offset(self):
        """Test slice method skips data that comes before the requested offset."""
        translator = LimitOffsetTranslator(limit=10, offset=20)
        data = list(range(10))  # Items 0-9, but offset is 20
        result = translator.slice(data)
        assert result == []
        assert translator.global_position == 10
        assert translator.remaining_items == 10

    def test_slice_data_spanning_offset(self):
        """Test slice method correctly extracts data that spans the target offset range."""
        translator = LimitOffsetTranslator(limit=5, offset=8)
        translator.global_position = 5  # Start at position 5
        data = list(range(20, 30))  # 10 items starting at position 5

        # Offset is 8, so we want items starting from position 8
        # chunk_start = max(0, 8 - 5) = 3
        # chunk_end = min(10, 3 + 5) = 8
        result = translator.slice(data)

        assert result == [23, 24, 25, 26, 27]  # Items at positions 8-12
        assert translator.global_position == 15
        assert translator.remaining_items == 0

    def test_slice_exact_limit_reached(self):
        """Test slice method stops at exact limit and updates remaining_items to zero."""
        translator = LimitOffsetTranslator(limit=3, offset=0)
        data = [1, 2, 3, 4, 5]
        result = translator.slice(data)

        assert result == [1, 2, 3]
        assert translator.remaining_items == 0

    @pytest.mark.asyncio
    async def test_generate_data_no_pagination_info(self, response_detail, mocker):
        """Test generate_data handles requests without pagination by using slice logic directly."""
        translator = LimitOffsetTranslator(limit=5, offset=3)

        request_detail = RequestDetail(
            request=Request(
                method="GET", url="https://api.example.com/items", type="ajax", queries={}, headers={}, post_data=None
            ),
            dynamic_parameters={},
            pagination_info=None,  # No pagination
            code_to_apply_parameters="def apply_parameters(request, **params): return request",
        )

        # Mock rnet client
        mock_rnet_response = AsyncMock()
        mock_rnet_response.status = 200
        mock_rnet_response.text = AsyncMock(return_value='{"items": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}')

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_rnet_response)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        results = []
        async for data in translator.generate_data(request_detail=request_detail, response_detail=response_detail):
            results.extend(data)

        # Should get items 4-8 (offset=3, limit=5)
        assert results == [4, 5, 6, 7, 8]

    @pytest.mark.asyncio
    async def test_generate_data_limit_offset_pagination(self, response_detail, mocker):
        """Test generate_data with limit/offset pagination handling multiple API requests."""
        translator = LimitOffsetTranslator(limit=15, offset=5)

        request_detail = RequestDetail(
            request=Request(
                method="GET", url="https://api.example.com/items", type="ajax", queries={}, headers={}, post_data=None
            ),
            dynamic_parameters={},
            pagination_info=PaginationInfo(
                page=None,
                limit=NumberParameter(key="limit", default_value=10),
                offset=NumberParameter(key="offset", default_value=0),
                cursor=None,
            ),
            code_to_apply_parameters="def apply_parameters(request, **params): return request",
        )

        # Mock multiple HTTP responses to simulate pagination
        responses = [
            '{"items": [' + ",".join(str(i) for i in range(5, 15)) + "]}",  # offset=5, limit=15
            '{"items": [' + ",".join(str(i) for i in range(20, 25)) + "]}",  # offset=20, limit=15
            '{"items": []}',  # End of data
        ]
        call_count = 0

        async def mock_rnet_request(*args, **kwargs):
            nonlocal call_count
            mock_rnet_response = AsyncMock()
            mock_rnet_response.status = 200
            mock_rnet_response.text = AsyncMock(return_value=responses[call_count])
            call_count += 1
            return mock_rnet_response

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=mock_rnet_request)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        results = []
        async for data in translator.generate_data(
            request_detail=request_detail, response_detail=response_detail, category="electronics"
        ):
            results.extend(data)

        assert len(results) == 15  # Should get exactly our limit
        assert results[:10] == list(range(5, 15))  # First batch
        assert results[10:] == list(range(20, 25))  # Partial second batch

    @pytest.mark.asyncio
    async def test_generate_data_page_limit_pagination(self, response_detail, mocker):
        """Test generate_data with page/limit pagination calculating correct page numbers."""
        translator = LimitOffsetTranslator(limit=8, offset=12)

        request_detail = RequestDetail(
            request=Request(
                method="GET", url="https://api.example.com/items", type="ajax", queries={}, headers={}, post_data=None
            ),
            dynamic_parameters={},
            pagination_info=PaginationInfo(
                page=NumberParameter(key="page", default_value=1),
                limit=NumberParameter(key="limit", default_value=5),
                offset=None,
                cursor=None,
            ),
            code_to_apply_parameters="def apply_parameters(request, **params): return request",
        )

        # Mock detect_start_page call
        translator.detect_start_page = AsyncMock(return_value=1)

        # Mock responses for page/limit pagination
        responses = [
            '{"items": [' + ",".join(str(i) for i in range(0, 5)) + "]}",  # Test request for page size
            '{"items": [' + ",".join(str(i) for i in range(15, 20)) + "]}",  # Page 3
            '{"items": [' + ",".join(str(i) for i in range(20, 25)) + "]}",  # Page 4
            '{"items": [' + ",".join(str(i) for i in range(25, 30)) + "]}",  # Page 5 (should pick 3 items from last)
            '{"items": []}',  # End of data
        ]
        call_count = 0

        async def mock_rnet_request(*args, **kwargs):
            nonlocal call_count
            mock_rnet_response = AsyncMock()
            mock_rnet_response.status = 200
            mock_rnet_response.text = AsyncMock(return_value=responses[call_count])
            call_count += 1
            return mock_rnet_response

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=mock_rnet_request)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        results = []
        async for data in translator.generate_data(request_detail=request_detail, response_detail=response_detail):
            results.extend(data)

        assert len(results) == 3  # Our limit
        assert translator.detect_start_page.called

    @pytest.mark.asyncio
    async def test_generate_data_page_offset_pagination(self, response_detail, mocker):
        """Test generate_data with page/offset pagination combining page and offset parameters."""
        translator = LimitOffsetTranslator(limit=6, offset=10)

        request_detail = RequestDetail(
            request=Request(
                method="GET", url="https://api.example.com/items", type="ajax", queries={}, headers={}, post_data=None
            ),
            dynamic_parameters={},
            pagination_info=PaginationInfo(
                page=NumberParameter(key="page", default_value=0),
                limit=None,
                offset=NumberParameter(key="offset", default_value=0),
                cursor=None,
            ),
            code_to_apply_parameters="def apply_parameters(request, **params): return request",
        )

        # Mock detect_start_page
        translator.detect_start_page = AsyncMock(return_value=0)

        # Mock rnet client for page/offset path
        mock_rnet_response = AsyncMock()
        mock_rnet_response.status = 200
        mock_rnet_response.text = AsyncMock(return_value='{"items": [' + ",".join(str(i) for i in range(10, 20)) + "]}")

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_rnet_response)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        results = []
        async for data in translator.generate_data(request_detail=request_detail, response_detail=response_detail):
            results.extend(data)

        assert len(results) == 6  # Limited by our slice

    @pytest.mark.asyncio
    async def test_generate_data_cursor_pagination(self, response_detail, mocker):
        """Test generate_data with cursor-based pagination using cursor tokens for navigation."""
        translator = LimitOffsetTranslator(limit=4, offset=2)

        request_detail = RequestDetail(
            request=Request(
                method="GET", url="https://api.example.com/items", type="ajax", queries={}, headers={}, post_data=None
            ),
            dynamic_parameters={},
            pagination_info=PaginationInfo(
                page=None,
                limit=None,
                offset=None,
                cursor=CursorParameter(key="cursor", default_value="start_cursor", pattern_map={}),
            ),
            apply_parameters_code="def apply_parameters(request, **params): return request",
        )

        # Mock rnet client for cursor pagination path
        mock_rnet_response = AsyncMock()
        mock_rnet_response.status = 200
        mock_rnet_response.text = AsyncMock(return_value='{"items": [' + ",".join(str(i) for i in range(10)) + "]}")

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_rnet_response)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        results = []
        async for data in translator.generate_data(request_detail=request_detail, response_detail=response_detail):
            results.extend(data)

        # Should slice from offset 2, limit 4
        assert results == [2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_generate_data_default_fallback_path(self, response_detail, mocker):
        """Test generate_data falls back to page/limit pagination when other pagination types are unavailable."""
        translator = LimitOffsetTranslator(limit=3, offset=1)

        request_detail = RequestDetail(
            request=Request(
                method="GET", url="https://api.example.com/items", type="ajax", queries={}, headers={}, post_data=None
            ),
            dynamic_parameters={},
            pagination_info=PaginationInfo(
                page=NumberParameter(key="page", default_value=1),
                limit=None,  # No limit, no offset, no cursor - should use default page/limit path
                offset=None,
                cursor=None,
            ),
            apply_parameters_code="def apply_parameters(request, **params): return request",
        )

        # Mock detect_start_page
        translator.detect_start_page = AsyncMock(return_value=1)

        # Mock rnet.Client properly
        mock_rnet_response = AsyncMock()
        mock_rnet_response.status = 200
        mock_rnet_response.text = AsyncMock(return_value='{"items": [' + ",".join(str(i) for i in range(10)) + "]}")

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_rnet_response)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        results = []
        async for data in translator.generate_data(request_detail=request_detail, response_detail=response_detail):
            results.extend(data)

        # Should slice from offset 1, limit 3
        assert results == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_generate_data_with_400_error_fallback(self, response_detail, mocker):
        """Test 400 error handling with automatic fallback to default page size when limit is rejected."""
        translator = LimitOffsetTranslator(limit=20, offset=0)

        request_detail = RequestDetail(
            request=Request(
                method="GET", url="https://api.example.com/items", type="ajax", queries={}, headers={}, post_data=None
            ),
            dynamic_parameters={},
            pagination_info=PaginationInfo(
                page=None,
                limit=NumberParameter(key="limit", default_value=10),
                offset=NumberParameter(key="offset", default_value=0),
                cursor=None,
            ),
            apply_parameters_code="def apply_parameters(request, **params): return request",
        )

        call_count = 0

        async def mock_make_request(parameters):
            nonlocal call_count
            call_count += 1

            # First call with limit=20 fails with 400
            if call_count == 1 and parameters.get("limit") == "20":
                raise RequestException(status_code=400, message="Invalid limit")

            # Retry with default limit succeeds
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value='{"items": [' + ",".join(str(i) for i in range(10)) + "]}")
            return mock_response

        # Mock rnet.Client properly with side_effect
        async def mock_client_request(*args, **kwargs):
            return await mock_make_request(parameters=kwargs.get("params", {}))

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=mock_client_request)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        results = []
        async for data in translator.generate_data(request_detail=request_detail, response_detail=response_detail):
            results.extend(data)

        # Should successfully get data after fallback
        assert results == list(range(10))
        assert call_count == 2  # Initial request + fallback

    @pytest.mark.asyncio
    async def test_generate_data_first_request_returns_no_data(self, response_detail, mocker):
        """Test early termination when API returns empty data on first request indicating no support for pagination."""
        translator = LimitOffsetTranslator(limit=10, offset=0)

        request_detail = RequestDetail(
            request=Request(
                method="GET", url="https://api.example.com/items", type="ajax", queries={}, headers={}, post_data=None
            ),
            dynamic_parameters={},
            pagination_info=PaginationInfo(
                page=None,
                limit=NumberParameter(key="limit", default_value=10),
                offset=NumberParameter(key="offset", default_value=0),
                cursor=None,
            ),
            apply_parameters_code="def apply_parameters(request, **params): return request",
        )

        # Mock response that returns empty data
        mock_rnet_response = AsyncMock()
        mock_rnet_response.status = 200
        mock_rnet_response.text = AsyncMock(return_value='{"items": []}')

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_rnet_response)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        results = []
        async for data in translator.generate_data(request_detail=request_detail, response_detail=response_detail):
            results.extend(data)

        # Should get no results and break early
        assert results == []

    @pytest.mark.asyncio
    async def test_generate_data_page_limit_with_request_exception(self, response_detail, mocker):
        """Test page/limit pagination gracefully handles RequestException during page size detection."""
        translator = LimitOffsetTranslator(limit=8, offset=0)

        request_detail = RequestDetail(
            request=Request(
                method="GET", url="https://api.example.com/items", type="ajax", queries={}, headers={}, post_data=None
            ),
            dynamic_parameters={},
            pagination_info=PaginationInfo(
                page=NumberParameter(key="page", default_value=1),
                limit=NumberParameter(key="limit", default_value=5),
                offset=None,
                cursor=None,
            ),
            apply_parameters_code="def apply_parameters(request, **params): return request",
        )

        # Mock detect_start_page call
        translator.detect_start_page = AsyncMock(return_value=1)

        # Mock _fetch_data to raise RequestException during test request
        translator._fetch_data = AsyncMock(side_effect=RequestException(status_code=400, message="Bad limit"))

        # Mock successful pagination requests
        mock_rnet_response = AsyncMock()
        mock_rnet_response.status = 200
        mock_rnet_response.text = AsyncMock(return_value='{"items": [' + ",".join(str(i) for i in range(8)) + "]}")

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(return_value=mock_rnet_response)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        results = []
        async for data in translator.generate_data(request_detail=request_detail, response_detail=response_detail):
            results.extend(data)

        # Should fallback to default page size and still work
        assert len(results) == 8

    @pytest.mark.asyncio
    async def test_generate_data_page_limit_with_400_error_fallback(self, response_detail, mocker):
        """Test page/limit pagination handles 400 errors by falling back to default entity count."""
        translator = LimitOffsetTranslator(limit=20, offset=0)

        request_detail = RequestDetail(
            request=Request(
                method="GET", url="https://api.example.com/items", type="ajax", queries={}, headers={}, post_data=None
            ),
            dynamic_parameters={},
            pagination_info=PaginationInfo(
                page=NumberParameter(key="page", default_value=1),
                limit=NumberParameter(key="limit", default_value=10),
                offset=None,
                cursor=None,
            ),
            apply_parameters_code="def apply_parameters(request, **params): return request",
        )

        # Mock detect_start_page
        translator.detect_start_page = AsyncMock(return_value=1)

        call_count = 0

        async def mock_make_request(parameters):
            nonlocal call_count
            call_count += 1

            # First call with limit=20 fails with 400
            if call_count == 1 and parameters.get("limit") == "20":
                raise RequestException(status_code=400, message="Invalid limit")

            # Retry with default limit succeeds
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value='{"items": [' + ",".join(str(i) for i in range(10)) + "]}")
            return mock_response

        # Mock rnet.Client
        async def mock_client_request(*args, **kwargs):
            return await mock_make_request(parameters=kwargs.get("params", {}))

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=mock_client_request)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        results = []
        async for data in translator.generate_data(request_detail=request_detail, response_detail=response_detail):
            results.extend(data)

        # Should get data after fallback to default limit
        assert results == list(range(10))
        assert call_count == 2 + 1  # +1 for limit detection

    @pytest.mark.asyncio
    async def test_generate_data_page_limit_duplicate_responses_page_1_continue(self, response_detail, mocker):
        """Test page/limit pagination continues when page 0 and 1 return identical responses."""
        translator = LimitOffsetTranslator(limit=5, offset=0)

        request_detail = RequestDetail(
            request=Request(
                method="GET", url="https://api.example.com/items", type="ajax", queries={}, headers={}, post_data=None
            ),
            dynamic_parameters={},
            pagination_info=PaginationInfo(
                page=NumberParameter(key="page", default_value=1),
                limit=NumberParameter(key="limit", default_value=5),
                offset=None,
                cursor=None,
            ),
            apply_parameters_code="def apply_parameters(request, **params): return request",
        )

        # Mock detect_start_page
        translator.detect_start_page = AsyncMock(return_value=1)

        call_count = 0

        async def mock_make_request(parameters):
            nonlocal call_count
            call_count += 1

            # First two calls return same response (page 0 and 1)
            if call_count <= 2:
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.text = AsyncMock(return_value='{"items": [1, 2, 3]}')
                return mock_response
            else:
                # Third call returns different data
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.text = AsyncMock(return_value='{"items": [4, 5, 6]}')
                return mock_response

        # Mock rnet.Client
        async def mock_client_request(*args, **kwargs):
            return await mock_make_request(parameters=kwargs.get("params", {}))

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=mock_client_request)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        results = []
        async for data in translator.generate_data(request_detail=request_detail, response_detail=response_detail):
            results.extend(data)

        # Should get data from both distinct responses
        assert results == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_generate_data_cursor_with_400_error_fallback(self, response_detail, mocker):
        """Test cursor pagination handles 400 errors by falling back to default limit size."""
        translator = LimitOffsetTranslator(limit=10, offset=0)

        request_detail = RequestDetail(
            request=Request(
                method="GET", url="https://api.example.com/items", type="ajax", queries={}, headers={}, post_data=None
            ),
            dynamic_parameters={},
            pagination_info=PaginationInfo(
                page=None,
                limit=NumberParameter(key="limit", default_value=5),
                offset=None,
                cursor=CursorParameter(key="cursor", default_value="start_cursor", pattern_map={}),
            ),
            apply_parameters_code="def apply_parameters(request, **params): return request",
        )

        # Mock detect_start_cursor
        translator.detect_start_cursor = AsyncMock(return_value="start_cursor")

        call_count = 0

        async def mock_make_request(parameters):
            nonlocal call_count
            call_count += 1

            # First call with limit=10 fails with 400
            if call_count == 1 and parameters.get("limit") == "10":
                raise RequestException(status_code=400, message="Invalid limit")

            # Retry with default limit succeeds
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value='{"items": [' + ",".join(str(i) for i in range(5)) + "]}")
            return mock_response

        # Mock rnet.Client
        async def mock_client_request(*args, **kwargs):
            return await mock_make_request(parameters=kwargs.get("params", {}))

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=mock_client_request)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        results = []
        async for data in translator.generate_data(request_detail=request_detail, response_detail=response_detail):
            results.extend(data)

        # Should get data after fallback to default limit
        assert results == list(range(5))

    @pytest.mark.asyncio
    async def test_generate_data_early_termination_conditions(self, response_detail, mocker):
        """Test pagination terminates when duplicate responses are detected indicating end of data."""
        translator = LimitOffsetTranslator(limit=10, offset=0)

        request_detail = RequestDetail(
            request=Request(
                method="GET", url="https://api.example.com/items", type="ajax", queries={}, headers={}, post_data=None
            ),
            dynamic_parameters={},
            pagination_info=PaginationInfo(
                page=None,
                limit=NumberParameter(key="limit", default_value=10),
                offset=NumberParameter(key="offset", default_value=0),
                cursor=None,
            ),
            apply_parameters_code="def apply_parameters(request, **params): return request",
        )

        # Test duplicate response termination
        call_count = 0

        async def mock_make_request(parameters):
            nonlocal call_count
            call_count += 1
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.text = AsyncMock(return_value='{"items": [1, 2, 3]}')
            return mock_response

        # Mock rnet.Client properly with side_effect
        async def mock_client_request(*args, **kwargs):
            # Extract parameters from the request URL or kwargs
            return await mock_make_request(parameters={})

        mock_client = AsyncMock()
        mock_client.request = AsyncMock(side_effect=mock_client_request)
        mocker.patch("strot.schema.request.detail.rnet.Client", return_value=mock_client)

        results = []
        async for data in translator.generate_data(request_detail=request_detail, response_detail=response_detail):
            results.extend(data)

        # Should terminate after detecting duplicate response
        assert results == [1, 2, 3]
        assert call_count == 2
