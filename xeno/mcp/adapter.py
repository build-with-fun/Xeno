"""Tool → MCP Server adapter. Wraps @tool-decorated functions as MCP servers.

Groups existing 105+ tools into logical MCP servers.
Each server exposes its tools via the MCP protocol (JSON-RPC 2.0).
The Main Agent connects to all servers as an MCP host.
"""

from __future__ import annotations

import inspect
import json
import logging
from typing import Any, Callable

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

_MCP_TOOL_SERVERS: dict[str, "ToolMCPServer"] = {}


def mcp_tool(name: str = "", description: str = ""):
    """Decorator that registers a function as an MCP tool.

    Can wrap sync or async functions. Auto-generates JSON schema
    from type hints. Groups tools by their module name into MCP servers.
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        sig = inspect.signature(func)
        params = []
        for p_name, p_param in sig.parameters.items():
            p_type = "string"
            if p_param.annotation is not inspect.Parameter.empty:
                type_map = {str: "string", int: "number", float: "number", bool: "boolean", list: "array", dict: "object"}
                p_type = type_map.get(p_param.annotation, "string")
            params.append({"name": p_name, "type": p_type, "required": p_param.default is inspect.Parameter.empty})
        func._mcp_tool = {
            "name": tool_name,
            "description": description or func.__doc__ or "",
            "inputSchema": {"type": "object", "properties": {p["name"]: {"type": p["type"]} for p in params},
                            "required": [p["name"] for p in params if p["required"]]},
        }
        return func
    return decorator


class ToolMCPServer:
    """Wraps a group of @tool functions as an MCP server.

    Each server has a name and a list of tools. Tools can be:
    - LangChain BaseTool objects (from registry.py)
    - Plain functions decorated with @mcp_tool
    """

    def __init__(self, name: str, tools: list):
        self.name = name
        self._tool_map: dict[str, Callable] = {}
        for tool in tools:
            if isinstance(tool, BaseTool):
                self._tool_map[tool.name] = tool
            elif hasattr(tool, "_mcp_tool"):
                self._tool_map[tool._mcp_tool["name"]] = tool
                setattr(tool, "_mcp_server", name)

    @property
    def tool_names(self) -> list[str]:
        return list(self._tool_map.keys())

    @property
    def tool_schemas(self) -> list[dict]:
        result = []
        for name, tool in self._tool_map.items():
            if isinstance(tool, BaseTool):
                result.append({
                    "name": name,
                    "description": getattr(tool, "description", "")[:200],
                    "inputSchema": {"type": "object"},
                })
            elif hasattr(tool, "_mcp_tool"):
                result.append(tool._mcp_tool)
        return result

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Call a tool by name with arguments. Returns string result."""
        tool = self._tool_map.get(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found in server '{self.name}'")

        try:
            if isinstance(tool, BaseTool):
                if hasattr(tool, "ainvoke"):
                    result = await tool.ainvoke(arguments)
                else:
                    result = tool.invoke(arguments)
            elif inspect.iscoroutinefunction(tool):
                result = await tool(**arguments)
            else:
                result = tool(**arguments)

            if not isinstance(result, str):
                try:
                    result = json.dumps(result, default=str)[:10000]
                except Exception:
                    result = str(result)[:10000]
            return result
        except Exception as e:
            logger.error(f"MCP tool '{self.name}.{tool_name}' failed: {e}")
            return f"Error: {e}"

    def to_dict(self) -> dict:
        return {"name": self.name, "tools": self.tool_schemas}


def register_server(server: ToolMCPServer):
    """Register an MCP server in the global registry."""
    _MCP_TOOL_SERVERS[server.name] = server


def get_server(name: str) -> ToolMCPServer | None:
    return _MCP_TOOL_SERVERS.get(name)


def list_servers() -> dict[str, list[str]]:
    return {name: srv.tool_names for name, srv in _MCP_TOOL_SERVERS.items()}


def group_tools_into_servers(all_tools: list) -> list[ToolMCPServer]:
    """Partition 105+ tools into logical MCP server groups."""
    from xeno.tools.registry import (
        read_file, write_file, list_files, file_exists,
        shell_execute, shell_run_python, execute_python, shell_run_background, shell_check_output,
        web_search, web_fetch,
        memory_store, memory_retrieve, memory_search, memory_store_knowledge, memory_search_knowledge,
        schedule_create, schedule_list, schedule_get, schedule_update, schedule_delete, schedule_toggle, schedule_view,
        skill_create, skill_load, skill_search, skill_list,
        todo_create, todo_complete, todo_list, todo_get, todo_update, todo_delete, todo_search,
        self_heal_diagnose, self_heal_fix, self_modify,
        mcp_add, mcp_list,
        task_queue_list, task_queue_get, task_queue_cancel, task_queue_stats,
        generate_image, create_pdf,
        set_default_timeout,
    )

    servers = [
        ToolMCPServer("filesystem", [read_file, write_file, list_files, file_exists]),
        ToolMCPServer("shell", [shell_execute, shell_run_python, execute_python, shell_run_background, shell_check_output, set_default_timeout]),
        ToolMCPServer("web", [web_search, web_fetch]),
        ToolMCPServer("memory", [memory_store, memory_retrieve, memory_search, memory_store_knowledge, memory_search_knowledge]),
        ToolMCPServer("schedule", [schedule_create, schedule_list, schedule_get, schedule_update, schedule_delete, schedule_toggle, schedule_view]),
        ToolMCPServer("skills", [skill_create, skill_load, skill_search, skill_list]),
        ToolMCPServer("todos", [todo_create, todo_complete, todo_list, todo_get, todo_update, todo_delete, todo_search]),
        ToolMCPServer("self_heal", [self_heal_diagnose, self_heal_fix, self_modify]),
        ToolMCPServer("mcp_admin", [mcp_add, mcp_list]),
        ToolMCPServer("task_queue", [task_queue_list, task_queue_get, task_queue_cancel, task_queue_stats]),
        ToolMCPServer("media", [generate_image, create_pdf]),
    ]

    try:
        from xeno.tools.desktop import take_screenshot, mouse_click, mouse_move, mouse_drag, mouse_scroll, type_text, press_key, type_and_enter, get_screen_size, get_mouse_position, clipboard_copy, clipboard_paste
        servers.append(ToolMCPServer("desktop", [take_screenshot, mouse_click, mouse_move, mouse_drag, mouse_scroll, type_text, press_key, type_and_enter, get_screen_size, get_mouse_position, clipboard_copy, clipboard_paste]))
    except Exception:
        pass

    try:
        from xeno.tools.browser import browser_open, browser_click, browser_type, browser_screenshot, browser_get_content, browser_get_title, browser_get_url, browser_evaluate, browser_scroll, browser_wait, browser_press_key, browser_close
        servers.append(ToolMCPServer("browser", [browser_open, browser_click, browser_type, browser_screenshot, browser_get_content, browser_get_title, browser_get_url, browser_evaluate, browser_scroll, browser_wait, browser_press_key, browser_close]))
    except Exception:
        pass

    try:
        from xeno.tools.vision import describe_screen, describe_camera, screen_status
        servers.append(ToolMCPServer("vision", [describe_screen, describe_camera, screen_status]))
    except Exception:
        pass

    try:
        from xeno.tools.whatsapp import whatsapp_send, whatsapp_status, whatsapp_web_check, whatsapp_start_bot, whatsapp_bot_logs, whatsapp_bot_status, whatsapp_stop_bot
        servers.append(ToolMCPServer("whatsapp", [whatsapp_send, whatsapp_status, whatsapp_web_check, whatsapp_start_bot, whatsapp_bot_logs, whatsapp_bot_status, whatsapp_stop_bot]))
    except Exception:
        pass

    try:
        from xeno.tools.gmail import gmail_list, gmail_read, gmail_send, gmail_search, gmail_filter, gmail_approve
        servers.append(ToolMCPServer("gmail", [gmail_list, gmail_read, gmail_send, gmail_search, gmail_filter, gmail_approve]))
    except Exception:
        pass

    try:
        from xeno.tools.research_deep import tavily_search, tavily_news_search, tavily_extract, firecrawl_scrape, firecrawl_crawl, firecrawl_search, arxiv_search
        servers.append(ToolMCPServer("deep_research", [tavily_search, tavily_news_search, tavily_extract, firecrawl_scrape, firecrawl_crawl, firecrawl_search, arxiv_search]))
    except Exception:
        pass

    for srv in servers:
        register_server(srv)

    return servers
