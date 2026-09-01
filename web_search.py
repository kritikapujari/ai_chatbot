from ddgs import DDGS


def web_search(query: str, max_results: int = 5) -> list[dict]:
    """Search the web and return relevant results."""

    try:
        results = DDGS().text(
            query,
            max_results=max_results,
        )

        return [
            {
                "title": result.get("title", ""),
                "url": result.get("href", ""),
                "snippet": result.get("body", ""),
            }
            for result in results
        ]

    except Exception as exc:
        return [{
            "title": "",
            "url": "",
            "snippet": "",
            "error": str(exc),
        }]