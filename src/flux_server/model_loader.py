"""Flux model loader with FP8 quantization for 16GB VRAM GPUs."""

import logging
import os
from pathlib import Path

import torch
from diffusers import Flux2KleinPipeline

logger = logging.getLogger(__name__)

# Default model: FLUX.2-klein-4B (Apache 2.0, 4B params)
DEFAULT_MODEL_ID = "black-forest-labs/FLUX.2-klein-4B"


def load_flux_pipeline(
    model_id: str = DEFAULT_MODEL_ID,
    cache_dir: str | None = None,
    device: str = "cuda",
    quantize_fp8: bool = True,
) -> Flux2KleinPipeline:
    """Load FLUX.2-klein pipeline with optional FP8 quantization.

    At BF16 the model uses ~13GB VRAM. With FP8 quantization on
    the transformer, VRAM drops to ~8GB — leaving headroom on
    16GB GPUs for larger resolutions or batch work.
    """
    if cache_dir is None:
        cache_dir = os.environ.get("HF_HOME", "/models/flux")

    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)

    logger.info("Loading Flux pipeline: %s (cache: %s)", model_id, cache_dir)

    pipe = Flux2KleinPipeline.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        cache_dir=cache_dir,
    )

    if quantize_fp8:
        from optimum.quanto import freeze, qfloat8, quantize

        logger.info("Quantizing transformer to FP8...")
        quantize(pipe.transformer, weights=qfloat8)
        freeze(pipe.transformer)
        logger.info("FP8 quantization complete")

    pipe.enable_model_cpu_offload(device=device)

    logger.info("Flux pipeline loaded successfully (fp8=%s)", quantize_fp8)
    return pipe


def generate_image(
    pipe: Flux2KleinPipeline,
    prompt: str,
    width: int = 1024,
    height: int = 1024,
    num_inference_steps: int = 4,
    seed: int | None = None,
):
    """Generate an image using FLUX.2-klein-4B.

    Uses 4 inference steps with guidance_scale=1.0.
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
        guidance_scale=1.0,
        generator=generator,
    )

    return result.images[0]
