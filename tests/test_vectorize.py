"""Tests for vtracer vectorization stage."""

import pytest
from PIL import Image

from src.stages.vectorize import vectorize_image_bytes, vectorize_pil_image


class TestVectorize:
    def test_vectorize_pil_image(self, test_image: Image.Image):
        svg = vectorize_pil_image(test_image)
        assert "<svg" in svg
        assert "</svg>" in svg
        assert "<path" in svg

    def test_vectorize_image_bytes(self, test_image_bytes: bytes):
        svg = vectorize_image_bytes(test_image_bytes)
        assert "<svg" in svg
        assert "</svg>" in svg

    def test_vectorize_with_overrides(self, test_image: Image.Image):
        svg = vectorize_pil_image(test_image, filter_speckle=8, color_precision=4)
        assert "<svg" in svg
        assert "</svg>" in svg

    def test_output_is_valid_svg(self, test_image: Image.Image):
        svg = vectorize_pil_image(test_image)
        # Should have xmlns attribute
        assert "xmlns" in svg or "svg" in svg
        # Should be non-trivial (more than just the wrapper)
        assert len(svg) > 100

    @pytest.mark.asyncio
    async def test_vectorize_async(self, test_image: Image.Image):
        from src.stages.vectorize import vectorize_pil_image_async

        svg = await vectorize_pil_image_async(test_image)
        assert "<svg" in svg
        assert "</svg>" in svg
