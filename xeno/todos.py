"""Todo/Task management system for Xeno.

Full-featured task tracker with:
- CRUD operations with status lifecycle
- Priority levels and categories/tags
- Lists and grouping
- Dependencies and blockers
- Recurring tasks
- Time tracking (estimated/actual)
- Reminders and due dates
- Search, filter, sort
- Statistics and reporting
- Persistence (JSON)
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class TodoStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TodoPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Recurrence(str, Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


@dataclass
class Todo:
    id: str
    title: str
    description: str = ""
    status: TodoStatus = TodoStatus.PENDING
    priority: TodoPriority = TodoPriority.MEDIUM
    category: str = ""
    tags: list[str] = field(default_factory=list)
    list_name: str = "default"
    parent_id: Optional[str] = None
    depends_on: list[str] = field(default_factory=list)
    subtasks: list[str] = field(default_factory=list)
    recurrence: Recurrence = Recurrence.NONE
    due_date: Optional[str] = None
    reminder: Optional[str] = None
    estimated_minutes: Optional[int] = None
    actual_minutes: Optional[int] = None
    completed_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    notes: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "category": self.category,
            "tags": self.tags,
            "list_name": self.list_name,
            "parent_id": self.parent_id,
            "depends_on": self.depends_on,
            "subtasks": self.subtasks,
            "recurrence": self.recurrence.value,
            "due_date": self.due_date,
            "reminder": self.reminder,
            "estimated_minutes": self.estimated_minutes,
            "actual_minutes": self.actual_minutes,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "notes": self.notes,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Todo:
        return cls(
            id=data["id"],
            title=data["title"],
            description=data.get("description", ""),
            status=TodoStatus(data.get("status", "pending")),
            priority=TodoPriority(data.get("priority", "medium")),
            category=data.get("category", ""),
            tags=data.get("tags", []),
            list_name=data.get("list_name", "default"),
            parent_id=data.get("parent_id"),
            depends_on=data.get("depends_on", []),
            subtasks=data.get("subtasks", []),
            recurrence=Recurrence(data.get("recurrence", "none")),
            due_date=data.get("due_date"),
            reminder=data.get("reminder"),
            estimated_minutes=data.get("estimated_minutes"),
            actual_minutes=data.get("actual_minutes"),
            completed_at=data.get("completed_at"),
            created_at=data.get("created_at", 0),
            updated_at=data.get("updated_at", 0),
            notes=data.get("notes", []),
            metadata=data.get("metadata", {}),
        )


class TodoManager:
    """Full-featured todo manager with persistence."""

    ACTIVE_STATUSES = {TodoStatus.PENDING, TodoStatus.IN_PROGRESS, TodoStatus.BLOCKED}

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("data/todos.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.todos: dict[str, Todo] = {}
        self._load()

    # ── CRUD ──────────────────────────────────────────────────────────────

    def create(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        category: str = "",
        tags: Optional[list[str]] = None,
        list_name: str = "default",
        due_date: Optional[str] = None,
        reminder: Optional[str] = None,
        estimated_minutes: Optional[int] = None,
        parent_id: Optional[str] = None,
        depends_on: Optional[list[str]] = None,
        recurrence: str = "none",
        metadata: Optional[dict] = None,
    ) -> Todo:
        """Create a new todo."""
        todo_id = f"todo_{uuid.uuid4().hex[:10]}"
        todo = Todo(
            id=todo_id,
            title=title,
            description=description,
            priority=TodoPriority(priority),
            category=category,
            tags=tags or [],
            list_name=list_name,
            parent_id=parent_id,
            depends_on=depends_on or [],
            recurrence=Recurrence(recurrence),
            due_date=due_date,
            reminder=reminder,
            estimated_minutes=estimated_minutes,
            metadata=metadata or {},
        )
        self.todos[todo_id] = todo

        # Link subtask to parent
        if parent_id and parent_id in self.todos:
            self.todos[parent_id].subtasks.append(todo_id)

        # Check if blocked by dependencies
        if todo.depends_on:
            for dep_id in todo.depends_on:
                dep = self.todos.get(dep_id)
                if dep and dep.status not in {TodoStatus.COMPLETED, TodoStatus.CANCELLED}:
                    todo.status = TodoStatus.BLOCKED
                    break

        self._save()
        return todo

    def get(self, todo_id: str) -> Optional[Todo]:
        """Get a todo by ID."""
        return self.todos.get(todo_id)

    def update(
        self,
        todo_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[list[str]] = None,
        list_name: Optional[str] = None,
        due_date: Optional[str] = None,
        reminder: Optional[str] = None,
        estimated_minutes: Optional[int] = None,
        actual_minutes: Optional[int] = None,
        recurrence: Optional[str] = None,
        depends_on: Optional[list[str]] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[Todo]:
        """Update a todo."""
        todo = self.todos.get(todo_id)
        if not todo:
            return None

        if title is not None:
            todo.title = title
        if description is not None:
            todo.description = description
        if status is not None:
            new_status = TodoStatus(status)
            todo.status = new_status
            if new_status == TodoStatus.COMPLETED:
                todo.completed_at = time.time()
                if todo.actual_minutes is None:
                    todo.actual_minutes = int((time.time() - todo.created_at) / 60)
        if priority is not None:
            todo.priority = TodoPriority(priority)
        if category is not None:
            todo.category = category
        if tags is not None:
            todo.tags = tags
        if list_name is not None:
            todo.list_name = list_name
        if due_date is not None:
            todo.due_date = due_date
        if reminder is not None:
            todo.reminder = reminder
        if estimated_minutes is not None:
            todo.estimated_minutes = estimated_minutes
        if actual_minutes is not None:
            todo.actual_minutes = actual_minutes
        if recurrence is not None:
            todo.recurrence = Recurrence(recurrence)
        if depends_on is not None:
            todo.depends_on = depends_on
            # Re-check blocked status
            if todo.status == TodoStatus.BLOCKED:
                all_done = all(
                    self.todos.get(d, Todo(id="", title="", status=TodoStatus.COMPLETED)).status == TodoStatus.COMPLETED
                    for d in todo.depends_on
                )
                if all_done:
                    todo.status = TodoStatus.PENDING
        if metadata is not None:
            todo.metadata.update(metadata)

        todo.updated_at = time.time()
        self._save()
        return todo

    def delete(self, todo_id: str) -> bool:
        """Delete a todo and unlink from parents/dependencies."""
        todo = self.todos.pop(todo_id, None)
        if not todo:
            return False

        # Unlink from parent
        if todo.parent_id and todo.parent_id in self.todos:
            parent = self.todos[todo.parent_id]
            parent.subtasks = [s for s in parent.subtasks if s != todo_id]

        # Unblock dependents
        for other in self.todos.values():
            if todo_id in other.depends_on:
                other.depends_on = [d for d in other.depends_on if d != todo_id]
                if other.depends_on:
                    still_blocked = any(
                        self.todos.get(d, Todo(id="", title="", status=TodoStatus.COMPLETED)).status
                        not in {TodoStatus.COMPLETED, TodoStatus.CANCELLED}
                        for d in other.depends_on
                    )
                    if not still_blocked and other.status == TodoStatus.BLOCKED:
                        other.status = TodoStatus.PENDING

        self._save()
        return True

    # ── Status Actions ────────────────────────────────────────────────────

    def start(self, todo_id: str) -> Optional[Todo]:
        """Mark a todo as in-progress."""
        todo = self.todos.get(todo_id)
        if not todo or todo.status == TodoStatus.BLOCKED:
            return todo
        return self.update(todo_id, status="in_progress")

    def complete(self, todo_id: str) -> Optional[Todo]:
        """Mark a todo as completed."""
        todo = self.todos.get(todo_id)
        if not todo:
            return None
        result = self.update(todo_id, status="completed")
        # Unblock dependents
        self._unblock_dependents(todo_id)
        # Create next occurrence for recurring tasks
        if result and result.recurrence != Recurrence.NONE:
            self._create_next_occurrence(result)
        return result

    def cancel(self, todo_id: str) -> Optional[Todo]:
        """Cancel a todo."""
        return self.update(todo_id, status="cancelled")

    def reopen(self, todo_id: str) -> Optional[Todo]:
        """Reopen a completed or cancelled todo."""
        todo = self.todos.get(todo_id)
        if not todo:
            return None
        return self.update(todo_id, status="pending", completed_at=None)

    def _unblock_dependents(self, completed_id: str) -> None:
        """Check if completing a task unblocks any dependents."""
        for todo in self.todos.values():
            if completed_id in todo.depends_on and todo.status == TodoStatus.BLOCKED:
                still_blocked = any(
                    self.todos.get(d, Todo(id="", title="", status=TodoStatus.COMPLETED)).status
                    not in {TodoStatus.COMPLETED, TodoStatus.CANCELLED}
                    for d in todo.depends_on
                )
                if not still_blocked:
                    todo.status = TodoStatus.PENDING
                    todo.updated_at = time.time()

    def _create_next_occurrence(self, todo: Todo) -> None:
        """Create the next occurrence of a recurring task."""
        from datetime import datetime, timedelta

        if not todo.due_date:
            return
        try:
            due = datetime.fromisoformat(todo.due_date)
        except (ValueError, TypeError):
            return

        delta_map = {
            Recurrence.DAILY: timedelta(days=1),
            Recurrence.WEEKLY: timedelta(weeks=1),
            Recurrence.BIWEEKLY: timedelta(weeks=2),
            Recurrence.MONTHLY: timedelta(days=30),
            Recurrence.YEARLY: timedelta(days=365),
        }
        delta = delta_map.get(todo.recurrence)
        if delta:
            new_due = due + delta
            self.create(
                title=todo.title,
                description=todo.description,
                priority=todo.priority.value,
                category=todo.category,
                tags=list(todo.tags),
                list_name=todo.list_name,
                due_date=new_due.isoformat(),
                reminder=todo.reminder,
                estimated_minutes=todo.estimated_minutes,
                depends_on=list(todo.depends_on),
                recurrence=todo.recurrence.value,
                metadata=dict(todo.metadata),
            )

    # ── Notes ─────────────────────────────────────────────────────────────

    def add_note(self, todo_id: str, content: str) -> Optional[Todo]:
        """Add a note to a todo."""
        todo = self.todos.get(todo_id)
        if not todo:
            return None
        todo.notes.append({
            "content": content,
            "timestamp": time.time(),
        })
        todo.updated_at = time.time()
        self._save()
        return todo

    # ── Search & Filter ───────────────────────────────────────────────────

    def search(self, query: str, limit: int = 20) -> list[Todo]:
        """Search todos by title, description, tags, and notes."""
        query_lower = query.lower()
        scored: list[tuple[float, Todo]] = []
        for todo in self.todos.values():
            score = 0.0
            if query_lower in todo.title.lower():
                score += 10.0
            if query_lower in todo.description.lower():
                score += 5.0
            if any(query_lower in tag.lower() for tag in todo.tags):
                score += 7.0
            if query_lower in todo.category.lower():
                score += 6.0
            if any(query_lower in n.get("content", "").lower() for n in todo.notes):
                score += 3.0
            # Priority boost
            priority_boost = {"urgent": 4, "high": 3, "medium": 2, "low": 1}
            score += priority_boost.get(todo.priority.value, 0) * 0.5
            # Recency boost
            age_hours = (time.time() - todo.created_at) / 3600
            if age_hours < 24:
                score += 1.0
            if score > 0:
                scored.append((score, todo))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:limit]]

    def filter(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        list_name: Optional[str] = None,
        due_before: Optional[str] = None,
        due_after: Optional[str] = None,
        has_dependencies: Optional[bool] = None,
        is_recurring: Optional[bool] = None,
        limit: int = 50,
    ) -> list[Todo]:
        """Filter todos by multiple criteria."""
        results = list(self.todos.values())

        if status:
            statuses = [s.strip() for s in status.split(",")]
            results = [t for t in results if t.status.value in statuses]
        if priority:
            results = [t for t in results if t.priority.value == priority]
        if category:
            results = [t for t in results if t.category == category]
        if tag:
            results = [t for t in results if tag in t.tags]
        if list_name:
            results = [t for t in results if t.list_name == list_name]
        if due_before:
            results = [t for t in results if t.due_date and t.due_date <= due_before]
        if due_after:
            results = [t for t in results if t.due_date and t.due_date >= due_after]
        if has_dependencies is not None:
            if has_dependencies:
                results = [t for t in results if t.depends_on]
            else:
                results = [t for t in results if not t.depends_on]
        if is_recurring is not None:
            if is_recurring:
                results = [t for t in results if t.recurrence != Recurrence.NONE]
            else:
                results = [t for t in results if t.recurrence == Recurrence.NONE]

        return results[:limit]

    def sort(
        self,
        todos: Optional[list[Todo]] = None,
        by: str = "priority",
        descending: bool = False,
    ) -> list[Todo]:
        """Sort todos by a field."""
        items = todos if todos is not None else list(self.todos.values())
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        status_order = {"in_progress": 0, "pending": 1, "blocked": 2, "completed": 3, "cancelled": 4}

        sort_keys = {
            "priority": lambda t: priority_order.get(t.priority.value, 5),
            "status": lambda t: status_order.get(t.status.value, 5),
            "due": lambda t: t.due_date or "9999",
            "created": lambda t: t.created_at,
            "updated": lambda t: t.updated_at,
            "title": lambda t: t.title.lower(),
        }
        key_func = sort_keys.get(by, sort_keys["priority"])
        items.sort(key=key_func, reverse=descending)
        return items

    # ── Lists ─────────────────────────────────────────────────────────────

    def get_lists(self) -> dict[str, int]:
        """Get all lists with their active todo counts."""
        lists: dict[str, int] = {}
        for todo in self.todos.values():
            if todo.status in self.ACTIVE_STATUSES:
                lists[todo.list_name] = lists.get(todo.list_name, 0) + 1
        return lists

    def get_categories(self) -> dict[str, int]:
        """Get all categories with counts."""
        cats: dict[str, int] = {}
        for todo in self.todos.values():
            if todo.category and todo.status in self.ACTIVE_STATUSES:
                cats[todo.category] = cats.get(todo.category, 0) + 1
        return cats

    def get_tags(self) -> dict[str, int]:
        """Get all tags with counts."""
        tags: dict[str, int] = {}
        for todo in self.todos.values():
            if todo.status in self.ACTIVE_STATUSES:
                for tag in todo.tags:
                    tags[tag] = tags.get(tag, 0) + 1
        return tags

    # ── Overdue & Upcoming ────────────────────────────────────────────────

    def get_overdue(self) -> list[Todo]:
        """Get all overdue todos."""
        from datetime import datetime
        now = datetime.now().isoformat()
        return [
            t for t in self.todos.values()
            if t.due_date
            and t.due_date < now
            and t.status in self.ACTIVE_STATUSES
        ]

    def get_due_soon(self, days: int = 7) -> list[Todo]:
        """Get todos due within N days."""
        from datetime import datetime, timedelta
        now = datetime.now()
        cutoff = (now + timedelta(days=days)).isoformat()
        now_str = now.isoformat()
        return [
            t for t in self.todos.values()
            if t.due_date
            and now_str <= t.due_date <= cutoff
            and t.status in self.ACTIVE_STATUSES
        ]

    def get_blocked(self) -> list[Todo]:
        """Get all blocked todos and their blockers."""
        result = []
        for todo in self.todos.values():
            if todo.status == TodoStatus.BLOCKED:
                blockers = []
                for dep_id in todo.depends_on:
                    dep = self.todos.get(dep_id)
                    if dep:
                        blockers.append(f"{dep.title} ({dep.status.value})")
                result.append({"todo": todo, "blockers": blockers})
        return result

    # ── Time Tracking ─────────────────────────────────────────────────────

    def start_timer(self, todo_id: str) -> Optional[Todo]:
        """Start tracking time on a todo (sets status to in_progress and records start)."""
        return self.update(todo_id, status="in_progress", metadata={"timer_started": time.time()})

    def stop_timer(self, todo_id: str, actual_minutes: Optional[int] = None) -> Optional[Todo]:
        """Stop tracking time. If actual_minutes not provided, calculates from timer start."""
        todo = self.todos.get(todo_id)
        if not todo:
            return None
        if actual_minutes is None and todo.metadata.get("timer_started"):
            elapsed = (time.time() - todo.metadata["timer_started"]) / 60
            actual_minutes = int(elapsed)
        return self.update(todo_id, actual_minutes=actual_minutes)

    # ── Statistics ────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Get comprehensive todo statistics."""
        all_todos = list(self.todos.values())
        active = [t for t in all_todos if t.status in self.ACTIVE_STATUSES]
        completed = [t for t in all_todos if t.status == TodoStatus.COMPLETED]
        overdue = self.get_overdue()

        priority_counts = {}
        for p in TodoPriority:
            priority_counts[p.value] = sum(1 for t in active if t.priority == p)

        status_counts = {}
        for s in TodoStatus:
            status_counts[s.value] = sum(1 for t in all_todos if t.status == s)

        est_total = sum(t.estimated_minutes or 0 for t in active)
        actual_total = sum(t.actual_minutes or 0 for t in completed)

        return {
            "total": len(all_todos),
            "active": len(active),
            "completed": len(completed),
            "overdue": len(overdue),
            "blocked": sum(1 for t in all_todos if t.status == TodoStatus.BLOCKED),
            "by_status": status_counts,
            "by_priority": priority_counts,
            "lists": self.get_lists(),
            "categories": self.get_categories(),
            "estimated_minutes": est_total,
            "actual_minutes": actual_total,
            "completion_rate": f"{len(completed) / len(all_todos):.0%}" if all_todos else "0%",
        }

    def summary(self) -> str:
        """Human-readable summary."""
        s = self.stats()
        lines = [
            f"Todo Summary: {s['active']} active, {s['completed']} done, {s['overdue']} overdue, {s['blocked']} blocked",
        ]
        if s["by_priority"]:
            parts = [f"{k}: {v}" for k, v in s["by_priority"].items() if v]
            lines.append(f"Priority: {', '.join(parts)}")
        if s["lists"]:
            parts = [f"{k}: {v}" for k, v in s["lists"].items()]
            lines.append(f"Lists: {', '.join(parts)}")
        return "\n".join(lines)

    # ── Persistence ───────────────────────────────────────────────────────

    def _save(self) -> None:
        data = {tid: t.to_dict() for tid, t in self.todos.items()}
        self.storage_path.write_text(json.dumps(data, indent=2, default=str))

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text())
            self.todos = {tid: Todo.from_dict(td) for tid, td in data.items()}
        except (json.JSONDecodeError, KeyError):
            self.todos = {}

    def export_list(self, list_name: str) -> str:
        """Export a list as formatted text."""
        todos = self.filter(list_name=list_name, limit=999)
        if not todos:
            return f"No todos in list '{list_name}'"
        lines = [f"=== List: {list_name} ({len(todos)} items) ===\n"]
        for t in self.sort(todos, by="priority"):
            status_icon = {
                "pending": "[ ]", "in_progress": "[~]", "blocked": "[!]",
                "completed": "[x]", "cancelled": "[-]",
            }.get(t.status.value, "[ ]")
            lines.append(f"{status_icon} {t.title}")
            if t.due_date:
                lines.append(f"    Due: {t.due_date}")
            if t.depends_on:
                lines.append(f"    Blocked by: {len(t.depends_on)} tasks")
            if t.subtasks:
                lines.append(f"    Subtasks: {len(t.subtasks)}")
            lines.append("")
        return "\n".join(lines)


# ============================================================================
# Singleton getter
# ============================================================================

_todo_manager_instance = None


def get_todo_manager():
    """Get or create the global todo manager singleton."""
    global _todo_manager_instance
    if _todo_manager_instance is None:
        try:
            _todo_manager_instance = TodoManager()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to create todo manager: {e}")
            return None
    return _todo_manager_instance
