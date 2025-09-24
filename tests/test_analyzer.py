"""Tests for the core analyzer functionality."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import BaseModel

from strot.analyzer.analyzer import Analyzer, MutableRange, analyze
from strot.analyzer.prompts.schema import PaginationKeys, ParameterDetectionResult, Point, StepResult
from strot.llm import LLMCompletion, LLMInput
from strot.logging import get_logger
from strot.schema.request import Request, RequestDetail
from strot.schema.request.pagination_info import NumberParameter, PaginationInfo
from strot.schema.response import Response, ResponseDetail
from strot.schema.response.preprocessor import HTMLResponsePreprocessor
from strot.schema.source import Source


class TestBuildPaginationInfo:
    """Test build_pagination_info method with all conditional branches and edge cases."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance with logger for pagination info testing."""
        return Analyzer(logger=get_logger())

    @pytest.fixture
    def sample_request(self):
        """Create sample request with various pagination parameters for testing extraction."""
        return Request(
            url="https://api.example.com/products",
            method="GET",
            queries={"page": "1", "limit": "20", "offset": "0", "cursor": "abc123"},
            post_data=None,
        )

    @pytest.fixture
    def sample_response(self):
        """Create sample response containing cursor data for pagination pattern matching."""
        mock_request = Request(
            url="https://api.example.com/products", method="GET", queries={"cursor": "abc123"}, post_data=None
        )
        return Response(
            request=mock_request, value='{"data": [{"id": "abc123", "name": "Product"}], "next_cursor": "def456"}'
        )

    def test_build_pagination_info_no_keys_returns_none(self, analyzer, sample_request):
        """Test pagination info creation returns None when no pagination keys are specified."""
        keys = PaginationKeys(page_number_key=None, cursor_key=None, offset_key=None, limit_key=None)

        result = analyzer.build_pagination_info(sample_request, keys)
        assert result is None

    def test_build_pagination_info_page_number_key_only(self, analyzer, sample_request):
        """Test pagination info creation with page number and limit keys extracts correct default values."""

        keys = PaginationKeys(page_number_key="page", cursor_key=None, offset_key=None, limit_key="limit")

        result = analyzer.build_pagination_info(sample_request, keys)

        assert result is not None
        assert result.page is not None
        assert result.page.key == "page"
        assert result.page.default_value == 1  # get_value returns "1", int() converts to 1
        assert result.limit is not None
        assert result.limit.key == "limit"
        assert result.limit.default_value == 20  # get_value returns "20", int() converts to 20
        assert result.cursor is None
        assert result.offset is None

    def test_build_pagination_info_offset_key_only(self, analyzer, sample_request):
        """Test pagination info creation with offset and limit keys extracts correct offset and limit values."""

        keys = PaginationKeys(page_number_key=None, cursor_key=None, offset_key="offset", limit_key="limit")

        result = analyzer.build_pagination_info(sample_request, keys)

        assert result is not None
        assert result.offset is not None
        assert result.offset.key == "offset"
        assert result.offset.default_value == 0  # get_value returns "0", int() converts to 0
        assert result.limit is not None
        assert result.limit.key == "limit"
        assert result.limit.default_value == 20  # get_value returns "20", int() converts to 20
        assert result.page is None
        assert result.cursor is None

    def test_build_pagination_info_cursor_with_matching_response(self, analyzer, sample_request, sample_response):
        """Test pagination info creation with cursor key builds pattern map when cursor value found in response."""

        keys = PaginationKeys(page_number_key=None, cursor_key="cursor", offset_key=None, limit_key=None)

        result = analyzer.build_pagination_info(sample_request, keys, sample_response)

        assert result is not None
        assert result.cursor is not None
        assert result.cursor.key == "cursor"
        assert result.cursor.default_value == "abc123"
        # Should have pattern_map since cursor value "abc123" appears in response
        assert result.cursor.pattern_map is not None
        assert result.page is None
        assert result.offset is None
        assert result.limit is None

    def test_build_pagination_info_cursor_no_matching_response(self, analyzer, sample_request):
        """Test pagination info creation returns None when cursor key exists but no matching patterns found in response."""

        keys = PaginationKeys(page_number_key=None, cursor_key="cursor", offset_key=None, limit_key=None)

        # Create response that doesn't contain the cursor value
        non_matching_request = Request(
            url="https://api.example.com/products", method="GET", queries={"other_param": "value"}, post_data=None
        )
        non_matching_response = Response(
            request=non_matching_request, value='{"data": [{"id": "xyz789", "name": "Other Product"}]}'
        )

        result = analyzer.build_pagination_info(sample_request, keys, non_matching_response)

        # Should return None because cursor exists but no matching patterns found
        assert result is None


class TestAnalyzeFunction:
    """Test the main analyze function entry point with browser handling and error scenarios."""

    @pytest.mark.asyncio
    async def test_analyze_success_flow(self, mocker, mock_browser, mock_tab, sample_schema):
        """Test successful analysis workflow from URL to source extraction with proper cleanup."""
        # Mock analyzer instance and return value
        mock_analyzer = mocker.AsyncMock()  # Use AsyncMock since analyzer() is awaited
        mock_source = mocker.Mock()
        mock_source.request_detail.request.url = "https://api.example.com/data"
        mock_analyzer.return_value = mock_source

        # Mock the Tab and Analyzer classes
        mocker.patch("strot.analyzer.analyzer.Tab", return_value=mock_tab)
        mocker.patch("strot.analyzer.analyzer.Analyzer", return_value=mock_analyzer)

        result = await analyze(
            url="https://example.com",
            query="find products",
            output_schema=sample_schema,  # Use proper Pydantic model
            browser=mock_browser,
        )

        # Verify the flow
        mock_browser.new_context.assert_called_once_with(bypass_csp=True)
        mock_tab.goto.assert_called_once_with("https://example.com")
        mock_analyzer.assert_called_once_with(mock_tab, "find products", sample_schema, 30)  # max_steps defaults to 30
        mock_tab.reset.assert_called_once()
        assert result == mock_source

    @pytest.mark.asyncio
    async def test_analyze_no_source_found(self, mocker, mock_browser, mock_tab, sample_schema):
        """Test analyze function returns None when no relevant data source can be discovered."""
        # Mock analyzer to return None (no source found)
        mock_analyzer = mocker.AsyncMock()
        mock_analyzer.return_value = None

        # Mock the Tab and Analyzer classes
        mocker.patch("strot.analyzer.analyzer.Tab", return_value=mock_tab)
        mocker.patch("strot.analyzer.analyzer.Analyzer", return_value=mock_analyzer)

        # Import and test

        result = await analyze(
            url="https://example.com", query="find nonexistent data", output_schema=sample_schema, browser=mock_browser
        )

        # Should return None when no source found
        assert result is None
        # Cleanup should still happen
        mock_tab.reset.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_exception_handling(self, mocker, mock_browser, mock_tab, sample_schema):
        """Test analyze function handles analyzer exceptions gracefully and still performs cleanup."""
        # Mock analyzer to raise exception
        mock_analyzer = mocker.AsyncMock()
        mock_analyzer.side_effect = Exception("Analysis failed")

        # Mock the Tab and Analyzer classes
        mocker.patch("strot.analyzer.analyzer.Tab", return_value=mock_tab)
        mocker.patch("strot.analyzer.analyzer.Analyzer", return_value=mock_analyzer)

        result = await analyze(
            url="https://example.com", query="find products", output_schema=sample_schema, browser=mock_browser
        )

        # Should return None on exception
        assert result is None
        # Cleanup should still happen even on exception
        mock_tab.reset.assert_called_once()


class TestRequestLLMCompletion:
    """Test request_llm_completion method with all scenarios and edge cases."""

    @pytest.fixture
    def analyzer(self, mocker):
        """Create analyzer instance with mocked dependencies."""

        # Mock LLM client
        mock_llm_client = mocker.Mock()
        mock_llm_client.provider = "anthropic"
        mock_llm_client.model = "claude-3-sonnet"
        mock_llm_client.calculate_cost.return_value = 0.05

        analyzer = Analyzer(logger=get_logger())
        analyzer._llm_client = mock_llm_client
        return analyzer

    @pytest.fixture
    def sample_llm_input(self):
        """Create sample LLM input for testing."""
        return LLMInput(prompt="Test prompt", image=None)

    @pytest.mark.asyncio
    async def test_request_llm_completion_success_sync_validator(self, analyzer):
        """Test successful LLM completion with synchronous validator."""

        # Mock successful completion
        mock_completion = LLMCompletion(
            value='{"result": "success"}',
            input_tokens=100,
            output_tokens=50,
            provider="anthropic",
            model="claude-3-sonnet",
        )
        analyzer._llm_client.get_completion = AsyncMock(return_value=mock_completion)

        # Synchronous validator that parses JSON
        def sync_validator(value: str):
            return json.loads(value)

        input_data = LLMInput(prompt="Test prompt", image=None)

        result = await analyzer.request_llm_completion(
            event="test-event", input=input_data, json=True, validator=sync_validator
        )

        # Verify result
        assert result == {"result": "success"}

        # Verify LLM client was called correctly
        analyzer._llm_client.get_completion.assert_called_once_with(input_data, json=True)
        analyzer._llm_client.calculate_cost.assert_called_once_with(100, 50)

    @pytest.mark.asyncio
    async def test_request_llm_completion_success_async_validator(self, analyzer):
        """Test successful LLM completion with asynchronous validator."""

        # Mock successful completion
        mock_completion = LLMCompletion(
            value='{"data": [1, 2, 3]}',
            input_tokens=120,
            output_tokens=30,
            provider="anthropic",
            model="claude-3-sonnet",
        )
        analyzer._llm_client.get_completion = AsyncMock(return_value=mock_completion)

        # Asynchronous validator
        async def async_validator(value: str):
            await asyncio.sleep(0)  # Simulate async work
            return json.loads(value)

        input_data = LLMInput(prompt="Async test", image=None)

        result = await analyzer.request_llm_completion(
            event="async-test", input=input_data, json=True, validator=async_validator
        )

        # Verify result
        assert result == {"data": [1, 2, 3]}

        # Verify LLM client interactions
        analyzer._llm_client.get_completion.assert_called_once_with(input_data, json=True)
        analyzer._llm_client.calculate_cost.assert_called_once_with(120, 30)

    @pytest.mark.asyncio
    async def test_request_llm_completion_llm_client_exception(self, analyzer):
        """Test LLM completion when LLM client raises exception."""

        # Mock LLM client to raise exception
        analyzer._llm_client.get_completion = AsyncMock(side_effect=Exception("API Error"))

        def simple_validator(value: str):
            return value

        input_data = LLMInput(prompt="Test prompt", image=None)

        # Should raise the exception
        with pytest.raises(Exception, match="API Error"):
            await analyzer.request_llm_completion(
                event="error-test", input=input_data, json=False, validator=simple_validator
            )

        # Verify LLM client was called
        analyzer._llm_client.get_completion.assert_called_once_with(input_data, json=False)

    @pytest.mark.asyncio
    async def test_request_llm_completion_validator_exception(self, analyzer):
        """Test LLM completion when validator raises exception."""

        # Mock successful completion
        mock_completion = LLMCompletion(
            value="invalid json {", input_tokens=50, output_tokens=20, provider="anthropic", model="claude-3-sonnet"
        )
        analyzer._llm_client.get_completion = AsyncMock(return_value=mock_completion)

        # Validator that will fail on invalid JSON
        def failing_validator(value: str):
            return json.loads(value)  # Will raise JSONDecodeError

        input_data = LLMInput(prompt="Test prompt", image=None)

        # Should raise the validation exception
        with pytest.raises(Exception):  # noqa: B017
            await analyzer.request_llm_completion(
                event="validation-error-test", input=input_data, json=True, validator=failing_validator
            )

        # Verify LLM client was called successfully
        analyzer._llm_client.get_completion.assert_called_once_with(input_data, json=True)

    @pytest.mark.asyncio
    async def test_request_llm_completion_async_validator_exception(self, analyzer):
        """Test LLM completion when async validator raises exception."""

        # Mock successful completion
        mock_completion = LLMCompletion(
            value="some value", input_tokens=80, output_tokens=40, provider="anthropic", model="claude-3-sonnet"
        )
        analyzer._llm_client.get_completion = AsyncMock(return_value=mock_completion)

        # Async validator that raises exception
        async def failing_async_validator(value: str):
            await asyncio.sleep(0)
            raise ValueError("Validation failed")

        input_data = LLMInput(prompt="Test prompt", image=None)

        # Should raise the validation exception
        with pytest.raises(ValueError, match="Validation failed"):
            await analyzer.request_llm_completion(
                event="async-validation-error", input=input_data, json=False, validator=failing_async_validator
            )

        # Verify LLM client was called
        analyzer._llm_client.get_completion.assert_called_once_with(input_data, json=False)


class TestRunStep:
    """Test run_step method with all conditional branches and edge cases."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance for testing."""
        return Analyzer(logger=get_logger())

    @pytest.mark.asyncio
    async def test_run_step_single_text_section_click_element(self, analyzer, mock_tab):
        """Test run_step with single text section - should click element directly."""

        # Mock step result with single text section
        step_result = StepResult(
            close_overlay_popup_coords=None,
            text_sections=["Single Product"],  # Single section triggers click_element
            load_more_content_coords=None,
            skip_to_content_coords=None,
        )

        # Mock analyzer's LLM completion method
        analyzer.request_llm_completion = AsyncMock(return_value=step_result)

        # Mock find_common_parent to return an element
        mock_parent_element = ".product-item"
        mock_tab.plugin.find_common_parent.return_value = mock_parent_element

        # Screenshot is already mocked with valid PNG data in conftest.py

        # Call run_step
        result = await analyzer.run_step(mock_tab, "find product")

        # Verify behavior - this should cover lines 211-212 (len(sections) == 1 path)
        mock_tab.plugin.find_common_parent.assert_called_once_with(["Single Product"])
        mock_tab.plugin.click_element.assert_called_once_with(mock_parent_element)

        # Should return None after clicking single element
        assert result is None

    @pytest.mark.asyncio
    async def test_run_step_skip_to_content_failed_click_with_scrolling(self, analyzer, mock_tab):
        """Test run_step when skip_to_content click fails, triggering fallback scrolling."""

        # Mock step result with skip_to_content_coords only
        step_result = StepResult(
            close_overlay_popup_coords=None,
            text_sections=None,
            load_more_content_coords=None,
            skip_to_content_coords=Point(x=150, y=250),
        )

        # Mock analyzer's LLM completion method
        analyzer.request_llm_completion = AsyncMock(return_value=step_result)

        # Mock FAILED click (return False) - this should cover lines 256-261
        mock_tab.plugin.click_at_point.return_value = False

        # Screenshot is already mocked with valid PNG data in conftest.py

        # Set _is_requirement_listed_data to False to trigger fallback scrolling
        analyzer._is_requirement_listed_data = False

        # Call run_step
        result = await analyzer.run_step(mock_tab, "find content")

        # Verify click was attempted and failed - covers lines 256-261
        mock_tab.plugin.click_at_point.assert_called_once_with(Point(x=150.0, y=250.0))

        # Should trigger fallback scrolling when click fails - covers lines 274-276
        mock_tab.plugin.scroll_to_next_view.assert_called_once()

        # Should return None
        assert result is None

    @pytest.mark.asyncio
    async def test_run_step_load_more_failed_click_with_scrolling(self, analyzer, mock_tab):
        """Test run_step when load_more click fails, triggering fallback scrolling."""

        # Mock step result with load_more_content_coords only
        step_result = StepResult(
            close_overlay_popup_coords=None,
            text_sections=None,
            load_more_content_coords=Point(x=200, y=300),
            skip_to_content_coords=None,
        )

        # Mock analyzer's LLM completion method
        analyzer.request_llm_completion = AsyncMock(return_value=step_result)

        # Mock FAILED click (return False) - this should cover line 253
        mock_tab.plugin.click_at_point.return_value = False

        # Screenshot is already mocked with valid PNG data in conftest.py

        # Set _is_requirement_listed_data to False to trigger fallback scrolling
        analyzer._is_requirement_listed_data = False

        # Call run_step
        result = await analyzer.run_step(mock_tab, "find content")

        # Verify click was attempted and failed - covers line 253
        mock_tab.plugin.click_at_point.assert_called_once_with(Point(x=200.0, y=300.0))

        # Should trigger fallback scrolling when click fails
        mock_tab.plugin.scroll_to_next_view.assert_called_once()

        # Should return None
        assert result is None

    @pytest.mark.asyncio
    async def test_run_step_exception_handling(self, analyzer, mock_tab):
        """Test run_step exception handling - covers lines 186-187."""

        # Mock request_llm_completion to raise exception
        analyzer.request_llm_completion = AsyncMock(side_effect=Exception("LLM Error"))

        # Call run_step and expect None return due to exception
        result = await analyzer.run_step(mock_tab, "test instruction")

        # Should return None when exception occurs
        assert result is None

    @pytest.mark.asyncio
    async def test_run_step_close_overlay_popup_success(self, analyzer, mock_tab):
        """Test run_step close overlay popup click success - covers lines 196-205."""

        # Mock step result with close overlay coords and no text sections
        step_result = StepResult(
            close_overlay_popup_coords=Point(x=100, y=200),
            text_sections=[],  # No text sections to trigger early return
            load_more_content_coords=None,
            skip_to_content_coords=None,
        )

        analyzer.request_llm_completion = AsyncMock(return_value=step_result)

        # Mock successful click
        mock_tab.plugin.click_at_point = AsyncMock(return_value=True)

        # Call run_step - should return None due to early exit after successful click
        result = await analyzer.run_step(mock_tab, "close popup")

        # Should return None (early exit)
        assert result is None
        mock_tab.plugin.click_at_point.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_step_text_matching_and_similar_elements(self, analyzer, mock_tab):
        """Test run_step text matching and similar element logic - covers lines 214-240."""

        # Mock step result with multiple text sections
        step_result = StepResult(
            close_overlay_popup_coords=None,
            text_sections=["Product A", "Product B"],
            load_more_content_coords=None,
            skip_to_content_coords=None,
        )

        analyzer.request_llm_completion = AsyncMock(return_value=step_result)

        # Mock find_common_parent
        mock_parent = ".product-container"
        mock_tab.plugin.find_common_parent.return_value = mock_parent

        # Create matching response
        mock_request = Request(method="GET", url="https://api.example.com/products", type="ssr")
        matching_response = Response(request=mock_request, value="Product A Product B similar content")
        mock_tab.responses = [matching_response]

        # Mock similar element found
        mock_tab.plugin.get_last_similar_children_or_sibling = AsyncMock(return_value=".last-product")

        # Call run_step
        result = await analyzer.run_step(mock_tab, "find products")

        # Should return the matching response with preprocessor set
        assert result == matching_response
        assert isinstance(result.preprocessor, HTMLResponsePreprocessor)
        assert result.preprocessor.element_selector == mock_parent

        # Should scroll to similar element and set listed data flag
        mock_tab.plugin.scroll_to_element.assert_called_once_with(".last-product")
        assert analyzer._is_requirement_listed_data is True

    @pytest.mark.asyncio
    async def test_run_step_load_more_click_success(self, analyzer, mock_tab):
        """Test run_step load more content click success - covers line 252."""

        # Mock step result with load_more_content_coords
        step_result = StepResult(
            close_overlay_popup_coords=None,
            text_sections=[],
            load_more_content_coords=Point(x=300, y=400),
            skip_to_content_coords=None,
        )

        analyzer.request_llm_completion = AsyncMock(return_value=step_result)

        # Mock successful click - should return None (early exit)
        mock_tab.plugin.click_at_point = AsyncMock(return_value=True)

        # Call run_step
        result = await analyzer.run_step(mock_tab, "load more")

        # Should return None due to successful click early exit
        assert result is None
        mock_tab.plugin.click_at_point.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_step_skip_to_content_success(self, analyzer, mock_tab):
        """Test run_step skip to content click success - covers line 260."""

        # Mock step result with skip_to_content_coords
        step_result = StepResult(
            close_overlay_popup_coords=None,
            text_sections=[],
            load_more_content_coords=None,
            skip_to_content_coords=Point(x=500, y=600),
        )

        analyzer.request_llm_completion = AsyncMock(return_value=step_result)

        # Mock successful click - should return None (early exit)
        mock_tab.plugin.click_at_point = AsyncMock(return_value=True)

        # Call run_step
        result = await analyzer.run_step(mock_tab, "skip to content")

        # Should return None due to successful click early exit
        assert result is None
        mock_tab.plugin.click_at_point.assert_called_once()


class TestDiscoverRelevantResponse:
    """Test discover_relevant_response method with all scenarios and edge cases."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance for testing."""
        return Analyzer(logger=get_logger())

    @pytest.fixture
    def sample_response(self):
        """Create sample response for testing."""

        request = Request(
            url="https://api.example.com/products", method="GET", type="ajax", queries={"page": "1"}, post_data=None
        )

        return Response(request=request, value='{"products": [{"id": 1, "name": "Product 1"}]}')

    @pytest.fixture
    def sample_response_with_preprocessor(self):
        """Create sample response with preprocessor for testing."""

        request = Request(
            url="https://api.example.com/products", method="GET", type="ssr", queries={"page": "1"}, post_data=None
        )

        response = Response(request=request, value="<html><body>Product data</body></html>")
        response.preprocessor = HTMLResponsePreprocessor(element_selector=".products")

        return response

    @pytest.mark.asyncio
    async def test_discover_relevant_response_success_first_step(self, analyzer, mock_tab, sample_response, mocker):
        """Test discover_relevant_response succeeds on first step."""
        # Mock asyncio.sleep to avoid delays
        mock_sleep = mocker.patch("asyncio.sleep")

        # Mock run_step to return response on first call
        analyzer.run_step = AsyncMock(return_value=sample_response)

        # Call discover_relevant_response
        result = await analyzer.discover_relevant_response(mock_tab, "find products", max_steps=3)

        # Verify success
        assert result == sample_response
        analyzer.run_step.assert_called_once_with(mock_tab, "find products")

        # Should not sleep since success on first step
        mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_discover_relevant_response_success_with_preprocessor(
        self, analyzer, mock_tab, sample_response_with_preprocessor, mocker
    ):
        """Test discover_relevant_response with response that has preprocessor - covers line 298."""

        # Mock run_step to return response with preprocessor
        analyzer.run_step = AsyncMock(return_value=sample_response_with_preprocessor)

        # Call discover_relevant_response
        result = await analyzer.discover_relevant_response(mock_tab, "find products", max_steps=1)

        # Verify success and preprocessor logging path (line 298)
        assert result == sample_response_with_preprocessor
        assert result.preprocessor is not None
        analyzer.run_step.assert_called_once_with(mock_tab, "find products")

    @pytest.mark.asyncio
    async def test_discover_relevant_response_success_after_failures(self, analyzer, mock_tab, sample_response, mocker):
        """Test discover_relevant_response succeeds after initial failures."""
        # Mock asyncio.sleep to avoid delays
        mock_sleep = mocker.patch("asyncio.sleep")

        # Mock run_step to fail twice, then succeed
        analyzer.run_step = AsyncMock(side_effect=[None, None, sample_response])

        # Call discover_relevant_response
        result = await analyzer.discover_relevant_response(mock_tab, "find products", max_steps=3)

        # Verify success after retries
        assert result == sample_response
        assert analyzer.run_step.call_count == 3

        # Should sleep twice (after first two failures)
        assert mock_sleep.call_count == 2
        mock_sleep.assert_has_calls([mocker.call(2.5), mocker.call(2.5)])

    @pytest.mark.asyncio
    async def test_discover_relevant_response_all_steps_fail(self, analyzer, mock_tab, mocker):
        """Test discover_relevant_response when all steps fail."""
        # Mock asyncio.sleep
        mock_sleep = mocker.patch("asyncio.sleep")

        # Mock run_step to always return None
        analyzer.run_step = AsyncMock(return_value=None)

        # Call discover_relevant_response
        result = await analyzer.discover_relevant_response(mock_tab, "find products", max_steps=3)

        # Should return None after exhausting all steps
        assert result is None
        assert analyzer.run_step.call_count == 3

        # Should sleep after each failure except the last
        assert mock_sleep.call_count == 3
        mock_sleep.assert_has_calls([mocker.call(2.5), mocker.call(2.5), mocker.call(2.5)])

    @pytest.mark.asyncio
    async def test_discover_relevant_response_exception_handling(self, analyzer, mock_tab, sample_response, mocker):
        """Test discover_relevant_response handles exceptions from run_step."""
        # Mock asyncio.sleep
        mock_sleep = mocker.patch("asyncio.sleep")

        # Mock run_step to raise exception, then succeed
        analyzer.run_step = AsyncMock(side_effect=[Exception("Run step failed"), sample_response])

        # Call discover_relevant_response
        result = await analyzer.discover_relevant_response(mock_tab, "find products", max_steps=2)

        # Should succeed after handling exception
        assert result == sample_response
        assert analyzer.run_step.call_count == 2

        # Should sleep once (after exception)
        mock_sleep.assert_called_once_with(2.5)

    @pytest.mark.asyncio
    async def test_discover_relevant_response_with_mutable_range(self, analyzer, mock_tab, sample_response, mocker):
        """Test discover_relevant_response with MutableRange instead of int."""

        # Mock asyncio.sleep
        mock_sleep = mocker.patch("asyncio.sleep")

        # Mock run_step to succeed on second call
        analyzer.run_step = AsyncMock(side_effect=[None, sample_response])

        # Create MutableRange
        max_steps = MutableRange(0, 2)

        # Call discover_relevant_response
        result = await analyzer.discover_relevant_response(mock_tab, "find products", max_steps=max_steps)

        # Should succeed
        assert result == sample_response
        assert analyzer.run_step.call_count == 2

        # Should sleep once (after first failure)
        mock_sleep.assert_called_once_with(2.5)


class TestBuildRequestDetail:
    """Test build_request_detail method with proper mocking strategy."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance for testing."""
        return Analyzer(logger=get_logger())

    @pytest.fixture
    def sample_request(self):
        """Create sample request for testing."""
        return Request(
            method="GET",
            url="https://api.example.com/data",
            type="ajax",
            queries={"page": "1", "limit": "10", "category": "electronics"},
            headers={"Content-Type": "application/json"},
            post_data=None,
        )

    @pytest.fixture
    def sample_response(self, sample_request):
        """Create sample response for testing."""
        return Response(
            request=sample_request, value='{"products": [{"id": 1, "name": "Product 1"}], "has_more": true}'
        )

    @pytest.mark.asyncio
    async def test_build_request_detail_success_with_all_parameters(
        self, analyzer, mock_code_executor, sample_request, sample_response
    ):
        """Test successful parameter detection with pagination and dynamic parameters."""

        # Create real ParameterDetectionResult instance (not mock)
        pagination_keys = PaginationKeys(page_number_key="page", limit_key="limit", offset_key=None, cursor_key=None)

        detection_result = ParameterDetectionResult(
            apply_parameters_code="def apply_parameters(request, page=1, limit=10):\n    request.queries['page'] = str(page)\n    request.queries['limit'] = str(limit)\n    return request",
            pagination_keys=pagination_keys,
            dynamic_parameter_keys=["category"],
        )

        # Create proper LLMCompletion instance instead of mocking

        llm_completion = LLMCompletion(
            value=detection_result.model_dump_json(),
            input_tokens=100,
            output_tokens=50,
            provider="anthropic",
            model="nil",
        )

        analyzer._llm_client.get_completion = AsyncMock(return_value=llm_completion)
        analyzer._code_executor = mock_code_executor
        mock_code_executor.execute = AsyncMock()
        mock_code_executor.is_definition_available = AsyncMock(return_value=True)

        # Call with responses to test that parameter
        result = await analyzer.build_request_detail(sample_request, sample_response)

        # Verify result structure
        assert isinstance(result, RequestDetail)
        assert result.request == sample_request
        assert result.pagination_info is not None  # build_pagination_info should create real object
        assert result.dynamic_parameters == {"category": "electronics"}  # get_value extracts from queries
        assert "def apply_parameters" in result.code_to_apply_parameters

        # Verify LLM was called correctly
        analyzer._llm_client.get_completion.assert_called_once()
        call_args = analyzer._llm_client.get_completion.call_args
        assert call_args[1]["json"] is True

        # Verify validator executed the code (this tests the real validator logic)
        mock_code_executor.execute.assert_called_once()
        mock_code_executor.is_definition_available.assert_called_once_with("apply_parameters")

    @pytest.mark.asyncio
    async def test_build_request_detail_validator_function_execution(
        self, analyzer, mock_code_executor, sample_request
    ):
        """Test the internal validator function logic - covers lines 382-391."""

        # Create LLMCompletion with JSON that will exercise the validator
        llm_completion = LLMCompletion(
            value='{"apply_parameters_code": "def apply_parameters():\\n    pass", "pagination_keys": {}, "dynamic_parameter_keys": []}',
            input_tokens=100,
            output_tokens=50,
            provider="anthropic",
            model="claude",
        )

        analyzer._llm_client.get_completion = AsyncMock(return_value=llm_completion)
        analyzer._code_executor = mock_code_executor
        mock_code_executor.execute = AsyncMock()
        mock_code_executor.is_definition_available = AsyncMock(return_value=True)

        result = await analyzer.build_request_detail(sample_request)

        # Should succeed
        assert isinstance(result, RequestDetail)
        assert result.code_to_apply_parameters == "def apply_parameters():\n    pass"

        # Verify validator executed the code
        mock_code_executor.execute.assert_called_once()
        mock_code_executor.is_definition_available.assert_called_once_with("apply_parameters")

    @pytest.mark.asyncio
    async def test_build_request_detail_validator_missing_apply_parameters_function(
        self, analyzer, mock_code_executor, sample_request
    ):
        """Test validator fails when apply_parameters function is missing - covers line 388-391."""

        # Create LLMCompletion with code that doesn't have apply_parameters function
        llm_completion = LLMCompletion(
            value='{"apply_parameters_code": "def wrong_function():\\n    pass", "pagination_keys": {}, "dynamic_parameter_keys": []}',
            input_tokens=100,
            output_tokens=50,
            provider="anthropic",
            model="claude",
        )

        analyzer._llm_client.get_completion = AsyncMock(return_value=llm_completion)
        analyzer._code_executor = mock_code_executor
        mock_code_executor.execute = AsyncMock()
        mock_code_executor.is_definition_available = AsyncMock(return_value=False)

        result = await analyzer.build_request_detail(sample_request)

        # Should return basic RequestDetail when validation fails
        assert isinstance(result, RequestDetail)
        assert result.request == sample_request
        assert result.pagination_info is None
        assert result.dynamic_parameters == {}  # defaults to empty dict, not None
        assert result.code_to_apply_parameters is None

        # Should have attempted 3 times due to the retry loop
        assert analyzer._llm_client.get_completion.call_count == 3

    @pytest.mark.asyncio
    async def test_build_request_detail_all_llm_attempts_fail(self, analyzer, sample_request):
        """Test when all 3 LLM attempts fail - covers lines 412-413, 416-422."""
        # Mock LLM completion to always raise exceptions
        analyzer._llm_client.get_completion = AsyncMock(side_effect=Exception("LLM error"))

        result = await analyzer.build_request_detail(sample_request)

        # Should return basic RequestDetail (line 422)
        assert isinstance(result, RequestDetail)
        assert result.request == sample_request
        assert result.pagination_info is None
        assert result.dynamic_parameters == {}  # defaults to empty dict, not None
        assert result.code_to_apply_parameters is None

        # Verify 3 attempts were made (loop with continue on line 413)
        assert analyzer._llm_client.get_completion.call_count == 3

    @pytest.mark.asyncio
    async def test_build_request_detail_parse_python_code_error_suppressed(
        self, analyzer, mock_code_executor, sample_request
    ):
        """Test that ValueError from parse_python_code is suppressed - covers line 384-385."""

        # Mock code executor
        analyzer._code_executor = mock_code_executor
        mock_code_executor.execute = AsyncMock()
        mock_code_executor.is_definition_available = AsyncMock(return_value=True)

        # Mock parse_python_code to raise ValueError (which should be suppressed)
        with patch("strot.analyzer.analyzer.parse_python_code", side_effect=ValueError("Parse error")):
            llm_completion = LLMCompletion(
                value='{"apply_parameters_code": "invalid python code", "pagination_keys": {}, "dynamic_parameter_keys": []}',
                input_tokens=100,
                output_tokens=50,
                provider="anthropic",
                model="claude",
            )

            analyzer._llm_client.get_completion = AsyncMock(return_value=llm_completion)

            result = await analyzer.build_request_detail(sample_request)

        # Should still succeed - ValueError was suppressed by contextlib.suppress
        assert isinstance(result, RequestDetail)
        # Code should remain unparsed due to suppressed error
        assert result.code_to_apply_parameters == "invalid python code"

    @pytest.mark.asyncio
    async def test_build_request_detail_with_dynamic_parameters_extraction(
        self, analyzer, mock_code_executor, sample_request
    ):
        """Test dynamic parameter extraction using get_value utility."""

        # Create result with dynamic parameters that exist in the request
        pagination_keys = PaginationKeys()
        detection_result = ParameterDetectionResult(
            apply_parameters_code="def apply_parameters():\n    pass",
            pagination_keys=pagination_keys,
            dynamic_parameter_keys=["category", "page", "nonexistent"],  # Mix of existing and non-existing
        )

        llm_completion = LLMCompletion(
            value=detection_result.model_dump_json(),
            input_tokens=150,
            output_tokens=75,
            provider="anthropic",
            model="claude",
        )

        analyzer._llm_client.get_completion = AsyncMock(return_value=llm_completion)
        analyzer._code_executor = mock_code_executor
        mock_code_executor.execute = AsyncMock()
        mock_code_executor.is_definition_available = AsyncMock(return_value=True)

        result = await analyzer.build_request_detail(sample_request)

        # Verify dynamic parameters extraction - get_value should extract real values
        assert result.dynamic_parameters == {
            "category": "electronics",  # Should extract from queries
            "page": "1",  # Should extract from queries
            "nonexistent": None,  # Should return None for missing keys
        }

    @pytest.mark.asyncio
    async def test_build_request_detail_pagination_info_creation(
        self, analyzer, mock_code_executor, sample_request, sample_response
    ):
        """Test that build_pagination_info is called with correct parameters."""

        # Create result with pagination keys
        pagination_keys = PaginationKeys(page_number_key="page", limit_key="limit")
        detection_result = ParameterDetectionResult(
            apply_parameters_code="def apply_parameters():\n    pass",
            pagination_keys=pagination_keys,
            dynamic_parameter_keys=[],
        )

        llm_completion = LLMCompletion(
            value=detection_result.model_dump_json(),
            input_tokens=150,
            output_tokens=75,
            provider="anthropic",
            model="claude",
        )

        analyzer._llm_client.get_completion = AsyncMock(return_value=llm_completion)
        analyzer._code_executor = mock_code_executor
        mock_code_executor.execute = AsyncMock()
        mock_code_executor.is_definition_available = AsyncMock(return_value=True)

        # Use real build_pagination_info, but spy on it
        original_build_pagination_info = analyzer.build_pagination_info
        analyzer.build_pagination_info = Mock(side_effect=original_build_pagination_info)

        # Call with responses to test pagination info creation
        result = await analyzer.build_request_detail(sample_request, sample_response)

        # Verify build_pagination_info was called with correct arguments
        analyzer.build_pagination_info.assert_called_once_with(sample_request, pagination_keys, sample_response)

        # Should have real pagination info
        assert result.pagination_info is not None


class TestBuildResponseDetail:
    """Test build_response_detail method with proper mocking strategy."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance for testing."""
        return Analyzer(logger=get_logger())

    @pytest.fixture
    def sample_response(self):
        """Create sample response for testing."""

        request = Request(
            method="GET",
            url="https://api.example.com/products",
            type="ajax",
            queries={"page": "1"},
            headers={},
            post_data=None,
        )

        return Response(
            request=request,
            value='[{"id": 1, "name": "Product 1", "price": 10.99}, {"id": 2, "name": "Product 2", "price": 15.99}]',
        )

    @pytest.fixture
    def output_schema(self):
        """Create sample output schema for testing."""

        class ProductSchema(BaseModel):
            id: int
            name: str
            price: float

        return ProductSchema

    @pytest.mark.asyncio
    async def test_build_response_detail_success_with_extraction_code(
        self, analyzer, mock_code_executor, sample_response, output_schema
    ):
        """Test successful response detail building with data extraction."""

        # Mock LLM to return extraction code in markdown format
        extraction_code = """```python
def extract_data(response_text):
    import json
    data = json.loads(response_text)
    return [{"id": item["id"], "name": item["name"], "price": item["price"]} for item in data]
```"""

        llm_completion = LLMCompletion(
            value=extraction_code, input_tokens=200, output_tokens=100, provider="anthropic", model="claude"
        )

        analyzer._llm_client.get_completion = AsyncMock(return_value=llm_completion)
        analyzer._code_executor = mock_code_executor
        mock_code_executor.execute = AsyncMock()
        mock_code_executor.is_definition_available = AsyncMock(return_value=True)

        # Mock the extract_data execution to return parsed data
        mock_extracted_data = [
            {"id": 1, "name": "Product 1", "price": 10.99},
            {"id": 2, "name": "Product 2", "price": 15.99},
        ]
        mock_code_executor.execute.side_effect = [
            None,
            mock_extracted_data,
        ]  # First call for code, second for extraction

        result = await analyzer.build_response_detail(sample_response, output_schema)

        # Verify result structure
        assert isinstance(result, ResponseDetail)
        assert result.code_to_extract_data is not None
        assert "def extract_data" in result.code_to_extract_data
        assert result.default_entity_count == 2  # Two products extracted
        assert result.preprocessor == sample_response.preprocessor
        # The code should be the parsed Python code, not the markdown
        expected_code = 'def extract_data(response_text):\n    import json\n    data = json.loads(response_text)\n    return [{"id": item["id"], "name": item["name"], "price": item["price"]} for item in data]'
        assert result.code_to_extract_data == expected_code

        # Verify LLM was called correctly
        analyzer._llm_client.get_completion.assert_called_once()
        call_args = analyzer._llm_client.get_completion.call_args
        assert call_args[1]["json"] is False

        # Verify validator executed the code
        assert mock_code_executor.execute.call_count == 2  # Code execution + data extraction
        mock_code_executor.is_definition_available.assert_called_once_with("extract_data")

    @pytest.mark.asyncio
    async def test_build_response_detail_with_preprocessor(
        self, analyzer, mock_code_executor, sample_response, output_schema
    ):
        """Test build_response_detail with response preprocessor - covers line 448."""

        # Add real preprocessor to response

        # Create a real HTMLResponsePreprocessor instance
        real_preprocessor = HTMLResponsePreprocessor(element_selector="body")
        sample_response.preprocessor = real_preprocessor

        extraction_code = """```python
def extract_data(response_text):
    return [{"processed": "data"}]
```"""

        llm_completion = LLMCompletion(
            value=extraction_code, input_tokens=150, output_tokens=75, provider="anthropic", model="claude"
        )

        analyzer._llm_client.get_completion = AsyncMock(return_value=llm_completion)
        analyzer._code_executor = mock_code_executor
        mock_code_executor.execute = AsyncMock()
        mock_code_executor.is_definition_available = AsyncMock(return_value=True)
        mock_code_executor.execute.side_effect = [None, [{"processed": "data"}]]

        result = await analyzer.build_response_detail(sample_response, output_schema)

        # Verify preprocessor is preserved in result
        assert result.preprocessor == real_preprocessor

        # Verify the extraction was successful
        assert result.code_to_extract_data is not None
        expected_code = 'def extract_data(response_text):\n    return [{"processed": "data"}]'
        assert result.code_to_extract_data == expected_code
        assert result.default_entity_count == 1  # Length of returned data

    @pytest.mark.asyncio
    async def test_build_response_detail_validator_missing_extract_data_function(
        self, analyzer, mock_code_executor, sample_response, output_schema
    ):
        """Test validator fails when extract_data function is missing - covers lines 464-465."""

        # Mock code executor to indicate function is not available
        analyzer._code_executor = mock_code_executor
        mock_code_executor.execute = AsyncMock()
        mock_code_executor.is_definition_available = AsyncMock(return_value=False)

        extraction_code = """```python
def wrong_function():
    return []
```"""

        llm_completion = LLMCompletion(
            value=extraction_code, input_tokens=100, output_tokens=50, provider="anthropic", model="claude"
        )

        analyzer._llm_client.get_completion = AsyncMock(return_value=llm_completion)

        result = await analyzer.build_response_detail(sample_response, output_schema)

        # Should return basic ResponseDetail when validation fails
        assert isinstance(result, ResponseDetail)
        assert result.code_to_extract_data is None
        assert result.default_entity_count == 0
        assert result.preprocessor == sample_response.preprocessor

        # Should have attempted 3 times due to the retry loop
        assert analyzer._llm_client.get_completion.call_count == 3

    @pytest.mark.asyncio
    async def test_build_response_detail_all_llm_attempts_fail(self, analyzer, sample_response, output_schema):
        """Test when all 3 LLM attempts fail - covers lines 486-487, 489-496."""

        # Mock LLM completion to always raise exceptions
        analyzer._llm_client.get_completion = AsyncMock(side_effect=Exception("LLM error"))

        result = await analyzer.build_response_detail(sample_response, output_schema)

        # Should return basic ResponseDetail (failure case)
        assert isinstance(result, ResponseDetail)
        assert result.code_to_extract_data is None
        assert result.default_entity_count == 0
        assert result.preprocessor == sample_response.preprocessor

        # Verify 3 attempts were made (loop with continue on line 487)
        assert analyzer._llm_client.get_completion.call_count == 3

    @pytest.mark.asyncio
    async def test_build_response_detail_parse_python_code_failure(
        self, analyzer, mock_code_executor, sample_response, output_schema
    ):
        """Test validator when parse_python_code fails - covers line 462, 469."""

        # Mock parse_python_code to return None (parse failure)
        with patch("strot.analyzer.analyzer.parse_python_code", return_value=None):
            invalid_code = "invalid python syntax {"

            llm_completion = LLMCompletion(
                value=invalid_code, input_tokens=100, output_tokens=50, provider="anthropic", model="claude"
            )

            analyzer._llm_client.get_completion = AsyncMock(return_value=llm_completion)

            result = await analyzer.build_response_detail(sample_response, output_schema)

        # Should return basic ResponseDetail when parsing fails
        assert isinstance(result, ResponseDetail)
        assert result.code_to_extract_data is None
        assert result.default_entity_count == 0

        # Should have attempted 3 times due to the retry loop
        assert analyzer._llm_client.get_completion.call_count == 3

    @pytest.mark.asyncio
    async def test_build_response_detail_validator_code_execution_and_data_extraction(
        self, analyzer, mock_code_executor, sample_response, output_schema
    ):
        """Test validator function execution path - covers lines 462-467."""

        extraction_code = """```python
def extract_data(response_text):
    import json
    return json.loads(response_text)
```"""

        llm_completion = LLMCompletion(
            value=extraction_code, input_tokens=150, output_tokens=75, provider="anthropic", model="claude"
        )

        analyzer._llm_client.get_completion = AsyncMock(return_value=llm_completion)
        analyzer._code_executor = mock_code_executor
        mock_code_executor.execute = AsyncMock()
        mock_code_executor.is_definition_available = AsyncMock(return_value=True)

        # Mock data extraction to return 3 items
        extracted_data = [{"id": 1}, {"id": 2}, {"id": 3}]
        mock_code_executor.execute.side_effect = [None, extracted_data]

        result = await analyzer.build_response_detail(sample_response, output_schema)

        # Verify validator logic executed correctly
        expected_code = "def extract_data(response_text):\n    import json\n    return json.loads(response_text)"
        assert result.code_to_extract_data == expected_code
        assert result.default_entity_count == 3  # Length of extracted data

        # Verify execution calls
        assert mock_code_executor.execute.call_count == 2
        mock_code_executor.is_definition_available.assert_called_once_with("extract_data")

        # Verify the data extraction call format
        expected_call = f"extract_data({sample_response.value!r})"
        mock_code_executor.execute.assert_any_call(expected_call)


class TestCall:
    """Test __call__ method (main analyzer workflow) with proper mocking strategy."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance for testing."""
        return Analyzer(logger=get_logger())

    @pytest.fixture
    def mock_tab(self):
        """Create mock tab for testing."""
        tab = Mock()
        tab.responses = []
        return tab

    @pytest.fixture
    def output_schema(self):
        """Create sample output schema for testing."""

        class ProductSchema(BaseModel):
            id: int
            name: str
            price: float

        return ProductSchema

    @pytest.fixture
    def sample_response(self):
        """Create sample response for testing."""

        request = Request(
            method="GET",
            url="https://api.example.com/products",
            type="ajax",
            queries={"page": "1", "limit": "10"},
            headers={"Content-Type": "application/json", ":authority": "example.com"},
            post_data=None,
        )

        return Response(request=request, value='[{"id": 1, "name": "Product 1", "price": 10.99}]')

    @pytest.fixture
    def sample_request_detail(self, sample_response):
        """Create sample request detail for testing."""

        pagination_info = PaginationInfo(
            page=NumberParameter(key="page", default_value=1), limit=NumberParameter(key="limit", default_value=10)
        )

        return RequestDetail(
            request=sample_response.request,
            pagination_info=pagination_info,
            dynamic_parameters={"category": "electronics"},
            code_to_apply_parameters="def apply_parameters(): pass",
        )

    @pytest.fixture
    def sample_response_detail(self):
        """Create sample response detail for testing."""

        return ResponseDetail(
            preprocessor=None, code_to_extract_data="def extract_data(response): return []", default_entity_count=1
        )

    @pytest.mark.asyncio
    async def test_call_success_full_workflow(
        self, analyzer, mock_tab, output_schema, sample_response, sample_request_detail, sample_response_detail
    ):
        """Test successful full analyzer workflow."""

        # Mock all the internal method calls
        analyzer.discover_relevant_response = AsyncMock(return_value=sample_response)
        analyzer.build_request_detail = AsyncMock(return_value=sample_request_detail)
        analyzer.build_response_detail = AsyncMock(return_value=sample_response_detail)

        # Mock code executor type
        analyzer._code_executor.type = "unsafe"

        result = await analyzer(mock_tab, "Find products", output_schema, max_steps=5)

        # Verify result structure
        assert isinstance(result, Source)
        assert result.request_detail == sample_request_detail
        assert result.response_detail == sample_response_detail

        # Verify all methods were called correctly
        analyzer.discover_relevant_response.assert_called_once()
        analyzer.build_request_detail.assert_called_once()
        analyzer.build_response_detail.assert_called_once_with(sample_response, output_schema)

        # Verify headers were filtered (HEADERS_TO_IGNORE)
        assert ":authority" not in result.request_detail.request.headers
        assert "Content-Type" in result.request_detail.request.headers

    @pytest.mark.asyncio
    async def test_call_no_relevant_response_detected(self, analyzer, mock_tab, output_schema):
        """Test when no relevant response is detected - covers lines 521-525."""
        # Mock discover_relevant_response to return None
        analyzer.discover_relevant_response = AsyncMock(return_value=None)

        result = await analyzer(mock_tab, "Find products", output_schema, max_steps=3)

        # Should return None when no response detected
        assert result is None

        # Verify discover_relevant_response was called
        analyzer.discover_relevant_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_pagination_requirement_not_met(self, analyzer, mock_tab, output_schema, sample_response):
        """Test when pagination is required but not detected - covers lines 532-536."""

        # Set the flag to require pagination
        analyzer._is_requirement_listed_data = True

        # Create request detail without pagination info
        request_detail_no_pagination = RequestDetail(
            request=sample_response.request,
            pagination_info=None,  # No pagination detected
            dynamic_parameters={},
            code_to_apply_parameters=None,
        )

        # Mock methods - discover returns response first time, then None to break the loop
        analyzer.discover_relevant_response = AsyncMock(side_effect=[sample_response, None])
        analyzer.build_request_detail = AsyncMock(return_value=request_detail_no_pagination)

        result = await analyzer(mock_tab, "Find products", output_schema, max_steps=2)

        # Should return None when pagination required but not found
        assert result is None

        # Verify methods were called but workflow stopped due to missing pagination
        assert analyzer.discover_relevant_response.call_count == 2  # Called twice before None returned
        analyzer.build_request_detail.assert_called_once()  # Only called once before continue

    @pytest.mark.asyncio
    async def test_call_structured_extraction_fails(
        self, analyzer, mock_tab, output_schema, sample_response, sample_request_detail
    ):
        """Test when structured extraction fails - covers lines 546-549."""

        # Create response detail without extraction code (failure case)
        failed_response_detail = ResponseDetail(
            preprocessor=None,
            code_to_extract_data=None,  # Extraction failed
            default_entity_count=0,
        )

        # Mock all methods
        analyzer.discover_relevant_response = AsyncMock(return_value=sample_response)
        analyzer.build_request_detail = AsyncMock(return_value=sample_request_detail)
        analyzer.build_response_detail = AsyncMock(return_value=failed_response_detail)
        analyzer._code_executor.type = "unsafe"

        result = await analyzer(mock_tab, "Find products", output_schema, max_steps=3)

        # Should still return Source even when extraction fails
        assert isinstance(result, Source)
        assert result.request_detail == sample_request_detail
        assert result.response_detail == failed_response_detail
        assert result.response_detail.code_to_extract_data is None

    @pytest.mark.asyncio
    async def test_call_workflow_with_captured_responses(
        self, analyzer, mock_tab, output_schema, sample_response, sample_request_detail, sample_response_detail
    ):
        """Test workflow accumulates captured responses properly."""

        # Mock tab to have existing responses
        existing_response = Mock()
        mock_tab.responses = [existing_response]

        # Mock all methods
        analyzer.discover_relevant_response = AsyncMock(return_value=sample_response)
        analyzer.build_request_detail = AsyncMock(return_value=sample_request_detail)
        analyzer.build_response_detail = AsyncMock(return_value=sample_response_detail)
        analyzer._code_executor.type = "unsafe"

        await analyzer(mock_tab, "Find products", output_schema)

        # Verify build_request_detail was called with both existing and captured responses
        call_args = analyzer.build_request_detail.call_args
        assert call_args[0][0] == sample_response.request  # First arg is request
        # Additional args should include existing responses + captured response
        additional_responses = call_args[0][1:]
        assert existing_response in additional_responses
        assert sample_response in additional_responses

    @pytest.mark.asyncio
    async def test_call_header_filtering_logic(
        self, analyzer, mock_tab, output_schema, sample_request_detail, sample_response_detail
    ):
        """Test header filtering removes ignored headers - covers lines 553-555."""

        # Create request with headers that should be filtered
        request_with_headers = Request(
            method="GET",
            url="https://api.example.com/products",
            type="ajax",
            queries={},
            headers={
                "Content-Type": "application/json",  # Should keep
                ":authority": "example.com",  # Should remove
                ":method": "GET",  # Should remove
                ":path": "/products",  # Should remove
                ":scheme": "https",  # Should remove
                "Authorization": "Bearer token",  # Should keep
                "user-agent": "Mozilla/5.0",  # Should keep
            },
            post_data=None,
        )

        response = Response(request=request_with_headers, value="[]")

        # Update request detail to use the new request
        sample_request_detail.request = request_with_headers

        # Mock all methods
        analyzer.discover_relevant_response = AsyncMock(return_value=response)
        analyzer.build_request_detail = AsyncMock(return_value=sample_request_detail)
        analyzer.build_response_detail = AsyncMock(return_value=sample_response_detail)
        analyzer._code_executor.type = "unsafe"

        result = await analyzer(mock_tab, "Find products", output_schema)

        # Verify headers were properly filtered
        filtered_headers = result.request_detail.request.headers

        # Should keep these headers
        assert "Content-Type" in filtered_headers
        assert "Authorization" in filtered_headers
        assert "user-agent" in filtered_headers

        # Should remove these headers (HEADERS_TO_IGNORE)
        assert ":authority" not in filtered_headers
        assert ":method" not in filtered_headers
        assert ":path" not in filtered_headers
        assert ":scheme" not in filtered_headers
