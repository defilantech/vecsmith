"""Batch pipeline: enhance once, generate N variations with different seeds."""

import base64
import io
import logging
import time
from collections.abc import AsyncGenerator

from ..config import Settings
from ..stages.image_generate import generate_image
from ..stages.prompt_enhance import enhance_prompt
from ..stages.svg_optimize import optimize_svg
from ..stages.vectorize import vectorize_pil_image_async
from .schemas import (
    BatchDoneEvent,
    BatchErrorEvent,
    BatchGenerateRequest,
    BatchProgressEvent,
    BatchResultEvent,
    GenerateResponse,
    StageTimings,
)

logger = logging.getLogger(__name__)

BatchEvent = BatchProgressEvent | BatchResultEvent | BatchDoneEvent | BatchErrorEvent


async def run_batch_pipeline(
    request: BatchGenerateRequest,
    settings: Settings,
) -> AsyncGenerator[BatchEvent, None]:
    """Execute batch generation: enhance once, then generate N variations.

    Yields SSE-ready event objects as each variation completes.
    """
    total = request.count

    # Stage 1: Prompt Enhancement (once for all iterations)
    if request.skip_enhance:
        prompt_used = request.prompt
    else:
        try:
            prompt_used = await enhance_prompt(
                user_prompt=request.prompt,
                llm_base_url=settings.llm_base_url,
                model=settings.llm_model,
                max_tokens=settings.llm_max_tokens,
                temperature=settings.llm_temperature,
                output_format=request.output_format,
                api_key=settings.llm_api_key,
            )
        except Exception as e:
            logger.exception("Batch prompt enhancement failed: %s", e)
            yield BatchErrorEvent(index=0, total=total, detail=f"Prompt enhancement failed: {e}")
            yield BatchDoneEvent(total=0, prompt_used=request.prompt)
            return

    # Generate N variations
    for i in range(total):
        iteration_start = time.monotonic()
        timings = StageTimings()
        seed = request.seed_for_iteration(i)

        try:
            # Image generation
            yield BatchProgressEvent(index=i, total=total, stage="generating")
            stage_start = time.monotonic()
            image, flux_time = await generate_image(
                prompt=prompt_used,
                flux_base_url=settings.flux_base_url,
                width=request.width,
                height=request.height,
                num_inference_steps=request.num_inference_steps,
                seed=seed,
            )
            timings.image_generate_s = round(time.monotonic() - stage_start, 3)

            if request.output_format == "png":
                buf = io.BytesIO()
                image.save(buf, format="PNG")
                png_bytes = buf.getvalue()
                png_b64 = base64.b64encode(png_bytes).decode("ascii")
                timings.total_s = round(time.monotonic() - iteration_start, 3)

                yield BatchResultEvent(
                    index=i,
                    total=total,
                    result=GenerateResponse(
                        svg="",
                        png_base64=png_b64,
                        output_format="png",
                        prompt_used=prompt_used,
                        timings=timings,
                        svg_size_bytes=len(png_bytes),
                        original_prompt=request.prompt,
                    ),
                )
            else:
                # Vectorize
                yield BatchProgressEvent(index=i, total=total, stage="vectorizing")
                stage_start = time.monotonic()
                svg_raw = await vectorize_pil_image_async(
                    image,
                    filter_speckle=settings.vtracer_filter_speckle,
                    color_precision=settings.vtracer_color_precision,
                )
                timings.vectorize_s = round(time.monotonic() - stage_start, 3)

                # Optimize
                yield BatchProgressEvent(index=i, total=total, stage="optimizing")
                stage_start = time.monotonic()
                svg_optimized = optimize_svg(svg_raw, precision=settings.svg_coordinate_precision)
                timings.svg_optimize_s = round(time.monotonic() - stage_start, 3)

                timings.total_s = round(time.monotonic() - iteration_start, 3)

                yield BatchResultEvent(
                    index=i,
                    total=total,
                    result=GenerateResponse(
                        svg=svg_optimized,
                        output_format="svg",
                        prompt_used=prompt_used,
                        timings=timings,
                        svg_size_bytes=len(svg_optimized.encode("utf-8")),
                        original_prompt=request.prompt,
                    ),
                )

            logger.info("Batch iteration %d/%d complete (seed=%d, %.2fs)", i + 1, total, seed, timings.total_s)

        except Exception as e:
            logger.exception("Batch iteration %d/%d failed: %s", i + 1, total, e)
            yield BatchErrorEvent(index=i, total=total, detail=str(e))

    yield BatchDoneEvent(total=total, prompt_used=prompt_used)
