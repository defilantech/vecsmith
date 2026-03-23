"""Shared test fixtures."""

import io
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def test_image() -> Image.Image:
    """Create a simple test image with a red circle on white background."""
    img = Image.new("RGB", (256, 256), "white")
    draw = ImageDraw.Draw(img)
    draw.ellipse([48, 48, 208, 208], fill="red", outline="black", width=3)
    return img


@pytest.fixture
def test_image_bytes(test_image: Image.Image) -> bytes:
    """Test image as PNG bytes."""
    buf = io.BytesIO()
    test_image.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_svg() -> str:
    """A minimal valid SVG string for testing."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">'
        '<circle cx="128" cy="128" r="80" fill="red"/>'
        "</svg>"
    )


@pytest.fixture
def vtracer_svg() -> str:
    """Simulated vtracer output with excessive precision."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256">'
        '<path d="M 128.12345 48.67891 C 128.12345 48.67891 208.98765 128.45678 '
        '128.12345 208.98765 C 48.67891 208.98765 48.67891 128.45678 128.12345 48.67891 Z" '
        'fill="#ff0000"/>'
        "</svg>"
    )
