"""
ollama_client.py

Small, dependency-light wrapper around the local Ollama REST API.

Responsibilities:
- List locally installed Ollama models.
- Send chat requests to Ollama, including system prompt, history and temperature.
- Ask the model to return a structured {"analysis": ..., "answer": ...} JSON object.
- Robustly parse that structure, with a text-based fallback if the model does not
  return valid JSON.

This module intentionally has no dependency on Streamlit so it can be reused
later (CLI tools, tests, future multi-model pipelines, etc).
"""

import json
import os
import re

import requests


class OllamaError(Exception):
    """Raised whenever something goes wrong talking to Ollama."""
    pass


def get_base_url() -> str:
    """
    Returns the configured Ollama base URL.
    Reads OLLAMA_BASE_URL from the environment, falling back to the default
    local Ollama address if it is not set.
    """
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def list_models(base_url: str = None) -> list:
    """
    Returns a sorted list of model names currently installed in Ollama
    (equivalent to running `ollama list`).

    Raises OllamaError if the Ollama server cannot be reached.
    """
    base_url = base_url or get_base_url()
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise OllamaError(
            f"Could not connect to Ollama at {base_url}. "
            f"Is 'ollama serve' running? ({exc})"
        )

    try:
        data = response.json()
    except ValueError:
        raise OllamaError("Ollama returned an unexpected (non-JSON) response for /api/tags.")

    models = [item.get("name", "") for item in data.get("models", []) if item.get("name")]
    return sorted(models)


# Instructions appended to whatever system prompt the user defines. These tell
# the model to produce a short, high-level analysis summary (NOT hidden
# chain-of-thought) plus the final answer, formatted as JSON so the app can
# reliably split the two in the UI.
REASONING_INSTRUCTIONS = """
For every reply, respond in two parts: an ANALYSIS and an ANSWER.

ANALYSIS must be a short, high-level summary (3-6 bullet points, plain sentences)
covering, where relevant:
- What you understood the user is asking
- The approach you chose to answer it
- Key concepts, facts or context you considered important
- Any assumptions you made or limitations of your answer
Do NOT write private step-by-step internal chain-of-thought, hidden deliberation,
or extremely long reasoning traces. This is a concise summary of your approach,
not a transcript of your thinking.

ANSWER must be the complete, final response to the user's message.

Respond with ONLY a single valid JSON object, and nothing else before or after it
(no markdown code fences, no extra commentary). Use exactly this shape:
{"analysis": "<your analysis summary here>", "answer": "<your final answer here>"}
""".strip()


def build_messages(system_prompt: str, history: list, user_message: str) -> list:
    """
    Builds the Ollama /api/chat "messages" list from the system prompt,
    prior conversation turns and the new user message.

    `history` is a list of dicts shaped like:
        {"user": "...", "analysis": "...", "answer": "...", ...}
    as stored in Streamlit's session state.
    """
    system_prompt = (system_prompt or "").strip()
    combined_system = (
        f"{system_prompt}\n\n{REASONING_INSTRUCTIONS}" if system_prompt else REASONING_INSTRUCTIONS
    )

    messages = [{"role": "system", "content": combined_system}]

    for turn in history:
        messages.append({"role": "user", "content": turn["user"]})
        # Feed the model its own prior final answer (not the JSON wrapper) as
        # conversational context, so multi-turn context stays natural.
        messages.append({"role": "assistant", "content": turn["answer"]})

    messages.append({"role": "user", "content": user_message})
    return messages


def _try_parse_json(text: str):
    """
    Attempts to parse `text` as the expected {"analysis": ..., "answer": ...}
    JSON object. Returns (analysis, answer) on success, or None on failure.
    """
    text = text.strip()

    # Strip markdown code fences if the model added them despite instructions.
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()

    def _extract(data):
        if isinstance(data, dict) and "answer" in data:
            analysis = str(data.get("analysis", "")).strip()
            answer = str(data.get("answer", "")).strip()
            return analysis, answer
        return None

    # First attempt: the whole string is valid JSON.
    try:
        result = _extract(json.loads(text))
        if result:
            return result
    except json.JSONDecodeError:
        pass

    # Second attempt: find the first "{" and the last "}" and try that slice
    # (handles cases where the model added stray text around the JSON).
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start:end + 1]
        try:
            result = _extract(json.loads(snippet))
            if result:
                return result
        except json.JSONDecodeError:
            pass

    return None


def _fallback_parse(text: str):
    """
    Fallback used when the model did not return valid JSON. Tries to find
    "Analysis:" / "Answer:" style markers. If nothing usable is found, the
    whole response is treated as the final answer with no analysis.
    """
    pattern = re.compile(
        r"analysis[:\-]\s*(.*?)\s*(?:final answer|answer)[:\-]\s*(.*)",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(text)
    if match:
        analysis = match.group(1).strip()
        answer = match.group(2).strip()
        if answer:
            return analysis, answer

    return "", text.strip()


def parse_response(raw_text: str):
    """
    Splits a raw model response into (analysis, answer), trying the structured
    JSON format first and falling back to plain-text heuristics.
    """
    parsed = _try_parse_json(raw_text)
    if parsed and parsed[1]:
        return parsed
    return _fallback_parse(raw_text)


def chat(model: str, system_prompt: str, history: list, user_message: str,
         temperature: float, base_url: str = None, timeout: int = 120):
    """
    Sends a chat request to Ollama and returns (analysis, answer).

    - model: name of an installed Ollama model, e.g. "llama3"
    - system_prompt: user-editable system prompt from the UI
    - history: prior conversation turns (see build_messages)
    - user_message: the new message from the user
    - temperature: float, generally between 0.0 and 2.0
    """
    base_url = base_url or get_base_url()
    messages = build_messages(system_prompt, history, user_message)

    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"temperature": float(temperature)},
        "format": "json",
    }

    try:
        response = requests.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise OllamaError(
            f"Error communicating with Ollama at {base_url} using model '{model}': {exc}"
        )

    try:
        data = response.json()
    except ValueError:
        raise OllamaError("Ollama returned an unexpected (non-JSON) response for /api/chat.")

    raw_content = data.get("message", {}).get("content", "")
    if not raw_content:
        raise OllamaError("Ollama returned an empty response. Try a different model or prompt.")

    analysis, answer = parse_response(raw_content)

    if not analysis:
        analysis = "No structured analysis was returned by the model for this response."
    if not answer:
        answer = raw_content.strip()

    return analysis, answer
