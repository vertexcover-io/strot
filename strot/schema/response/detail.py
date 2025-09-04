from typing import Any

from pydantic import PrivateAttr

from strot.schema.base import BaseSchema
from strot.schema.response.preprocessor import ResponsePreprocessorUnion

__all__ = ("ResponseDetail",)


class ResponseDetail(BaseSchema):
    preprocessor: ResponsePreprocessorUnion | None = None
    code_to_extract_data: str | None = None
    default_entity_count: int = 0

    _namespace: dict[str, Any] = PrivateAttr(default_factory=dict)

    def extract_data(self, response_text: str) -> list[Any]:
        if not (text := self.preprocessor.run(response_text) if self.preprocessor else response_text):
            return []

        try:
            if self.code_to_extract_data and not self._namespace:
                exec(self.code_to_extract_data, self._namespace)  # noqa: S102

            if "extract_data" in self._namespace:
                return self._namespace["extract_data"](text) or []
        except Exception:
            return []
