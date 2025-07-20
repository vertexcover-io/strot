import re

from pydantic import BaseModel


class Pattern(BaseModel):
    before: str
    after: str

    def __hash__(self):
        return hash((self.before, self.after))

    def test(self, input: str) -> str | None:
        """Test a pattern against the input and get output if any."""
        full_pattern = re.escape(self.before) + r"(.*?)" + re.escape(self.after)
        matches = re.findall(full_pattern, input)
        return matches[-1] if matches else None

    @classmethod
    def generate_list(cls, input: str, output: str) -> "list[Pattern]":
        """Extract patterns from a single input/output pair, sorted by accuracy."""
        patterns: list[Pattern] = []

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

        # Score patterns by testing them against the original input/output
        pattern_scores = []
        for pattern in patterns:
            score = 1.0 if pattern.test(input) == output else 0.0
            pattern_scores.append((pattern, score))

        # Sort by score (highest first) and return patterns
        pattern_scores.sort(key=lambda x: x[1], reverse=True)
        return [pattern for pattern, _ in pattern_scores]
