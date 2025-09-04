from pydantic import BaseModel

from strot.schema.request import Request
from strot.schema.response.preprocessor import ResponsePreprocessorUnion

__all__ = ("Response",)


class Response(BaseModel):
    request: Request
    value: str = ""
    preprocessor: ResponsePreprocessorUnion | None = None
