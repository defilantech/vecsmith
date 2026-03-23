"""FastAPI route handlers."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sse_starlette.sse import EventSourceResponse

from ..config import Settings, get_settings
from .batch import run_batch_pipeline
from .pipeline import run_pipeline
from .schemas import BatchGenerateRequest, GenerateRequest, GenerateResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health(settings: Settings = Depends(get_settings)):
    return {
        "status": "healthy",
        "llm_url": settings.llm_base_url,
        "flux_url": settings.flux_base_url,
    }


@router.post("/generate", response_model=GenerateResponse)
async def generate(
    request: GenerateRequest,
    settings: Settings = Depends(get_settings),
):
    """Generate an SVG from a text description.

    Returns JSON with the SVG string, timings, and metadata.
    """
    try:
        return await run_pipeline(request, settings)
    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/svg-only")
async def generate_svg_only(
    request: GenerateRequest,
    settings: Settings = Depends(get_settings),
):
    """Generate an SVG from a text description.

    Returns raw SVG with image/svg+xml content type.
    """
    try:
        result = await run_pipeline(request, settings)
        return Response(
            content=result.svg,
            media_type="image/svg+xml",
            headers={
                "X-Pipeline-Time": str(result.timings.total_s),
                "X-SVG-Size": str(result.svg_size_bytes),
            },
        )
    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/batch")
async def generate_batch(
    request: BatchGenerateRequest,
    settings: Settings = Depends(get_settings),
):
    """Generate multiple variations via SSE.

    Enhances the prompt once, then generates N images with different seeds,
    streaming each result as it completes.
    """

    async def event_generator():
        async for event in run_batch_pipeline(request, settings):
            yield {"event": event.event, "data": event.model_dump_json()}

    return EventSourceResponse(event_generator())
