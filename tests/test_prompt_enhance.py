"""Tests for prompt enhancement stage."""

import pytest
import respx
from httpx import Response

from src.stages.prompt_enhance import SYSTEM_PROMPT, SYSTEM_PROMPT_PHOTO, SYSTEM_PROMPT_SVG, _sanitize_llm_output, enhance_prompt


@pytest.fixture
def mock_llm_response():
    """Mock OpenAI-compatible chat completion response."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": (
                        "A warm, inviting vector illustration of a relaxed mother "
                        "sitting on a cozy sofa in a sunlit living room, reading a "
                        "picture book to her toddler. Soft pastel colors, clean lines, "
                        "flat design style with gentle shadows. Potted plants on the "
                        "windowsill, a cat sleeping nearby, warm afternoon light "
                        "streaming through curtains."
                    ),
                },
                "finish_reason": "stop",
            }
        ],
    }


class TestPromptEnhance:
    @respx.mock
    @pytest.mark.asyncio
    async def test_enhance_prompt(self, mock_llm_response):
        respx.post("http://test-llm:8080/v1/chat/completions").mock(
            return_value=Response(200, json=mock_llm_response)
        )

        result = await enhance_prompt(
            "relaxed mom reading to kid",
            llm_base_url="http://test-llm:8080/v1",
            model="test-model",
        )

        assert "vector illustration" in result
        assert len(result) > len("relaxed mom reading to kid")

    @respx.mock
    @pytest.mark.asyncio
    async def test_enhance_prompt_sends_correct_payload(self, mock_llm_response):
        route = respx.post("http://test-llm:8080/v1/chat/completions").mock(
            return_value=Response(200, json=mock_llm_response)
        )

        await enhance_prompt(
            "a blue star",
            llm_base_url="http://test-llm:8080/v1",
            model="my-model",
            max_tokens=256,
            temperature=0.5,
        )

        request = route.calls[0].request
        import json

        body = json.loads(request.content)
        assert body["model"] == "my-model"
        assert body["max_tokens"] == 256
        assert body["temperature"] == 0.5
        assert body["messages"][0]["content"] == SYSTEM_PROMPT
        assert body["messages"][1]["content"] == "a blue star"

    @respx.mock
    @pytest.mark.asyncio
    async def test_enhance_prompt_handles_error(self):
        respx.post("http://test-llm:8080/v1/chat/completions").mock(
            return_value=Response(500, json={"error": "model not loaded"})
        )

        with pytest.raises(Exception):
            await enhance_prompt(
                "test prompt",
                llm_base_url="http://test-llm:8080/v1",
            )

    @respx.mock
    @pytest.mark.asyncio
    async def test_enhance_prompt_png_uses_photo_system_prompt(self, mock_llm_response):
        route = respx.post("http://test-llm:8080/v1/chat/completions").mock(
            return_value=Response(200, json=mock_llm_response)
        )

        await enhance_prompt(
            "a mountain landscape",
            llm_base_url="http://test-llm:8080/v1",
            output_format="png",
        )

        import json

        body = json.loads(route.calls[0].request.content)
        assert body["messages"][0]["content"] == SYSTEM_PROMPT_PHOTO
        assert "photorealistic" in body["messages"][0]["content"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_enhance_prompt_svg_uses_svg_system_prompt(self, mock_llm_response):
        route = respx.post("http://test-llm:8080/v1/chat/completions").mock(
            return_value=Response(200, json=mock_llm_response)
        )

        await enhance_prompt(
            "a mountain landscape",
            llm_base_url="http://test-llm:8080/v1",
            output_format="svg",
        )

        import json

        body = json.loads(route.calls[0].request.content)
        assert body["messages"][0]["content"] == SYSTEM_PROMPT_SVG

    def test_system_prompt_content(self):
        assert "vector illustration" in SYSTEM_PROMPT
        assert "flat design" in SYSTEM_PROMPT

    def test_photo_prompt_no_illustration_language(self):
        assert "vector" not in SYSTEM_PROMPT_PHOTO.lower() or "Do NOT mention" in SYSTEM_PROMPT_PHOTO
        assert "photorealistic" in SYSTEM_PROMPT_PHOTO


class TestSanitizeLlmOutput:
    def test_passthrough_clean_text(self):
        text = "A beautiful sunset over the ocean with warm golden light"
        assert _sanitize_llm_output(text) == text

    def test_strips_function_call_wrapper(self):
        text = 'expand_prompt("A beautiful sunset over the ocean")'
        assert _sanitize_llm_output(text) == "A beautiful sunset over the ocean"

    def test_strips_function_call_single_quotes(self):
        text = "generate('A beautiful sunset over the ocean')"
        assert _sanitize_llm_output(text) == "A beautiful sunset over the ocean"

    def test_strips_markdown_code_fences(self):
        text = "```\nA beautiful sunset over the ocean\n```"
        assert _sanitize_llm_output(text) == "A beautiful sunset over the ocean"

    def test_strips_markdown_code_fences_with_lang(self):
        text = "```text\nA beautiful sunset over the ocean\n```"
        assert _sanitize_llm_output(text) == "A beautiful sunset over the ocean"

    def test_strips_leading_label(self):
        text = "Enhanced prompt: A beautiful sunset over the ocean"
        assert _sanitize_llm_output(text) == "A beautiful sunset over the ocean"

    def test_strips_here_is_preamble(self):
        text = "Here is the enhanced prompt: A beautiful sunset over the ocean"
        assert _sanitize_llm_output(text) == "A beautiful sunset over the ocean"

    def test_strips_wrapping_quotes(self):
        text = '"A beautiful sunset over the ocean"'
        assert _sanitize_llm_output(text) == "A beautiful sunset over the ocean"

    def test_strips_combined_artifacts(self):
        text = '```\nexpand_prompt("A beautiful sunset")\n```'
        result = _sanitize_llm_output(text)
        assert result == "A beautiful sunset"

    def test_strips_json_tool_call_input_text(self):
        text = '{"name": "expand_prompt", "parameters": {"input_text": "A beautiful sunset over the ocean"}}'
        assert _sanitize_llm_output(text) == "A beautiful sunset over the ocean"

    def test_strips_json_tool_call_prompt_key(self):
        text = '{"name": "generate", "parameters": {"prompt": "A mountain landscape at dawn"}}'
        assert _sanitize_llm_output(text) == "A mountain landscape at dawn"

    def test_json_tool_call_no_prompt_field_uses_fallback(self):
        text = '{"name": "expand_prompt", "parameters": {"unknown_key": "value"}}'
        assert _sanitize_llm_output(text, fallback="original prompt") == "original prompt"

    def test_json_tool_call_no_fallback_returns_raw(self):
        text = '{"name": "expand_prompt", "parameters": {"unknown_key": "value"}}'
        assert _sanitize_llm_output(text) == text
