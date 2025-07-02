import io
import re
import threading
import unicodedata
from base64 import b64encode

import regex
from json_repair import repair_json
from PIL import Image
from rapidfuzz import fuzz


def normalize(text: str) -> str:
    """Unicode normalization and case folding."""
    return unicodedata.normalize("NFKC", text).casefold()


def tokenize(text: str) -> list[str]:
    """
    Tokenize text into words in a language-agnostic way using Unicode-aware regex.
    This works for space-delimited and non-space-delimited languages.
    """
    return regex.findall(r"\p{L}+", text)


def keyword_match_ratio(keywords: list[str], text: str) -> float:
    """
    Compute the ratio of keywords found in text (exact or fuzzy),
    supporting Unicode and non-English text.
    """
    norm_text = normalize(text)
    words = tokenize(norm_text)

    match_count = 0
    lock = threading.Lock()

    def check_one(kw: str):
        nonlocal match_count
        norm_kw = normalize(kw)

        # Exact match (substring)
        if norm_kw in norm_text:  # noqa: SIM108
            found = True
        else:
            # Fuzzy match with words in text
            found = any(fuzz.ratio(norm_kw, w, score_cutoff=80) for w in words)

        if found:
            with lock:
                match_count += 1

    threads: list[threading.Thread] = []
    for kw in keywords:
        t = threading.Thread(target=check_one, args=(kw,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    return match_count / len(keywords) if keywords else 0.0


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
    x: int,
    y: int,
    radius: int = 5,
    color: "tuple[int, int, int] | str" = "red",
):
    """Draw a small circle at the given ``(x, y)`` coordinates on an image.

    The function accepts raw image bytes (any format supported by Pillow), draws
    a filled circle of the requested *radius* and *color* centred at the given
    coordinates, and returns a ``PIL.Image.Image`` instance with the
    modification applied.

    This is useful for visualising feature/key-points returned by detection
    algorithms or for quick debugging of coordinate systems.

    Args:
        image_bytes: Raw bytes of the image (e.g. as read from a file or HTTP response).
        x:           X-coordinate (pixels) of the centre of the point.
        y:           Y-coordinate (pixels) of the centre of the point.
        radius:      Radius of the circle to draw in pixels. Defaults to ``5``.
        color:       Fill colour for the circle. Accepts an ``(R, G, B)`` tuple
                      or any Pillow-compatible colour string (default ``"red"``).

    Returns:
        PIL.Image.Image: The image with the point drawn on it.
    """
    from PIL import ImageDraw

    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")

    draw = ImageDraw.Draw(img)

    fill_color = tuple(color) if isinstance(color, tuple) else color

    bbox = (x - radius, y - radius, x + radius, y + radius)
    draw.ellipse(bbox, fill=fill_color)

    return img
