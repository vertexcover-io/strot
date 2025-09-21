"""Tests for image utility functions."""

import base64
import io

import pytest
from PIL import Image

from strot.schema.point import Point
from strot.utils.image import draw_point_on_image, encode_image, guess_image_type


class TestGuessImageType:
    """Test image type guessing function."""

    def test_png_image_type(self):
        """Test PNG image type detection."""
        # Create a minimal PNG
        img = Image.new("RGB", (1, 1), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")

        result = guess_image_type(img_bytes.getvalue())
        assert result == "png"

    def test_jpeg_image_type(self):
        """Test JPEG image type detection."""
        # Create a minimal JPEG
        img = Image.new("RGB", (1, 1), color="blue")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="JPEG")

        result = guess_image_type(img_bytes.getvalue())
        assert result == "jpeg"

    def test_invalid_image_data_raises_error(self):
        """Test that invalid image data raises ValueError."""
        with pytest.raises(ValueError, match="image type could not be guessed"):
            guess_image_type(b"invalid_image_data")

    def test_empty_data_raises_error(self):
        """Test that empty data raises ValueError."""
        with pytest.raises(ValueError, match="image type could not be guessed"):
            guess_image_type(b"")

    def test_partial_image_data_raises_error(self):
        """Test that partial/corrupted image data raises ValueError."""
        # Just PNG signature without actual image data
        with pytest.raises(ValueError, match="image type could not be guessed"):
            guess_image_type(b"\x89PNG\r\n\x1a\n")


class TestEncodeImage:
    """Test base64 image encoding function."""

    def test_basic_encoding(self):
        """Test basic image encoding to base64."""
        test_data = b"test image data"
        result = encode_image(test_data)

        # Should be base64 encoded string
        assert isinstance(result, str)
        assert len(result) > 0

        # Verify it's valid base64 by decoding
        decoded = base64.b64decode(result)
        assert decoded == test_data

    def test_empty_data_encoding(self):
        """Test encoding empty data."""
        result = encode_image(b"")
        assert result == ""

    def test_binary_data_encoding(self):
        """Test encoding binary image data."""
        # Create actual image bytes
        img = Image.new("RGB", (2, 2), color="green")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")
        binary_data = img_bytes.getvalue()

        result = encode_image(binary_data)
        assert isinstance(result, str)
        assert len(result) > 0

        # Verify round-trip
        decoded = base64.b64decode(result)
        assert decoded == binary_data


class TestDrawPointOnImage:
    """Test drawing points on images."""

    def test_draw_point_basic(self):
        """Test basic point drawing."""
        # Create a test image
        img = Image.new("RGB", (10, 10), color="white")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")

        point = Point(x=5, y=5)
        result = draw_point_on_image(img_bytes.getvalue(), point)

        assert isinstance(result, Image.Image)
        assert result.size == (10, 10)
        assert result.mode == "RGBA"

    def test_draw_point_with_custom_radius(self):
        """Test drawing point with custom radius."""
        img = Image.new("RGB", (20, 20), color="white")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")

        point = Point(x=10, y=10)
        result = draw_point_on_image(img_bytes.getvalue(), point, radius=10)

        assert isinstance(result, Image.Image)
        assert result.size == (20, 20)

    def test_draw_point_with_tuple_color(self):
        """Test drawing point with RGB tuple color."""
        img = Image.new("RGB", (10, 10), color="white")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")

        point = Point(x=5, y=5)
        result = draw_point_on_image(
            img_bytes.getvalue(),
            point,
            color=(255, 0, 0),  # Red tuple
        )

        assert isinstance(result, Image.Image)
        assert result.mode == "RGBA"

    def test_draw_point_with_string_color(self):
        """Test drawing point with string color."""
        img = Image.new("RGB", (10, 10), color="white")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")

        point = Point(x=5, y=5)
        result = draw_point_on_image(img_bytes.getvalue(), point, color="blue")

        assert isinstance(result, Image.Image)
        assert result.mode == "RGBA"

    def test_draw_point_edge_coordinates(self):
        """Test drawing point at edge coordinates."""
        img = Image.new("RGB", (10, 10), color="white")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")

        # Point at corner
        point = Point(x=0, y=0)
        result = draw_point_on_image(img_bytes.getvalue(), point, radius=2)

        assert isinstance(result, Image.Image)
        assert result.size == (10, 10)

    def test_draw_point_outside_image_bounds(self):
        """Test drawing point outside image bounds."""
        img = Image.new("RGB", (10, 10), color="white")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")

        # Point outside image
        point = Point(x=15, y=15)
        result = draw_point_on_image(img_bytes.getvalue(), point, radius=2)

        # Should still work, just partially outside
        assert isinstance(result, Image.Image)
        assert result.size == (10, 10)

    def test_draw_point_zero_radius(self):
        """Test drawing point with zero radius."""
        img = Image.new("RGB", (10, 10), color="white")
        img_bytes = io.BytesIO()
        img.save(img_bytes, format="PNG")

        point = Point(x=5, y=5)
        result = draw_point_on_image(img_bytes.getvalue(), point, radius=0)

        assert isinstance(result, Image.Image)
        assert result.size == (10, 10)
