from pathlib import Path
from typing import Self

from pydantic import BaseModel

__all__ = ("BaseSchema",)


class BaseSchema(BaseModel):
    @classmethod
    def load_from_file(cls, path: str | Path) -> Self:
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path!r}")

        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def save_to_file(self, path: str | Path) -> None:
        path = Path(path)
        path.write_text(self.model_dump_json(indent=2, exclude_none=True), encoding="utf-8")
