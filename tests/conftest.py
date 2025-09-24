"""Shared test fixtures and configuration."""

from unittest.mock import AsyncMock, Mock

import pytest
from pydantic import BaseModel

from strot.llm import LLMCompletion, LLMInput
from strot.schema.request import Request
from strot.schema.response import Response


@pytest.fixture
def mock_anthropic_client(mocker):
    """Mock Anthropic HTTP client to avoid real API calls."""
    mock_client = mocker.patch("anthropic.AsyncClient")
    mock_response = Mock()
    mock_response.content = [Mock(text='{"test": "response"}')]
    mock_response.usage = Mock(input_tokens=100, output_tokens=50)
    mock_client.return_value.beta.messages.create = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.fixture
def mock_openai_client(mocker):
    """Mock OpenAI HTTP client to avoid real API calls."""
    mock_client = mocker.patch("openai.AsyncClient")
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"test": "response"}'))]
    mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)
    mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client


@pytest.fixture
def sample_llm_input():
    """Real LLMInput instance for testing."""
    return LLMInput(prompt="Test prompt", image=None)


@pytest.fixture
def sample_llm_completion():
    """Real LLMCompletion instance for testing."""
    return LLMCompletion(
        value='{"result": "test"}',
        input_tokens=100,
        output_tokens=50,
        provider="anthropic",
        model="claude-sonnet-4-20250514",
    )


@pytest.fixture
def sample_request():
    """Real Request instance for testing."""
    return Request(
        method="GET",
        url="https://api.example.com/data",
        type="ajax",
        queries={"page": "1", "limit": "10"},
        headers={"Content-Type": "application/json"},
        post_data=None,
    )


@pytest.fixture
def sample_response():
    """Real Response instance for testing."""
    return Response(
        value='{"items": [{"id": 1, "name": "test"}]}',
        request=Request(
            method="GET",
            url="https://api.example.com/data",
            type="ajax",
            queries={"page": "1"},
            headers={},
            post_data=None,
        ),
    )


@pytest.fixture
def sample_schema():
    """Sample Pydantic schema for testing extraction."""

    class Product(BaseModel):
        id: int
        name: str
        price: float | None = None

    return Product


@pytest.fixture
def mock_browser_page(mocker):
    """Mock Playwright page to avoid real browser automation."""
    mock_page = mocker.Mock()
    mock_page.goto = AsyncMock()
    mock_page.screenshot = AsyncMock(return_value=b"fake_screenshot_data")
    mock_page.evaluate = AsyncMock(return_value=[])
    mock_page.content = AsyncMock(return_value="<html><body>test content</body></html>")
    mock_page.url = "https://example.com"
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.set_viewport_size = AsyncMock()
    mock_page.on = Mock()
    mock_page.close = AsyncMock()
    mock_page.locator = Mock()
    mock_page.mouse = Mock()
    mock_page.mouse.move = AsyncMock()
    mock_page.mouse.click = AsyncMock()
    return mock_page


@pytest.fixture
def mock_browser_context(mocker):
    """Mock browser context to avoid real browser setup."""
    mock_ctx = mocker.Mock()
    mock_ctx.new_page = AsyncMock()
    mock_ctx.close = AsyncMock()
    return mock_ctx


@pytest.fixture
def mock_code_executor(mocker):
    """Mock code executor to avoid executing potentially unsafe code."""
    mock_executor = mocker.Mock()
    mock_executor.execute = AsyncMock(return_value=[{"id": 1, "name": "test"}])
    mock_executor.is_definition_available = AsyncMock(return_value=True)
    mock_executor.type = "unsafe"
    return mock_executor


@pytest.fixture
def mock_e2b_client(mocker):
    """Mock E2B code interpreter to avoid external service calls."""
    return mocker.patch("e2b_code_interpreter.CodeInterpreter")


@pytest.fixture
def mock_file_operations(mocker):
    """Mock file system operations for logging tests."""
    return mocker.patch("pathlib.Path")


@pytest.fixture
def mock_s3_client(mocker):
    """Mock S3 client to avoid AWS calls."""
    return mocker.patch("boto3.client")


@pytest.fixture
def mock_browser(mocker, mock_browser_context):
    """Mock Browser instance with context creation."""
    mock_browser = mocker.Mock()
    mock_browser.new_context = AsyncMock(return_value=mock_browser_context)
    return mock_browser


@pytest.fixture
def valid_screenshot():
    """Create valid PNG screenshot data for testing."""
    import io

    from PIL import Image

    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="PNG")
    return img_bytes.getvalue()


@pytest.fixture
def mock_tab(mocker, mock_browser_page, valid_screenshot):
    """Mock Tab instance with browser page operations."""
    mock_tab = mocker.Mock()
    mock_tab.goto = AsyncMock()
    mock_tab.reset = AsyncMock()
    mock_tab.plugin = mocker.Mock()
    mock_tab.plugin.take_screenshot = AsyncMock(return_value=valid_screenshot)
    mock_tab.plugin.click_at_point = AsyncMock(return_value=True)
    mock_tab.plugin.find_common_parent = AsyncMock(return_value=None)
    mock_tab.plugin.get_last_similar_children_or_sibling = AsyncMock(return_value=None)
    mock_tab.plugin.scroll_to_element = AsyncMock()
    mock_tab.plugin.click_element = AsyncMock()
    mock_tab.plugin.scroll_by = AsyncMock()
    mock_tab.plugin.scroll_to_next_view = AsyncMock()
    mock_tab.responses = []
    mock_tab.page_response = AsyncMock(return_value=None)
    return mock_tab
