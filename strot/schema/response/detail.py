from typing import Any

from pydantic import PrivateAttr

from strot.code_executor import CodeExecutorT, CodeExecutorType, create_executor
from strot.schema.base import BaseSchema
from strot.schema.response.preprocessor import ResponsePreprocessorUnion

__all__ = ("ResponseDetail",)


class ResponseDetail(BaseSchema):
    preprocessor: ResponsePreprocessorUnion | None = None
    code_to_extract_data: str | None = None
    default_entity_count: int = 0

    _code_executor: CodeExecutorT | None = PrivateAttr(default=None)

    def set_code_executor(self, type: CodeExecutorType) -> None:
        self._code_executor = create_executor(type)

    async def extract_data(self, response_text: str) -> list[Any]:
        if not (text := self.preprocessor.run(response_text) if self.preprocessor else response_text):
            return []

        try:
            if self._code_executor is None:
                self._code_executor = create_executor("unsafe")

            if self.code_to_extract_data and (not await self._code_executor.is_definition_available("extract_data")):
                await self._code_executor.execute(self.code_to_extract_data)

            if await self._code_executor.is_definition_available("extract_data"):
                await self._code_executor.execute(f"_response_text = {text!r}")
                result = await self._code_executor.execute("extract_data(_response_text)")
                return result or []
        except Exception:
            return []
