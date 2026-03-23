"""Helper script to generate test PNG fixtures."""

from PIL import Image, ImageDraw


def create_test_image(path: str = "tests/fixtures/test_circle.png"):
    """Create a simple test PNG with a red circle on white background."""
    img = Image.new("RGB", (256, 256), "white")
    draw = ImageDraw.Draw(img)
    draw.ellipse([48, 48, 208, 208], fill="red", outline="black", width=3)
    img.save(path, format="PNG")


if __name__ == "__main__":
    create_test_image()
