import imghdr
import re
import threading
from difflib import get_close_matches

from json_repair import repair_json


def keyword_match_ratio(keywords: list[str], text: str) -> float:
    """
    Compute the ratio of keywords found in `text`, either exactly
    (case-insensitive substring) or fuzzily within individual words.

    Args:
        keywords: List of keywords to search for.
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
    img_type = imghdr.what(None, image)
    if img_type is None:
        raise ValueError("image type could not be guessed")

    return img_type
