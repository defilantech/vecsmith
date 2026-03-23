"""Flux model loader with memory optimization for 16GB VRAM GPUs."""

import logging
import os
from pathlib import Path

import torch
from diffusers import FluxPipeline

logger = logging.getLogger(__name__)

# Default model for FLUX.1-schnell (Apache 2.0)
DEFAULT_MODEL_ID = "black-forest-labs/FLUX.1-schnell"


def load_flux_pipeline(
    model_id: str = DEFAULT_MODEL_ID,
    cache_dir: str | None = None,
    device: str = "cuda",
) -> FluxPipeline:
    """Load Flux pipeline with memory optimization for 16GB VRAM.

    Uses BF16 precision and CPU offloading to fit within a single
    16GB VRAM GPU.
    """
    if cache_dir is None:
        cache_dir = os.environ.get("HF_HOME", "/models/flux")

    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    logger.info("Loading Flux pipeline: %s (cache: %s)", model_id, cache_dir)

    pipe = FluxPipeline.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        cache_dir=cache_dir,
    )

    # Sequential CPU offloading moves one layer at a time to GPU,
    # keeping peak VRAM usage well within 16GB
    pipe.enable_sequential_cpu_offload(device=device)

    logger.info("Flux pipeline loaded successfully with CPU offloading")
    return pipe


def generate_image(
    pipe: FluxPipeline,
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    num_inference_steps: int = 4,
    seed: int | None = None,
):
    """Generate an image using Flux.1-schnell.

    FLUX.1-schnell uses 4 inference steps and no CFG (guidance_scale=0.0).
    Returns a PIL Image.
    """
    generator = None
    if seed is not None:
        generator = torch.Generator(device="cpu").manual_seed(seed)

    result = pipe(
        prompt=prompt,
        width=width,
        height=height,
        num_inference_steps=num_inference_steps,
        guidance_scale=0.0,
        generator=generator,
    )

    return result.images[0]
