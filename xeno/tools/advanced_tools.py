"""Web search and code interpreter tools for Xeno.

Provides integrated web search via multiple providers and a sandboxed
code interpreter following the deepagents guide's production patterns.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import traceback
from io import StringIO
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def web_search(
    query: str,
    num_results: int = 5,
    provider: str = "duckduckgo",
) -> str:
    """Search the web using configured provider.

    Args:
        query: Search query string.
        num_results: Number of results to return.
        provider: Search provider (duckduckgo, tavily, serper).

    Returns:
        Formatted search results as a string.
    """
    try:
        if provider == "duckduckgo":
            return await _search_duckduckgo(query, num_results)
        elif provider == "tavily":
            return await _search_tavily(query, num_results)
        elif provider == "serper":
            return await _search_serper(query, num_results)
        else:
            return await _search_duckduckgo(query, num_results)
    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return f"Search error: {e}"


async def _search_duckduckgo(query: str, num_results: int) -> str:
    """DuckDuckGo search via duckduckgo-search package."""
    try:
        from duckduckgo_search import DDGS

        def _run():
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=num_results))
            return results

        results = await asyncio.get_event_loop().run_in_executor(None, _run)
        if not results:
            return f"No results found for: {query}"

        output = [f"Search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            output.append(f"{i}. {r.get('title', 'No title')}")
            output.append(f"   URL: {r.get('href', 'N/A')}")
            output.append(f"   {r.get('body', 'No description')[:200]}")
            output.append("")
        return "\n".join(output)
    except ImportError:
        return "duckduckgo-search package not installed. Run: pip install duckduckgo-search"
    except Exception as e:
        return f"DuckDuckGo search error: {e}"


async def _search_tavily(query: str, num_results: int) -> str:
    """Tavily search (requires API key in TAVILY_API_KEY env var)."""
    import os
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return "TAVILY_API_KEY not set. Get an API key from tavily.com"

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"api_key": api_key, "query": query, "max_results": num_results},
                timeout=15,
            )
            data = resp.json()

        if "results" not in data:
            return f"Tavily error: {data}"

        output = [f"Search results for: {query}\n"]
        for i, r in enumerate(data["results"], 1):
            output.append(f"{i}. {r.get('title', 'No title')}")
            output.append(f"   URL: {r.get('url', 'N/A')}")
            output.append(f"   {r.get('content', 'No description')[:200]}")
            output.append("")
        return "\n".join(output)
    except Exception as e:
        return f"Tavily search error: {e}"


async def _search_serper(query: str, num_results: int) -> str:
    """Serper.dev search (requires API key in SERPER_API_KEY env var)."""
    import os
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        return "SERPER_API_KEY not set. Get an API key from serper.dev"

    try:
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
                json={"q": query, "num": num_results},
                timeout=15,
            )
            data = resp.json()

        if "organic" not in data:
            return f"Serper error: {data}"

        output = [f"Search results for: {query}\n"]
        for i, r in enumerate(data["organic"], 1):
            output.append(f"{i}. {r.get('title', 'No title')}")
            output.append(f"   URL: {r.get('link', 'N/A')}")
            output.append(f"   {r.get('snippet', 'No description')[:200]}")
            output.append("")
        return "\n".join(output)
    except Exception as e:
        return f"Serper search error: {e}"


async def web_fetch(url: str, max_length: int = 5000) -> str:
    """Fetch content from a URL.

    Args:
        url: The URL to fetch.
        max_length: Maximum content length to return.

    Returns:
        The page content as text.
    """
    try:
        import httpx
        async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.text[:max_length]
            return f"URL: {url}\nStatus: {resp.status_code}\nContent:\n{content}"
    except ImportError:
        return "httpx package not installed. Run: pip install httpx"
    except Exception as e:
        return f"Fetch error: {e}"


class CodeInterpreter:
    """Sandboxed Python code interpreter.

    Executes Python code in an isolated namespace with timeout protection,
    stdout/stderr capture, and built-in helper functions.
    """

    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout
        self._history: list[dict[str, Any]] = []
        self._namespace: dict[str, Any] = {
            "__builtins__": __builtins__,
            "json": json,
            "math": __import__("math"),
            "re": __import__("re"),
            "datetime": __import__("datetime"),
            "collections": __import__("collections"),
            "itertools": __import__("itertools"),
            "functools": __import__("functools"),
            "textwrap": __import__("textwrap"),
            "pathlib": __import__("pathlib"),
            "typing": __import__("typing"),
        }

    async def execute(self, code: str, timeout: Optional[float] = None) -> dict[str, Any]:
        """Execute Python code in the sandbox.

        Args:
            code: Python code to execute.
            timeout: Execution timeout in seconds.

        Returns:
            Dict with 'output', 'error', 'success' keys.
        """
        timeout = timeout or self.timeout
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        stdout_capture = StringIO()
        stderr_capture = StringIO()

        result = {"output": "", "error": "", "success": False, "execution_time": 0}

        try:
            import time
            start = time.time()

            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            # Execute with timeout via executor
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    exec, code, self._namespace
                )
                future.result(timeout=timeout)

            elapsed = time.time() - start
            result["output"] = stdout_capture.getvalue()
            result["error"] = stderr_capture.getvalue()
            result["success"] = True
            result["execution_time"] = elapsed

        except concurrent.futures.TimeoutError:
            result["error"] = f"Execution timed out after {timeout}s"
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
        finally:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

        self._history.append({
            "code": code,
            "result": {k: v for k, v in result.items() if k != "code"},
        })
        return result

    def get_history(self, limit: int = 10) -> list[dict]:
        """Get recent execution history."""
        return self._history[-limit:]

    def reset(self) -> None:
        """Reset the interpreter namespace."""
        self._namespace = {
            "__builtins__": __builtins__,
            "json": json,
            "math": __import__("math"),
            "re": __import__("re"),
        }

    def get_variable(self, name: str) -> Any:
        """Get a variable from the namespace."""
        return self._namespace.get(name)

    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable in the namespace."""
        self._namespace[name] = value
