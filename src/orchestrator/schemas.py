"""Pydantic models for API request/response."""

import random
from typing import Literal

from pydantic import BaseModel, Field


class StageTimings(BaseModel):
    prompt_enhance_s: float | None = None
    image_generate_s: float | None = None
    vectorize_s: float | None = None
    svg_optimize_s: float | None = None
    total_s: float = 0.0


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000, description="Text description of the desired image")
    width: int = Field(default=1024, ge=256, le=2048, description="Image width in pixels")
    height: int = Field(default=1024, ge=256, le=2048, description="Image height in pixels")
    skip_enhance: bool = Field(default=False, description="Skip LLM prompt enhancement")
    seed: int | None = Field(default=None, description="Optional seed for reproducible generation")
    num_inference_steps: int = Field(default=4, ge=1, le=50, description="Flux diffusion steps")
    output_format: Literal["svg", "png"] = Field(default="svg", description="Output format")


class GenerateResponse(BaseModel):
    svg: str = Field(default="", description="Generated SVG content (empty when format is png)")
    png_base64: str | None = Field(default=None, description="Base64-encoded PNG (only when format is png)")
    output_format: str = Field(default="svg", description="Output format used")
    prompt_used: str = Field(..., description="The prompt used for image generation (original or enhanced)")
    timings: StageTimings
    svg_size_bytes: int
    original_prompt: str


class BatchGenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000, description="Text description of the desired image")
    count: int = Field(default=1, ge=1, le=10, description="Number of variations to generate")
    width: int = Field(default=1024, ge=256, le=2048, description="Image width in pixels")
    height: int = Field(default=1024, ge=256, le=2048, description="Image height in pixels")
    skip_enhance: bool = Field(default=False, description="Skip LLM prompt enhancement")
    seed: int | None = Field(default=None, description="Optional base seed (iterations get seed, seed+1, ...)")
    num_inference_steps: int = Field(default=4, ge=1, le=50, description="Flux diffusion steps")
    output_format: Literal["svg", "png"] = Field(default="svg", description="Output format")

    def seed_for_iteration(self, index: int) -> int:
        base = self.seed if self.seed is not None else random.randint(0, 2**32 - 1)
        return base + index


class BatchProgressEvent(BaseModel):
    event: Literal["progress"] = "progress"
    index: int
    total: int
    stage: Literal["generating", "vectorizing", "optimizing"]


class BatchResultEvent(BaseModel):
    event: Literal["result"] = "result"
    index: int
    total: int
    result: GenerateResponse


class BatchDoneEvent(BaseModel):
    event: Literal["done"] = "done"
    total: int
    prompt_used: str


class BatchErrorEvent(BaseModel):
    event: Literal["error"] = "error"
    index: int
    total: int
    detail: str
