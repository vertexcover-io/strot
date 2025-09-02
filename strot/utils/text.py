import re
import threading
import unicodedata

import regex
from json_repair import repair_json
from rapidfuzz import fuzz

__all__ = ("extract_json", "normalize", "text_match_ratio", "tokenize")


def normalize(text: str) -> str:
    """Unicode normalization and case folding."""
    return unicodedata.normalize("NFKC", text).casefold()


def tokenize(text: str) -> list[str]:
    """
    Tokenize text into words in a language-agnostic way using Unicode-aware regex.
    This works for space-delimited and non-space-delimited languages.
    """
    return regex.findall(r"\p{L}+", text)


def text_match_ratio(subtexts: list[str], text: str, *, cutoff: int = 80) -> float:
    """
    Compute the ratio of substrings found in text (exact or fuzzy), supporting Unicode and non-English text.
    """
    norm_text = normalize(text)
    words = tokenize(norm_text)

    match_count = 0
    lock = threading.Lock()

    def check_one(subtext: str):
        nonlocal match_count
        norm_subtext = normalize(subtext)

        # Exact match (substring)
        if norm_subtext in norm_text:
            found = True
        else:
            # Fuzzy match with words in text
            found = any(fuzz.ratio(norm_subtext, w, score_cutoff=cutoff) for w in words)

        if found:
            with lock:
                match_count += 1

    threads: list[threading.Thread] = []
    for subtext in subtexts:
        t = threading.Thread(target=check_one, args=(subtext,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    return match_count / len(subtexts) if subtexts else 0.0


def extract_json(s: str) -> str:
    """
    Extracts and repairs JSON value from given string.

    Args:
        s: String to extract JSON from
    """
    text = re.sub(r"^```(?:json)?\s*", "", s.strip())
    return repair_json(re.sub(r"\s*```$", "", text))


def parse_python_code(markdown: str) -> str:
    # Pattern to match code fences with optional language specification
    # Matches ```python, ```py, or just ``` followed by code and ending ```
    pattern = r"```(?:python|py)?\s*\n(.*?)\n```"

    matches = re.findall(pattern, markdown, re.DOTALL)
    if not matches:
        raise ValueError("No code found in markdown")

    return matches[0].strip()
