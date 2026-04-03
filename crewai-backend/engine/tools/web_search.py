"""
Web search tool using DuckDuckGo (no API key required).
"""
from __future__ import annotations
from crewai.tools import tool

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None  # type: ignore[assignment,misc]

MAX_RESULTS = 5


@tool("web_search")
def web_search_tool(query: str) -> str:
    """Search the web using DuckDuckGo. Returns up to 5 results. Args: query."""
    if not query or not query.strip():
        return "Error: query must be a non-empty string"
    if DDGS is None:
        return "Search error: duckduckgo-search is not installed"
    try:
        results = list(DDGS().text(query.strip(), max_results=MAX_RESULTS))
        if not results:
            return f"No results found for: {query}"
        lines = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            url   = r.get("href", "")
            body  = r.get("body", "")[:200]
            lines.append(f"{i}. {title}")
            if url:
                lines.append(f"   {url}")
            if body:
                lines.append(f"   {body}")
        return "\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"
