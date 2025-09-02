from pydantic import BaseModel

__all__ = ("Point",)


class Point(BaseModel):
    x: float
    y: float
