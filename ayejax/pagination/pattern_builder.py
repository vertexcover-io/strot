import re

from pydantic import BaseModel


class Example(BaseModel):
    input: str
    output: str


class Pattern(BaseModel):
    before: str
    after: str

    def __hash__(self):
        return hash((self.before, self.after))


class PatternBuilder:
    def __init__(self, examples: list[Example]):
        self._examples = examples
        self._patterns: list[Pattern] = []

    @property
    def patterns(self) -> list[Pattern]:
        return self._patterns

    def add_example(self, example: Example):
        self._examples.append(example)

    def _extract_output(self, input: str, pattern: Pattern) -> str | None:
        full_pattern = re.escape(pattern.before) + r"(.*?)" + re.escape(pattern.after)
        matches = re.findall(full_pattern, input)
        return matches[0] if matches else None

    def _score_pattern(self, pattern: Pattern) -> float:
        correct_extractions = 0
        total_tests = len(self._examples)

        for example in self._examples:
            extracted = self._extract_output(example.input, pattern)

            if extracted == example.output:
                correct_extractions += 1

        return correct_extractions / total_tests if total_tests > 0 else 0

    def run(self) -> None:
        all_patterns = list(self._patterns)
        for example in self._examples:
            pos = example.input.find(example.output)
            if pos != -1:
                before = example.input[:pos]
                after = example.input[pos + len(example.output) :]
                all_patterns.append(Pattern(before=before, after=after))

        pattern_scores: dict[Pattern, float] = {}
        for pattern in all_patterns:
            for delim_len in range(1, 21):
                if len(pattern.before) >= delim_len and len(pattern.after) >= delim_len:
                    delim_pattern = Pattern(before=pattern.before[-delim_len:], after=pattern.after[:delim_len])
                    if delim_pattern not in pattern_scores:
                        score = self._score_pattern(delim_pattern)
                        if score > 0:
                            pattern_scores[delim_pattern] = score

        self._patterns = [x[0] for x in sorted(pattern_scores.items(), key=lambda x: x[1], reverse=True)]

    def extract_output(self, input: str) -> str | None:
        for pattern in self._patterns:
            extracted = self._extract_output(input, pattern)
            if extracted:
                return extracted
        return None
