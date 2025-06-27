import io
import re
import threading
from base64 import b64encode
from collections.abc import Iterable
from difflib import get_close_matches
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from json_repair import repair_json
from PIL import Image


def extract_fragments(html_bytes: bytes, base_url: str) -> set[str]:
    """
    Extracts fragments from hrefs that match base_url or base_url + #fragment.

    Args:
        html_bytes: HTML content in bytes.
        base_url: The base URL to match against.

    Returns:
        A set of fragments (without base_url).
    """
    soup = BeautifulSoup(html_bytes, "html.parser")
    base_url = base_url.rstrip("/")
    base_parts = urlparse(base_url)

    fragments = set()

    for tag in soup.find_all("a", href=True):
        raw_href = tag["href"]
        if raw_href.startswith(("javascript:", "mailto:")):
            continue

        absolute_href = urljoin(base_url + "/", raw_href)
        parsed = urlparse(absolute_href)

        # Match scheme, netloc, and path
        if (
            parsed.scheme == base_parts.scheme
            and parsed.netloc == base_parts.netloc
            and parsed.path.rstrip("/") == base_parts.path.rstrip("/")
            and parsed.query == ""
            and parsed.fragment
        ):
            print([child.get_text().strip() for child in tag.children])
            fragments.add(parsed.fragment)

    return fragments


def keyword_match_ratio(keywords: list[str], text: str) -> float:
    """
    Compute the ratio of keywords found in `text`, either exactly
    (case-insensitive substring) or fuzzily within individual words.

    Args:
        keywords: list of keywords to search for.
        text:     The text to search in.

    Returns:
        float: fraction of keywords found (0.0 to 1.0).
    """
    # Split and clean words for fuzzy matching
    clean_words = []
    for w in text.split():
        if w_clean := w.strip(".,!?:;\"'()[]{}<>"):
            clean_words.append(w_clean)

    match_count = 0
    lock = threading.Lock()

    def check_one(kw: str):
        nonlocal match_count
        found = False
        # exact (case insensitive) substring
        if kw.lower() in text.lower():
            found = True
        else:
            # fuzzy match: any close match among the clean words
            if get_close_matches(kw, clean_words, n=1, cutoff=0.8):
                found = True

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

    return match_count / len(keywords)


def bash_escape(s: str) -> str:
    """
    Escape a string for use in bash shell using the Chrome DevTools approach.

    Args:
        s: String to escape
    """

    def escape_character(char):
        code = ord(char)
        hex_string = format(code, "04x")  # Zero pad to four digits
        return f"\\u{hex_string}"

    # Test for characters that need ANSI-C quoting
    if re.search(r"[\0-\x1F\x7F-\x9F!]|\'", s):
        # Use ANSI-C quoting syntax
        result = "$'" + (s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r"))

        # Replace control characters and other special chars with \uXXXX
        result = re.sub(r"[\0-\x1F\x7F-\x9F!]", lambda m: escape_character(m.group(0)), result)
        return result + "'"

    # Use simple single quote syntax
    return "'" + s + "'"


def cmd_escape(s: str) -> str:
    """
    Escape a string for use in Windows Command Prompt.

    Args:
        s: String to escape
    """
    # prefix & suffix with ^"
    # 1) backslashes
    s = s.replace("\\", "\\\\")
    # 2) quotes
    s = s.replace('"', '\\"')
    # 3) other special chars
    s = re.sub(r"[^A-Za-z0-9\s_\-:=+~'/\.,\?\;\(\)\*`]", lambda m: "^" + m.group(0), s)
    # 4) percent signs before alnum or underscore
    s = re.sub(r"%(?=[A-Za-z0-9_])", "%^", s)
    # 5) newlines → ^\n\n
    s = re.sub(r"\r?\n", "^\n\n", s)
    return '^"' + s + '^"'


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
                raise ValueError("image type could not be guessed")
            return img_type.lower()
    except Exception:
        raise ValueError("image type could not be guessed")


def encode_image(image: bytes) -> str:
    """
    Encode image to base64.

    Args:
        image: Image data to encode

    Returns:
        str: Base64 encoded image data
    """
    return b64encode(image).decode("utf-8")


PAGE_KEY_CANDIDATES = {
    "page",
    "pageno",
    "page_no",
    "page_number",
    "pagenum",
    "pagenumber",
    "pageindex",
    "page_index",
    "p",
}

OFFSET_KEY_CANDIDATES = {"offset"}


def determine_page_and_offset_keys(keys: Iterable[str]) -> tuple[str | None, str | None]:
    """
    Determine page-number and offset parameter keys.

    Args:
        keys: List of query parameter names.

    Returns:
        tuple[str | None, str | None]: Page-number and offset parameter keys or None if no suitable keys are found.
    """

    page_key, offset_key = None, None
    for k in keys:
        kl = k.lower()
        if kl in PAGE_KEY_CANDIDATES:
            page_key = k
        elif kl in OFFSET_KEY_CANDIDATES:
            offset_key = k

    return page_key, offset_key


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
