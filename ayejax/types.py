from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ayejax.llm import LLMCompletion

__all__ = ("LLMValue", "Context", "CapturedRequest", "CapturedResponse", "Candidate", "Output")


class PydanticModel(BaseModel):
    @classmethod
    def load_from_file(cls, path: str | Path):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path!r}")

        return cls.model_validate_json(path.read_bytes())

    def save_to_file(self, path: str | Path) -> None:
        path = Path(path)
        path.write_text(self.model_dump_json(indent=3, exclude_none=True))


class LLMValue(PydanticModel):
    keywords: list[str] = []
    navigation_element_point: dict[str, float] | None = None
    popup_element_point: dict[str, float] | None = None


class Context(PydanticModel):
    page_screenshot: bytes
    extracted_keywords: list[str]
    relevance_score: float


class CapturedRequest(PydanticModel):
    method: str
    url: str
    queries: dict[str, str]
    headers: dict[str, str]
    post_data: dict[str, Any] | str | None = None


class CapturedResponse(PydanticModel):
    value: str
    request: CapturedRequest


class Candidate(PydanticModel):
    request: CapturedRequest
    context: Context


class Output(PydanticModel):
    candidates: list[Candidate]
    completions: list[LLMCompletion]
