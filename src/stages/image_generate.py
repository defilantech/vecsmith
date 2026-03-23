"""Flux image generation client - calls the Flux server HTTP API."""

import base64
import io
import logging

import httpx
from PIL import Image

logger = logging.getLogger(__name__)


async def generate_image(
    prompt: str,
    flux_base_url: str,
    width: int = 1024,
    height: int = 1024,
    num_inference_steps: int = 4,
    seed: int | None = None,
) -> tuple[Image.Image, float]:
    """Call the Flux server to generate an image.

    Args:
        prompt: Text prompt for image generation.
        flux_base_url: Base URL for the Flux server (e.g., http://flux-server:8081).
        width: Image width in pixels.
        height: Image height in pixels.
        num_inference_steps: Number of diffusion steps (4 for schnell).
        seed: Optional seed for reproducibility.

    Returns:
        Tuple of (PIL Image, generation_time_seconds).
    """
    url = f"{flux_base_url.rstrip('/')}/generate"

    # Flux server enforces max 2000 chars; CLIP/T5 tokenizer truncates anyway
    if len(prompt) > 2000:
        logger.warning("Truncating prompt from %d to 2000 chars", len(prompt))
        prompt = prompt[:2000]

    payload = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_inference_steps": num_inference_steps,
        "output_format": "png",
    }
    if seed is not None:
        payload["seed"] = seed

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()

    data = response.json()
    image_bytes = base64.b64decode(data["image_base64"])
    image = Image.open(io.BytesIO(image_bytes))
    gen_time = data["generation_time_s"]

    logger.info(
        "Generated %dx%d image in %.2fs",
        data["width"],
        data["height"],
        gen_time,
    )

    return image, gen_time
