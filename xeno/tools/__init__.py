"""Xeno tools — all tools are @tool decorated LangChain tools.

Import from xeno.tools.registry for the canonical list.
This file re-exports for backwards compatibility.
"""

# Import everything from the registry (the new canonical source)
from xeno.tools.registry import (
    ALL_TOOLS, TOOL_MAP, get_tools_by_names, get_all_tool_names,
    # File
    read_file, write_file, list_files, file_exists,
    # Shell
    shell_execute, shell_run_python, execute_python,
    # Web
    web_search, web_fetch,
    # Memory (full CRUD)
    memory_store, memory_retrieve, memory_search,
    memory_store_knowledge, memory_search_knowledge,
    memory_delete, memory_list, memory_update, memory_clear,
    # Schedule
    schedule_create, schedule_list, schedule_get, schedule_update, schedule_delete, schedule_toggle, schedule_view,
    # Skill
    skill_create, skill_load, skill_search, skill_list,
    # Todo
    todo_create, todo_complete, todo_list, todo_get, todo_update, todo_delete, todo_search,
    # Self-heal
    self_heal_diagnose, self_heal_fix, self_modify,
    # MCP
    mcp_add, mcp_list,
    # Task queue
    task_queue_list, task_queue_get, task_queue_cancel, task_queue_stats,
    # Desktop
    take_screenshot, mouse_click, type_text, press_key,
    # Browser
    browser_open, browser_click, browser_screenshot,
    # Media
    generate_image, create_pdf,
    # WhatsApp
    whatsapp_send, whatsapp_status, whatsapp_web_check,
    whatsapp_list_contacts, whatsapp_search_contacts, whatsapp_get_contact,
    whatsapp_get_chat_history, whatsapp_get_unread,
    # Deep Research
    tavily_search, tavily_news_search, tavily_extract,
    firecrawl_scrape, firecrawl_crawl, firecrawl_search,
    arxiv_search,
    # Comprehensive Research
    research,
)

# Backwards-compat alias
ALL_TOOLS = ALL_TOOLS

__all__ = [
    "ALL_TOOLS", "TOOL_MAP", "get_tools_by_names", "get_all_tool_names",
    "read_file", "write_file", "list_files", "file_exists",
    "shell_execute", "shell_run_python", "execute_python",
    "web_search", "web_fetch",
    "memory_store", "memory_retrieve", "memory_search",
    "memory_store_knowledge", "memory_search_knowledge",
    "memory_delete", "memory_list", "memory_update", "memory_clear",
    "schedule_create", "schedule_list", "schedule_get", "schedule_update", "schedule_delete", "schedule_toggle", "schedule_view",
    "skill_create", "skill_load", "skill_search", "skill_list",
    "todo_create", "todo_complete", "todo_list", "todo_get", "todo_update", "todo_delete", "todo_search",
    "self_heal_diagnose", "self_heal_fix", "self_modify",
    "mcp_add", "mcp_list",
    "task_queue_list", "task_queue_get", "task_queue_cancel", "task_queue_stats",
    "take_screenshot", "mouse_click", "type_text", "press_key",
    "browser_open", "browser_click", "browser_screenshot",
    "generate_image", "create_pdf",
    "whatsapp_send", "whatsapp_status", "whatsapp_web_check",
    "whatsapp_list_contacts", "whatsapp_search_contacts", "whatsapp_get_contact",
    "whatsapp_get_chat_history", "whatsapp_get_unread",
    "tavily_search", "tavily_news_search", "tavily_extract",
    "firecrawl_scrape", "firecrawl_crawl", "firecrawl_search",
    "arxiv_search",
    "research",
]
