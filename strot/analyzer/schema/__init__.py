import re

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


class Response(BaseModel):
    value: str
    request: Request
