"""
web_scraper.py

ScrapeGraphAI integration for external website context.

Wraps SmartScraperGraph to scrape websites and return structured content
for use in both Chat and Agent modes.

Graceful degradation: if scrapegraphai is not installed or fails, the
function returns an informative error string rather than crashing.
"""

from __future__ import annotations

import os
import re
from typing import Optional


SCRAPEGRAPH_AVAILABLE = False
try:
    # pyrefly: ignore [missing-import]
    from scrapegraphai.graphs import SmartScraperGraph
    SCRAPEGRAPH_AVAILABLE = True
except ImportError:
    pass


class ScraperError(Exception):
    """Raised when web scraping fails."""
    pass


def is_url(text: str) -> bool:
    """Return True if the text looks like a URL."""
    url_pattern = re.compile(
        r"https?://[^\s\]\[<>\"']+",
        re.IGNORECASE,
    )
    return bool(url_pattern.match(text.strip()))


def extract_url(text: str) -> Optional[str]:
    """Extract the first URL found in a string."""
    url_pattern = re.compile(r"https?://[^\s\]\[<>\"']+", re.IGNORECASE)
    match = url_pattern.search(text)
    return match.group(0) if match else None


def scrape_website(
    url: str,
    prompt: str = "Extract the main content, key information, and any important details from this page.",
    llm_model: str = "ollama/llama3",
    ollama_base_url: str = "http://localhost:11434",
) -> str:
    """
    Scrape a website using ScrapeGraphAI and return the extracted content as text.

    Args:
        url: The URL to scrape
        prompt: What information to extract
        llm_model: The Ollama model to use for scraping (e.g. 'ollama/llama3')
        ollama_base_url: Base URL of the Ollama server

    Returns:
        Extracted content as a string.

    Raises:
        ScraperError: If scraping fails or the package is not installed.
    """
    if not SCRAPEGRAPH_AVAILABLE:
        raise ScraperError(
            "ScrapeGraphAI is not installed. Run: pip install scrapegraphai playwright\n"
            "Then: playwright install chromium"
        )

    try:
        graph_config = {
            "llm": {
                "model": llm_model,
                "base_url": ollama_base_url,
            },
            "verbose": False,
            "headless": True,
        }

        scraper = SmartScraperGraph(
            prompt=prompt,
            source=url,
            config=graph_config,
        )
        result = scraper.run()

        if isinstance(result, dict):
            # Flatten dict to readable text
            lines = []
            for k, v in result.items():
                lines.append(f"**{k}**: {v}")
            return "\n".join(lines)
        elif isinstance(result, list):
            return "\n".join(str(item) for item in result)
        else:
            return str(result)

    except ScraperError:
        raise
    except Exception as exc:
        raise ScraperError(f"Failed to scrape {url}: {exc}") from exc


def scrape_website_safe(
    url: str,
    prompt: str = "Extract the main content from this page.",
    llm_model: str = "ollama/llama3",
    ollama_base_url: str = "http://localhost:11434",
) -> tuple[str, Optional[str]]:
    """
    Safe wrapper around scrape_website.
    Returns (content, error_message). error_message is None on success.
    """
    try:
        content = scrape_website(url, prompt, llm_model, ollama_base_url)
        return content, None
    except ScraperError as exc:
        return "", str(exc)
    except Exception as exc:
        return "", f"Unexpected scraping error: {exc}"
