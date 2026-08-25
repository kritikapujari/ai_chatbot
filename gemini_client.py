"""
gemini_client.py

Gemini LLM backend wrapper — mirrors the interface of ollama_client.py
so app.py can use any backend uniformly.

Reads GEMINI_API_KEY from environment (.env via python-dotenv).
Never hard-codes or exposes the API key.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

GEMINI_AVAILABLE = False
try:
    # pyrefly: ignore [missing-import]
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    pass


class GeminiError(Exception):
    """Raised when Gemini API calls fail."""
    pass


def _check_available():
    if not GEMINI_AVAILABLE:
        raise GeminiError(
            "google-generativeai is not installed. Run: pip install google-generativeai"
        )


def get_api_key() -> str:
    return os.getenv("GEMINI_API_KEY", "").strip()


def list_models() -> list:
    """Return a curated list of available Gemini chat models."""
    return [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash",
        "gemini-pro",
    ]


REASONING_INSTRUCTIONS = """
For every reply, respond in two parts: an ANALYSIS and an ANSWER.

ANALYSIS: A concise 3-6 bullet summary of your approach, what you understood,
key concepts considered, and any assumptions or limitations.
Do NOT write private chain-of-thought or internal reasoning traces.

ANSWER: The complete, final response to the user.

Respond with ONLY a valid JSON object (no markdown fences):
{"analysis": "<summary>", "answer": "<final answer>"}
""".strip()


def build_messages(system_prompt: str, history: list, user_message: str) -> list:
    """Build the Gemini message format from history + new message."""
    combined_system = f"{system_prompt}\n\n{REASONING_INSTRUCTIONS}".strip() if system_prompt else REASONING_INSTRUCTIONS
    messages = [{"role": "system", "content": combined_system}]
    for turn in history:
        messages.append({"role": "user", "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["answer"]})
    messages.append({"role": "user", "content": user_message})
    return messages


def chat(
    model: str,
    system_prompt: str,
    history: list,
    user_message: str,
    temperature: float = 0.7,
) -> Tuple[str, str]:
    """
    Send a chat request to the Gemini API.
    Returns (analysis, answer) matching the ollama_client.chat() interface.
    """
    _check_available()
    api_key = get_api_key()
    if not api_key:
        raise GeminiError(
            "GEMINI_API_KEY is not set. Add it to your .env file."
        )

    try:
        genai.configure(api_key=api_key)
        combined_system = f"{system_prompt}\n\n{REASONING_INSTRUCTIONS}".strip() if system_prompt else REASONING_INSTRUCTIONS

        gemini_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=combined_system,
        )

        # Build Gemini-compatible chat history
        gemini_history = []
        for turn in history:
            gemini_history.append({"role": "user", "parts": [turn["user"]]})
            gemini_history.append({"role": "model", "parts": [turn["answer"]]})

        chat_session = gemini_model.start_chat(history=gemini_history)
        response = chat_session.send_message(
            user_message,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )

        raw_text = response.text.strip()
        return _parse_response(raw_text)

    except GeminiError:
        raise
    except Exception as exc:
        raise GeminiError(f"Gemini API error: {exc}") from exc


def _parse_response(raw_text: str) -> Tuple[str, str]:
    """Parse {analysis, answer} JSON from Gemini response."""
    import json

    # Strip markdown fences
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
