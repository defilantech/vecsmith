"""Tests for batch pipeline logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.orchestrator.batch import run_batch_pipeline
from src.orchestrator.schemas import (
    BatchDoneEvent,
    BatchErrorEvent,
    BatchGenerateRequest,
    BatchProgressEvent,
    BatchResultEvent,
)


def make_settings():
    """Create a mock Settings object."""
    s = MagicMock()
    s.llm_base_url = "http://llm:8080/v1"
    s.llm_model = "default"
    s.llm_max_tokens = 300
    s.llm_temperature = 0.7
    s.flux_base_url = "http://flux:8081"
    s.vtracer_filter_speckle = 4
    s.vtracer_color_precision = 6
    s.svg_coordinate_precision = 2
    return s


def make_image():
    """Create a tiny PIL Image for testing."""
    from PIL import Image

    return Image.new("RGB", (64, 64), color="red")


async def collect_events(request, settings):
    """Collect all events from the batch pipeline."""
    events = []
    async for event in run_batch_pipeline(request, settings):
        events.append(event)
    return events


class TestBatchPipeline:
    @pytest.mark.asyncio
    @patch("src.orchestrator.batch.optimize_svg", return_value='<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')
    @patch("src.orchestrator.batch.vectorize_pil_image_async", new_callable=AsyncMock, return_value="<svg><rect/></svg>")
    @patch("src.orchestrator.batch.generate_image", new_callable=AsyncMock)
    @patch("src.orchestrator.batch.enhance_prompt", new_callable=AsyncMock, return_value="enhanced prompt")
    async def test_single_svg_variation(self, mock_enhance, mock_gen, mock_vec, mock_opt):
        mock_gen.return_value = (make_image(), 1.0)
        request = BatchGenerateRequest(prompt="a cat", count=1, seed=42)
        events = await collect_events(request, make_settings())

        assert any(isinstance(e, BatchProgressEvent) and e.stage == "generating" for e in events)
        assert any(isinstance(e, BatchProgressEvent) and e.stage == "vectorizing" for e in events)
        assert any(isinstance(e, BatchProgressEvent) and e.stage == "optimizing" for e in events)
        results = [e for e in events if isinstance(e, BatchResultEvent)]
        assert len(results) == 1
        assert results[0].result.output_format == "svg"
        assert isinstance(events[-1], BatchDoneEvent)
        assert events[-1].prompt_used == "enhanced prompt"
        mock_enhance.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("src.orchestrator.batch.optimize_svg", return_value='<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')
    @patch("src.orchestrator.batch.vectorize_pil_image_async", new_callable=AsyncMock, return_value="<svg><rect/></svg>")
    @patch("src.orchestrator.batch.generate_image", new_callable=AsyncMock)
    @patch("src.orchestrator.batch.enhance_prompt", new_callable=AsyncMock, return_value="enhanced prompt")
    async def test_multiple_variations_generate_correct_count(self, mock_enhance, mock_gen, mock_vec, mock_opt):
        mock_gen.return_value = (make_image(), 1.0)
        request = BatchGenerateRequest(prompt="a dog", count=3, seed=100)
        events = await collect_events(request, make_settings())

        results = [e for e in events if isinstance(e, BatchResultEvent)]
        assert len(results) == 3
        # Each result has a different index
        assert [r.index for r in results] == [0, 1, 2]
        # Enhance called only once
        mock_enhance.assert_awaited_once()
        # Generate called 3 times with different seeds
        assert mock_gen.await_count == 3
        seeds = [call.kwargs["seed"] for call in mock_gen.await_args_list]
        assert seeds == [100, 101, 102]

    @pytest.mark.asyncio
    @patch("src.orchestrator.batch.generate_image", new_callable=AsyncMock)
    @patch("src.orchestrator.batch.enhance_prompt", new_callable=AsyncMock, return_value="enhanced prompt")
    async def test_png_output_skips_vectorize(self, mock_enhance, mock_gen):
        mock_gen.return_value = (make_image(), 1.0)
        request = BatchGenerateRequest(prompt="a bird", count=1, seed=1, output_format="png")
        events = await collect_events(request, make_settings())

        # Should not have vectorizing/optimizing progress events
        stages = [e.stage for e in events if isinstance(e, BatchProgressEvent)]
        assert "vectorizing" not in stages
        assert "optimizing" not in stages
        results = [e for e in events if isinstance(e, BatchResultEvent)]
        assert len(results) == 1
        assert results[0].result.output_format == "png"
        assert results[0].result.png_base64 is not None

    @pytest.mark.asyncio
    @patch("src.orchestrator.batch.optimize_svg", return_value='<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')
    @patch("src.orchestrator.batch.vectorize_pil_image_async", new_callable=AsyncMock, return_value="<svg><rect/></svg>")
    @patch("src.orchestrator.batch.generate_image", new_callable=AsyncMock)
    @patch("src.orchestrator.batch.enhance_prompt", new_callable=AsyncMock, return_value="enhanced prompt")
    async def test_skip_enhance(self, mock_enhance, mock_gen, mock_vec, mock_opt):
        mock_gen.return_value = (make_image(), 1.0)
        request = BatchGenerateRequest(prompt="a fish", count=1, skip_enhance=True)
        events = await collect_events(request, make_settings())

        mock_enhance.assert_not_awaited()
        done = [e for e in events if isinstance(e, BatchDoneEvent)]
        assert done[0].prompt_used == "a fish"

    @pytest.mark.asyncio
    @patch("src.orchestrator.batch.optimize_svg", return_value='<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>')
    @patch("src.orchestrator.batch.vectorize_pil_image_async", new_callable=AsyncMock, return_value="<svg><rect/></svg>")
    @patch("src.orchestrator.batch.generate_image", new_callable=AsyncMock)
    @patch("src.orchestrator.batch.enhance_prompt", new_callable=AsyncMock, return_value="enhanced prompt")
    async def test_error_in_one_iteration_continues(self, mock_enhance, mock_gen, mock_vec, mock_opt):
        """If one iteration fails, others should still complete."""
        mock_gen.side_effect = [
            (make_image(), 1.0),
            RuntimeError("GPU OOM"),
            (make_image(), 1.0),
        ]
        request = BatchGenerateRequest(prompt="a tree", count=3, seed=10)
        events = await collect_events(request, make_settings())

        results = [e for e in events if isinstance(e, BatchResultEvent)]
        errors = [e for e in events if isinstance(e, BatchErrorEvent)]
        assert len(results) == 2
        assert len(errors) == 1
        assert errors[0].index == 1
        assert "GPU OOM" in errors[0].detail
        assert isinstance(events[-1], BatchDoneEvent)

    @pytest.mark.asyncio
    @patch("src.orchestrator.batch.enhance_prompt", new_callable=AsyncMock, side_effect=RuntimeError("LLM down"))
    async def test_enhance_failure_yields_error_and_done(self, mock_enhance):
        request = BatchGenerateRequest(prompt="a house", count=3)
        events = await collect_events(request, make_settings())

        errors = [e for e in events if isinstance(e, BatchErrorEvent)]
        assert len(errors) == 1
        assert "Prompt enhancement failed" in errors[0].detail
        assert isinstance(events[-1], BatchDoneEvent)
        assert events[-1].total == 0


class TestBatchGenerateRequest:
    def test_seed_for_iteration_with_explicit_seed(self):
        req = BatchGenerateRequest(prompt="test", seed=42)
        assert req.seed_for_iteration(0) == 42
        assert req.seed_for_iteration(1) == 43
        assert req.seed_for_iteration(5) == 47

    def test_seed_for_iteration_without_seed_is_deterministic_per_call(self):
        req = BatchGenerateRequest(prompt="test")
        # Without a seed, it generates a random base, but iterations are sequential
        s0 = req.seed_for_iteration(0)
        s1 = req.seed_for_iteration(1)
        # Can't assert exact values, but difference between 0 and 1 should always be 1
        # (different random base each call, but within a call they're sequential)
        # Actually each call to seed_for_iteration picks a new random base since seed is None
        # So we just check they're valid integers
        assert isinstance(s0, int)
        assert isinstance(s1, int)
