"""
mcp/web_client.py

Simple web client for the agent.

Provides:
    - web_search: Search the public web
    - web_fetch: Fetch and extract readable text from a URL

Web content is treated as UNTRUSTED DATA.
"""

from __future__ import annotations

import html
import re
from typing import Any, Dict, List
from urllib.parse import quote_plus, urljoin, urlparse

import requests


class WebToolResult:
    """Result returned by web tools."""

    def __init__(
        self,
        tool: str,
        success: bool,
        data: Any = None,
        error: str = "",
    ):
        self.tool = tool
        self.success = success
        self.data = data
        self.error = error

    def format_for_llm(self) -> str:
        if not self.success:
            return (
                f"Web tool `{self.tool}` failed.\n"
                f"Error: {self.error}"
            )

        return str(self.data)


class WebClient:
    """
    Client for public web search and webpage fetching.

    No write operations are supported.
    """

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 "
                    "(KHTML, like Gecko) "
                    "Chrome/151.0 Safari/537.36"
                )
            }
        )

    # ------------------------------------------------------------------
    # Public execution method
    # ------------------------------------------------------------------

    def execute(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> WebToolResult:

        if tool_name == "web_search":
            return self.search(
                query=tool_args.get("query", ""),
                max_results=tool_args.get("max_results", 5),
            )

        if tool_name == "web_fetch":
            return self.fetch(
                url=tool_args.get("url", ""),
            )

        return WebToolResult(
            tool=tool_name,
            success=False,
            error=f"Unknown web tool: {tool_name}",
        )

    # ------------------------------------------------------------------
    # Web search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        max_results: int = 5,
    ) -> WebToolResult:

        if not query.strip():
            return WebToolResult(
                tool="web_search",
                success=False,
                error="Search query cannot be empty.",
            )

        max_results = max(1, min(int(max_results), 10))

        try:
            url = (
                "https://html.duckduckgo.com/html/"
                f"?q={quote_plus(query)}"
            )

            response = self.session.get(
                url,
                timeout=self.timeout,
            )

            response.raise_for_status()

            results = self._parse_search_results(
                response.text,
                max_results,
            )

            if not results:
                return WebToolResult(
                    tool="web_search",
                    success=True,
                    data=(
                        f"No search results found for: {query}"
                    ),
                )

            return WebToolResult(
                tool="web_search",
                success=True,
                data={
                    "query": query,
                    "results": results,
                },
            )

        except Exception as exc:
            return WebToolResult(
                tool="web_search",
                success=False,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Web fetch
    # ------------------------------------------------------------------

    def fetch(self, url: str) -> WebToolResult:

        if not url.strip():
            return WebToolResult(
                tool="web_fetch",
                success=False,
                error="URL cannot be empty.",
            )

        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return WebToolResult(
                tool="web_fetch",
                success=False,
                error="Only HTTP and HTTPS URLs are supported.",
            )

        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=True,
            )

            response.raise_for_status()

            content_type = response.headers.get(
                "content-type",
                "",
            ).lower()

            if "text/html" not in content_type:
                return WebToolResult(
                    tool="web_fetch",
                    success=True,
                    data={
                        "url": response.url,
                        "content_type": content_type,
                        "content": response.text[:30000],
                    },
                )

            text = self._extract_text(response.text)

            # Prevent enormous tool messages.
            text = text[:30000]

            return WebToolResult(
                tool="web_fetch",
                success=True,
                data={
                    "url": response.url,
                    "title": self._extract_title(response.text),
                    "content": text,
                },
            )

        except Exception as exc:
            return WebToolResult(
                tool="web_fetch",
                success=False,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # HTML parsing
    # ------------------------------------------------------------------

    def _parse_search_results(
        self,
        page: str,
        max_results: int,
    ) -> List[Dict[str, str]]:

        results: List[Dict[str, str]] = []

        # DuckDuckGo result blocks
        blocks = re.findall(
            r'<div[^>]*class="[^"]*result[^"]*"[^>]*>(.*?)</div>\s*</div>',
            page,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Fallback: locate result links directly.
        if not blocks:
            links = re.findall(
                r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
                page,
                flags=re.DOTALL | re.IGNORECASE,
            )

            for href, title in links[:max_results]:
                results.append(
                    {
                        "title": self._clean_html(title),
                        "url": html.unescape(href),
                        "snippet": "",
                    }
                )

            return results

        for block in blocks:

            title_match = re.search(
                r'class="[^"]*result__a[^"]*"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                block,
                flags=re.DOTALL | re.IGNORECASE,
            )

            if not title_match:
                continue

            url = html.unescape(title_match.group(1))
            title = self._clean_html(title_match.group(2))

            snippet_match = re.search(
                r'class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</',
                block,
                flags=re.DOTALL | re.IGNORECASE,
            )

            snippet = (
                self._clean_html(snippet_match.group(1))
                if snippet_match
                else ""
            )

            results.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                }
            )

            if len(results) >= max_results:
                break

        return results

    def _extract_title(self, page: str) -> str:

        match = re.search(
            r"<title[^>]*>(.*?)</title>",
            page,
            flags=re.DOTALL | re.IGNORECASE,
        )

        if not match:
            return ""

        return self._clean_html(match.group(1))

    def _extract_text(self, page: str) -> str:

        # Remove scripts/styles.
        page = re.sub(
            r"<script[^>]*>.*?</script>",
            " ",
            page,
            flags=re.DOTALL | re.IGNORECASE,
        )

        page = re.sub(
            r"<style[^>]*>.*?</style>",
            " ",
            page,
            flags=re.DOTALL | re.IGNORECASE,
        )

        page = re.sub(
            r"<noscript[^>]*>.*?</noscript>",
            " ",
            page,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # Convert common structural tags into line breaks.
        page = re.sub(
            r"</?(p|div|br|li|h1|h2|h3|h4|h5|h6|tr)[^>]*>",
            "\n",
            page,
            flags=re.IGNORECASE,
        )

        # Remove remaining HTML.
        page = re.sub(
            r"<[^>]+>",
            " ",
            page,
        )

        page = html.unescape(page)

        # Normalize whitespace.
        page = re.sub(
            r"[ \t]+",
            " ",
            page,
        )

        page = re.sub(
            r"\n\s*\n+",
            "\n\n",
            page,
        )

        return page.strip()

    def _clean_html(self, value: str) -> str:

        value = re.sub(
            r"<[^>]+>",
            " ",
            value,
        )

        value = html.unescape(value)

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()