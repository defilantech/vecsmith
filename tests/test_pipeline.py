"""Tests for the pipeline orchestration."""

import base64
import io
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from src.config import Settings
from src.orchestrator.pipeline import run_pipeline
from src.orchestrator.schemas import GenerateRequest


def _make_test_image():
    img = Image.new("RGB", (64, 64), "red")
    return img


@pytest.fixture
def settings():
    return Settings(
        llm_base_url="http://test-llm:8080/v1",
        flux_base_url="http://test-flux:8081",
    )


class TestPipeline:
    @pytest.mark.asyncio
    async def test_full_pipeline(self, settings):
        request = GenerateRequest(prompt="a red circle")

        with (
            patch(
                "src.orchestrator.pipeline.enhance_prompt",
                new_callable=AsyncMock,
                return_value="A vibrant red circle, vector illustration style",
            ) as mock_enhance,
            patch(
                "src.orchestrator.pipeline.generate_image",
                new_callable=AsyncMock,
                return_value=(_make_test_image(), 2.5),
            ) as mock_generate,
            patch(
                "src.orchestrator.pipeline.vectorize_pil_image_async",
                new_callable=AsyncMock,
                return_value='<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><circle cx="32" cy="32" r="30" fill="red"/></svg>',
            ) as mock_vectorize,
        ):
            result = await run_pipeline(request, settings)

        assert "<svg" in result.svg
        assert result.output_format == "svg"
        assert result.png_base64 is None
        assert result.original_prompt == "a red circle"
        assert result.prompt_used == "A vibrant red circle, vector illustration style"
        assert result.timings.prompt_enhance_s is not None
        assert result.timings.image_generate_s is not None
        assert result.timings.vectorize_s is not None
        assert result.timings.svg_optimize_s is not None
        assert result.timings.total_s >= 0  # May be 0.0 with mocked stages
        assert result.svg_size_bytes > 0

        mock_enhance.assert_called_once()
        mock_generate.assert_called_once()
        mock_vectorize.assert_called_once()

    @pytest.mark.asyncio
    async def test_png_output(self, settings):
        request = GenerateRequest(prompt="a red circle", output_format="png")

        with (
            patch(
                "src.orchestrator.pipeline.enhance_prompt",
                new_callable=AsyncMock,
                return_value="A vibrant red circle",
            ) as mock_enhance,
            patch(
                "src.orchestrator.pipeline.generate_image",
                new_callable=AsyncMock,
                return_value=(_make_test_image(), 2.5),
            ) as mock_generate,
            patch(
                "src.orchestrator.pipeline.vectorize_pil_image_async",
                new_callable=AsyncMock,
            ) as mock_vectorize,
        ):
            result = await run_pipeline(request, settings)

        assert result.output_format == "png"
        assert result.svg == ""
        assert result.png_base64 is not None
        # Verify it's valid base64-encoded PNG
        decoded = base64.b64decode(result.png_base64)
        assert decoded[:4] == b"\x89PNG"
        assert result.timings.image_generate_s is not None
        assert result.timings.vectorize_s is None
        assert result.timings.svg_optimize_s is None
        assert result.svg_size_bytes > 0

        mock_enhance.assert_called_once()
        mock_generate.assert_called_once()
        mock_vectorize.assert_not_called()

    @pytest.mark.asyncio
    async def test_pipeline_skip_enhance(self, settings):
        request = GenerateRequest(prompt="detailed prompt already", skip_enhance=True)

        with (
            patch(
                "src.orchestrator.pipeline.enhance_prompt",
                new_callable=AsyncMock,
            ) as mock_enhance,
            patch(
                "src.orchestrator.pipeline.generate_image",
                new_callable=AsyncMock,
                return_value=(_make_test_image(), 1.0),
            ),
            patch(
                "src.orchestrator.pipeline.vectorize_pil_image_async",
                new_callable=AsyncMock,
                return_value='<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect width="64" height="64" fill="blue"/></svg>',
            ),
        ):
            result = await run_pipeline(request, settings)

        mock_enhance.assert_not_called()
        assert result.prompt_used == "detailed prompt already"
        assert result.timings.prompt_enhance_s is None

    @pytest.mark.asyncio
    async def test_pipeline_passes_settings(self, settings):
        settings.flux_width = 512
        settings.flux_height = 512
        request = GenerateRequest(prompt="test", width=512, height=512, seed=42)

        with (
            patch(
                "src.orchestrator.pipeline.enhance_prompt",
                new_callable=AsyncMock,
                return_value="enhanced test",
            ),
            patch(
                "src.orchestrator.pipeline.generate_image",
                new_callable=AsyncMock,
                return_value=(_make_test_image(), 1.0),
            ) as mock_generate,
            patch(
                "src.orchestrator.pipeline.vectorize_pil_image_async",
                new_callable=AsyncMock,
                return_value='<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"></svg>',
            ),
        ):
            await run_pipeline(request, settings)

        call_kwargs = mock_generate.call_args
        assert call_kwargs.kwargs["width"] == 512
        assert call_kwargs.kwargs["height"] == 512
        assert call_kwargs.kwargs["seed"] == 42
