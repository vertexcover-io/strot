from __future__ import annotations

import functools

from pydantic import BaseModel, model_validator

from strot.schema.base import BaseSchema
from strot.schema.pattern import Pattern

__all__ = ("PaginationInfo", "NumberParameter", "CursorParameter")


class PaginationInfo(BaseSchema):
    page: NumberParameter | None = None
    cursor: CursorParameter | None = None
    limit: NumberParameter | None = None
    offset: NumberParameter | None = None

    @model_validator(mode="after")
    def validate_required_fields(self):
        if not self.page and not self.offset and not self.cursor:
            raise ValueError("Either page, offset or cursor parameter is required")
        return self

    @functools.cached_property
    def keys(self):
        keys = []
        if self.page:
            keys.append(self.page.key)
        if self.cursor:
            keys.append(self.cursor.key)
        if self.limit:
            keys.append(self.limit.key)
        if self.offset:
            keys.append(self.offset.key)
        return keys


class NumberParameter(BaseModel):
    key: str
    default_value: int


class CursorParameter(BaseModel):
    key: str
    default_value: str
    pattern_map: dict[str, list[Pattern]]

    def extract_cursor(self, response_text: str) -> str | None:
        """Extract cursor from response using pattern map"""

        cursor_values = {}
        for value, patterns in self.pattern_map.items():
            if not patterns:
                # Constant value that doesn't need updating
                cursor_values[value] = value
                continue

            for pattern in patterns:
                if output := pattern.test(response_text):
                    cursor_values[value] = output
                    break
            else:
                # If we can't find a pattern for this value, cursor extraction failed
                return None

        if not cursor_values:
            return None

        # Reconstruct cursor with new values
        new_cursor = self.default_value
        for old_value in sorted(cursor_values.keys(), key=len, reverse=True):
            new_cursor = new_cursor.replace(old_value, cursor_values[old_value])

        return new_cursor

    def get_nullable_cursor(self) -> str | None:
        value = self.default_value
        for sub_value in self.pattern_map:
            # Replace the cursor sub_value with "null", handling quoted values properly
            pos = value.find(sub_value)
            if pos != -1:
                # Check for quotes around the sub_value
                if pos > 0 and value[pos - 1] == '"':
                    sub_value = f'"{sub_value}"'
                    i = 2
                    while pos >= i and value[pos - i] == "\\":
                        sub_value = f"\\{sub_value}\\"
                        i += 1

                value = value.replace(sub_value, "null")
        return None if value == "null" else value
