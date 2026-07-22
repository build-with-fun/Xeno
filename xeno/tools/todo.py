"""Todo/Task management tools for the agent."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import uuid

TODOS_FILE = Path(__file__).parent.parent.parent / "data" / "todos.json"


def _load() -> list[dict]:
    if TODOS_FILE.exists():
        try:
            return json.loads(TODOS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save(todos: list[dict]):
    TODOS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TODOS_FILE.write_text(json.dumps(todos, indent=2, ensure_ascii=False), encoding="utf-8")


def add_todo(title: str, description: str = "", priority: str = "medium", due: str = "") -> str:
    """Add a new todo/task. priority: low/medium/high/critical. due: YYYY-MM-DD."""
    todos = _load()
    todo = {
        "id": uuid.uuid4().hex[:8],
        "title": title,
        "description": description,
        "priority": priority,
        "status": "pending",
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
        "due": due or None,
    }
    todos.append(todo)
    _save(todos)
    return f"Created todo [{todo['id']}] ({priority}): {title}"


def list_todos(status: str = "all", priority: str = "") -> str:
    """List todos. status: all/pending/completed/in_progress. priority: filter by priority."""
    todos = _load()
    if status != "all":
        todos = [t for t in todos if t.get("status") == status]
    if priority:
        todos = [t for t in todos if t.get("priority") == priority]
    if not todos:
        return "No todos found."
    lines = []
    for t in todos:
        icon = {"pending": "[ ]", "in_progress": "[>]", "completed": "[x]", "cancelled": "[~]"}.get(t["status"], "[ ]")
        due = f" due:{t['due']}" if t.get("due") else ""
        lines.append(f"{icon} [{t['id']}] ({t['priority']}) {t['title']}{due}")
        if t.get("description"):
            lines.append(f"    {t['description'][:100]}")
    return "\n".join(lines)


def complete_todo(todo_id: str) -> str:
    """Mark a todo as completed."""
    todos = _load()
    for t in todos:
        if t["id"] == todo_id:
            t["status"] = "completed"
            t["updated"] = datetime.now().isoformat()
            _save(todos)
            return f"Completed: {t['title']}"
    return f"Todo {todo_id} not found."


def update_todo(todo_id: str, title: str = "", status: str = "", priority: str = "", due: str = "") -> str:
    """Update a todo's fields. Only changed fields are updated."""
    todos = _load()
    for t in todos:
        if t["id"] == todo_id:
            if title:
                t["title"] = title
            if status:
                t["status"] = status
            if priority:
                t["priority"] = priority
            if due:
                t["due"] = due
            t["updated"] = datetime.now().isoformat()
            _save(todos)
            return f"Updated todo {todo_id}: {t['title']}"
    return f"Todo {todo_id} not found."


def delete_todo(todo_id: str) -> str:
    """Delete a todo."""
    todos = _load()
    for i, t in enumerate(todos):
        if t["id"] == todo_id:
            removed = todos.pop(i)
            _save(todos)
            return f"Deleted: {removed['title']}"
    return f"Todo {todo_id} not found."


# Tool metadata for register()
add_todo_meta = {
    "name": "add_todo",
    "description": "Add a new todo/task. priority: low/medium/high/critical. due: YYYY-MM-DD",
    "func": add_todo,
}

list_todos_meta = {
    "name": "list_todos",
    "description": "List todos. status: all/pending/completed/in_progress. priority: filter.",
    "func": list_todos,
}

complete_todo_meta = {
    "name": "complete_todo",
    "description": "Mark a todo as completed by ID.",
    "func": complete_todo,
}

update_todo_meta = {
    "name": "update_todo",
    "description": "Update a todo's title, status, priority, or due date.",
    "func": update_todo,
}

delete_todo_meta = {
    "name": "delete_todo",
    "description": "Delete a todo by ID.",
    "func": delete_todo,
}
