from typing import Literal

from pydantic import BaseModel

from ayejax.types import CapturedRequest


class BaseCode(BaseModel):
    code_block: str
    caller_block: str
    loop_caller_block: str

    class Config:
        frozen = True

    def __new__(cls, *args, **kwargs):
        if cls is BaseCode:
            raise TypeError("BaseCode is an abstract base class and cannot be instantiated directly.")
        return super().__new__(cls)

    @classmethod
    def from_request(cls, request: CapturedRequest) -> "BaseCode":
        raise NotImplementedError("Subclasses must implement `from_request()`.")

    def render(self, caller_type: Literal["default", "loop"] | None = None) -> str:
        if caller_type == "default":
            return self.code_block + "\n\n" + self.caller_block
        elif caller_type == "loop":
            return self.code_block + "\n\n" + self.loop_caller_block
        else:
            return self.code_block
