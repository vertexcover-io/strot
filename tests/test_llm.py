"""Tests for LLM client functionality."""

import io
from unittest.mock import AsyncMock, Mock

import anthropic
import openai
import pytest
from PIL import Image

from strot.llm import LLMClient, LLMCompletion, LLMInput


class TestLLMInput:
    """Test LLMInput Pydantic model validation."""

    def test_valid_input_text_only(self):
        """Test LLMInput validation accepts text-only prompts without image data."""
        input_data = LLMInput(prompt="Test prompt")
        assert input_data.prompt == "Test prompt"
        assert input_data.image is None

    def test_valid_input_with_image(self):
        """Test LLMInput validation accepts prompts with valid PNG image data and detects image type."""
        # Create a minimal valid PNG image
        img = Image.new("RGB", (1, 1), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        fake_png = img_bytes.getvalue()

        input_data = LLMInput(prompt="Describe image", image=fake_png)
        assert input_data.prompt == "Describe image"
        assert input_data.image == fake_png
        assert input_data._img_type == "png"

    def test_empty_prompt_raises_error(self):
        """Test that empty prompt raises validation error."""
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            LLMInput(prompt="")

    def test_whitespace_only_prompt_raises_error(self):
        """Test that whitespace-only prompt raises validation error."""
        with pytest.raises(ValueError, match="Prompt cannot be empty"):
            LLMInput(prompt="   \n\t  ")

    def test_invalid_image_type_raises_error(self):
        """Test that invalid image data raises validation error."""
        with pytest.raises(ValueError):
            LLMInput(prompt="Test", image=b"invalid_image_data")


class TestLLMCompletion:
    """Test LLMCompletion Pydantic model."""

    def test_valid_completion(self):
        """Test creating valid LLMCompletion."""
        completion = LLMCompletion(
            value="Test response",
            input_tokens=100,
            output_tokens=50,
            provider="anthropic",
            model="claude-sonnet-4-20250514",
        )
        assert completion.value == "Test response"
        assert completion.input_tokens == 100
        assert completion.output_tokens == 50
        assert completion.provider == "anthropic"
        assert completion.model == "claude-sonnet-4-20250514"

    def test_completion_immutable(self):
        """Test that LLMCompletion is immutable (frozen)."""
        completion = LLMCompletion(
            value="Test", input_tokens=100, output_tokens=50, provider="anthropic", model="claude-sonnet-4-20250514"
        )
        with pytest.raises(ValueError):
            completion.value = "Modified"


class TestLLMClient:
    """Test LLMClient functionality with mocked external calls."""

    def test_client_initialization_anthropic(self):
        """Test LLMClient initialization with Anthropic provider."""
        client = LLMClient(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key",
            cost_per_1m_input=3.0,
            cost_per_1m_output=15.0,
        )
        assert client.provider == "anthropic"
        assert client.model == "claude-sonnet-4-20250514"

    def test_client_initialization_openai(self):
        """Test LLMClient initialization with OpenAI provider."""
        client = LLMClient(
            provider="openai", model="gpt-4", api_key="test-key", cost_per_1m_input=10.0, cost_per_1m_output=30.0
        )
        assert client.provider == "openai"
        assert client.model == "gpt-4"

    def test_client_initialization_unsupported_provider(self):
        """Test that unsupported provider raises error."""
        with pytest.raises(ValueError, match="Unsupported provider"):
            LLMClient(
                provider="unsupported",
                model="test-model",
                api_key="test-key",
                cost_per_1m_input=1.0,
                cost_per_1m_output=1.0,
            )

    def test_cost_calculation(self):
        """Test cost calculation logic."""
        client = LLMClient(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key",
            cost_per_1m_input=3.0,
            cost_per_1m_output=15.0,
        )

        # 100k input tokens, 50k output tokens
        cost = client.calculate_cost(100_000, 50_000)
        expected = (100_000 / 1_000_000 * 3.0) + (50_000 / 1_000_000 * 15.0)
        assert cost == expected

    @pytest.mark.asyncio
    async def test_anthropic_completion_success(self, mock_anthropic_client, sample_llm_input):
        """Test successful Anthropic API completion."""
        # Setup mock response
        mock_response = Mock()
        mock_response.content = [Mock(text='{"result": "success"}')]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)
        mock_anthropic_client.return_value.beta.messages.create = AsyncMock(return_value=mock_response)

        client = LLMClient(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key",
            cost_per_1m_input=3.0,
            cost_per_1m_output=15.0,
        )

        completion = await client.get_completion(sample_llm_input)

        assert isinstance(completion, LLMCompletion)
        assert completion.value == '{"result": "success"}'
        assert completion.input_tokens == 100
        assert completion.output_tokens == 50
        assert completion.provider == "anthropic"
        assert completion.model == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_openai_completion_success(self, mock_openai_client, sample_llm_input):
        """Test successful OpenAI API completion."""
        # Setup mock response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"result": "success"}'))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)
        mock_openai_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)

        client = LLMClient(
            provider="openai", model="gpt-4", api_key="test-key", cost_per_1m_input=10.0, cost_per_1m_output=30.0
        )

        completion = await client.get_completion(sample_llm_input)

        assert isinstance(completion, LLMCompletion)
        assert completion.value == '{"result": "success"}'
        assert completion.input_tokens == 100
        assert completion.output_tokens == 50
        assert completion.provider == "openai"
        assert completion.model == "gpt-4"

    @pytest.mark.asyncio
    async def test_anthropic_json_completion(self, mock_anthropic_client, sample_llm_input):
        """Test Anthropic JSON completion mode."""
        mock_response = Mock()
        mock_response.content = [Mock(text='```json\n{"result": "success"}\n```')]
        mock_response.usage = Mock(input_tokens=100, output_tokens=50)
        mock_anthropic_client.return_value.beta.messages.create = AsyncMock(return_value=mock_response)

        client = LLMClient(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key",
            cost_per_1m_input=3.0,
            cost_per_1m_output=15.0,
        )

        completion = await client.get_completion(sample_llm_input, json=True)

        # Should extract JSON from markdown code block
        assert '{"result": "success"}' in completion.value

    @pytest.mark.asyncio
    async def test_openai_json_completion(self, mock_openai_client, sample_llm_input):
        """Test OpenAI JSON completion mode."""
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content='{"result": "success"}'))]
        mock_response.usage = Mock(prompt_tokens=100, completion_tokens=50)
        mock_openai_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)

        client = LLMClient(
            provider="openai", model="gpt-4", api_key="test-key", cost_per_1m_input=10.0, cost_per_1m_output=30.0
        )

        completion = await client.get_completion(sample_llm_input, json=True)

        assert completion.value == '{"result": "success"}'

        # Verify JSON mode was requested
        call_args = mock_openai_client.return_value.chat.completions.create.call_args
        assert call_args[1]["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    async def test_completion_with_image(self, mock_anthropic_client):
        """Test completion with image input."""
        # Create a minimal valid PNG image

        img = Image.new("RGB", (1, 1), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        fake_png = img_bytes.getvalue()

        input_with_image = LLMInput(prompt="Describe this image", image=fake_png)

        mock_response = Mock()
        mock_response.content = [Mock(text="Image description")]
        mock_response.usage = Mock(input_tokens=150, output_tokens=75)
        mock_anthropic_client.return_value.beta.messages.create = AsyncMock(return_value=mock_response)

        client = LLMClient(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key",
            cost_per_1m_input=3.0,
            cost_per_1m_output=15.0,
        )

        completion = await client.get_completion(input_with_image)

        assert completion.value == "Image description"

        # Verify the API was called with image data
        call_args = mock_anthropic_client.return_value.beta.messages.create.call_args
        messages = call_args[1]["messages"]
        assert len(messages[0]["content"]) == 2  # Text + image
        assert messages[0]["content"][1]["type"] == "image"

    @pytest.mark.asyncio
    async def test_anthropic_api_error_propagation(self, mock_anthropic_client, sample_llm_input):
        """Test that Anthropic API errors are properly propagated."""
        mock_anthropic_client.return_value.beta.messages.create = AsyncMock(
            side_effect=anthropic.APIError("API Error", request=Mock(), body="error body")
        )

        client = LLMClient(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            api_key="test-key",
            cost_per_1m_input=3.0,
            cost_per_1m_output=15.0,
        )

        with pytest.raises(anthropic.APIError):
            await client.get_completion(sample_llm_input)

    @pytest.mark.asyncio
    async def test_openai_api_error_propagation(self, mock_openai_client, sample_llm_input):
        """Test that OpenAI API errors are properly propagated."""
        mock_openai_client.return_value.chat.completions.create = AsyncMock(
            side_effect=openai.APIError("API Error", request=Mock(), body="error body")
        )

        client = LLMClient(
            provider="openai", model="gpt-4", api_key="test-key", cost_per_1m_input=10.0, cost_per_1m_output=30.0
        )

        with pytest.raises(openai.APIError):
            await client.get_completion(sample_llm_input)
