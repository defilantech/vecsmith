"""LLM-based prompt enhancement via any OpenAI-compatible API."""

import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_SVG = """\
You are an expert at writing detailed image generation prompts. Given a brief user description, \
expand it into a detailed, vivid prompt optimized for a text-to-image model.

Rules:
- Output ONLY the enhanced prompt, no explanations or preamble
- Be specific about colors, composition, lighting, and style
- Include "vector illustration style, clean lines, flat design" to guide SVG-friendly output
- Keep under 200 words
- Describe a single coherent scene
"""

SYSTEM_PROMPT_PHOTO = """\
You are an expert at writing detailed image generation prompts. Given a brief user description, \
expand it into a detailed, vivid prompt optimized for a text-to-image model producing photorealistic images.

Rules:
- Output ONLY the enhanced prompt, no explanations or preamble
- Be specific about colors, composition, lighting, and style
- Guide toward photorealistic output: mention camera type, lens, lighting setup, depth of field, or film stock where appropriate
- Do NOT mention illustration, vector, flat design, or cartoon styles
- Keep under 200 words
- Describe a single coherent scene
"""

# Keep backward-compatible alias
SYSTEM_PROMPT = SYSTEM_PROMPT_SVG


async def enhance_prompt(
    user_prompt: str,
    llm_base_url: str,
    model: str = "default",
    max_tokens: int = 512,
    temperature: float = 0.7,
    output_format: str = "svg",
    api_key: str = "",
) -> str:
    """Enhance a user prompt using an OpenAI-compatible chat completions API.

    Args:
        user_prompt: The user's brief description.
        llm_base_url: Base URL for the LLM API (e.g., http://llm-service:8080/v1).
        model: Model name to use.
        max_tokens: Maximum tokens for the response.
        temperature: Sampling temperature.
        output_format: Target output format ("svg" or "png"). Controls style guidance.

    Returns:
        Enhanced prompt string.
    """
    system_prompt = SYSTEM_PROMPT_PHOTO if output_format == "png" else SYSTEM_PROMPT_SVG
    url = f"{llm_base_url.rstrip('/')}/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()

    data = response.json()
    raw = data["choices"][0]["message"]["content"].strip()
    enhanced = _sanitize_llm_output(raw, fallback=user_prompt)

    logger.info(
        "Enhanced prompt: %d -> %d chars",
        len(user_prompt),
        len(enhanced),
    )
    return enhanced


def _sanitize_llm_output(text: str, fallback: str = "") -> str:
    """Clean common LLM artifacts from enhanced prompt output.

    Small models often wrap output in function calls, JSON tool-call objects,
    markdown fences, or add preamble/labels that would pollute the image
    generation prompt. If the LLM completely fails to produce a useful prompt
    (e.g. outputs only a JSON tool call with no enhancement), falls back to
    the original user prompt.
    """
    # Try to extract from JSON tool-call format:
    # {"name": "expand_prompt", "parameters": {"input_text": "..."}}
    stripped = text.strip()
    if stripped.startswith("{"):
        try:
            obj = json.loads(stripped)
            if isinstance(obj, dict):
                # Extract from {"parameters": {"input_text": "..."}} or similar
                params = obj.get("parameters") or obj.get("params") or {}
                for key in ("input_text", "prompt", "text", "enhanced_prompt", "output"):
                    if key in params and isinstance(params[key], str):
                        extracted = params[key].strip()
                        if extracted:
                            logger.warning("Stripped JSON tool-call wrapper from LLM output")
                            return extracted
                # If JSON but no recognized prompt field, fall back
                logger.warning("LLM returned JSON without extractable prompt: %s", stripped[:200])
                return fallback if fallback else text
        except (json.JSONDecodeError, TypeError):
            pass  # Not valid JSON, continue with other sanitization

    # Strip markdown code fences: ```...```
    text = re.sub(r"^```[\w]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)

    # Strip function-call wrappers: expand_prompt("..."), generate("..."), etc.
    m = re.match(r"^\w+\s*\(\s*[\"'](.+)[\"']\s*\)\s*$", text, re.DOTALL)
    if m:
        text = m.group(1)

    # Strip leading labels: "Enhanced prompt:", "Output:", "Here is...", etc.
    text = re.sub(
        r"^(?:enhanced\s+prompt|output|result|prompt|here\s+is[^:]*)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Strip wrapping quotes
    if len(text) > 2 and text[0] in ('"', "'") and text[-1] == text[0]:
        text = text[1:-1]

    return text.strip()
