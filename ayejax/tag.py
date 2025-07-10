from enum import StrEnum
from typing import Literal


class Tag(StrEnum):
    reviews = (
        "All the user reviews for the product. "
        "Ignore the summary of the reviews. "
        "The reviews are typically available as a list of reviews towards the bottom of the page."
    )


TagLiteral = Literal["reviews"]

__all__ = ("Tag", "TagLiteral")
