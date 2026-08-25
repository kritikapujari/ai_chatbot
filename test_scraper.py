# pyrefly: ignore [missing-import]
from scrapegraphai.graphs import SmartScraperGraph

graph_config = {
    "llm": {
        "model": "ollama/llama3.2",
        "base_url": "http://localhost:11434",
    },
    "verbose": True,
    "headless": True,
}

smart_scraper = SmartScraperGraph(
    prompt="Extract the first 5 quotes and their authors.",
    source="https://quotes.toscrape.com/",
    config=graph_config,
)

result = smart_scraper.run()

print("\n===== SCRAPED RESULT =====")
print(result)