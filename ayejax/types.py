from pathlib import Path
from typing import Any

from pydantic import BaseModel

from ayejax.llm import LLMCompletion
from ayejax.pagination.strategy import StrategyInfo

__all__ = ("AnalysisResult", "Request", "Response", "Metadata", "Output")


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


class Point(BaseModel):
    x: float
    y: float


class AnalysisResult(PydanticModel):
    keywords: list[str] = []
    navigation_element_point: Point | None = None
    popup_element_point: Point | None = None


class Request(PydanticModel):
    method: str
    url: str
    queries: dict[str, str]
    headers: dict[str, str]
    post_data: dict[str, Any] | str | None = None


class Response(PydanticModel):
    value: str
    request: Request


class Metadata(PydanticModel):
    extracted_keywords: list[str]
    completions: list[LLMCompletion]


class Output(PydanticModel):
    request: Request
    pagination_strategy: StrategyInfo | None = None
    schema_extractor_code: str | None = None
    items_count_on_first_extraction: int
