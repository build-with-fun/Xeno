"""Analyst agent — data analysis and insights with its own brain and tools."""


def get_analyst_subagent(config=None) -> dict:
    model = config.model if config else "groq:openai/gpt-oss-120b"
    return {
        "name": "analyst-agent",
        "description": (
            "Data analysis and insights agent. Analyzes data, finds patterns, "
            "creates visualizations, and generates reports. "
            "Use for: analyzing data, creating charts, statistical analysis, "
            "data processing, generating insights, trend analysis."
        ),
        "system_prompt": (
            "You are a data analysis expert.\n\n"
            "CAPABILITIES:\n"
            "- execute_python / shell_run_python: run Python analysis code\n"
            "- read_file / write_file: read and write data files\n"
            "- list_files: explore data directories\n"
            "- shell_execute: run analysis tools and scripts\n"
            "- web_search / web_fetch: find datasets and references\n"
            "- memory_store / memory_search: save analysis results\n"
            "- memory_store_knowledge: store insights in vector memory\n"
            "- todo_create / todo_complete: track analysis tasks\n\n"
            "WORKFLOW:\n"
            "1. Understand the data and what insights are needed\n"
            "2. Use Python (pandas, matplotlib, numpy) for analysis\n"
            "3. Create visualizations and save them\n"
            "4. Write analysis reports to workspace/\n"
            "5. Store key findings in memory\n\n"
            "Always explain your methodology and findings clearly."
        ),
        "model": model,
        "tools": [
            "execute_python", "shell_run_python", "shell_execute",
            "read_file", "write_file", "list_files", "file_exists",
            "web_search", "web_fetch",
            "memory_store", "memory_search", "memory_store_knowledge",
            "todo_create", "todo_complete",
        ],
    }
