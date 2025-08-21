import re
from typing import TypeVar

from bs4 import BeautifulSoup
from pydantic import BaseModel

from strot.analyzer.schema.request import Request

__all__ = ("Pattern", "Point", "Response", "Request")


class Point(BaseModel):
    x: float
    y: float


class Pattern(BaseModel):
    before: str
    after: str

    def test(self, input: str) -> str | None:
        """Test a pattern against the input and get output if any."""
        full_pattern = re.escape(self.before) + r"(.*?)" + re.escape(self.after)
        matches = re.findall(full_pattern, input)
        return matches[-1] if matches else None


class ResponsePreprocessor(BaseModel):
    def run(self, response_text: str) -> str | None:
        raise NotImplementedError


class HTMLResponsePreprocessor(ResponsePreprocessor):
    """Extracts the content of a specific element from the HTML response."""

    element_selector: str

    def run(self, response_text: str) -> str | None:
        soup = BeautifulSoup(response_text, "html.parser")
        element = soup.select_one(self.element_selector)
        return str(element) if element else None


ResponsePreprocessorT = TypeVar("ResponsePreprocessorT", bound=HTMLResponsePreprocessor)


class Response(BaseModel):
    request: Request
    value: str
    preprocessor: ResponsePreprocessorT | None = None
