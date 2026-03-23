"""Tests for the FastAPI API endpoints."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.orchestrator.app import create_app
from src.orchestrator.schemas import (
    BatchDoneEvent,
    BatchProgressEvent,
    BatchResultEvent,
    GenerateResponse,
    StageTimings,
)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "llm_url" in data
        assert "flux_url" in data


class TestGenerateEndpoint:
    @pytest.mark.asyncio
    async def test_generate(self, client):
        mock_response = GenerateResponse(
            svg='<svg xmlns="http://www.w3.org/2000/svg"><circle/></svg>',
            prompt_used="enhanced prompt",
            timings=StageTimings(
                prompt_enhance_s=1.0,
                image_generate_s=8.0,
                vectorize_s=0.5,
                svg_optimize_s=0.01,
                total_s=9.51,
            ),
            svg_size_bytes=55,
            original_prompt="test",
        )

        with patch(
            "src.orchestrator.routes.run_pipeline",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await client.post(
                "/generate",
                json={"prompt": "a red circle"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "<svg" in data["svg"]
        assert "timings" in data
        assert data["timings"]["total_s"] == 9.51
        assert data["output_format"] == "svg"
        assert data["png_base64"] is None

    @pytest.mark.asyncio
    async def test_generate_png(self, client):
        mock_response = GenerateResponse(
            svg="",
            png_base64="iVBORw0KGgo=",
            output_format="png",
            prompt_used="enhanced prompt",
            timings=StageTimings(
                prompt_enhance_s=1.0,
                image_generate_s=8.0,
                total_s=9.0,
            ),
            svg_size_bytes=1024,
            original_prompt="test",
        )

        with patch(
            "src.orchestrator.routes.run_pipeline",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await client.post(
                "/generate",
                json={"prompt": "a red circle", "output_format": "png"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["output_format"] == "png"
        assert data["png_base64"] == "iVBORw0KGgo="
        assert data["svg"] == ""

    @pytest.mark.asyncio
    async def test_generate_validation_error(self, client):
        response = await client.post("/generate", json={"prompt": ""})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_generate_missing_prompt(self, client):
        response = await client.post("/generate", json={})
        assert response.status_code == 422


class TestGenerateSvgOnlyEndpoint:
    @pytest.mark.asyncio
    async def test_svg_only(self, client):
        mock_response = GenerateResponse(
            svg='<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>',
            prompt_used="test",
            timings=StageTimings(total_s=5.0),
            svg_size_bytes=48,
            original_prompt="test",
        )

        with patch(
            "src.orchestrator.routes.run_pipeline",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            response = await client.post(
                "/generate/svg-only",
                json={"prompt": "a blue square"},
            )

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/svg+xml"
        assert response.headers["x-pipeline-time"] == "5.0"
        assert "<svg" in response.text


def _make_batch_events(count=2):
    """Create a sequence of batch events for mocking."""
    events = []
    for i in range(count):
        events.append(BatchProgressEvent(index=i, total=count, stage="generating"))
        events.append(
            BatchResultEvent(
                index=i,
                total=count,
                result=GenerateResponse(
                    svg=f'<svg xmlns="http://www.w3.org/2000/svg"><rect id="{i}"/></svg>',
                    prompt_used="enhanced",
                    timings=StageTimings(image_generate_s=1.0, total_s=1.5),
                    svg_size_bytes=50,
                    original_prompt="test",
                ),
            )
        )
    events.append(BatchDoneEvent(total=count, prompt_used="enhanced"))
    return events


def _parse_sse_events(text: str) -> list[dict]:
    """Parse SSE text into a list of {event, data} dicts."""
    events = []
    current_event = None
    current_data = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current_data.append(line[len("data:"):].strip())
        elif line == "" and current_event is not None:
            events.append({"event": current_event, "data": json.loads("".join(current_data))})
            current_event = None
            current_data = []
    return events


class TestBatchEndpoint:
    @pytest.mark.asyncio
    async def test_batch_returns_sse_stream(self, client):
        async def mock_generator(request, settings):
            for event in _make_batch_events(2):
                yield event

        with patch("src.orchestrator.routes.run_batch_pipeline", side_effect=mock_generator):
            response = await client.post(
                "/generate/batch",
                json={"prompt": "a red circle", "count": 2, "seed": 42},
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        events = _parse_sse_events(response.text)
        event_types = [e["event"] for e in events]
        assert event_types.count("progress") == 2
        assert event_types.count("result") == 2
        assert event_types.count("done") == 1

    @pytest.mark.asyncio
    async def test_batch_results_contain_svg(self, client):
        async def mock_generator(request, settings):
            for event in _make_batch_events(1):
                yield event

        with patch("src.orchestrator.routes.run_batch_pipeline", side_effect=mock_generator):
            response = await client.post(
                "/generate/batch",
                json={"prompt": "a blue square", "count": 1},
            )

        events = _parse_sse_events(response.text)
        result_events = [e for e in events if e["event"] == "result"]
        assert len(result_events) == 1
        assert "<svg" in result_events[0]["data"]["result"]["svg"]

    @pytest.mark.asyncio
    async def test_batch_validation_error(self, client):
        response = await client.post(
            "/generate/batch",
            json={"prompt": "test", "count": 20},
        )
        assert response.status_code == 422
