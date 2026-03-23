"""PNG-to-SVG vectorization using vtracer."""

import asyncio
import io
import logging

import vtracer
from PIL import Image

logger = logging.getLogger(__name__)

# vtracer defaults tuned for illustration-style output
DEFAULT_VTRACER_CONFIG = {
    "colormode": "color",
    "hierarchical": "stacked",
    "mode": "spline",
    "filter_speckle": 4,
    "color_precision": 6,
    "layer_difference": 16,
    "corner_threshold": 60,
    "length_threshold": 4.0,
    "max_iterations": 10,
    "splice_threshold": 45,
    "path_precision": 3,
}


def vectorize_image_bytes(
    image_bytes: bytes,
    **overrides,
) -> str:
    """Convert a PNG/JPEG image (as bytes) to SVG string using vtracer.

    Args:
        image_bytes: Raw image bytes (PNG or JPEG).
        **overrides: Override any DEFAULT_VTRACER_CONFIG values.

    Returns:
        SVG string.
    """
    config = {**DEFAULT_VTRACER_CONFIG, **overrides}

    svg_str = vtracer.convert_raw_image_to_svg(
        image_bytes,
        img_format="png",
        colormode=config["colormode"],
        hierarchical=config["hierarchical"],
        mode=config["mode"],
        filter_speckle=config["filter_speckle"],
        color_precision=config["color_precision"],
        layer_difference=config["layer_difference"],
        corner_threshold=config["corner_threshold"],
        length_threshold=config["length_threshold"],
        max_iterations=config["max_iterations"],
        splice_threshold=config["splice_threshold"],
        path_precision=config["path_precision"],
    )

    logger.info("Vectorized image to SVG (%d bytes)", len(svg_str))
    return svg_str


def vectorize_pil_image(
    image: Image.Image,
    **overrides,
) -> str:
    """Convert a PIL Image to SVG string.

    Args:
        image: PIL Image (will be saved as PNG for vtracer).
        **overrides: Override any DEFAULT_VTRACER_CONFIG values.

    Returns:
        SVG string.
    """
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return vectorize_image_bytes(buf.getvalue(), **overrides)


async def vectorize_pil_image_async(
    image: Image.Image,
    **overrides,
) -> str:
    """Async wrapper that runs vectorization in a thread pool."""
    return await asyncio.to_thread(vectorize_pil_image, image, **overrides)
