from scrapegraphai.graphs import SmartScraperGraph
MODEL = "llama3.2"

config = {
    "llm": {
        "model": f"ollama/{MODEL}",
        "model_tokens": 8192,
    },
    "verbose": True,
    "headless": True,
}

scraper = SmartScraperGraph(
prompt="""
Read the webpage carefully and answer the following.

A. What is the main purpose of ScrapeGraphAI?

B. What problem is it trying to solve?

C. Explain the difference between traditional web scraping
and the approach described on this webpage.

D. Identify three specific features mentioned on the webpage
and explain why each feature could be useful.

E. Who appears to be the target audience?

F. Write a 3-sentence summary that preserves the most important
information from the webpage.

Important:
- Use only information supported by the webpage.
- Do not invent features or claims.
- If the webpage does not provide enough information for an answer,
  explicitly say so.
""",
    source="https://scrapegraphai.com/",
    config=config,
)

result = scraper.run()

print("\n========== OLLAMA RESULT ==========\n")
print(result)