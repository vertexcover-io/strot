import re
from typing import Any

from strot.schema.request import Request

__all__ = (
    "is_digit_value",
    "is_potential_cursor",
    "extract_potential_cursors",
)


def is_digit_value(value: Any) -> bool:
    """Check if value is a digit (for page, limit, offset)"""
    return isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit())


def is_potential_cursor(value: str) -> bool:
    if re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", value):  # ISO datetime format
        return True
    if len(value) < 8:
        return False
    return bool(re.match(r"^[A-Za-z0-9_\-+:.=/]+$", value))


def extract_potential_cursors(value: Any) -> list[str]:
    """Extract all potential cursors using regex patterns with proper boundaries"""
    value_str = str(value)
    extracted_values = []

    # Step 1: Check if whole string is a cursor
    if is_potential_cursor(value_str):
        return [value_str]

    # Step 2: Look for patterns
    patterns = [
        r'"([^"]+)"',  # Double quoted strings
        r"'([^']+)'",  # Single quoted strings
        r'\\"([^"]+)\\"',  # Double quoted strings
    ]

    for pattern in patterns:
        matches = re.findall(pattern, value_str)
        for match in matches:
            if is_potential_cursor(match):
                extracted_values.append(match)

    return list(set(extracted_values))


def get_value(request: Request, key: str) -> Any:
    def get_value_from_dict(d: dict, key: str) -> Any:
        for k, v in d.items():
            if k == key:
                return v
            if isinstance(v, dict):
                result = get_value_from_dict(v, key)
                if result is not None:
                    return result

    if request.queries:
        return get_value_from_dict(request.queries, key)
    if isinstance(request.post_data, dict):
        return get_value_from_dict(request.post_data, key)
    return None
