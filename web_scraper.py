"""
web_scraper.py

Website scraping layer for the chatbot.

Supports:
- URL detection
- ScrapeGraphAI website extraction
- Ollama-backed scraping
- Gemini-backed scraping
- Result truncation
- Friendly scraping errors

The chatbot backend is selected by app.py.

IMPORTANT:
Scraping and final-answer generation are separate operations.

The scraper extracts website data.
The selected chatbot backend (Ollama or Gemini) then uses that data
to generate the final answer.
"""

import json
import os
import re

from dotenv import load_dotenv

load_dotenv()


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAX_SCRAPED_CONTENT_CHARS = int(
    os.getenv("MAX_SCRAPED_CONTENT_CHARS", "8000")
)

SCRAPER_MODEL_TOKENS = int(
    os.getenv("SCRAPER_MODEL_TOKENS", "8192")
)

SCRAPER_EMBEDDING_MODEL = os.getenv(
    "SCRAPER_EMBEDDING_MODEL",
    "ollama/nomic-embed-text",
)

SCRAPER_VERBOSE = (
    os.getenv("SCRAPER_VERBOSE", "false")
    .strip()
    .lower()
    == "true"
)

SCRAPER_HEADLESS = (
    os.getenv("SCRAPER_HEADLESS", "true")
    .strip()
    .lower()
    != "false"
)

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
)

URL_PATTERN = re.compile(
    r'https?://[^\s<>"\')]+',
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ScraperError(Exception):
    """
    Raised whenever a website cannot be scraped.

    The message is written to be displayed directly to the user.
    """
    pass


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def find_first_url(text: str):
    """
    Return the first HTTP/HTTPS URL found in text.

    Returns:
        str | None
    """

    if not text:
        return None

    match = URL_PATTERN.search(text)

    if not match:
        return None

    return match.group(0).rstrip(
        ".,;:!?)]}"
        "\u201d\u2019"
    )


def strip_url(text: str, url: str) -> str:
    """
    Remove the URL from the user's message.

    The remaining text becomes the extraction prompt.
    """

    if not text:
        return ""

    return text.replace(url, "").strip()


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------

def truncate_content(
    text: str,
    max_chars: int = None,
):
    """
    Truncate scraped content.

    Returns:
        (text, was_truncated)
    """

    limit = (
        max_chars
        if max_chars is not None
        else MAX_SCRAPED_CONTENT_CHARS
    )

    if len(text) <= limit:
        return text, False

    return (
        text[:limit] + "\n...[truncated]",
        True,
    )


def _serialise_result(result):
    """
    Convert ScrapeGraphAI's result into a string.
    """

    try:
        return json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    except TypeError:
        return str(result)


# ---------------------------------------------------------------------------
# Ollama configuration
# ---------------------------------------------------------------------------

def _to_ollama_model_name(model: str) -> str:
    """
    ScrapeGraphAI expects Ollama models to use the ollama/ prefix.
    """

    model = (model or "").strip()

    if model.startswith("ollama/"):
        return model

    return f"ollama/{model}"


def _build_ollama_config(
    model: str,
    temperature: float,
    base_url: str,
):
    """
    Build ScrapeGraphAI configuration for Ollama.
    """

    return {
        "llm": {
            "model": _to_ollama_model_name(model),
            "temperature": float(temperature),
            "format": "json",
            "model_tokens": SCRAPER_MODEL_TOKENS,
            "base_url": base_url or OLLAMA_BASE_URL,
        },
        "embeddings": {
            "model": SCRAPER_EMBEDDING_MODEL,
            "base_url": base_url or OLLAMA_BASE_URL,
        },
        "verbose": SCRAPER_VERBOSE,
        "headless": SCRAPER_HEADLESS,
    }


# ---------------------------------------------------------------------------
# Gemini configuration
# ---------------------------------------------------------------------------

def _get_gemini_api_key():
    """
    Read Gemini API key from .env.
    """

    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ScraperError(
            "GEMINI_API_KEY was not found in your .env file."
        )

    return api_key


def _build_gemini_config(
    model: str,
    temperature: float,
):
    """
    Build ScrapeGraphAI configuration for Gemini.

    This configuration is kept separate from the Ollama configuration.
    """

    api_key = _get_gemini_api_key()

    return {
        "llm": {
            "model": model,
            "temperature": float(temperature),
            "format": "json",
            "model_tokens": SCRAPER_MODEL_TOKENS,
            "api_key": api_key,
        },
        "verbose": SCRAPER_VERBOSE,
        "headless": SCRAPER_HEADLESS,
    }


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

def scrape_website(
    url: str,
    prompt: str,
    model: str,
    temperature: float,
    backend: str = "Ollama",
    base_url: str = None,
) -> dict:
    """
    Scrape a website using the selected AI backend.

    Args:
        url:
            Website URL.

        prompt:
            Natural-language extraction request.

        model:
            Selected Ollama or Gemini model.

        temperature:
            Model temperature.

        backend:
            Either "Ollama" or "Gemini".

        base_url:
            Ollama base URL.
            Ignored when backend is Gemini.

    Returns:
        {
            "data": str,
            "truncated": bool,
        }

    Raises:
        ScraperError
    """

    # -----------------------------------------------------------------------
    # Validate URL
    # -----------------------------------------------------------------------

    if not url:
        raise ScraperError(
            "No website URL was provided."
        )

    if not url.lower().startswith(
        ("http://", "https://")
    ):
        raise ScraperError(
            f"'{url}' does not look like a valid website URL."
        )

    # -----------------------------------------------------------------------
    # Validate backend
    # -----------------------------------------------------------------------

    backend = (backend or "Ollama").strip().lower()

    if backend not in ("ollama", "gemini"):
        raise ScraperError(
            f"Unsupported backend '{backend}'. "
            "Choose Ollama or Gemini."
        )

    # -----------------------------------------------------------------------
    # Import ScrapeGraphAI lazily
    # -----------------------------------------------------------------------

    try:
        from scrapegraphai.graphs import SmartScraperGraph

    except ImportError as exc:
        raise ScraperError(
            "Could not import 'scrapegraphai'.\n\n"
            "Make sure it is installed inside the active virtual "
            "environment:\n\n"
            "pip install scrapegraphai\n\n"
            "You may also need:\n\n"
            "playwright install"
        ) from exc

    # -----------------------------------------------------------------------
    # Choose scraper configuration
    # -----------------------------------------------------------------------

    if backend == "ollama":

        if not model:
            raise ScraperError(
                "No Ollama model was selected."
            )

        graph_config = _build_ollama_config(
            model=model,
            temperature=temperature,
            base_url=base_url,
        )

    else:

        if not model:
            model = "gemini-3.6-flash"

        graph_config = _build_gemini_config(
            model=model,
            temperature=temperature,
        )

    # -----------------------------------------------------------------------
    # Extraction prompt
    # -----------------------------------------------------------------------

    extraction_prompt = (
        (prompt or "").strip()
        or
        "Extract the main useful information from this page."
    )

    # -----------------------------------------------------------------------
    # Run scraper
    # -----------------------------------------------------------------------

    try:

        graph = SmartScraperGraph(
            prompt=extraction_prompt,
            source=url,
            config=graph_config,
        )

        result = graph.run()

    except Exception as exc:

        msg = str(exc).lower()

        # Timeout
        if "timeout" in msg:

            raise ScraperError(
                f"Scraping {url} timed out. "
                "The website may be slow, very large, "
                "or blocking automated access."
            ) from exc

        # Connection problems
        if any(
            term in msg
            for term in (
                "net::",
                "connection",
                "resolve",
                "unreachable",
                "name or service",
            )
        ):

            raise ScraperError(
                f"Could not reach {url}. "
                "Check that the URL is correct and reachable."
            ) from exc

        # Anti-bot / blocked website
        if any(
            term in msg
            for term in (
                "403",
                "forbidden",
                "blocked",
                "captcha",
                "bot detect",
            )
        ):

            raise ScraperError(
                f"{url} appears to be blocking "
                "automated access."
            ) from exc

        # Embedding problem — only relevant to Ollama setup
        if (
            backend == "ollama"
            and "embed" in msg
        ):

            raise ScraperError(
                "The Ollama embedding model required "
                "for scraping isn't available.\n\n"
                f"Run:\n"
                f"ollama pull "
                f"{SCRAPER_EMBEDDING_MODEL.replace('ollama/', '')}"
            ) from exc

        # Gemini authentication
        if (
            backend == "gemini"
            and (
                "api key" in msg
                or "401" in msg
                or "403" in msg
                or "unauthorized" in msg
            )
        ):

            raise ScraperError(
                "Gemini authentication failed. "
                "Check GEMINI_API_KEY in your .env file."
            ) from exc

        raise ScraperError(
            f"ScrapeGraphAI could not scrape {url}:\n{exc}"
        ) from exc

    # -----------------------------------------------------------------------
    # Validate result
    # -----------------------------------------------------------------------

    if not result:

        raise ScraperError(
            f"No useful information could be extracted from {url}."
        )

    data_str = _serialise_result(result)

    if (
        not data_str.strip()
        or data_str.strip()
        in ("{}", "null", '""')
    ):

        raise ScraperError(
            f"No useful information could be extracted from {url}."
        )

    # -----------------------------------------------------------------------
    # Truncate
    # -----------------------------------------------------------------------

    truncated_str, was_truncated = truncate_content(
        data_str
    )

    return {
        "data": truncated_str,
        "truncated": was_truncated,
    }