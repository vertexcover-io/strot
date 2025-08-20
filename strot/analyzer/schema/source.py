from pathlib import Path
from typing import Any

from pydantic import BaseModel, PrivateAttr

from strot.analyzer.schema import ResponsePreprocessorT
from strot.analyzer.schema.pagination_strategy import PaginationStrategy
from strot.analyzer.schema.request import Request
from strot.analyzer.utils import LimitOffsetTracker

__all__ = ("Source",)


class Source(BaseModel):
    request: Request
    pagination_strategy: PaginationStrategy | None = None
    response_preprocessor: ResponsePreprocessorT | None = None
    extraction_code: str | None = None
    default_limit: int = 1

    _namespace: dict[str, Any] = PrivateAttr(default_factory=dict)

    @classmethod
    def load_from_file(cls, path: str | Path):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path!r}")

        return cls.model_validate_json(path.read_bytes().decode("utf-8"))

    def save_to_file(self, path: str | Path) -> None:
        path = Path(path)
        path.write_text(self.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")

    def extract_data(self, response_text: str) -> list[Any]:
        if self.extraction_code and not self._namespace:
            exec(self.extraction_code, self._namespace)  # noqa: S102

        if "extract_data" in self._namespace:
            return self._namespace["extract_data"](response_text)

        return [response_text]

    async def generate_data(self, *, limit: int, offset: int):
        tracker = LimitOffsetTracker(limit, offset)
        if self.pagination_strategy:
            async for data in self.pagination_strategy.generate_data(
                request=self.request,
                tracker=tracker,
                response_preprocessor=self.response_preprocessor,
                extract_fn=self.extract_data,
                default_limit=self.default_limit,
            ):
                yield data
        else:
            response_text = await (await self.request.make()).text()
            if self.response_preprocessor:
                response_text = self.response_preprocessor.run(response_text)

            if response_text:
                data = self.extract_data(response_text)
                if slice_data := tracker.slice(data):
                    yield slice_data
