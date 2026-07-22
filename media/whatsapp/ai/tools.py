"""AI function-calling tools.

Allows the AI to invoke external tools during reply generation:
  - get_weather(city): Current weather
  - web_search(query): Web search
  - calculator(expression): Math evaluation
  - get_time(timezone): Current time
  - send_email(to, subject, body): Email (requires SMTP config)

The AI sees a list of available tools in its system prompt and can
request to call them. The router executes the calls and feeds results
back into the conversation.
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.parse
from datetime import datetime
from typing import Any, Callable, Optional

from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)


class Tool:
    """A callable tool that the AI can invoke."""

    def __init__(
        self, name: str, description: str, parameters: dict,
        handler: Callable[[dict], str],
    ):
        self.name = name
        self.description = description
        self.parameters = parameters  # JSON Schema-like
        self.handler = handler

    def execute(self, args: dict) -> str:
        """Execute the tool with the given arguments."""
        try:
            result = self.handler(args)
            return str(result)
        except Exception as e:
            logger.warning(f"[Tool] {self.name} error: {e}")
            return f"Error: {e}"

    def to_prompt_description(self) -> str:
        """Return a description for the AI's system prompt."""
        params_str = ", ".join(
            f"{name}: {info.get('type', 'string')}"
            for name, info in self.parameters.get("properties", {}).items()
        )
        return f"- {self.name}({params_str}): {self.description}"


class ToolRegistry:
    """Registry of available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._register_defaults()

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def to_prompt(self) -> str:
        """Return a prompt section listing all available tools."""
        if not self._tools:
            return ""
        lines = [
            "You have access to the following tools. To call a tool, reply with "
            "ONLY a JSON object in this format:",
            '  {"tool": "tool_name", "args": {"param": "value"}}',
            "",
            "Available tools:",
        ]
        for tool in self._tools.values():
            lines.append(f"  {tool.to_prompt_description()}")
        lines.append("")
        lines.append(
            "If you need to use a tool, output ONLY the tool call JSON. "
            "The system will execute it and ask you again for the final reply. "
            "If you don't need a tool, just reply normally."
        )
        return "\n".join(lines)

    def parse_and_execute(self, ai_response: str) -> Optional[dict]:
        """Check if the AI response is a tool call. If so, execute it.

        Returns {"tool": name, "args": dict, "result": str} if a tool was called,
        or None if the response is a normal reply.
        """
        if not ai_response:
            return None
        # Try to extract a JSON tool call from the response
        try:
            # Try to find a JSON object containing "tool" — handle nested braces
            # First try the simple case (no nested args)
            match = re.search(r'\{[^{}]*"tool"[^{}]*\}', ai_response, re.DOTALL)
            if not match:
                # Try with nested braces (one level: {"tool": "...", "args": {...}})
                match = re.search(
                    r'\{"tool"\s*:\s*"[^"]+"\s*,\s*"args"\s*:\s*\{[^{}]*\}\s*\}',
                    ai_response, re.DOTALL,
                )
            if not match:
                # Last resort: try parsing the whole response as JSON
                try:
                    parsed = json.loads(ai_response.strip())
                    if "tool" in parsed:
                        match = type('Match', (), {'group': lambda self: ai_response.strip()})()
                except (json.JSONDecodeError, ValueError):
                    pass
            if not match:
                return None
            parsed = json.loads(match.group())
            if "tool" not in parsed:
                return None
            tool_name = parsed["tool"]
            tool_args = parsed.get("args", {})
            tool = self.get(tool_name)
            if tool is None:
                return {
                    "tool": tool_name, "args": tool_args,
                    "result": f"Error: Unknown tool '{tool_name}'",
                    "error": True,
                }
            result = tool.execute(tool_args)
            logger.info(f"[Tool] {tool_name}({tool_args}) -> {result[:80]}")
            return {"tool": tool_name, "args": tool_args, "result": result}
        except (json.JSONDecodeError, KeyError) as e:
            logger.debug(f"[Tool] Not a tool call: {e}")
            return None

    def _register_defaults(self) -> None:
        """Register the built-in tools."""
        # ── Calculator ───────────────────────────────────────────────────────
        self.register(Tool(
            name="calculator",
            description="Evaluate a mathematical expression (e.g., '2+2', 'sqrt(16)', 'sin(30)')",
            parameters={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Math expression to evaluate"},
                },
                "required": ["expression"],
            },
            handler=self._tool_calculator,
        ))

        # ── Get time ─────────────────────────────────────────────────────────
        self.register(Tool(
            name="get_time",
            description="Get the current date and time, optionally for a specific timezone",
            parameters={
                "type": "object",
                "properties": {
                    "timezone": {"type": "string", "description": "IANA timezone (e.g., 'America/New_York'). Default: server timezone."},
                },
            },
            handler=self._tool_get_time,
        ))

        # ── Web search ───────────────────────────────────────────────────────
        self.register(Tool(
            name="web_search",
            description="Search the web for current information. Returns top results with titles and snippets.",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
            handler=self._tool_web_search,
        ))

        # ── Get weather ──────────────────────────────────────────────────────
        self.register(Tool(
            name="get_weather",
            description="Get current weather for a city",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                },
                "required": ["city"],
            },
            handler=self._tool_get_weather,
        ))

        # ── Knowledge base search ────────────────────────────────────────────
        self.register(Tool(
            name="knowledge_search",
            description="Search the bot's knowledge base for factual information (FAQs, policies, product info)",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
            handler=self._tool_knowledge_search,
        ))

    @staticmethod
    def _tool_calculator(args: dict) -> str:
        """Safe math expression evaluator."""
        expr = args.get("expression", "").strip()
        if not expr:
            return "Error: empty expression"
        # Whitelist: digits, operators, parens, decimal, and math functions
        import math
        allowed_names = {
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "log": math.log, "log10": math.log10, "pi": math.pi, "e": math.e,
            "abs": abs, "pow": pow, "ceil": math.ceil, "floor": math.floor,
            "round": round, "min": min, "max": max,
        }
        # Validate: only allow safe characters
        if not re.match(r'^[\d\s+\-*/().,a-z_]+$', expr, re.I):
            return "Error: invalid characters in expression"
        try:
            result = eval(expr, {"__builtins__": {}}, allowed_names)  # noqa: S307
            return f"{expr} = {result}"
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _tool_get_time(args: dict) -> str:
        """Get current time."""
        tz = args.get("timezone")
        try:
            if tz:
                from zoneinfo import ZoneInfo
                now = datetime.now(ZoneInfo(tz))
                return now.strftime(f"%Y-%m-%d %H:%M:%S {tz}")
            else:
                from media.whatsapp.config import settings
                tz = settings.browser_timezone
                from zoneinfo import ZoneInfo
                now = datetime.now(ZoneInfo(tz))
                return now.strftime(f"%Y-%m-%d %H:%M:%S {tz}")
        except Exception as e:
            return f"Error: {e}"

    @staticmethod
    def _tool_web_search(args: dict) -> str:
        """Web search via DuckDuckGo (no API key needed)."""
        query = args.get("query", "").strip()
        if not query:
            return "Error: empty query"
        try:
            import requests
            # DuckDuckGo Instant Answer API
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query, "format": "json", "no_html": 1,
                "skip_disambig": 1,
            }
            r = requests.get(url, params=params, timeout=5)
            if r.ok:
                data = r.json()
                results = []
                if data.get("Answer"):
                    results.append(f"Answer: {data['Answer']}")
                if data.get("AbstractText"):
                    results.append(f"Summary: {data['AbstractText'][:300]}")
                if data.get("RelatedTopics"):
                    for t in data["RelatedTopics"][:5]:
                        if isinstance(t, dict) and t.get("Text"):
                            results.append(f"- {t['Text'][:200]}")
                if results:
                    return "\n".join(results)
                return f"No results found for '{query}'"
            return f"Search error: HTTP {r.status_code}"
        except Exception as e:
            return f"Search error: {e}"

    @staticmethod
    def _tool_get_weather(args: dict) -> str:
        """Get weather via wttr.in (no API key needed)."""
        city = args.get("city", "").strip()
        if not city:
            return "Error: empty city"
        try:
            import requests
            r = requests.get(
                f"https://wttr.in/{urllib.parse.quote(city)}?format=%C+%t+%w+%h+%p",
                timeout=5, headers={"User-Agent": "curl"},
            )
            if r.ok:
                return f"Weather in {city}: {r.text.strip()}"
            return f"Weather error: HTTP {r.status_code}"
        except Exception as e:
            return f"Weather error: {e}"

    @staticmethod
    def _tool_knowledge_search(args: dict) -> str:
        """Search the RAG knowledge base."""
        query = args.get("query", "").strip()
        if not query:
            return "Error: empty query"
        from media.whatsapp.ai.rag import knowledge_base
        results = knowledge_base.search(query, limit=3)
        if not results:
            return "No knowledge base results found"
        return "\n".join(f"[{r['source']}] {r['text'][:200]}" for r in results)


# Singleton
tool_registry = ToolRegistry()
