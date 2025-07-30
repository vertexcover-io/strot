import io
import json
import re
import threading
import unicodedata
from base64 import b64encode
from typing import Any

import regex
from json_repair import repair_json
from PIL import Image, ImageDraw
from rapidfuzz import fuzz

from strot.analyzer.schema import Pattern, Point

__all__ = (
    "draw_point_on_image",
    "encode_image",
    "extract_json",
    "guess_image_type",
    "normalize",
    "text_match_ratio",
    "tokenize",
)


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


def guess_image_type(image: bytes) -> str:
    """
    Guess the image type from the image data.

    Args:
        image: Image data to guess the type of

    Raises:
        ValueError: If image type could not be guessed.

    Returns:
        str: Image type (e.g. "png", "jpeg")
    """
    try:
        with Image.open(io.BytesIO(image)) as img:
            img_type = img.format
            if img_type is None:
                raise ValueError("image type could not be guessed")  # noqa: TRY301
            return img_type.lower()
    except Exception as e:
        raise ValueError("image type could not be guessed") from e


def encode_image(image: bytes) -> str:
    """
    Encode image to base64.

    Args:
        image: Image data to encode

    Returns:
        str: Base64 encoded image data
    """
    return b64encode(image).decode("utf-8")


def draw_point_on_image(
    image_bytes: bytes,
    coords: Point,
    radius: int = 5,
    color: "tuple[int, int, int] | str" = "red",
):
    """
    Draw a small circle at the given `(x, y)` coordinates on an image.

    Args:
        image_bytes: Raw image bytes.
        coords: X and Y coordinates (pixels) of the centre of the point.
        radius: Radius of the circle to draw in pixels.
        color: Fill colour for the circle. An `(R, G, B)` tuple or any Pillow-compatible colour string.

    Returns:
        PIL.Image.Image: The image with the point drawn on it.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    draw = ImageDraw.Draw(img)

    fill_color = tuple(color) if isinstance(color, tuple) else color

    bbox = (coords.x - radius, coords.y - radius, coords.x + radius, coords.y + radius)
    draw.ellipse(bbox, fill=fill_color)

    return img


def generate_patterns(input: str, output: str) -> list[Pattern]:
    """
    Generate output patterns from input.

    Args:
        input: Input string.
        output: Output string.

    Returns:
        list[Pattern]: List of patterns.
    """
    pos = input.find(output)
    if pos == -1:
        return []

    # Get the full before/after context
    before = input[:pos]
    after = input[pos + len(output) :]

    # Generate patterns of different delimiter lengths
    return [
        Pattern(before=before[-delim_len:], after=after[:delim_len])
        for delim_len in range(min(20, len(before), len(after)), 0, -1)
    ]


def parse_python_code(markdown: str) -> str:
    # Pattern to match code fences with optional language specification
    # Matches ```python, ```py, or just ``` followed by code and ending ```
    pattern = r"```(?:python|py)?\s*\n(.*?)\n```"

    matches = re.findall(pattern, markdown, re.DOTALL)
    if not matches:
        raise ValueError("No code found in markdown")

    return matches[0].strip()


class LimitOffsetTracker:
    def __init__(self, limit: int, offset: int):
        self.offset = offset
        self.limit = limit
        self.global_position = 0
        self.remaining_items = limit

    def slice(self, data: list) -> list:
        if not data:
            return []

        chunk_start = max(0, self.offset - self.global_position)
        chunk_end = min(len(data), chunk_start + self.remaining_items)

        if chunk_start < len(data):
            slice_data = data[chunk_start:chunk_end]
            if slice_data:
                self.remaining_items -= len(slice_data)
                self.global_position += len(data)
                return slice_data

        return []


def json_load_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json_load_value(json.loads(value))
        except (json.JSONDecodeError, ValueError):
            return value
    elif isinstance(value, dict):
        return {k: json_load_value(v) for k, v in value.items()}
    else:
        return value


def is_flat_or_flat_dict(value: Any) -> bool:
    if not isinstance(value, dict):
        return not isinstance(value, (list, tuple, set))

    return all(not isinstance(v, (dict, list, tuple, set)) for v in value.values())
