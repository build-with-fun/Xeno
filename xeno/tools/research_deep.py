from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional


logger = logging.getLogger(__name__)

_HAS_TAVILY = False
_HAS_FIRECRAWL = False
_HAS_ARXIV = False

try:
    from tavily import TavilyClient
    _HAS_TAVILY = True
except ImportError:
    pass

try:
    from firecrawl import FirecrawlApp
    _HAS_FIRECRAWL = True
except ImportError:
    pass

try:
    import arxiv
    _HAS_ARXIV = True
except ImportError:
    pass


def _get_tavily():
    key = os.environ.get("TAVILY_API_KEY", "")
    if not key or not _HAS_TAVILY:
        return None
    return TavilyClient(api_key=key)


def _get_firecrawl():
    key = os.environ.get("FIRECRAWL_API_KEY", "")
    if not key or not _HAS_FIRECRAWL:
        return None
    return FirecrawlApp(api_key=key)


def tavily_search(
    query: str,
    max_results: int = 5,
    search_depth: str = "advanced",
    topic: str = "general",
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
    days: Optional[int] = None,
) -> str:
    """Search the web using Tavily with advanced filtering. Returns comprehensive results with answer, sources, and content."""
    client = _get_tavily()
    if not client:
        return "Tavily API not available. Set TAVILY_API_KEY and `uv add tavily-py`."
    try:
        result = client.search(
            query=query,
            search_depth=search_depth,
            topic=topic,
            max_results=min(max_results, 20),
            include_answer=True,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            days=days,
        )
        lines = [f"Query: {query}"]
        if result.get("answer"):
            lines.append(f"Answer: {result['answer']}")
        for r in result.get("results", []):
            lines.append(f"\n- {r.get('title', '?')}")
            lines.append(f"  {r.get('url', '')}")
            lines.append(f"  {r.get('content', '')[:200]}")
        if not result.get("results"):
            lines.append("No results found.")
        return "\n".join(lines)
    except Exception as e:
        return f"Tavily search error: {e}"


def tavily_news_search(query: str, max_results: int = 5, days: int = 3) -> str:
    """Search for breaking news and recent events using Tavily."""
    return tavily_search(query, max_results=max_results, topic="news", days=days)


def tavily_extract(urls: list[str]) -> str:
    """Extract clean structured content from one or more URLs using Tavily."""
    client = _get_tavily()
    if not client:
        return "Tavily API not available."
    try:
        result = client.extract(urls=urls)
        lines = []
        for item in result.get("results", []):
            lines.append(f"URL: {item.get('url', '?')}")
            lines.append(f"Content: {item.get('raw_content', '')[:2000]}")
        if not lines:
            lines.append("No content extracted.")
        return "\n".join(lines)
    except Exception as e:
        return f"Tavily extract error: {e}"



def firecrawl_scrape(url: str, formats: Optional[list[str]] = None, only_main: bool = True) -> str:
    """Scrape a URL using Firecrawl. Returns clean markdown content. Use for deep page analysis."""
    app = _get_firecrawl()
    if not app:
        return "Firecrawl API not available. Set FIRECRAWL_API_KEY and `uv add firecrawl-py`."
    try:
        formats = formats or ["markdown"]
        params = {"formats": formats, "onlyMainContent": only_main}
        result = app.scrape_url(url, params=params)
        if isinstance(result, dict):
            if "markdown" in result:
                return result["markdown"][:5000]
            if "html" in result:
                return result["html"][:5000]
            return str(result)[:5000]
        return str(result)[:5000]
    except Exception as e:
        return f"Firecrawl scrape error: {e}"


def firecrawl_crawl(url: str, limit: int = 10, max_depth: int = 2) -> str:
    """Crawl a website starting from a base URL using Firecrawl. Returns all discovered pages."""
    app = _get_firecrawl()
    if not app:
        return "Firecrawl API not available."
    try:
        result = app.crawl_url(url, params={"limit": limit, "maxDepth": max_depth})
        lines = [f"Crawl results for {url}:"]
        if isinstance(result, dict):
            for page in result.get("pages", result.get("data", [])):
                lines.append(f"- {page.get('url', '?')} ({len(page.get('markdown', page.get('content', '')))} chars)")
        return "\n".join(lines)
    except Exception as e:
        return f"Firecrawl crawl error: {e}"


def firecrawl_search(query: str, limit: int = 5) -> str:
    """Search the web using Firecrawl's search capabilities."""
    app = _get_firecrawl()
    if not app:
        return "Firecrawl API not available."
    try:
        result = app.search(query, params={"limit": limit})
        lines = [f"Firecrawl search: {query}"]
        if isinstance(result, dict):
            for r in result.get("data", result.get("results", [])):
                lines.append(f"\n- {r.get('title', '?')}: {r.get('url', '')}")
        return "\n".join(lines)
    except Exception as e:
        return f"Firecrawl search error: {e}"


def arxiv_search(query: str, max_results: int = 5) -> str:
    """Search for academic papers on ArXiv. Returns titles, authors, summaries, and PDF links."""
    if not _HAS_ARXIV:
        return "arxiv package not installed. Run: uv add arxiv"
    try:
        client = arxiv.Client()
        search = arxiv.Search(query=query, max_results=min(max_results, 50), sort_by=arxiv.SortCriterion.Relevance)
        results = []
        for r in client.results(search):
            results.append(
                f"Title: {r.title}\n"
                f"Authors: {', '.join(a.name for a in r.authors)}\n"
                f"Published: {r.published.date()}\n"
                f"PDF: {r.pdf_url}\n"
                f"Summary: {r.summary[:300]}..."
            )
        return "\n\n".join(results) if results else "No papers found."
    except Exception as e:
        return f"ArXiv search error: {e}"


RESEARCH_DEEP_TOOLS = [
    tavily_search, tavily_news_search, tavily_extract,
    firecrawl_scrape, firecrawl_crawl, firecrawl_search,
    arxiv_search,
]