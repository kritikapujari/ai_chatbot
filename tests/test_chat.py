"""
tests/test_chat.py

Unit tests for the Chat mode backends:
  - Ollama response parsing (JSON + fallback)
  - OpenRouter response parsing
  - Gemini response parsing
"""

import os
import sys
import json
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ─── Ollama Client ────────────────────────────────────────────────────────────

class TestOllamaParser:
    def test_valid_json_response(self):
        from ollama_client import parse_response
        raw = json.dumps({"analysis": "This is analysis.", "answer": "This is the answer."})
        analysis, answer = parse_response(raw)
        assert analysis == "This is analysis."
        assert answer == "This is the answer."

    def test_json_with_markdown_fences(self):
        from ollama_client import parse_response
        raw = "```json\n" + json.dumps({"analysis": "A", "answer": "B"}) + "\n```"
        _, answer = parse_response(raw)
        assert answer == "B"

    def test_fallback_to_plain_text(self):
        from ollama_client import parse_response
        raw = "Analysis: Some reasoning\nAnswer: The final result"
        analysis, answer = parse_response(raw)
        assert "result" in answer

    def test_malformed_json_returns_raw(self):
        from ollama_client import parse_response
        raw = "This is just plain text with no structure."
        _, answer = parse_response(raw)
        assert "plain text" in answer

    def test_analysis_key_missing_still_works(self):
        from ollama_client import parse_response
        raw = json.dumps({"answer": "Only the answer here."})
        analysis, answer = parse_response(raw)
        assert answer == "Only the answer here."
        assert analysis == ""

    def test_embedded_json_in_text(self):
        from ollama_client import parse_response
        raw = 'Here is my response: {"analysis": "brief", "answer": "result"} done.'
        _, answer = parse_response(raw)
        assert answer == "result"

    def test_build_messages_includes_history(self):
        from ollama_client import build_messages
        history = [
            {"user": "What is Python?", "answer": "Python is a language."},
        ]
        msgs = build_messages("You are helpful.", history, "Tell me more.")
        roles = [m["role"] for m in msgs]
        assert roles[0] == "system"
        assert "user" in roles
        assert "assistant" in roles

    def test_build_messages_empty_history(self):
        from ollama_client import build_messages
        msgs = build_messages("System prompt.", [], "Hello!")
        assert msgs[-1]["content"] == "Hello!"
        assert msgs[0]["role"] == "system"

    def test_get_base_url_default(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        from ollama_client import get_base_url
        url = get_base_url()
        assert url == "http://localhost:11434"

    def test_get_base_url_from_env(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://myserver:11434/")
        from ollama_client import get_base_url
        import importlib
        import ollama_client
        importlib.reload(ollama_client)
        url = ollama_client.get_base_url()
        assert url == "http://myserver:11434"  # trailing slash stripped


# ─── OpenRouter Client ────────────────────────────────────────────────────────

class TestOpenRouterParser:
    def test_valid_json_response(self):
        from openrouter_client import _parse_response
        raw = json.dumps({"analysis": "Analyzed.", "answer": "Answered."})
        analysis, answer = _parse_response(raw)
        assert analysis == "Analyzed."
        assert answer == "Answered."

    def test_malformed_json_returns_raw(self):
        from openrouter_client import _parse_response
        raw = "Some plain text response."
        analysis, answer = _parse_response(raw)
        assert "plain text" in answer

    def test_get_default_model_env(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_MODEL", "openai/gpt-4o")
        from openrouter_client import get_default_model
        import importlib, openrouter_client
        importlib.reload(openrouter_client)
        assert openrouter_client.get_default_model() == "openai/gpt-4o"

    def test_list_models_fallback_no_key(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        from openrouter_client import list_models, POPULAR_MODELS
        models = list_models()
        assert models == POPULAR_MODELS

    def test_no_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        from openrouter_client import chat, OpenRouterError
        with pytest.raises(OpenRouterError, match="OPENROUTER_API_KEY"):
            chat("openai/gpt-4o", "system", [], "hello")


# ─── Gemini Client ────────────────────────────────────────────────────────────

class TestGeminiParser:
    def test_valid_json_response(self):
        from gemini_client import _parse_response
        raw = json.dumps({"analysis": "Gem analysis.", "answer": "Gem answer."})
        analysis, answer = _parse_response(raw)
        assert analysis == "Gem analysis."
        assert answer == "Gem answer."

    def test_fallback_on_plain_text(self):
        from gemini_client import _parse_response
        raw = "Just a plain gemini response."
        analysis, answer = _parse_response(raw)
        assert "gemini response" in answer

    def test_no_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        from gemini_client import chat, GeminiError
        with pytest.raises(GeminiError, match="GEMINI_API_KEY"):
            chat("gemini-1.5-flash", "system", [], "hello")

    def test_list_models_returns_list(self):
        from gemini_client import list_models
        models = list_models()
        assert isinstance(models, list)
        assert len(models) > 0


# ─── Web Scraper ─────────────────────────────────────────────────────────────

class TestWebScraper:
    def test_extract_url_finds_url(self):
        from web_scraper import extract_url
        text = "Check out https://example.com for more info."
        url = extract_url(text)
        assert url == "https://example.com"

    def test_extract_url_no_url(self):
        from web_scraper import extract_url
        text = "No URL here."
        assert extract_url(text) is None

    def test_extract_url_http_and_https(self):
        from web_scraper import extract_url
        text = "See http://mysite.org/page"
        url = extract_url(text)
        assert url.startswith("http://")

    def test_scrape_website_safe_error_no_crash(self):
        from web_scraper import scrape_website_safe
        # Should not crash even with an invalid URL
        content, error = scrape_website_safe("https://this-url-does-not-exist-xyz.invalid")
        # Either content or error must be set; neither should cause an exception
        assert isinstance(content, str)
        assert error is None or isinstance(error, str)
