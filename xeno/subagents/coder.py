"""Coder agent — expert coding with its own brain and tools."""


def get_coder_subagent(config=None) -> dict:
    model = config.model if config else "groq:openai/gpt-oss-120b"
    return {
        "name": "coder-agent",
        "description": (
            "Expert software engineering agent for writing, debugging, reviewing, refactoring, "
            "and testing code in ANY programming language. "
            "Use for: building apps, fixing bugs, code reviews, refactoring, "
            "creating scripts, automation, API integration, database work."
        ),
        "system_prompt": (
            "You are an expert software engineer with full system access.\n\n"
            "CAPABILITIES:\n"
            "- read_file / write_file / list_files: read and write code files\n"
            "- shell_execute: run commands (install, build, test, git)\n"
            "- execute_python / shell_run_python: run Python code\n"
            "- web_search / web_fetch: look up documentation and solutions\n"
            "- memory_store / memory_search: learn from past coding sessions\n"
            "- skill_create / skill_load: create reusable coding workflows\n"
            "- mcp_add / mcp_list: connect to databases, APIs via MCP\n"
            "- todo_create / todo_complete: track coding tasks\n"
            "- self_heal_diagnose / self_heal_fix: fix errors automatically\n\n"
            "WORKFLOW:\n"
            "1. Plan the solution before writing code\n"
            "2. Write clean, well-structured code with error handling\n"
            "3. Test after every change\n"
            "4. If errors occur, read the error message and fix it\n"
            "5. Create reusable skills for repeated coding patterns\n\n"
            "Always use type hints, docstrings, and follow language conventions."
        ),
        "model": model,
        "tools": [
            "read_file", "write_file", "list_files", "file_exists",
            "shell_execute", "shell_run_python", "execute_python",
            "web_search", "web_fetch",
            "memory_store", "memory_search", "memory_store_knowledge",
            "skill_create", "skill_load",
            "mcp_add", "mcp_list",
            "todo_create", "todo_complete",
            "self_heal_diagnose", "self_heal_fix", "self_modify",
        ],
    }
