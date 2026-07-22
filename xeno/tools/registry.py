"""Tool registry — converts all Xeno tools to proper LangChain BaseTool objects.

This is the SINGLE source of truth for tools. Every tool is:
1. Decorated with @tool (so LangChain sees the schema)
2. Has proper type hints + docstring (so the LLM knows how to call it)
3. Is Windows-compatible (no shell=True dangers, proper Path handling)
4. Returns strings (so the LLM can read the result)

The main agent gets ALL tools directly (not via call_tool indirection).
Each sub-agent gets only its specified tools.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from langchain_core.tools import tool, StructuredTool

logger = logging.getLogger(__name__)

# Global default timeout (seconds) — agent can change this via set_default_timeout tool
DEFAULT_TIMEOUT: int = 30

# Background process registry (for shell_run_background / shell_check_output)
_BG_PROCESSES: dict[str, dict] = {}
_BG_COUNTER: int = 0


@tool
def set_default_timeout(seconds: int = 30) -> str:
    """Change the default timeout for shell commands, code execution, and other operations. Default is 30 seconds. Increase for long-running operations like package installs."""
    global DEFAULT_TIMEOUT
    old = DEFAULT_TIMEOUT
    DEFAULT_TIMEOUT = max(5, min(seconds, 600))
    return f"Default timeout changed from {old}s to {DEFAULT_TIMEOUT}s"


# ============================================================================
# File Tools (Windows-safe: uses pathlib, no shell)
# ============================================================================

@tool
def read_file(path: str) -> str:
    """Read the contents of a file and return them as text. Use for reading code, config, docs, any text file."""
    try:
        p = Path(path)
        if not p.exists():
            return f"File not found: {path}"
        if p.stat().st_size > 1_000_000:
            return f"File too large ({p.stat().st_size} bytes). Read it in chunks with shell_execute."
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed. Overwrites existing files. Use for creating code, docs, config, any text file."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes to {p.resolve()}"
    except Exception as e:
        return f"Error writing file: {e}"


@tool
def list_files(directory: str = ".", pattern: str = "*") -> str:
    """List files in a directory. Returns file names and sizes. Use pattern to filter (e.g. '*.py')."""
    try:
        d = Path(directory)
        if not d.exists():
            return f"Directory not found: {directory}"
        if not d.is_dir():
            return f"Not a directory: {directory}"
        files = sorted(d.glob(pattern), key=lambda x: (x.is_dir(), x.name))
        if not files:
            return f"No files matching '{pattern}' in {d.resolve()}"
        lines = [f"Files in {d.resolve()} ({len(files)} total):"]
        for f in files[:200]:
            if f.is_dir():
                lines.append(f"  {f.name}/")
            else:
                size = f.stat().st_size
                size_str = f"{size}B" if size < 1024 else f"{size/1024:.1f}KB" if size < 1024*1024 else f"{size/1024/1024:.1f}MB"
                lines.append(f"  {f.name}  ({size_str})")
        if len(files) > 200:
            lines.append(f"  ... and {len(files) - 200} more")
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing files: {e}"


@tool
def file_exists(path: str) -> str:
    """Check if a file or directory exists. Returns path info."""
    p = Path(path)
    if not p.exists():
        return f"Path does not exist: {path}"
    if p.is_dir():
        try:
            count = sum(1 for _ in p.iterdir())
            return f"Directory: {p.resolve()} ({count} items)"
        except Exception:
            return f"Directory: {p.resolve()}"
    else:
        size = p.stat().st_size
        return f"File: {p.resolve()} ({size} bytes)"


# ============================================================================
# Shell Tools (Windows-safe: uses shell=False, proper command splitting)
# ============================================================================

@tool
def shell_execute(command: str, timeout: int = None) -> str:
    """Execute a shell command and return output. Use for: git, pip, npm, npx, ls, dir, uv, cargo, system commands. Default timeout controlled by set_default_timeout tool (30s default). Increase for long operations like package installs."""
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    try:
        # Windows: use shell=True so cmd.exe handles quoting natively
        # (split()+list2cmdline corrupts quoted arguments with spaces)
        if sys.platform == "win32":
            result = subprocess.run(
                command,
                capture_output=True, text=True, timeout=timeout, cwd=os.getcwd(),
                shell=True,
            )
        else:
            result = subprocess.run(
                ["/bin/bash", "-c", command],
                capture_output=True, text=True, timeout=timeout, cwd=os.getcwd(),
            )
        output = result.stdout or ""
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}" if output else result.stderr
        if result.returncode != 0:
            output += f"\n[EXIT CODE: {result.returncode}]"
        return output.strip()[:10000] if output.strip() else "Command executed successfully (no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds"
    except Exception as e:
        return f"Error executing command: {e}"


@tool
def shell_run_python(code: str, timeout: int = None) -> str:
    """Run Python code and return the output. Use for quick Python snippets, calculations, data processing. Default timeout controlled by set_default_timeout tool (30s default)."""
    if timeout is None:
        timeout = DEFAULT_TIMEOUT
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=timeout, cwd=os.getcwd(),
        )
        output = result.stdout or ""
        if result.stderr:
            output += f"\n[STDERR]\n{result.stderr}" if output else result.stderr
        return output.strip()[:10000] if output.strip() else "Code executed successfully (no output)"
    except subprocess.TimeoutExpired:
        return f"Code execution timed out after {timeout} seconds"
    except Exception as e:
        return f"Error running code: {e}"


@tool
def execute_python(code: str) -> str:
    """Execute Python code and return the output. Use for running scripts, calculations, data analysis."""
    return shell_run_python.invoke({"code": code})


@tool
def shell_run_background(command: str, timeout: int = 600) -> str:
    """Start a command in the background and return a task_id. Use for long-running commands like npm install, npx create-next-app, pip install, etc. Check result later with shell_check_output(task_id)."""
    global _BG_COUNTER
    _BG_COUNTER += 1
    task_id = f"bg_{_BG_COUNTER}"
    try:
        proc = subprocess.Popen(
            command if sys.platform == "win32" else ["/bin/bash", "-c", command],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=os.getcwd(), shell=(sys.platform == "win32"),
        )
        _BG_PROCESSES[task_id] = {"proc": proc, "started": time.time(), "timeout": timeout, "done": False}
        return f"Background task {task_id} started (PID {proc.pid}). Check later with shell_check_output('{task_id}')"
    except Exception as e:
        return f"Failed to start background task: {e}"


@tool
def shell_check_output(task_id: str) -> str:
    """Check the output of a background task started with shell_run_background. If still running, returns status. If completed, returns output."""
    if task_id not in _BG_PROCESSES:
        return f"Unknown task_id: {task_id}"
    entry = _BG_PROCESSES[task_id]
    proc: subprocess.Popen = entry["proc"]
    elapsed = time.time() - entry["started"]

    if proc.poll() is None:
        if elapsed > entry["timeout"]:
            proc.kill()
            stdout, stderr = proc.communicate()
            output = stdout or ""
            if stderr:
                output += f"\n[STDERR]\n{stderr}" if output else stderr
            entry["done"] = True
            return f"Background task {task_id} timed out after {entry['timeout']}s\n{output.strip()[:5000]}"
        return f"Background task {task_id} still running ({elapsed:.0f}s elapsed)"

    stdout, stderr = proc.communicate()
    output = stdout or ""
    if stderr:
        output += f"\n[STDERR]\n{stderr}" if output else stderr
    if proc.returncode != 0:
        output += f"\n[EXIT CODE: {proc.returncode}]"
    entry["done"] = True
    return f"Background task {task_id} completed ({elapsed:.0f}s, exit {proc.returncode}):\n{output.strip()[:10000]}"


# ============================================================================
# Web Tools
# ============================================================================

@tool
async def web_search(query: str, num_results: int = 5) -> str:
    """Search the web for information. Returns search results with titles, URLs, and snippets."""
    try:
        from ddgs import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=num_results):
                results.append(f"Title: {r.get('title', '')}\nURL: {r.get('href', '')}\nSnippet: {r.get('body', '')}")
        return "\n---\n".join(results) if results else f"No results found for: {query}"
    except ImportError:
        # Fallback to duckduckgo_search if ddgs not available
        try:
            from duckduckgo_search import DDGS
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=num_results):
                    results.append(f"Title: {r.get('title', '')}\nURL: {r.get('href', '')}\nSnippet: {r.get('body', '')}")
            return "\n---\n".join(results) if results else f"No results found for: {query}"
        except ImportError:
            return "Web search unavailable. Install: pip install ddgs"
    except Exception as e:
        return f"Search error: {e}"


@tool
async def web_fetch(url: str) -> str:
    """Fetch the content of a web page. Returns the text content of the page."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0 (XenoAgent)"})
            r.raise_for_status()
            # Strip HTML tags crudely
            text = r.text
            # Try BeautifulSoup if available
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(text, "html.parser")
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                text = soup.get_text()
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = "\n".join(chunk for chunk in chunks if chunk)
            except ImportError:
                pass
            return text[:10000]
    except Exception as e:
        return f"Fetch error: {e}"


# ============================================================================
# Memory Tools (use the unified memory manager)
# ============================================================================

def _get_memory():
    """Get the unified memory manager (singleton)."""
    try:
        from xeno.memory import MemoryManager
        from xeno.config import XenoConfig
        return MemoryManager(XenoConfig.from_env())
    except Exception:
        return None


@tool
def memory_store(key: str, value: str) -> str:
    """Store a fact in memory. Use for: user preferences, important info, context. The fact will be remembered across sessions."""
    mem = _get_memory()
    if mem is None:
        return "Memory not available"
    try:
        return mem.store_fact(key, value)
    except Exception as e:
        return f"Error storing: {e}"


@tool
def memory_retrieve(key: str) -> str:
    """Retrieve a fact from memory by key."""
    mem = _get_memory()
    if mem is None:
        return "Memory not available"
    try:
        return mem.retrieve_fact(key)
    except Exception as e:
        return f"Error retrieving: {e}"


@tool
def memory_search(query: str) -> str:
    """Search all memory (context + vector) for relevant info. Use when you need to recall past info."""
    mem = _get_memory()
    if mem is None:
        return "Memory not available"
    try:
        return mem.search_memory(query)
    except Exception as e:
        return f"Error searching: {e}"


@tool
def memory_store_knowledge(content: str) -> str:
    """Store knowledge in long-term vector memory. Use for: research findings, learned facts, important info that should be searchable."""
    mem = _get_memory()
    if mem is None:
        return "Memory not available"
    try:
        return mem.store_knowledge(content)
    except Exception as e:
        return f"Error storing knowledge: {e}"


@tool
def memory_search_knowledge(query: str) -> str:
    """Search long-term vector memory for relevant knowledge."""
    mem = _get_memory()
    if mem is None:
        return "Memory not available"
    try:
        return mem.search_knowledge(query, n=5)
    except Exception as e:
        return f"Error searching knowledge: {e}"


@tool
def memory_delete(key: str) -> str:
    """Delete a specific fact from memory by key. Use for: removing outdated or incorrect info."""
    mem = _get_memory()
    if mem is None:
        return "Memory not available"
    try:
        return mem.delete_fact(key)
    except Exception as e:
        return f"Error deleting memory: {e}"


@tool
def memory_list() -> str:
    """List all stored memory facts. Use for: seeing everything the system remembers about the user."""
    mem = _get_memory()
    if mem is None:
        return "Memory not available"
    try:
        return mem.list_facts()
    except Exception as e:
        return f"Error listing memory: {e}"


@tool
def memory_update(key: str, value: str) -> str:
    """Update an existing fact in memory. Use for: correcting info (e.g. 'my name changed from X to Y')."""
    mem = _get_memory()
    if mem is None:
        return "Memory not available"
    try:
        return mem.update_fact(key, value)
    except Exception as e:
        return f"Error updating memory: {e}"


@tool
def memory_clear(confirm: str = "no") -> str:
    """DELETE ALL MEMORY — clears context, vector, and temporal knowledge graph. Requires confirm='yes' to proceed."""
    if confirm != "yes":
        return "I'll clear your memory — please confirm with memory_clear(confirm='yes'). This cannot be undone."
    mem = _get_memory()
    if mem is None:
        return "Memory not available"
    try:
        return mem.clear_all()
    except Exception as e:
        return f"Error clearing memory: {e}"


# ============================================================================
# Schedule Tools
# ============================================================================

@tool
def schedule_create(name: str, prompt: str, schedule_type: str, config_json: str) -> str:
    """Schedule a task to run later. Types: 'after_delay' ({delay_seconds}), 'daily' ({hour,minute}), 'weekly' ({weekday,hour,minute}), 'monthly' ({day,hour,minute}), 'yearly' ({month,day,hour,minute}), 'once' ({run_at: ISO datetime})."""
    try:
        import json
        from xeno.scheduler import get_scheduler
        sched = get_scheduler()
        if sched is None:
            return "Scheduler not available"
        config = json.loads(config_json) if config_json else {}
        return sched.create(name=name, prompt=prompt, schedule_type=schedule_type, schedule_config=config)
    except Exception as e:
        return f"Error creating schedule: {e}"


@tool
def schedule_list() -> str:
    """List all scheduled tasks."""
    try:
        from xeno.scheduler import get_scheduler
        sched = get_scheduler()
        if sched is None:
            return "Scheduler not available"
        return sched.list_all()
    except Exception as e:
        return f"Error: {e}"


@tool
def schedule_delete(task_id: str) -> str:
    """Delete a scheduled task by ID."""
    try:
        from xeno.scheduler import get_scheduler
        sched = get_scheduler()
        if sched is None:
            return "Scheduler not available"
        return sched.delete(task_id)
    except Exception as e:
        return f"Error: {e}"


@tool
def schedule_get(task_id: str) -> str:
    """Get details of a specific scheduled task by ID. Returns full JSON with all fields."""
    try:
        from xeno.scheduler import get_scheduler
        sched = get_scheduler()
        if sched is None:
            return "Scheduler not available"
        return sched.read(task_id)
    except Exception as e:
        return f"Error: {e}"


@tool
def schedule_update(task_id: str, name: str = "", prompt: str = "", schedule_type: str = "", config_json: str = "", enabled: str = "") -> str:
    """Update a scheduled task. Provide only the fields to change. Set enabled to 'true' or 'false' to toggle. config_json must be a valid JSON string if provided."""
    try:
        import json
        from xeno.scheduler import get_scheduler
        sched = get_scheduler()
        if sched is None:
            return "Scheduler not available"
        kwargs = {}
        if name:
            kwargs["name"] = name
        if prompt:
            kwargs["prompt"] = prompt
        if schedule_type:
            kwargs["schedule_type"] = schedule_type
        if config_json:
            kwargs["schedule_config"] = json.loads(config_json)
        if enabled.lower() in ("true", "false"):
            kwargs["enabled"] = enabled.lower() == "true"
        return sched.update(task_id, **kwargs)
    except Exception as e:
        return f"Error: {e}"


@tool
def schedule_toggle(task_id: str) -> str:
    """Toggle a schedule between enabled and disabled."""
    try:
        from xeno.scheduler import get_scheduler
        sched = get_scheduler()
        if sched is None:
            return "Scheduler not available"
        task_json = sched.read(task_id)
        if "No schedule found" in task_json:
            return task_json
        import json
        task_data = json.loads(task_json)
        if task_data.get("enabled", True):
            return sched.disable(task_id)
        else:
            return sched.enable(task_id)
    except Exception as e:
        return f"Error: {e}"


@tool
def schedule_view(days: int = 30) -> str:
    """View all upcoming scheduled tasks with a timeline. Shows schedules sorted by next run within the given number of days (default 30)."""
    try:
        from xeno.scheduler import get_scheduler
        sched = get_scheduler()
        if sched is None:
            return "Scheduler not available"
        raw = sched.list_all()
        if "No schedules" in raw:
            return raw
        import re
        lines = raw.split("\n")
        parsed = []
        for line in lines:
            m = re.match(r'\[(\S+)\]\s+(\S+)\s+(.+?)\s+\((.+?)\)\s+-\s+next:\s+(.+)', line)
            if m:
                tid, status, name, sched_type, next_run = m.groups()
                parsed.append((next_run, tid, status, name, sched_type))
        from datetime import datetime, timedelta
        now = datetime.now()
        cutoff = now + timedelta(days=days)
        future = []
        for next_run, tid, status, name, sched_type in parsed:
            try:
                dt = datetime.fromisoformat(next_run)
                if dt <= cutoff and status == "ENABLED":
                    future.append((dt, tid, name, sched_type))
            except (ValueError, TypeError):
                continue
        future.sort(key=lambda x: x[0])
        if not future:
            return f"No upcoming schedules within {days} days."
        result = [f"Upcoming schedules (next {days} days, {len(future)} found):"]
        for dt, tid, name, sched_type in future:
            result.append(f"  {dt.strftime('%Y-%m-%d %H:%M')}  [{tid}] {name} ({sched_type})")
        return "\n".join(result)
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# Skill Tools
# ============================================================================

@tool
def skill_create(name: str, description: str, body: str) -> str:
    """Create a reusable skill (workflow). Use for: saving repeated task patterns, creating how-to guides."""
    try:
        from xeno.skills_manager import get_skills_manager
        sm = get_skills_manager()
        if sm is None:
            return "Skills manager not available"
        return sm.create_skill(name, description, body)
    except Exception as e:
        return f"Error creating skill: {e}"


@tool
def skill_load(name: str) -> str:
    """Load a skill by name. Returns the skill's instructions and content."""
    try:
        from xeno.skills_manager import get_skills_manager
        sm = get_skills_manager()
        if sm is None:
            return "Skills manager not available"
        skill = sm.get_skill(name)
        if skill is None:
            return f"Skill '{name}' not found"
        return f"Skill: {skill['name']}\n\n{skill['content']}"
    except Exception as e:
        return f"Error: {e}"


@tool
def skill_search(query: str) -> str:
    """Search for skills matching a query. Returns matching skill names and descriptions."""
    try:
        from xeno.skills_manager import get_skills_manager
        sm = get_skills_manager()
        if sm is None:
            return "Skills manager not available"
        results = sm.search_skills(query)
        if not results:
            return f"No skills found matching '{query}'"
        lines = [f"Skills matching '{query}' ({len(results)}):"]
        for s in results[:10]:
            name = s.get("name", "?")
            desc = s.get("meta", {}).get("description", "")[:80]
            lines.append(f"  - {name}: {desc}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


@tool
def skill_list() -> str:
    """List all available skills."""
    try:
        from xeno.skills_manager import get_skills_manager
        sm = get_skills_manager()
        if sm is None:
            return "Skills manager not available"
        skills = sm.list_skills()
        if not skills:
            return "No skills available."
        lines = [f"Available skills ({len(skills)}):"]
        for s in skills[:30]:
            name = s.get("name", "?")
            desc = s.get("description", "")[:80]
            lines.append(f"  - {name}: {desc}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# Todo Tools
# ============================================================================

@tool
def todo_create(title: str, description: str = "", priority: str = "medium") -> str:
    """Create a todo item. Priority: low, medium, high. Returns the todo ID."""
    try:
        from xeno.todos import get_todo_manager
        tm = get_todo_manager()
        if tm is None:
            return "Todo manager not available"
        todo = tm.create(title=title, description=description, priority=priority)
        return f"Created todo: {todo.id} — {todo.title} (priority={todo.priority.value})"
    except Exception as e:
        return f"Error: {e}"


@tool
def todo_complete(todo_id: str) -> str:
    """Mark a todo as complete by ID."""
    try:
        from xeno.todos import get_todo_manager
        tm = get_todo_manager()
        if tm is None:
            return "Todo manager not available"
        todo = tm.complete(todo_id)
        if todo:
            return f"Completed: {todo.title}"
        return f"Todo not found: {todo_id}"
    except Exception as e:
        return f"Error: {e}"


@tool
def todo_list(status: str = "") -> str:
    """List todos. Optional status filter: pending, completed, blocked, all."""
    try:
        from xeno.todos import get_todo_manager
        tm = get_todo_manager()
        if tm is None:
            return "Todo manager not available"
        if status and status != "all":
            todos = tm.filter(status=status)
        else:
            todos = list(tm.todos.values())
        if not todos:
            return "No todos found."
        lines = [f"Todos ({len(todos)}):"]
        for t in todos[:50]:
            lines.append(f"  [{t.status.value}] {t.id}: {t.title} (priority={t.priority.value})")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


@tool
def todo_get(todo_id: str) -> str:
    """Get full details of a specific todo by ID."""
    try:
        from xeno.todos import get_todo_manager
        tm = get_todo_manager()
        if tm is None:
            return "Todo manager not available"
        todo = tm.get(todo_id)
        if todo is None:
            return f"Todo not found: {todo_id}"
        import json
        return json.dumps(todo.to_dict(), indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@tool
def todo_update(todo_id: str, title: str = "", description: str = "", status: str = "", priority: str = "", due_date: str = "") -> str:
    """Update a todo. Provide only the fields to change. Status options: pending, in_progress, blocked, completed, cancelled."""
    try:
        from xeno.todos import get_todo_manager
        tm = get_todo_manager()
        if tm is None:
            return "Todo manager not available"
        kwargs = {}
        if title:
            kwargs["title"] = title
        if description:
            kwargs["description"] = description
        if status:
            kwargs["status"] = status
        if priority:
            kwargs["priority"] = priority
        if due_date:
            kwargs["due_date"] = due_date
        todo = tm.update(todo_id, **kwargs)
        if todo is None:
            return f"Todo not found: {todo_id}"
        return f"Updated todo: {todo.id} — {todo.title} (status={todo.status.value})"
    except Exception as e:
        return f"Error: {e}"


@tool
def todo_delete(todo_id: str) -> str:
    """Delete a todo permanently by ID."""
    try:
        from xeno.todos import get_todo_manager
        tm = get_todo_manager()
        if tm is None:
            return "Todo manager not available"
        ok = tm.delete(todo_id)
        if ok:
            return f"Deleted todo: {todo_id}"
        return f"Todo not found: {todo_id}"
    except Exception as e:
        return f"Error: {e}"


@tool
def todo_search(query: str) -> str:
    """Search todos by title, description, or tags."""
    try:
        from xeno.todos import get_todo_manager
        tm = get_todo_manager()
        if tm is None:
            return "Todo manager not available"
        results = tm.search(query)
        if not results:
            return f"No todos found matching '{query}'"
        lines = [f"Todos matching '{query}' ({len(results)}):"]
        for t in results[:20]:
            lines.append(f"  [{t.status.value}] {t.id}: {t.title} (priority={t.priority.value})")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# Self-Heal Tools
# ============================================================================

@tool
def self_heal_diagnose(problem: str) -> str:
    """Diagnose a problem with the agent or system. Use when something isn't working."""
    try:
        from xeno.self_heal import SelfHealer
        from xeno.config import XenoConfig
        healer = SelfHealer(XenoConfig.from_env())
        return healer.diagnose_issue(problem)
    except Exception as e:
        return f"Error: {e}"


@tool
def self_heal_fix(error: str) -> str:
    """Attempt to auto-fix an error. Tries common fixes like installing missing dependencies."""
    try:
        from xeno.self_heal import SelfHealer
        from xeno.config import XenoConfig
        healer = SelfHealer(XenoConfig.from_env())
        # Check for missing module errors
        import re
        mod_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", error)
        if mod_match:
            return healer.fix_missing_dependency(mod_match.group(1))
        # Check for MCP errors
        mcp_match = re.search(r"mcp[:\s]+([a-zA-Z0-9_-]+)", error, re.IGNORECASE)
        if mcp_match:
            return healer.fix_broken_mcp(mcp_match.group(1), error)
        return f"Could not auto-fix. Diagnose: {healer.diagnose_issue(error)}"
    except Exception as e:
        return f"Error: {e}"


@tool
def self_modify(file_path: str, old_str: str, new_str: str) -> str:
    """Modify a file by replacing old_str with new_str. Use for: fixing code, updating config, editing files surgically."""
    try:
        from xeno.self_heal import SelfHealer
        from xeno.config import XenoConfig
        healer = SelfHealer(XenoConfig.from_env())
        return healer.self_modify(file_path, old_str, new_str)
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# MCP Tools
# ============================================================================

@tool
def mcp_add(name: str, server_type: str, command_or_url: str, env_json: str = "{}") -> str:
    """Add an MCP server. server_type: 'local' (stdio) or 'remote' (HTTP/SSE). For local, command_or_url is the command (e.g. 'npx -y @modelcontextprotocol/server-filesystem /path'). For remote, it's the URL."""
    try:
        import json
        from xeno.mcp_client import get_mcp_manager, MCPServerConfig
        mcp = get_mcp_manager()
        if mcp is None:
            return "MCP manager not available"
        env = json.loads(env_json) if env_json else {}
        # Parse command into program + args
        if server_type == "local":
            parts = command_or_url.split()
            config = MCPServerConfig(
                name=name,
                command=parts[0] if parts else command_or_url,
                args=parts[1:] if len(parts) > 1 else [],
                env=env,
                transport="stdio",
                enabled=True,
            )
        else:
            config = MCPServerConfig(
                name=name,
                url=command_or_url,
                env=env,
                transport="sse",
                enabled=True,
            )
        mcp.add_server(config)
        return f"MCP server '{name}' added ({server_type})"
    except Exception as e:
        return f"Error: {e}"


@tool
def mcp_list() -> str:
    """List all configured MCP servers and their connection status."""
    try:
        from xeno.mcp_client import get_mcp_manager
        mcp = get_mcp_manager()
        if mcp is None:
            return "MCP manager not available"
        servers = mcp.list_servers()
        if not servers:
            return "No MCP servers configured."
        lines = [f"MCP servers ({len(servers)}):"]
        for name, status in servers.items():
            lines.append(f"  - {name}: {status}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# Task Queue Tools
# ============================================================================

@tool
def task_queue_list(status: str = "") -> str:
    """List tasks in the execution queue. Optional status filter: pending, queued, running, completed, failed, cancelled, blocked, all."""
    try:
        from xeno.server.task_queue import TaskQueue, TaskState, get_task_queue
        q = get_task_queue()
        if q is None:
            return "Task queue not available"
        if status and status != "all":
            try:
                state = TaskState(status)
                tasks = q.list_tasks(state=state)
            except ValueError:
                return f"Invalid status: {status}"
        else:
            tasks = q.list_tasks()
        if not tasks:
            return "No tasks in queue."
        lines = [f"Task queue ({len(tasks)} total):"]
        for t in tasks[:30]:
            lines.append(f"  [{t.state.value}] {t.id}: {t.name} (progress={t.progress:.0%})")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


@tool
def task_queue_get(task_id: str) -> str:
    """Get details of a specific task in the execution queue by ID."""
    try:
        from xeno.server.task_queue import get_task_queue
        q = get_task_queue()
        if q is None:
            return "Task queue not available"
        task = q.get_task(task_id)
        if task is None:
            return f"Task not found: {task_id}"
        import json
        return json.dumps(task.to_dict(), indent=2, default=str)
    except Exception as e:
        return f"Error: {e}"


@tool
def task_queue_cancel(task_id: str) -> str:
    """Cancel a queued or running task by ID."""
    try:
        from xeno.server.task_queue import get_task_queue
        q = get_task_queue()
        if q is None:
            return "Task queue not available"
        ok = q.cancel(task_id)
        if ok:
            return f"Cancelled task: {task_id}"
        return f"Task not found or already completed: {task_id}"
    except Exception as e:
        return f"Error: {e}"


@tool
def task_queue_stats() -> str:
    """Get statistics about the task execution queue."""
    try:
        from xeno.server.task_queue import get_task_queue
        q = get_task_queue()
        if q is None:
            return "Task queue not available"
        stats = q.stats()
        lines = [f"Task Queue Stats:"]
        lines.append(f"  Total: {stats.get('total', 0)}")
        lines.append(f"  Running: {stats.get('running', 0)} / {stats.get('max_concurrent', '?')} max")
        states = stats.get("states", {})
        if states:
            lines.append(f"  By state: {', '.join(f'{k}={v}' for k, v in states.items())}")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# Desktop Control Tools — imported from desktop.py
# ============================================================================

from xeno.tools.desktop import (
    take_screenshot, mouse_click, mouse_move, mouse_drag, mouse_scroll,
    type_text, press_key, type_and_enter,
    get_screen_size, get_mouse_position,
    clipboard_copy, clipboard_paste,
)

# ============================================================================
# Vision Tools — screen/camera description via vision model
# ============================================================================

from xeno.tools.vision import (
    describe_screen, describe_camera, screen_status, analyze_image,
)

# ============================================================================
# Browser Tools — imported from browser.py (async Playwright)
# ============================================================================

from xeno.tools.browser import (
    browser_open, browser_click, browser_type, browser_screenshot,
    browser_get_content, browser_get_title, browser_get_url,
    browser_evaluate, browser_scroll, browser_wait, browser_press_key,
    browser_close,
)


# ============================================================================
# Image Generation
# ============================================================================

@tool
async def generate_image(prompt: str, project: str = "general", filename: str = "", output_path: str = "") -> str:
    """Generate an image from a text prompt.

    Use project+filename to save as workspace/<project>/images/<filename>.
    Use output_path to save to an exact location (e.g. workspace/site/hero.png).
    Use just project to auto-name inside workspace/<project>/images/.
    """
    try:
        from xeno.tools.image_gen import generate_image as _gen
        return await _gen(prompt, project=project, filename=filename, output_path=output_path)
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# PDF Generation
# ============================================================================

@tool
def create_pdf(title: str, content: str, project: str = "general") -> str:
    """Create a PDF document from markdown content. Saves to workspace/<project>/docs/."""
    try:
        from xeno.tools.pdf_gen import create_pdf as _pdf
        return _pdf(title, content, project)
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# WhatsApp Tools (optional — only if WhatsApp module is available)
# ============================================================================

@tool
def whatsapp_send(contact: str, message: str) -> str:
    """Send a WhatsApp message to a contact."""
    try:
        from xeno.tools.whatsapp import whatsapp_send as _send
        return _send(contact, message)
    except Exception as e:
        return f"Error: {e}"


@tool
def whatsapp_status() -> str:
    """Check WhatsApp connection status."""
    try:
        from xeno.tools.whatsapp import whatsapp_status as _status
        return _status()
    except Exception as e:
        return f"Error: {e}"


@tool
async def whatsapp_web_check() -> str:
    """Open WhatsApp Web in the browser, check status, take a screenshot."""
    try:
        from xeno.tools.whatsapp import whatsapp_web_check as _check
        return await _check()
    except Exception as e:
        return f"Error: {e}"


_whatsapp_bot_process: dict = {"proc": None}


@tool
async def whatsapp_start_bot(auto_reply_message: str = "", stop_after_minutes: int = 120) -> str:
    """Start the WhatsApp bot service as a background process. It auto-responds to incoming messages.

    Args:
        auto_reply_message: Message to auto-reply (empty = use bot's AI to generate replies)
        stop_after_minutes: Auto-stop after N minutes (default 120 = 2 hours)
    """
    global _whatsapp_bot_process
    if _whatsapp_bot_process.get("proc") and _whatsapp_bot_process["proc"].poll() is None:
        return "WhatsApp bot is already running."
    import subprocess, time, threading, asyncio
    from pathlib import Path

    # Clean up any stale WhatsApp schedules from previous sessions
    stale_ids = []
    try:
        from xeno.scheduler import scheduler
        stale_ids = [tid for tid, t in list(scheduler.tasks.items()) if "whatsapp" in t.name.lower()]
        for tid in stale_ids:
            scheduler.delete(tid)
    except Exception:
        pass

    project_root = Path(__file__).parent.parent.parent
    env = os.environ.copy()
    if auto_reply_message:
        env["AUTO_REPLY_MESSAGE"] = auto_reply_message
    if stop_after_minutes > 0:
        env["STOP_AFTER_MINUTES"] = str(stop_after_minutes)

    # Set model env vars so the WhatsApp bot subprocess inherits them
    from xeno.config import XenoConfig
    cfg = XenoConfig.from_env()
    if hasattr(cfg, 'provider') and cfg.provider == 'ollama':
        env.setdefault("OPENAI_BASE_URL", "http://localhost:11434/v1")
        env.setdefault("OPENAI_API_KEY", "ollama")
        if cfg.model and ":" in cfg.model:
            env.setdefault("OPENAI_MODEL", cfg.model.split(":", 1)[1])

    # Use port 5000 by default (separate profile means no conflict with Xeno's browser)
    env.setdefault("ADMIN_PORT", "5000")

    try:
        proc = subprocess.Popen(
            ["uv", "run", "python", "-m", "media.whatsapp.main"],
            cwd=str(project_root),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
        )
        _whatsapp_bot_process["proc"] = proc

        # Wait a few seconds and check if the process is still alive
        await asyncio.sleep(5)
        if proc.poll() is not None:
            out, err = proc.communicate(timeout=3)
            err_text = (out + err).decode("utf-8", errors="replace")[:1000]
            _whatsapp_bot_process["proc"] = None
            return (
                f"WhatsApp bot failed to start (exited with code {proc.returncode}).\n"
                f"Output: {err_text}"
            )

        # Read initial output in a thread to avoid blocking
        initial_lines = []

        def _reader(stream, out_list):
            try:
                for line in iter(stream.readline, b""):
                    out_list.append(line.decode("utf-8", errors="replace").rstrip())
                    if len(out_list) > 20:
                        break
            except Exception:
                pass

        t1 = threading.Thread(target=_reader, args=(proc.stdout, initial_lines), daemon=True)
        t2 = threading.Thread(target=_reader, args=(proc.stderr, initial_lines), daemon=True)
        t1.start()
        t2.start()
        await asyncio.sleep(2)

        status = f"WhatsApp bot started (pid={proc.pid}). "
        if stop_after_minutes > 0:
            status += f"Auto-stop in {stop_after_minutes} min."

        if initial_lines:
            for line in initial_lines:
                if "error" in line.lower() or "fail" in line.lower() or "traceback" in line.lower():
                    status += f"\nBot log: {line[:200]}"
                    break
            else:
                status += "\nBot startup looks clean."
        else:
            status += "\nWaiting for bot to initialize..."

        if stale_ids:
            status += f"\nCleaned up {len(stale_ids)} old WhatsApp schedule(s)."

        return status
    except Exception as e:
        return f"Failed to start WhatsApp bot: {e}"


@tool
def whatsapp_bot_logs(lines: int = 20) -> str:
    """Show recent output from the running WhatsApp bot process."""
    global _whatsapp_bot_process
    proc = _whatsapp_bot_process.get("proc")
    if not proc or proc.poll() is not None:
        return "No WhatsApp bot is running."
    try:
        out = []
        for _ in range(lines):
            try:
                import select
                if select.select([proc.stdout], [], [], 0.1)[0]:
                    line = proc.stdout.readline()
                    if line:
                        out.append(line.decode("utf-8", errors="replace").rstrip())
            except Exception:
                break
        return "\n".join(out) if out else "(no recent output)"
    except Exception as e:
        return f"Error reading logs: {e}"


@tool
def whatsapp_bot_status() -> str:
    """Check if the WhatsApp bot is alive and get its PID and health."""
    global _whatsapp_bot_process
    proc = _whatsapp_bot_process.get("proc")
    if not proc:
        return "WhatsApp bot has not been started."
    if proc.poll() is not None:
        return f"WhatsApp bot exited (code {proc.returncode})."
    try:
        import httpx
        r = httpx.get("http://127.0.0.1:5000/api/health", timeout=5)
        if r.status_code == 200:
            data = r.json()
            status = data.get("status", "unknown")
            checks = data.get("checks", [])
            failures = [c for c in checks if not c.get("healthy")]
            s = f"Bot PID {proc.pid} — overall: {status}"
            if failures:
                s += "\nUnhealthy checks:"
                for f in failures:
                    s += f"\n  - {f['name']}: {f['message']}"
            else:
                s += "\nAll checks healthy."
            return s
        return f"Bot PID {proc.pid} — API returned HTTP {r.status_code}"
    except httpx.ConnectError:
        return f"Bot PID {proc.pid} — API not reachable (admin server may not be running)."
    except Exception as e:
        return f"Bot PID {proc.pid} — status check error: {e}"


@tool
def whatsapp_stop_bot() -> str:
    """Stop the running WhatsApp bot."""
    global _whatsapp_bot_process
    proc = _whatsapp_bot_process.get("proc")
    if not proc or proc.poll() is not None:
        return "No WhatsApp bot is running."
    try:
        proc.terminate()
        proc.wait(timeout=5)
        _whatsapp_bot_process["proc"] = None
        # Clear cached browser state so next browser_open recreates it
        try:
            from xeno.tools.browser import _browser_state
            _browser_state.clear()
        except Exception:
            pass
        return "WhatsApp bot stopped."
    except subprocess.TimeoutExpired:
        proc.kill()
        _whatsapp_bot_process["proc"] = None
        return "WhatsApp bot killed (did not respond to terminate)."
    except Exception as e:
        return f"Failed to stop: {e}"


@tool
def whatsapp_list_contacts(limit: int = 100, offset: int = 0) -> str:
    """List all WhatsApp contacts/chats from the bot's database.

    Args:
        limit: Max contacts to return (default 100)
        offset: Pagination offset

    Returns:
        Formatted list of contacts with details.
    """
    try:
        from xeno.tools.whatsapp import whatsapp_list_contacts as _list
        return _list(limit=limit, offset=offset)
    except Exception as e:
        return f"Error: {e}"


@tool
def whatsapp_search_contacts(query: str) -> str:
    """Search WhatsApp contacts by name.

    Args:
        query: Name or partial name to search for

    Returns:
        Matching contacts with phone, tags, and message count.
    """
    try:
        from xeno.tools.whatsapp import whatsapp_search_contacts as _search
        return _search(query=query)
    except Exception as e:
        return f"Error: {e}"


@tool
def whatsapp_get_contact(name: str) -> str:
    """Get detailed information about a specific WhatsApp contact.

    Args:
        name: Contact name exactly as stored in the bot's database

    Returns:
        Contact details: tags, phone, message count, last seen, sentiment, etc.
    """
    try:
        from xeno.tools.whatsapp import whatsapp_get_contact as _get
        return _get(name=name)
    except Exception as e:
        return f"Error: {e}"


@tool
def whatsapp_get_chat_history(contact_name: str, limit: int = 50) -> str:
    """Get chat history with a WhatsApp contact from the bot's database.

    Args:
        contact_name: Contact name exactly as stored
        limit: Max messages to return (default 50, max 500)

    Returns:
        Formatted chat history with timestamps, roles, and content.
    """
    try:
        from xeno.tools.whatsapp import whatsapp_get_chat_history as _history
        return _history(contact_name=contact_name, limit=limit)
    except Exception as e:
        return f"Error: {e}"


@tool
def whatsapp_get_unread() -> str:
    """Get unread WhatsApp messages detected by the bot.

    Returns:
        Contacts with unread messages, previews, and message types.
    """
    try:
        from xeno.tools.whatsapp import whatsapp_get_unread as _unread
        return _unread()
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# Gmail Tools (optional — only if Gmail API modules are available)
# ============================================================================

@tool
def gmail_list(max_results: int = 10, query: str = "") -> str:
    """List recent emails. query: optional Gmail search syntax."""
    try:
        from xeno.tools.gmail import gmail_list as _list
        return _list(max_results=max_results, query=query)
    except Exception as e:
        return f"Error: {e}"


@tool
def gmail_read(message_id: str) -> str:
    """Read a specific email by its ID."""
    try:
        from xeno.tools.gmail import gmail_read as _read
        return _read(message_id)
    except Exception as e:
        return f"Error: {e}"


@tool
def gmail_send(to: str, subject: str, body: str) -> str:
    """Send an email. to: recipient email address."""
    try:
        from xeno.tools.gmail import gmail_send as _send
        return _send(to, subject, body)
    except Exception as e:
        return f"Error: {e}"


@tool
def gmail_search(query: str, max_results: int = 10) -> str:
    """Search emails with Gmail search syntax."""
    try:
        from xeno.tools.gmail import gmail_search as _search
        return _search(query=query, max_results=max_results)
    except Exception as e:
        return f"Error: {e}"


@tool
def gmail_filter(query: str = "", days: int = 7, max_results: int = 20) -> str:
    """Filter recent emails into categories (important/spam/promotions)."""
    try:
        from xeno.tools.gmail import gmail_filter as _filter
        return _filter(query=query, days=days, max_results=max_results)
    except Exception as e:
        return f"Error: {e}"


@tool
def gmail_approve(message_id: str, action: str = "reply") -> str:
    """Queue an email for approval response."""
    try:
        from xeno.tools.gmail import gmail_approve as _approve
        return _approve(message_id, action=action)
    except Exception as e:
        return f"Error: {e}"


@tool
def email_filter_set(mode: str, contacts: str = "") -> str:
    """Set email sender filter. Controls which senders' emails are shown.
    
    Args:
        mode: "all" (show all), "allowlist" (only these), or "blocklist" (all except these)
        contacts: Comma-separated sender names/emails. Empty for all-mode.
    """
    try:
        from xeno.tools.gmail import email_filter_set as _set
        clist = [c.strip() for c in contacts.split(",")] if contacts else []
        return _set(mode, clist if clist else None)
    except Exception as e:
        return f"Error: {e}"


@tool
def email_filter_get() -> str:
    """Get the current email sender filter settings."""
    try:
        from xeno.tools.gmail import email_filter_get as _get
        return _get()
    except Exception as e:
        return f"Error: {e}"


@tool
def whatsapp_set_filter(mode: str, contacts: str = "") -> str:
    """Set WhatsApp contact filter. Controls which contacts the bot auto-replies to.
    
    Args:
        mode: "all" (reply to all), "allowlist" (only these), or "blocklist" (all except these)
        contacts: Comma-separated contact names. Empty for all-mode.
    """
    try:
        from media.whatsapp.filter import contact_filter
        clist = [c.strip() for c in contacts.split(",")] if contacts else []
        return contact_filter.set_filter(mode, clist if clist else None)
    except Exception as e:
        return f"Error: {e}"


@tool
def whatsapp_get_filter() -> str:
    """Get the current WhatsApp contact filter settings."""
    try:
        from media.whatsapp.filter import contact_filter
        status = contact_filter.get_status()
        if status["mode"] == "all":
            return "WhatsApp filter: replying to ALL contacts."
        elif status["mode"] == "allowlist":
            return f"WhatsApp filter: ONLY replying to: {', '.join(status['contacts']) or '(none)'}"
        else:
            return f"WhatsApp filter: replying to EVERYONE except: {', '.join(status['contacts']) or '(none)'}"
    except Exception as e:
        return f"Error: {e}"


# ============================================================================
# Deep Research Tools (Tavily, Firecrawl, ArXiv)
# ============================================================================

@tool
def tavily_search(query: str, max_results: int = 5, search_depth: str = "advanced", topic: str = "general") -> str:
    """Search the web using Tavily with optional news topic filtering. Returns answer, sources, and content."""
    try:
        from xeno.tools.research_deep import tavily_search as _ts
        return _ts(query, max_results=max_results, search_depth=search_depth, topic=topic)
    except Exception as e:
        return f"Error: {e}"


@tool
def tavily_news_search(query: str, max_results: int = 5, days: int = 3) -> str:
    """Search for recent news using Tavily. Best for breaking news and current events."""
    try:
        from xeno.tools.research_deep import tavily_news_search as _tns
        return _tns(query, max_results=max_results, days=days)
    except Exception as e:
        return f"Error: {e}"


@tool
def tavily_extract(urls: list[str]) -> str:
    """Extract clean content from one or more URLs using Tavily."""
    try:
        from xeno.tools.research_deep import tavily_extract as _te
        return _te(urls)
    except Exception as e:
        return f"Error: {e}"


@tool
def firecrawl_scrape(url: str) -> str:
    """Scrape a URL using Firecrawl. Returns clean markdown content for deep page analysis."""
    try:
        from xeno.tools.research_deep import firecrawl_scrape as _fs
        return _fs(url)
    except Exception as e:
        return f"Error: {e}"


@tool
def firecrawl_crawl(url: str, limit: int = 10, max_depth: int = 2) -> str:
    """Crawl a website starting from a base URL. Returns list of all discovered pages."""
    try:
        from xeno.tools.research_deep import firecrawl_crawl as _fc
        return _fc(url, limit=limit, max_depth=max_depth)
    except Exception as e:
        return f"Error: {e}"


@tool
def firecrawl_search(query: str, limit: int = 5) -> str:
    """Search the web using Firecrawl."""
    try:
        from xeno.tools.research_deep import firecrawl_search as _fcs
        return _fcs(query, limit=limit)
    except Exception as e:
        return f"Error: {e}"


@tool
def arxiv_search(query: str, max_results: int = 5) -> str:
    """Search academic papers on ArXiv. Returns titles, authors, dates, PDF links, and summaries."""
    try:
        from xeno.tools.research_deep import arxiv_search as _as
        return _as(query, max_results=max_results)
    except Exception as e:
        return f"Error: {e}"


@tool
async def research(topic: str, depth: str = "standard") -> str:
    """Do comprehensive research on any topic. Searches the web, reads top results, and returns a consolidated summary with sources. Use for factual questions, current events, people, companies, or any topic research. Depth: 'quick' (1-2 results), 'standard' (3-5), 'deep' (5-10)."""
    try:
        from xeno.tools.advanced_tools import web_search, web_fetch
        num_results = {"quick": 2, "standard": 5, "deep": 10}.get(depth, 5)
        search_out = await web_search(topic, num_results=num_results)
        import json, re
        urls = re.findall(r'https?://[^\s\)\]\},"]+', search_out)
        urls = [u.rstrip(".,;:!?") for u in urls[:5]]
        fetched = []
        for url in urls:
            try:
                text = await web_fetch(url, max_length=3000)
                fetched.append(f"--- {url} ---\n{text[:2000]}")
            except Exception:
                continue
        parts = [f"=== SEARCH RESULTS ===\n{search_out}"]
        if fetched:
            parts.append(f"=== FETCHED CONTENT ===\n" + "\n\n".join(fetched))
        return "\n\n".join(parts)
    except Exception as e:
        return f"Research failed: {e}"


# ============================================================================
# XenoAtlas Metacognition Tools
# ============================================================================

_pattern_registry_loaded: bool = False


async def _ensure_patterns():
    global _pattern_registry_loaded
    if not _pattern_registry_loaded:
        try:
            from xeno.patterns.registry import register_default_patterns
            register_default_patterns()
            _pattern_registry_loaded = True
        except Exception:
            pass


@tool
async def use_pattern(pattern_name: str, query: str = "", **kwargs) -> str:
    """Invoke a metacognition pattern (reflexion, plan_and_execute, tree_of_thoughts, self_consistency).

    Patterns are advanced reasoning strategies:
    - reflexion: Generate-critique-revise cycle for iterative improvement
    - plan_and_execute: Decompose complex tasks into dependency-resolved steps
    - tree_of_thoughts: Explore multiple reasoning paths with branching and pruning
    - self_consistency: Run N independent attempts and pick the best

    Args:
        pattern_name: One of: reflexion, plan_and_execute, tree_of_thoughts, self_consistency
        query: The query/task to apply the pattern to
        **kwargs: Pattern-specific parameters

    Returns:
        Pattern execution result as JSON string
    """
    await _ensure_patterns()
    from xeno.patterns.registry import call_pattern, get_pattern, list_patterns

    pattern = get_pattern(pattern_name)
    if not pattern:
        available = list_patterns()
        return f"Unknown pattern '{pattern_name}'. Available: {', '.join(available.keys())}"

    result = await call_pattern(pattern_name, query=query, **kwargs)
    import json
    return json.dumps(result, default=str, indent=2)


# ============================================================================
# XenoAtlas AgentPool Tools
# ============================================================================

@tool
async def pool_run(task_description: str, agent_type: str = "default", max_workers: int = 1) -> str:
    """Run a task via the AgentPool (parallel execution engine).

    Distributes work across multiple workers for concurrent execution.
    Use for: running multiple tasks, parallel research, batch processing.

    Args:
        task_description: What to do
        agent_type: Worker type (research, coder, browser, planner, analyst, default)
        max_workers: How many parallel workers to use (default 1)

    Returns:
        Task execution results
    """
    from xeno.pool.dispatch import AgentDispatch
    dispatch = AgentDispatch()
    results = await dispatch.dispatch(task_description, agent_type=agent_type, max_workers=max_workers)
    import json
    return json.dumps(results, default=str, indent=2)


@tool
async def pool_cancel(task_id: str) -> str:
    """Cancel a running AgentPool task.

    Args:
        task_id: The task ID to cancel (from pool_run or pool_list)

    Returns:
        Confirmation or error message
    """
    from xeno.pool.agent_pool import get_pool
    pool = get_pool()
    result = await pool.cancel(task_id)
    return f"Task '{task_id}' cancelled: {result}"


@tool
async def pool_status(task_id: str = "") -> str:
    """Get status of a specific pool task or all tasks.

    Args:
        task_id: Optional task ID. Empty = show all active tasks.

    Returns:
        Task status information
    """
    from xeno.pool.agent_pool import get_pool
    pool = get_pool()
    if task_id:
        info = pool.get_task_info(task_id)
        import json
        return json.dumps(info, default=str, indent=2) if info else f"Task '{task_id}' not found"
    return pool.list_active()


@tool
async def pool_list() -> str:
    """List all active AgentPool tasks with their status.

    Returns:
        Formatted list of active tasks
    """
    from xeno.pool.agent_pool import get_pool
    pool = get_pool()
    return pool.list_active()


# ============================================================================
# XenoAtlas Temporal KG Tools
# ============================================================================

@tool
async def temporal_add_fact(namespace: str, key: str, value: str, source: str = "agent") -> str:
    """Store a fact in the Temporal Knowledge Graph with versioning.

    Facts are versioned and can be queried with temporal_query.
    Use for: storing cross-session knowledge, user preferences, learned patterns.

    Args:
        namespace: Category (e.g. 'user', 'project', 'system')
        key: Fact key (e.g. 'preferred_language', 'last_task')
        value: Fact value
        source: Origin of the fact (agent, user, system, mcp_call)

    Returns:
        Confirmation with fact ID
    """
    from xeno.memory.temporal import get_temporal_kg
    kg = get_temporal_kg(namespace)
    kg.add_fact(namespace, key, value, source=source)
    return f"Fact stored: {namespace}/{key}"


@tool
async def temporal_query(namespace: str = "", query: str = "", limit: int = 10) -> str:
    """Query the Temporal Knowledge Graph for relevant facts.

    Searches across namespaces for facts matching the query.
    Use for: remembering what was learned across conversations.

    Args:
        namespace: Optional namespace filter (e.g. 'user', 'project')
        query: Search query text
        limit: Max results (default 10)

    Returns:
        Matching facts as formatted text
    """
    from xeno.memory.temporal import get_temporal_kg
    kg = get_temporal_kg(namespace or "default")
    results = kg.query(query, namespace=namespace, limit=limit)
    if not results:
        return "No matching facts found."
    lines = [f"[{r.get('namespace','?')}] {r.get('key','?')}: {r.get('value','?')}" for r in results]
    return "\n".join(lines)


@tool
async def temporal_history(namespace: str, key: str) -> str:
    """Get the version history of a specific fact in the Temporal KG.

    Shows all past values of a fact with timestamps.
    Use for: seeing how information has changed over time.

    Args:
        namespace: Fact namespace
        key: Fact key

    Returns:
        Version history as formatted text
    """
    from xeno.memory.temporal import get_temporal_kg
    kg = get_temporal_kg(namespace)
    history = kg.get_history(namespace, key)
    if not history:
        return f"No history for {namespace}/{key}"
    lines = [f"[v{v}] {h.get('value','')} (source={h.get('source','?')})" for v, h in enumerate(history)]
    return "\n".join(lines)


@tool
async def temporal_context(namespace: str = "", limit: int = 20) -> str:
    """Export Temporal KG context as formatted text for the system prompt.

    Use for: loading relevant facts into the agent's context window.

    Args:
        namespace: Optional namespace filter
        limit: Max facts to include

    Returns:
        Formatted context string
    """
    from xeno.memory.temporal import get_temporal_kg
    kg = get_temporal_kg(namespace or "default")
    return kg.export_context(namespace=namespace, limit=limit)


# ============================================================================
# XenoAtlas Chat Store Tools
# ============================================================================

@tool
async def chat_session_create(name: str = "") -> str:
    """Create a new chat session with persistence.

    Args:
        name: Optional session name

    Returns:
        Session ID
    """
    from xeno.chat.store import get_chat_store
    store = get_chat_store()
    session = store.create_session(name=name)
    return f"Session created: {session.session_id}"


@tool
async def chat_session_list() -> str:
    """List all chat sessions.

    Returns:
        Formatted list of sessions
    """
    from xeno.chat.store import get_chat_store
    store = get_chat_store()
    sessions = store.list_sessions()
    if not sessions:
        return "No sessions found."
    lines = [f"[{s.session_id}] {s.name or 'unnamed'} — {s.message_count} messages" for s in sessions]
    return "\n".join(lines)


@tool
async def chat_message_add(session_id: str, role: str, content: str, agent_name: str = "") -> str:
    """Add a message to a chat session.

    Args:
        session_id: Session ID from chat_session_create
        role: Message role (user, assistant, system, agent)
        content: Message content
        agent_name: Optional agent name if role is 'agent'

    Returns:
        Confirmation
    """
    from xeno.chat.store import get_chat_store, ChatMessage
    store = get_chat_store()
    msg = ChatMessage(role=role, content=content, agent_name=agent_name)
    store.add_message(session_id, msg)
    return f"Message added to session '{session_id}'"


@tool
async def chat_context_get(session_id: str, limit: int = 20) -> str:
    """Get recent messages from a chat session for context.

    Args:
        session_id: Session ID
        limit: Max messages to return (default 20)

    Returns:
        Conversation history as formatted text
    """
    from xeno.chat.store import get_chat_store
    store = get_chat_store()
    messages = store.get_context(session_id, limit=limit)
    if not messages:
        return f"No messages in session '{session_id}'"
    lines = []
    for msg in messages:
        prefix = f"[{msg.role}]"
        if msg.agent_name:
            prefix += f" ({msg.agent_name})"
        lines.append(f"{prefix}: {msg.content[:200]}")
    return "\n".join(lines)


# ============================================================================
# XenoAtlas Always-On Agent Tools
# ============================================================================

@tool
async def always_on_list() -> str:
    """List all registered always-on agents with their status.

    Returns:
        Formatted list of always-on agents
    """
    from xeno.always_on.manager import get_always_on_manager
    mgr = get_always_on_manager()
    agents = mgr.list_agents()
    if not agents:
        return "No always-on agents registered."
    lines = []
    for a in agents:
        status = a.get("state", "unknown")
        name = a.get("name", "?")
        mode = a.get("mode", "?")
        mem = a.get("memory_facts", 0)
        lines.append(f"[{status}] {name} (mode={mode}, facts={mem})")
    return "\n".join(lines)


@tool
async def always_on_status(agent_name: str = "") -> str:
    """Get detailed status of an always-on agent.

    Args:
        agent_name: Agent name (whatsapp, email, or custom)

    Returns:
        Agent status details
    """
    from xeno.always_on.manager import get_always_on_manager
    mgr = get_always_on_manager()
    if agent_name:
        agent = mgr.get(agent_name)
        if not agent:
            return f"Agent '{agent_name}' not found. Use always_on_list to see available agents."
        return str(agent.get_status())
    return str(mgr.get_status())


@tool
async def always_on_start(agent_name: str) -> str:
    """Start an always-on agent.

    Args:
        agent_name: Agent name to start

    Returns:
        Confirmation or error
    """
    from xeno.always_on.manager import get_always_on_manager
    mgr = get_always_on_manager()
    return await mgr.start_agent(agent_name)


@tool
async def always_on_stop(agent_name: str) -> str:
    """Stop an always-on agent.

    Args:
        agent_name: Agent name to stop

    Returns:
        Confirmation or error
    """
    from xeno.always_on.manager import get_always_on_manager
    mgr = get_always_on_manager()
    return await mgr.stop_agent(agent_name)


# ============================================================================
# XenoAtlas Security Tools
# ============================================================================

@tool
async def security_check(tool_name: str, caller: str = "agent") -> str:
    """Check if a tool call would be permitted by the security gateway.

    Args:
        tool_name: Name of the tool to check
        caller: Identity to check as (agent, user, system)

    Returns:
        Whether the call is allowed or denied
    """
    from xeno.security.gateway import get_gateway
    from xeno.security.permissions import PermissionModel, PermissionLevel
    gateway = get_gateway()
    perm_model = PermissionModel(base_level=PermissionLevel.STANDARD)
    allowed, reason, level = await gateway.check(caller, tool_name, {}, perm_model)
    return f"{'ALLOWED' if allowed else 'DENIED'}: {reason or 'OK'}"


@tool
async def security_audit_log(limit: int = 20) -> str:
    """View the security audit log (recent tool calls).

    Args:
        limit: Max entries to show (default 20)

    Returns:
        Recent audit log entries
    """
    from xeno.security.gateway import get_gateway
    gateway = get_gateway()
    entries = gateway.get_audit_log(limit=limit)
    if not entries:
        return "No audit entries yet."
    import json
    return json.dumps(entries, indent=2)


@tool
async def security_stats() -> str:
    """Get security gateway statistics.

    Returns:
        Stats as JSON string
    """
    from xeno.security.gateway import get_gateway
    gateway = get_gateway()
    import json
    return json.dumps(gateway.get_stats(), indent=2)


# ============================================================================
# AGGREGATE ALL TOOLS
# ============================================================================

ALL_TOOLS: list = [
    # Meta
    set_default_timeout,
    # File ops
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
    # Skills
    skill_create, skill_load, skill_search, skill_list,
    # Todo
    todo_create, todo_complete, todo_list, todo_get, todo_update, todo_delete, todo_search,
    # Self-heal
    self_heal_diagnose, self_heal_fix, self_modify,
    # MCP
    mcp_add, mcp_list,
    # Task queue
    task_queue_list, task_queue_get, task_queue_cancel, task_queue_stats,
    # Desktop control (full)
    take_screenshot, mouse_click, mouse_move, mouse_drag, mouse_scroll,
    type_text, press_key, type_and_enter,
    get_screen_size, get_mouse_position,
    clipboard_copy, clipboard_paste,
    # Vision — screen/camera description + image analysis (text-based, uses vision model)
    describe_screen, describe_camera, screen_status, analyze_image,
    # Browser automation (full)
    browser_open, browser_click, browser_type, browser_screenshot,
    browser_get_content, browser_get_title, browser_get_url,
    browser_evaluate, browser_scroll, browser_wait, browser_press_key,
    browser_close,
    # Media
    generate_image, create_pdf,
    # WhatsApp
    whatsapp_send, whatsapp_status, whatsapp_web_check,
    whatsapp_start_bot, whatsapp_bot_logs, whatsapp_bot_status, whatsapp_stop_bot,
    whatsapp_list_contacts, whatsapp_search_contacts, whatsapp_get_contact,
    whatsapp_get_chat_history, whatsapp_get_unread,
    whatsapp_set_filter, whatsapp_get_filter,
    # Gmail
    gmail_list, gmail_read, gmail_send, gmail_search, gmail_filter, gmail_approve,
    email_filter_set, email_filter_get,
    # Deep Research (Tavily, Firecrawl, ArXiv)
    tavily_search, tavily_news_search, tavily_extract,
    firecrawl_scrape, firecrawl_crawl, firecrawl_search,
    arxiv_search,
    # Comprehensive Research (unified — web search + page fetch)
    research,
    # ── XenoAtlas Metacognition Tools ────────────────────────────────────
    use_pattern,
    # ── XenoAtlas Pool Tools ─────────────────────────────────────────────
    pool_run, pool_cancel, pool_status, pool_list,
    # ── XenoAtlas Temporal KG Tools ──────────────────────────────────────
    temporal_add_fact, temporal_query, temporal_history, temporal_context,
    # ── XenoAtlas Chat Tools ─────────────────────────────────────────────
    chat_session_create, chat_session_list, chat_message_add, chat_context_get,
    # ── XenoAtlas Always-On Agent Tools ──────────────────────────────────
    always_on_list, always_on_status, always_on_start, always_on_stop,
    # ── XenoAtlas Security Tools ─────────────────────────────────────────
    security_check, security_audit_log, security_stats,
]


# Tool name -> callable mapping (for sub-agent resolution)
TOOL_MAP: dict[str, Any] = {t.name: t for t in ALL_TOOLS}


def get_tools_by_names(names: list[str]) -> list:
    """Resolve a list of tool names to actual tool callables.

    Logs warnings for unknown names (instead of silently dropping them).
    """
    resolved = []
    for name in names:
        if name in TOOL_MAP:
            resolved.append(TOOL_MAP[name])
        else:
            logger.warning(f"Unknown tool '{name}' — skipping (not in TOOL_MAP)")
    return resolved


def get_all_tool_names() -> list[str]:
    """Return all registered tool names."""
    return list(TOOL_MAP.keys())


__all__ = [
    "ALL_TOOLS", "TOOL_MAP", "get_tools_by_names", "get_all_tool_names",
    "DEFAULT_TIMEOUT", "set_default_timeout",
    # Individual tools (for direct import)
    "read_file", "write_file", "list_files", "file_exists",
    "shell_execute", "shell_run_python", "execute_python",
    "web_search", "web_fetch",
    "memory_store", "memory_retrieve", "memory_search",
    "memory_store_knowledge", "memory_search_knowledge",
    "schedule_create", "schedule_list", "schedule_get", "schedule_update", "schedule_delete", "schedule_toggle", "schedule_view",
    "skill_create", "skill_load", "skill_search", "skill_list",
    "todo_create", "todo_complete", "todo_list", "todo_get", "todo_update", "todo_delete", "todo_search",
    "self_heal_diagnose", "self_heal_fix", "self_modify",
    "mcp_add", "mcp_list",
    "task_queue_list", "task_queue_get", "task_queue_cancel", "task_queue_stats",
    # Desktop (full)
    "take_screenshot", "mouse_click", "mouse_move", "mouse_drag", "mouse_scroll",
    "type_text", "press_key", "type_and_enter",
    "get_screen_size", "get_mouse_position",
    "clipboard_copy", "clipboard_paste",
    # Browser (full)
    "browser_open", "browser_click", "browser_type", "browser_screenshot",
    "browser_get_content", "browser_get_title", "browser_get_url",
    "browser_evaluate", "browser_scroll", "browser_wait", "browser_press_key",
    "browser_close",
    # Media + WhatsApp
    "generate_image", "create_pdf",
    "whatsapp_send", "whatsapp_status",
    "whatsapp_start_bot", "whatsapp_stop_bot", "whatsapp_bot_logs", "whatsapp_bot_status",
    "whatsapp_set_filter", "whatsapp_get_filter",
    # Email
    "email_filter_set", "email_filter_get",
]
