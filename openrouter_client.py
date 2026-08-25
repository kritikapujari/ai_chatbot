"""
openrouter_client.py

OpenRouter LLM backend wrapper — mirrors the interface of ollama_client.py.

Uses the OpenAI-compatible API provided by OpenRouter.
Reads OPENROUTER_API_KEY and OPENROUTER_MODEL from environment.
Never hard-codes or exposes API keys.
"""

from __future__ import annotations

import os
from typing import List, Optional, Tuple

OPENROUTER_AVAILABLE = False
try:
    # pyrefly: ignore [missing-import]
    from openai import OpenAI
    OPENROUTER_AVAILABLE = True
except ImportError:
    pass


class OpenRouterError(Exception):
    """Raised when OpenRouter API calls fail."""
    pass


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Curated list of popular OpenRouter models
POPULAR_MODELS = [
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3-haiku",
    "google/gemini-flash-1.5",
    "google/gemini-pro-1.5",
    "meta-llama/llama-3.1-70b-instruct",
    "meta-llama/llama-3.1-8b-instruct",
    "mistralai/mistral-7b-instruct",
    "mistralai/mixtral-8x7b-instruct",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "openai/gpt-3.5-turbo",
    "qwen/qwen-2.5-72b-instruct",
    "deepseek/deepseek-r1",
]


def _check_available():
    if not OPENROUTER_AVAILABLE:
        raise OpenRouterError(
            "openai package is not installed. Run: pip install openai"
        )


def get_api_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "").strip()


def get_default_model() -> str:
    return os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet").strip()


def list_models() -> List[str]:
    """
    Attempts to fetch the live model list from OpenRouter.
    Falls back to the curated list if the request fails.
    """
    api_key = get_api_key()
    if not api_key or not OPENROUTER_AVAILABLE:
        return POPULAR_MODELS

    try:
        import requests
        resp = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=5,
        )
        if resp.ok:
            data = resp.json().get("data", [])
            return sorted([m["id"] for m in data if m.get("id")])
    except Exception:
        pass
    return POPULAR_MODELS


REASONING_INSTRUCTIONS = """
For every reply, respond in two parts: an ANALYSIS and an ANSWER.

ANALYSIS: A concise 3-6 bullet summary of your approach, what you understood,
key concepts considered, and any assumptions or limitations.
Do NOT write private chain-of-thought or internal reasoning traces.

ANSWER: The complete, final response to the user.

Respond with ONLY a valid JSON object (no markdown fences):
{"analysis": "<summary>", "answer": "<final answer>"}
""".strip()


def chat(
    model: str,
    system_prompt: str,
    history: list,
    user_message: str,
    temperature: float = 0.7,
) -> Tuple[str, str]:
    """
    Send a chat request to OpenRouter.
    Returns (analysis, answer) matching the ollama_client.chat() interface.
    """
    _check_available()
    api_key = get_api_key()
    if not api_key:
        raise OpenRouterError(
            "OPENROUTER_API_KEY is not set. Add it to your .env file."
        )

    combined_system = f"{system_prompt}\n\n{REASONING_INSTRUCTIONS}".strip() if system_prompt else REASONING_INSTRUCTIONS

    messages = [{"role": "system", "content": combined_system}]
    for turn in history:
        messages.append({"role": "user", "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["answer"]})
    messages.append({"role": "user", "content": user_message})

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": "https://github.com/kritikapujari/ai_chatbot",
                "X-Title": "AI Chatbot",
            },
        )
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        raw_text = response.choices[0].message.content or ""
        return _parse_response(raw_text)

    except OpenRouterError:
        raise
    except Exception as exc:
        raise OpenRouterError(f"OpenRouter API error: {exc}") from exc


def _parse_response(raw_text: str) -> Tuple[str, str]:
    """Parse {analysis, answer} JSON from OpenRouter response."""
    import json

    raw_text = raw_text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:]
        raw_text = raw_text.strip()

    try:
        data = json.loads(raw_text)
        if isinstance(data, dict) and "answer" in data:
            return str(data.get("analysis", "")).strip(), str(data["answer"]).strip()
    except Exception:
        pass

    return "No structured analysis returned.", raw_text
