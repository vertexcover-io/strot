from enum import Enum
from typing import Literal

from pydantic import BaseModel

from ayejax.adapter import SchemaAdapter
from ayejax.tag.schema.reviews import ReviewSchema


class TagValue(BaseModel):
    class Config:
        arbitrary_types_allowed = True

    query: str
    output_schema_adapter: SchemaAdapter


class Tag(Enum):
    reviews = TagValue(
        query=(
            "All the user reviews for the product. "
            "Ignore the summary of the reviews. "
            "The reviews are typically available as a list of reviews towards the bottom of the page."
        ),
        output_schema_adapter=SchemaAdapter(list[ReviewSchema]),
    )


TagLiteral = Literal["reviews"]

__all__ = ("Tag", "TagLiteral")
