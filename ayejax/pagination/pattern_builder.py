import re

from pydantic import BaseModel


class Pattern(BaseModel):
    before: str
    after: str

    def __hash__(self):
        return hash((self.before, self.after))


def get_patterns(input: str, output: str) -> list[Pattern]:
    """Extract patterns from a single input/output pair."""
    patterns = []

    # Find the position of output in input
    pos = input.find(output)
    if pos == -1:
        return patterns

    # Get the full before/after context
    before = input[:pos]
    after = input[pos + len(output) :]

    # Generate patterns of different delimiter lengths
    for delim_len in range(1, min(21, len(before) + 1, len(after) + 1)):
        if len(before) >= delim_len and len(after) >= delim_len:
            pattern = Pattern(before=before[-delim_len:], after=after[:delim_len])
            patterns.append(pattern)

    return patterns


def extract_with_pattern(input: str, pattern: Pattern) -> str | None:
    """Extract output from input using the given pattern."""
    full_pattern = re.escape(pattern.before) + r"(.*?)" + re.escape(pattern.after)
    matches = re.findall(full_pattern, input)
    return matches[0] if matches else None
