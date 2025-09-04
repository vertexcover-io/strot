from __future__ import annotations

import re

from pydantic import BaseModel

__all__ = ("Pattern",)


class Pattern(BaseModel):
    before: str
    after: str

    def __len__(self) -> int:
        return len(self.before) + len(self.after)

    @classmethod
    def generate_multiple(cls, input: str, output: str) -> list[Pattern]:
        """
        Generate output patterns from input for ALL occurrences of output, starting from the right.

        Args:
            input: Input string.
            output: Output string.

        Returns:
            list[Pattern]: List of patterns from all occurrences, prioritizing rightmost matches.
        """
        patterns: list[Pattern] = []
        positions: list[int] = []

        # Find all occurrences of output in input (from right to left)
        start = len(input)
        while True:
            pos = input.rfind(output, 0, start)
            if pos == -1:
                break
            positions.append(pos)
            start = pos  # Continue searching to the left

        # Process positions (already in right-to-left order)
        for pos in positions:
            # Get the full before/after context for this occurrence
            before = input[:pos]
            after = input[pos + len(output) :]

            # Generate patterns of different delimiter lengths for this occurrence
            for delim_len in range(min(20, len(before), len(after)), 0, -1):
                patterns.append(cls(before=before[-delim_len:], after=after[:delim_len]))

        patterns.sort(key=len, reverse=True)
        return patterns

    def test(self, input: str) -> str | None:
        """Test a pattern against the input and get output if any."""
        full_pattern = re.escape(self.before) + r"(.*?)" + re.escape(self.after)
        matches = re.findall(full_pattern, input)
        return matches[-1] if matches else None
