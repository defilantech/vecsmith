"""Standalone FastAPI server for Flux image generation."""

import asyncio
import base64
import io
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .model_loader import generate_image, load_flux_pipeline

logger = logging.getLogger(__name__)

# Global pipeline reference, loaded at startup
_pipe = None
_gpu_semaphore = asyncio.Semaphore(1)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    width: int = Field(default=1024, ge=256, le=2048)
    height: int = Field(default=1024, ge=256, le=2048)
    num_inference_steps: int = Field(default=4, ge=1, le=50)
    seed: int | None = Field(default=None)
    output_format: str = Field(default="png", pattern="^(png|jpeg)$")


class GenerateResponse(BaseModel):
    image_base64: str
    format: str
    width: int
    height: int
    generation_time_s: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipe
    quantize_fp8 = os.environ.get("FLUX_QUANTIZE_FP8", "true").lower() in ("true", "1", "yes")
    logger.info("Loading Flux model (fp8=%s)...", quantize_fp8)
    _pipe = load_flux_pipeline(quantize_fp8=quantize_fp8)
    logger.info("Flux model ready")
    yield
    _pipe = None
    logger.info("Flux server shut down")


app = FastAPI(title="Flux Image Generation Server", lifespan=lifespan)


@app.get("/health")
async def health():
    if _pipe is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "healthy", "model": "FLUX.2-klein-4B"}


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    if _pipe is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    start = time.monotonic()

    async with _gpu_semaphore:
        image = await asyncio.to_thread(
            generate_image,
            _pipe,
            req.prompt,
            req.width,
            req.height,
            req.num_inference_steps,
            req.seed,
        )

    elapsed = time.monotonic() - start

    buf = io.BytesIO()
    fmt = req.output_format.upper()
    if fmt == "JPEG":
        image.save(buf, format="JPEG", quality=95)
    else:
        image.save(buf, format="PNG")
    buf.seek(0)

    image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    logger.info(
        "Generated %dx%d image in %.2fs (%d steps)",
        req.width,
        req.height,
        elapsed,
        req.num_inference_steps,
    )

    return GenerateResponse(
        image_base64=image_b64,
        format=req.output_format,
        width=req.width,
        height=req.height,
        generation_time_s=round(elapsed, 3),
    )


def main():
    import uvicorn

    host = os.environ.get("FLUX_HOST", "0.0.0.0")
    port = int(os.environ.get("FLUX_PORT", "8081"))

    uvicorn.run(
        "src.flux_server.server:app",
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
