from typing import Literal

from bs4 import BeautifulSoup
from pydantic import BaseModel

__all__ = ("HTMLResponsePreprocessor", "ResponsePreprocessorUnion")


class BaseResponsePreprocessor(BaseModel):
    type: str

    def run(self, response_text: str) -> str | None:
        raise NotImplementedError


class HTMLResponsePreprocessor(BaseResponsePreprocessor):
    """Extracts the content of a specific element from the HTML response."""

    type: Literal["html"] = "html"
    element_selector: str

    def run(self, response_text: str) -> str | None:
        soup = BeautifulSoup(response_text, "html.parser")
        element = soup.select_one(self.element_selector)
        return str(element) if element else None


ResponsePreprocessorUnion = HTMLResponsePreprocessor
