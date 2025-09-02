import io
from base64 import b64encode

from PIL import Image, ImageDraw

from strot.schema.point import Point

__all__ = ("draw_point_on_image", "encode_image", "guess_image_type")


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
