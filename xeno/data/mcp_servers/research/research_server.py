import os
import asyncio
import logging
from typing import List, Optional, Dict, Any
from fastmcp import FastMCP
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("research-server")

# Load environment variables
load_dotenv()

# ── Optional dependencies ─────────────────────────────────────

try:
    import arxiv
    _HAS_ARXIV = True
except ImportError:
    _HAS_ARXIV = False
    logger.warning("arxiv package not installed. ArXiv tools disabled.")

try:
    from firecrawl import FirecrawlApp
    _HAS_FIRECRAWL = True
except ImportError:
    _HAS_FIRECRAWL = False
    logger.warning("firecrawl package not installed. Crawl/scrape tools disabled.")

try:
    import tavily
    from tavily import TavilyClient
    _HAS_TAVILY = True
except ImportError:
    _HAS_TAVILY = False
    tavily = None
    logger.warning("tavily package not installed. Search tools disabled.")

class KeyRotator:
    def __init__(self, base_name: str):
        self.keys = []
        # Check for the base name itself first
        base_key = os.getenv(base_name)
        if base_key:
            self.keys.append(base_key)
        
        # Check for numbered keys (e.g., NAME_1, NAME_2, ...)
        i = 1
        while True:
            key = os.getenv(f"{base_name}_{i}")
            if not key:
                break
            if key not in self.keys:
                self.keys.append(key)
            i += 1
            
        if not self.keys:
            logger.warning(f"No API keys found for {base_name}. Tools using this rotator will be disabled.")
        
        self.index = 0

    def get_next_key(self) -> str | None:
        if not self.keys:
            return None
        key = self.keys[self.index]
        self.index = (self.index + 1) % len(self.keys)
        return key

# Initialize rotators (non-fatal if keys missing)
firecrawl_rotator = KeyRotator("FIRECRAWL_API_KEY")
tavily_rotator = KeyRotator("TAVILY_API_KEY")

# Initialize FastMCP server
mcp = FastMCP("Deep Research Agent")

# Initialize clients (safe — return None if unavailable)
def get_firecrawl():
    key = firecrawl_rotator.get_next_key()
    if not key or not _HAS_FIRECRAWL:
        return None
    return FirecrawlApp(api_key=key)

def get_tavily():
    key = tavily_rotator.get_next_key()
    if not key or not _HAS_TAVILY:
        return None
    return TavilyClient(api_key=key)

@mcp.tool
def get_current_datetime() -> str:
    """
    Returns the current local date and time in ISO 8601 format. 
    Extremely useful for determining the current date when scheduling future tasks, understanding 'tomorrow', or researching recent events.
    """
    from datetime import datetime
    return datetime.now().astimezone().isoformat()

@mcp.tool
def tavily_search(
    query: str, 
    search_depth: str = "advanced", 
    topic: str = "general", 
    max_results: int = 5,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    days: Optional[int] = None
) -> Dict[str, Any]:
    """
    Search the web using Tavily with advanced filtering.
    
    Args:
        query: The search query.
        search_depth: "basic" or "advanced".
        topic: "general" or "news".
        max_results: Number of results (up to 20).
        include_domains: Search only in these domains.
        exclude_domains: Exclude these domains from search.
        days: Search results from the last N days (for news).
    """
    client = get_tavily()
    if not client:
        return {"error": "Tavily API not available. Set TAVILY_API_KEY and install tavily package."}
    return client.search(
        query=query,
        search_depth=search_depth,
        topic=topic,
        max_results=max_results,
        include_answer=True,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        days=days
    )

@mcp.tool
def tavily_news_search(query: str, max_results: int = 5, days: int = 3) -> Dict[str, Any]:
    """
    Specialized search for breaking news and recent events.
    """
    client = get_tavily()
    if not client:
        return {"error": "Tavily API not available. Set TAVILY_API_KEY and install tavily package."}
    return client.search(
        query=query,
        topic="news",
        search_depth="advanced",
        max_results=max_results,
        days=days,
        include_answer=True
    )

@mcp.tool
def tavily_domain_search(query: str, domains: List[str], max_results: int = 5) -> Dict[str, Any]:
    """
    Search strictly within a specific list of domains.
    """
    client = get_tavily()
    if not client:
        return {"error": "Tavily API not available. Set TAVILY_API_KEY and install tavily package."}
    return client.search(
        query=query,
        include_domains=domains,
        search_depth="advanced",
        max_results=max_results,
        include_answer=True
    )

@mcp.tool
def tavily_extract(urls: List[str]) -> Dict[str, Any]:
    """
    Extract clean, structured content from a list of URLs using Tavily.
    """
    client = get_tavily()
    if not client:
        return {"error": "Tavily API not available. Set TAVILY_API_KEY and install tavily package."}
    return client.extract(urls=urls)

@mcp.tool
def tavily_get_search_context(query: str, search_depth: str = "advanced", max_tokens: int = 4000) -> str:
    """
    Get a concise search context from Tavily, optimized for LLM context windows.
    """
    client = get_tavily()
    if not client:
        return {"error": "Tavily API not available. Set TAVILY_API_KEY and install tavily package."}
    return client.get_search_context(query=query, search_depth=search_depth, max_tokens=max_tokens)

@mcp.tool
def firecrawl_scrape(
    url: str, 
    formats: List[str] = ["markdown"],
    only_main_content: bool = True,
    wait_for: int = 0,
    selectors: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Scrape a URL with advanced control over content and rendering.
    
    Args:
        url: The URL to scrape.
        formats: List of formats (markdown, html).
        only_main_content: Skip headers, footers, and sidebars.
        wait_for: Milliseconds to wait for dynamic content.
        selectors: List of CSS selectors to target specific areas.
    """
    app = get_firecrawl()
    params = {
        "formats": formats,
        "onlyMainContent": only_main_content,
        "waitFor": wait_for
    }
    if selectors:
        params["includeSelectors"] = selectors
    return app.scrape_url(url, params=params)

@mcp.tool
def firecrawl_crawl(url: str, limit: int = 10, max_depth: int = 2) -> Dict[str, Any]:
    """
    Crawl a website starting from a base URL using Firecrawl.
    """
    app = get_firecrawl()
    if not app:
        return {"error": "Firecrawl API not available. Set FIRECRAWL_API_KEY and install firecrawl package."}
    return app.crawl_url(url, params={"limit": limit, "maxDepth": max_depth})

@mcp.tool
def firecrawl_map(url: str) -> Dict[str, Any]:
    """
    Map a website to find all its subpages using Firecrawl.
    """
    app = get_firecrawl()
    if not app:
        return {"error": "Firecrawl API not available. Set FIRECRAWL_API_KEY and install firecrawl package."}
    return app.map_url(url)

@mcp.tool
def firecrawl_search(query: str, limit: int = 5) -> Dict[str, Any]:
    """
    Search the web using Firecrawl's search capabilities.
    """
    app = get_firecrawl()
    if not app:
        return {"error": "Firecrawl API not available. Set FIRECRAWL_API_KEY and install firecrawl package."}
    return app.search(query, params={"limit": limit})

@mcp.tool
def firecrawl_extract(url: str, prompt: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extract structured data from a webpage using Firecrawl and LLMs.
    """
    app = get_firecrawl()
    params = {
        "formats": ["json"],
        "jsonOptions": {"prompt": prompt}
    }
    if schema:
        params["jsonOptions"]["schema"] = schema
        
    return app.scrape_url(url, params=params)

@mcp.tool
async def deep_comprehensive_research(query: str, max_search_results: int = 3) -> Dict[str, Any]:
    """
    Performs a deep research task combining Tavily search and Firecrawl scraping.
    """
    tavily = get_tavily()
    if not tavily:
        return {"error": "Tavily API not available. Set TAVILY_API_KEY and install tavily-py package."}
    firecrawl = get_firecrawl()
    
    search_results = await asyncio.get_running_loop().run_in_executor(
        None, lambda: tavily.search(query=query, search_depth="advanced", max_results=max_search_results)
    )
    
    results = {
        "query": query,
        "answer": search_results.get("answer"),
        "search_metadata": search_results.get("results", []),
        "full_contents": []
    }
    
    urls = [r["url"] for r in search_results.get("results", [])[:max_search_results]]
    
    loop = asyncio.get_running_loop()
    tasks = [loop.run_in_executor(None, firecrawl.scrape_url, url, {"formats": ["markdown"]}) for url in urls]
    
    scrape_responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    for url, resp in zip(urls, scrape_responses):
        if isinstance(resp, Exception):
            results["full_contents"].append({"url": url, "error": str(resp)})
        else:
            results["full_contents"].append({"url": url, "content": resp})
            
    return results

@mcp.tool
def arxiv_academic_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search for academic papers on ArXiv. Returns metadata and PDF links.
    """
    if not _HAS_ARXIV:
        return [{"error": "arxiv package not installed. Install with: pip install arxiv"}]
    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance
    )
    
    results = []
    for result in client.results(search):
        results.append({
            "title": result.title,
            "authors": [a.name for a in result.authors],
            "summary": result.summary,
            "published": result.published.isoformat(),
            "pdf_url": result.pdf_url,
            "entry_id": result.entry_id
        })
    return results

@mcp.tool
async def research_fact_checker(claim: str) -> Dict[str, Any]:
    """
    Fact-checks a specific claim by searching authoritative sources.
    """
    tavily = get_tavily()
    if not tavily:
        return {"error": "Tavily API not available. Set TAVILY_API_KEY and install tavily-py package."}
    queries = [
        f"is it true that {claim}",
        f"evidence for {claim}",
        f"evidence against {claim}",
        f"official statements on {claim}"
    ]
    
    results = {}
    async def run_query(q):
        return await asyncio.get_running_loop().run_in_executor(None, tavily.search, q, "advanced", "general", 3)

    query_tasks = [run_query(q) for q in queries]
    query_results = await asyncio.gather(*query_tasks)
    
    for q, res in zip(queries, query_results):
        results[q] = res
        
    return results

@mcp.tool
async def research_recursive_topic_tree(topic: str, depth: int = 1) -> Dict[str, Any]:
    """
    Performs recursive research by identifying sub-topics and searching for them.
    """
    tavily = get_tavily()
    if not tavily:
        return {"error": "Tavily API not available. Set TAVILY_API_KEY and install tavily-py package."}
    
    # Initial search to find context and potential sub-topics
    initial_search = await asyncio.get_running_loop().run_in_executor(
        None, lambda: tavily.search(query=topic, search_depth="advanced", max_results=5)
    )
    
    tree = {
        "topic": topic,
        "results": initial_search.get("results", []),
        "sub_topics": []
    }
    
    # In a real "super advanced" version, we'd use an LLM here to extract sub-topics.
    # For now, we'll simulate by searching for "key aspects of [topic]"
    if depth > 0:
        aspects_query = f"key aspects and components of {topic}"
        aspects_search = await asyncio.get_running_loop().run_in_executor(
            None, lambda: tavily.search(query=aspects_query, search_depth="basic", max_results=3)
        )
        
        # We treat each result title as a potential sub-topic for demonstration
        for res in aspects_search.get("results", []):
            sub_topic = res["title"]
            sub_res = await asyncio.get_running_loop().run_in_executor(
                None, lambda: tavily.search(query=sub_topic, search_depth="basic", max_results=2)
            )
            tree["sub_topics"].append({
                "topic": sub_topic,
                "results": sub_res.get("results", [])
            })
            
    return tree

@mcp.tool
async def research_competitor_analysis(company_name: str) -> Dict[str, Any]:
    """
    Performs a specialized research task to analyze a company and its competitors.
    """
    queries = [
        f"{company_name} products and features",
        f"{company_name} pricing and plans",
        f"{company_name} main competitors",
        f"{company_name} customer reviews and complaints",
        f"{company_name} recent news and funding"
    ]
    
    tavily = get_tavily()
    if not tavily:
        return {"error": "Tavily API not available. Set TAVILY_API_KEY and install tavily-py package."}
    results = {}
    
    async def run_query(q):
        return await asyncio.get_running_loop().run_in_executor(None, tavily.search, q, "advanced", "general", 3)

    query_tasks = [run_query(q) for q in queries]
    query_results = await asyncio.gather(*query_tasks)
    
    for q, res in zip(queries, query_results):
        results[q] = res
        
    return results

@mcp.tool
async def research_technical_deep_dive(topic: str) -> Dict[str, Any]:
    """
    Performs a deep technical investigation into a topic.
    """
    queries = [
        f"{topic} official documentation",
        f"{topic} technical whitepaper",
        f"{topic} architecture diagram and explanation",
        f"{topic} implementation examples and code",
        f"{topic} vs alternative technologies comparison"
    ]
    
    tavily = get_tavily()
    if not tavily:
        return {"error": "Tavily API not available. Set TAVILY_API_KEY and install tavily-py package."}
    results = {}
    
    async def run_query(q):
        return await asyncio.get_running_loop().run_in_executor(None, tavily.search, q, "advanced", "general", 5)

    query_tasks = [run_query(q) for q in queries]
    query_results = await asyncio.gather(*query_tasks)
    
    for q, res in zip(queries, query_results):
        results[q] = res
        
    return results

@mcp.tool
async def research_market_trends(industry: str) -> Dict[str, Any]:
    """
    Research latest trends, market size, and future outlook for an industry.
    """
    queries = [
        f"{industry} market size and growth 2024 2025",
        f"top trends in {industry} for 2025",
        f"major challenges in {industry} industry",
        f"key players in {industry} market",
        f"future outlook for {industry} industry"
    ]
    
    tavily = get_tavily()
    if not tavily:
        return {"error": "Tavily API not available. Set TAVILY_API_KEY and install tavily-py package."}
    results = {}
    
    async def run_query(q):
        return await asyncio.get_running_loop().run_in_executor(None, tavily.search, q, "advanced", "general", 5)

    query_tasks = [run_query(q) for q in queries]
    query_results = await asyncio.gather(*query_tasks)
    
    for q, res in zip(queries, query_results):
        results[q] = res
        
    return results

@mcp.resource("research://templates/comprehensive")
def get_comprehensive_template() -> str:
    """Provides a template for comprehensive research reports."""
    return """
# Comprehensive Research Report: [Topic]

## 1. Executive Summary
- Core findings
- Key takeaways

## 2. Market/Topic Overview
- Current state
- Background and history

## 3. Detailed Analysis
- Technical specs (if applicable)
- Competitor/Alternative landscape
- Strengths and Weaknesses

## 4. Future Outlook
- Trends
- Predictions

## 5. Sources
- [Link 1]
- [Link 2]
    """

if __name__ == "__main__":
    mcp.run(transport="stdio")
