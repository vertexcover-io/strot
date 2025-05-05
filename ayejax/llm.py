from __future__ import annotations

import base64
from typing import Literal, Protocol

import anthropic
import openai
from pydantic import BaseModel, PrivateAttr, model_validator

from .helpers import extract_json, guess_image_type
from .logging import Logger

LLMProvider = Literal["openai", "anthropic", "groq", "open-router"]


class LLMInput(BaseModel):
    """
    Input to the LLM: text prompt and optional image bytes.

    Raises:
        ValueError: If prompt is empty.
        ValueError: If image type could not be guessed.
    """

    prompt: str
    image: bytes | None = None

    _img_type: str = PrivateAttr(default="")

    class Config:
        extra = "ignore"
        frozen = True

    @model_validator(mode="after")
    def validate(self) -> LLMInput:
        """Validate the input"""

        # validate prompt not empty
        if not self.prompt.strip():
            raise ValueError("Prompt cannot be empty")

        # validate image type if not empty
        if self.image:
            # this raises ValueError if image type could not be guessed
            self._img_type = guess_image_type(self.image)

        return self


class LLMCompletion(BaseModel):
    """
    Completion from an LLM: content string plus token metadata.
    """

    class Config:
        frozen = True

    value: str
    input_tokens: int
    output_tokens: int
    provider: LLMProvider
    model: str

    def calculate_cost(self, cost_per_1m_input: float, cost_per_1m_output: float) -> float:
        """
        Compute total cost given rates per million tokens.
        """
        return self.input_tokens / 1_000_000 * cost_per_1m_input + self.output_tokens / 1_000_000 * cost_per_1m_output


class LLMClientInterface(Protocol):
    """
    Protocol for LLM client implementations.
    """

    @property
    def provider(self) -> LLMProvider:
        """LLM provider."""

    @property
    def model(self) -> str:
        """LLM model."""

    def get_completion(self, input: LLMInput, *, json: bool = False) -> LLMCompletion:
        """
        Get LLM completion.

        Args:
            input: Input to the LLM: text prompt and optional image bytes.
            json: Whether to return JSON completion (default: False)

        Returns:
            LLMCompletion: LLM completion.
        """


class LLMClient(Logger):
    def __init__(
        self,
        *,
        provider: LLMProvider,
        model: str,
        api_key: str | None = None,
    ):
        self.__provider = provider.lower()
        self.__model = model

        self.logger.info(f"Initializing LLM client | provider={self.__provider!r} | model={self.__model!r}")

        client: anthropic.Client | openai.Client
        match self.__provider:
            case "anthropic":
                client = anthropic.Client(api_key=api_key)
            case "openai" | "groq" | "open-router":
                client = openai.Client(api_key=api_key)
                if self.__provider == "groq":
                    client.base_url = "https://api.groq.com/openai/v1/"
                elif self.__provider == "open-router":
                    client.base_url = "https://openrouter.ai/api/v1/"
            case _:
                raise ValueError(f"Unsupported provider: {self.__provider}")

        self.__client = client

    @property
    def provider(self) -> LLMProvider:
        return self.__provider

    @property
    def model(self) -> str:
        return self.__model

    def get_completion(self, input: LLMInput, *, json: bool = False) -> LLMCompletion:
        """
        Get LLM completion.

        Args:
            input: Input to the LLM: text prompt and optional image bytes.
            json: Whether to return JSON completion (default: False)

        Returns:
            LLMCompletion: LLM completion.
        """
        self.logger.info(f"Requesting LLM completion | json={json}")
        if self.provider == "anthropic":
            completion = self.__request_anthropic_client(input, json=json)
        else:
            completion = self.__request_openai_client(input, json=json)

        self.logger.info(
            "Got LLM completion | "
            f"input_tokens={completion.input_tokens} | "
            f"output_tokens={completion.output_tokens}"
        )
        return completion

    def __request_openai_client(self, input: LLMInput, json: bool) -> LLMCompletion:
        """
        Request completion from OpenAI client.

        Args:
            input: LLMInput to the LLM: text prompt and optional image bytes.
            json: Whether to return JSON completion

        Returns:
            LLMCompletion: LLM completion.
        """
        if image := input.image:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": input.prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (
                                    f"data:image/{input._img_type};" f"base64,{base64.b64encode(image).decode('utf-8')}"
                                )
                            },
                        },
                    ],
                }
            ]
        else:
            messages = [{"role": "user", "content": input.prompt}]

        response_format = openai._types.NOT_GIVEN
        if json:
            response_format = {"type": "json_object"}

        chat_completion = self.__client.chat.completions.create(
            model=self.model, messages=messages, response_format=response_format
        )

        value = chat_completion.choices[0].message.content
        return LLMCompletion(
            value=extract_json(value) if json else value,
            input_tokens=chat_completion.usage.prompt_tokens,
            output_tokens=chat_completion.usage.completion_tokens,
            provider=self.provider,
            model=self.model,
        )

    def __request_anthropic_client(self, input: LLMInput, json: bool) -> LLMCompletion:
        """
        Request completion from Anthropic client.

        Args:
            input: LLMInput to the LLM: text prompt and optional image bytes.
            json: Whether to return JSON completion

        Returns:
            LLMCompletion: LLM completion.
        """
        if image := input.image:
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": input.prompt},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": f"image/{input._img_type}",
                                "data": base64.b64encode(image).decode("utf-8"),
                            },
                        },
                    ],
                }
            ]
        else:
            messages = [{"role": "user", "content": input.prompt}]

        if json:
            messages.append({"role": "assistant", "content": "```json"})

        ai_message = self.__client.beta.messages.create(model=self.model, messages=messages, max_tokens=1024)

        value = ai_message.content[0].text
        return LLMCompletion(
            value=extract_json(value) if json else value,
            input_tokens=ai_message.usage.input_tokens,
            output_tokens=ai_message.usage.output_tokens,
            provider=self.provider,
            model=self.model,
        )
