from web_search import web_search
from web_scraper import scrape_website


def search_and_scrape(query: str) -> str:
    """Search the web and scrape accessible, relevant sources."""

    results = web_search(query, max_results=5)

    if not results:
        return "No web results found."

    collected = []

    for result in results:
        url = result.get("url")

        if not url:
            continue

        try:
            content = scrape_website(
                url=url,
                prompt=f"""
                Extract accurate information needed to answer:

                {query}

                Focus on:
                - current temperature
                - feels-like temperature
                - weather conditions
                - humidity
                - wind
                - visibility
                - pressure
                - precipitation/rain
                - air quality
                - today's and upcoming forecast
                - date and time

                Only return information actually available on
                the webpage. Do not invent missing values.
                """,
                llm_model="ollama/llama3.2",
                ollama_base_url="http://localhost:11434",
            )

            collected.append(
                f"SOURCE: {result.get('title', '')}\n"
                f"URL: {url}\n"
                f"CONTENT:\n{content}"
            )

        except Exception as exc:
            # Skip websites that block automated scraping.
            print(f"Skipping inaccessible source: {url}")
            print(f"Reason: {exc}")

            continue

    if not collected:
        return "The web search found sources, but none could be scraped."

    return "\n\n---\n\n".join(collected)