"""Tests for image generation stage."""

import base64
import io

import pytest
import respx
from httpx import Response
from PIL import Image

from src.stages.image_generate import generate_image


@pytest.fixture
def mock_flux_response():
    """Create a mock Flux server response with a tiny test image."""
    img = Image.new("RGB", (64, 64), "blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return {
        "image_base64": b64,
        "format": "png",
        "width": 64,
        "height": 64,
        "generation_time_s": 1.234,
    }


class TestImageGenerate:
    @respx.mock
    @pytest.mark.asyncio
    async def test_generate_image(self, mock_flux_response):
        respx.post("http://test-flux:8081/generate").mock(
            return_value=Response(200, json=mock_flux_response)
        )

        image, gen_time = await generate_image(
            prompt="a blue square",
            flux_base_url="http://test-flux:8081",
        )

        assert isinstance(image, Image.Image)
        assert image.size == (64, 64)
        assert gen_time == 1.234

    @respx.mock
    @pytest.mark.asyncio
    async def test_generate_image_with_seed(self, mock_flux_response):
        route = respx.post("http://test-flux:8081/generate").mock(
            return_value=Response(200, json=mock_flux_response)
        )

        await generate_image(
            prompt="a red circle",
            flux_base_url="http://test-flux:8081",
            seed=42,
        )

        import json

        body = json.loads(route.calls[0].request.content)
        assert body["seed"] == 42

    @respx.mock
    @pytest.mark.asyncio
    async def test_generate_image_custom_size(self, mock_flux_response):
        route = respx.post("http://test-flux:8081/generate").mock(
            return_value=Response(200, json=mock_flux_response)
        )

        await generate_image(
            prompt="test",
            flux_base_url="http://test-flux:8081",
            width=512,
            height=768,
            num_inference_steps=8,
        )

        import json

        body = json.loads(route.calls[0].request.content)
        assert body["width"] == 512
        assert body["height"] == 768
        assert body["num_inference_steps"] == 8

    @respx.mock
    @pytest.mark.asyncio
    async def test_generate_image_server_error(self):
        respx.post("http://test-flux:8081/generate").mock(
            return_value=Response(503, json={"detail": "Model not loaded"})
        )

        with pytest.raises(Exception):
            await generate_image(
                prompt="test",
                flux_base_url="http://test-flux:8081",
            )
