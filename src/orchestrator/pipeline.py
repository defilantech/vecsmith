"""Core pipeline: chains enhance -> generate -> vectorize -> optimize."""

import base64
import io
import logging
import time

from ..config import Settings
from ..stages.image_generate import generate_image
from ..stages.prompt_enhance import enhance_prompt
from ..stages.svg_optimize import optimize_svg
from ..stages.vectorize import vectorize_pil_image_async
from .schemas import GenerateRequest, GenerateResponse, StageTimings

logger = logging.getLogger(__name__)


async def run_pipeline(request: GenerateRequest, settings: Settings) -> GenerateResponse:
    """Execute the full VecSmith pipeline (text to SVG or PNG).

    Stages:
    1. Prompt enhancement (LLM) - optional, skipped if skip_enhance=True
    2. Image generation (Flux)
    3. Vectorization (vtracer)
    4. SVG optimization
    """
    total_start = time.monotonic()
    timings = StageTimings()

    # Stage 1: Prompt Enhancement
    if request.skip_enhance:
        prompt_used = request.prompt
        logger.info("Skipping prompt enhancement (skip_enhance=True)")
    else:
        stage_start = time.monotonic()
        prompt_used = await enhance_prompt(
            user_prompt=request.prompt,
            llm_base_url=settings.llm_base_url,
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            temperature=settings.llm_temperature,
            output_format=request.output_format,
            api_key=settings.llm_api_key,
        )
        timings.prompt_enhance_s = round(time.monotonic() - stage_start, 3)
        logger.info("Stage 1 (enhance): %.2fs", timings.prompt_enhance_s)

    # Stage 2: Image Generation
    stage_start = time.monotonic()
    image, flux_time = await generate_image(
        prompt=prompt_used,
        flux_base_url=settings.flux_base_url,
        width=request.width,
        height=request.height,
        num_inference_steps=request.num_inference_steps,
        seed=request.seed,
    )
    timings.image_generate_s = round(time.monotonic() - stage_start, 3)
    logger.info("Stage 2 (generate): %.2fs (flux: %.2fs)", timings.image_generate_s, flux_time)

    # PNG output: skip vectorization and optimization
    if request.output_format == "png":
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        png_bytes = buf.getvalue()
        png_b64 = base64.b64encode(png_bytes).decode("ascii")
        timings.total_s = round(time.monotonic() - total_start, 3)
        logger.info("Pipeline complete (PNG): %.2fs total", timings.total_s)
        return GenerateResponse(
            svg="",
            png_base64=png_b64,
            output_format="png",
            prompt_used=prompt_used,
            timings=timings,
            svg_size_bytes=len(png_bytes),
            original_prompt=request.prompt,
        )

    # Stage 3: Vectorization
    stage_start = time.monotonic()
    svg_raw = await vectorize_pil_image_async(
        image,
        filter_speckle=settings.vtracer_filter_speckle,
        color_precision=settings.vtracer_color_precision,
    )
    timings.vectorize_s = round(time.monotonic() - stage_start, 3)
    logger.info("Stage 3 (vectorize): %.2fs", timings.vectorize_s)

    # Stage 4: SVG Optimization
    stage_start = time.monotonic()
    svg_optimized = optimize_svg(svg_raw, precision=settings.svg_coordinate_precision)
    timings.svg_optimize_s = round(time.monotonic() - stage_start, 3)
    logger.info("Stage 4 (optimize): %.2fs", timings.svg_optimize_s)

    timings.total_s = round(time.monotonic() - total_start, 3)
    logger.info("Pipeline complete: %.2fs total", timings.total_s)

    return GenerateResponse(
        svg=svg_optimized,
        output_format="svg",
        prompt_used=prompt_used,
        timings=timings,
        svg_size_bytes=len(svg_optimized.encode("utf-8")),
        original_prompt=request.prompt,
    )
