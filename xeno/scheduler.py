from __future__ import annotations
import json
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Callable
from dataclasses import dataclass, field, asdict

from xeno.config import XenoConfig


@dataclass
class ScheduledTask:
    id: str
    name: str
    prompt: str
    schedule_type: str  # "once", "interval", "daily", "weekly", "monthly", "yearly"
    schedule_config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: str = ""
    last_run: str | None = None
    next_run: str | None = None
    agent_name: str | None = None
    action: dict | None = None  # e.g. {"tool": "describe_screen", "args": {}}

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


_scheduler_instance: Scheduler | None = None


def get_scheduler() -> Scheduler | None:
    """Get or create the global scheduler singleton."""
    global _scheduler_instance
    if _scheduler_instance is None:
        try:
            _scheduler_instance = Scheduler(XenoConfig.from_env())
        except Exception:
            return None
    return _scheduler_instance


class Scheduler:
    """Full CRUD scheduling system with once, interval, daily, weekly, monthly, yearly support."""

    def __init__(self, config: XenoConfig):
        self.config = config
        self.schedules_file = config.data_dir / "schedules.json"
        self.tasks: dict[str, ScheduledTask] = self._load()
        self._callbacks: dict[str, Callable] = {}
        self._running = False

    def stop(self):
        """Stop the scheduler."""
        self._running = False

    def _load(self) -> dict[str, ScheduledTask]:
        if self.schedules_file.exists():
            try:
                data = json.loads(self.schedules_file.read_text(encoding="utf-8"))
                return {k: ScheduledTask(**v) for k, v in data.items()}
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save(self):
        data = {k: asdict(v) for k, v in self.tasks.items()}
        self.schedules_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def create(self, name: str, prompt: str, schedule_type: str, schedule_config: dict[str, Any] | None = None, agent_name: str | None = None) -> str:
        task_id = str(uuid.uuid4())[:8]
        task = ScheduledTask(
            id=task_id,
            name=name,
            prompt=prompt,
            schedule_type=schedule_type,
            schedule_config=schedule_config or {},
            agent_name=agent_name,
        )
        task.next_run = self._calculate_next_run(task)
        self.tasks[task_id] = task
        self._save()
        return f"Created schedule '{name}' (id: {task_id}, type: {schedule_type}, next: {task.next_run})"

    def read(self, task_id: str) -> str:
        task = self.tasks.get(task_id)
        if not task:
            return f"No schedule found with id '{task_id}'"
        return json.dumps(asdict(task), indent=2, default=str)

    def update(self, task_id: str, **kwargs) -> str:
        task = self.tasks.get(task_id)
        if not task:
            return f"No schedule found with id '{task_id}'"
        for key, val in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, val)
        task.next_run = self._calculate_next_run(task)
        self._save()
        return f"Updated schedule '{task.name}'"

    def delete(self, task_id: str) -> str:
        task = self.tasks.pop(task_id, None)
        if task:
            self._save()
            return f"Deleted schedule '{task.name}'"
        return f"No schedule found with id '{task_id}'"

    def list_all(self) -> str:
        if not self.tasks:
            return "No schedules configured."
        output = []
        for tid, task in self.tasks.items():
            status = "ENABLED" if task.enabled else "DISABLED"
            output.append(f"[{tid}] {status} {task.name} ({task.schedule_type}) - next: {task.next_run}")
        return "\n".join(output)

    def get_due_tasks(self) -> list[ScheduledTask]:
        # Re-read from disk so we pick up tasks created by other Scheduler instances
        self.tasks = self._load()
        now = datetime.now()
        due = []
        for task in self.tasks.values():
            if not task.enabled or not task.next_run:
                continue
            try:
                next_dt = datetime.fromisoformat(task.next_run)
                if next_dt <= now:
                    due.append(task)
            except (ValueError, TypeError):
                continue
        return due

    def mark_executed(self, task_id: str):
        task = self.tasks.get(task_id)
        if task:
            if task.schedule_type in ("after_delay", "once"):
                # One-shot: delete after first execution
                del self.tasks[task_id]
            else:
                task.last_run = datetime.now().isoformat()
                task.next_run = self._calculate_next_run(task)
            self._save()

    def enable(self, task_id: str) -> str:
        return self.update(task_id, enabled=True)

    def disable(self, task_id: str) -> str:
        return self.update(task_id, enabled=False)

    def _calculate_next_run(self, task: ScheduledTask) -> str:
        now = datetime.now()
        cfg = task.schedule_config

        if task.schedule_type == "once":
            # Support both run_at and delay_seconds
            run_at = cfg.get("run_at")
            if run_at:
                return run_at
            delay = cfg.get("delay_seconds", cfg.get("seconds", 0))
            if delay > 0:
                return (now + timedelta(seconds=delay)).isoformat()
            return (now + timedelta(hours=1)).isoformat()

        elif task.schedule_type == "after_delay":
            seconds = cfg.get("seconds", 0) or cfg.get("delay_seconds", 0)
            minutes = cfg.get("minutes", 0)
            hours = cfg.get("hours", 0)
            days = cfg.get("days", 0)
            total = seconds + (minutes * 60) + (hours * 3600) + (days * 86400)
            if total <= 0:
                total = 3600  # Default 1 hour
            return (now + timedelta(seconds=total)).isoformat()

        elif task.schedule_type == "interval":
            seconds = cfg.get("seconds", 0)
            minutes = cfg.get("minutes", 0)
            hours = cfg.get("hours", 0)
            total = seconds + (minutes * 60) + (hours * 3600)
            if total <= 0:
                total = 3600
            return (now + timedelta(seconds=total)).isoformat()

        elif task.schedule_type == "daily":
            hour = cfg.get("hour", 9)
            minute = cfg.get("minute", 0)
            next_dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_dt <= now:
                next_dt += timedelta(days=1)
            return next_dt.isoformat()

        elif task.schedule_type == "weekly":
            weekday = cfg.get("weekday", 0)
            hour = cfg.get("hour", 9)
            minute = cfg.get("minute", 0)
            days_ahead = weekday - now.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_dt = now + timedelta(days=days_ahead)
            next_dt = next_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
            return next_dt.isoformat()

        elif task.schedule_type == "monthly":
            day = cfg.get("day", 1)
            hour = cfg.get("hour", 9)
            minute = cfg.get("minute", 0)
            if now.day >= day:
                if now.month == 12:
                    next_dt = now.replace(year=now.year + 1, month=1, day=day, hour=hour, minute=minute, second=0, microsecond=0)
                else:
                    next_dt = now.replace(month=now.month + 1, day=day, hour=hour, minute=minute, second=0, microsecond=0)
            else:
                next_dt = now.replace(day=day, hour=hour, minute=minute, second=0, microsecond=0)
            return next_dt.isoformat()

        elif task.schedule_type == "yearly":
            month = cfg.get("month", 1)
            day = cfg.get("day", 1)
            hour = cfg.get("hour", 9)
            minute = cfg.get("minute", 0)
            next_dt = now.replace(year=now.year, month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
            if next_dt <= now:
                next_dt = next_dt.replace(year=now.year + 1)
            return next_dt.isoformat()

        elif task.schedule_type == "cron":
            return self._calculate_cron_next(cfg, now)

        return (now + timedelta(hours=1)).isoformat()

    def _calculate_cron_next(self, cfg: dict, now: datetime) -> str:
        """Calculate next run from a simple cron-like expression.
        Supports: minute, hour, day_of_month, month, day_of_week (0=Mon)
        Uses '*' for 'every'. Limited implementation — no step values or ranges.
        """
        minute = cfg.get("minute", "*")
        hour = cfg.get("hour", "*")
        day_of_month = cfg.get("day_of_month", "*")
        month = cfg.get("month", "*")
        day_of_week = cfg.get("day_of_week", "*")

        # Simple approach: try next 365 days
        check = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(525600):  # max 1 year of minutes
            if self._cron_matches(check.minute, minute, 0, 59):
                if self._cron_matches(check.hour, hour, 0, 23):
                    if self._cron_matches(check.day, day_of_month, 1, 31):
                        if self._cron_matches(check.month, month, 1, 12):
                            if self._cron_matches(check.isoweekday() % 7, day_of_week, 0, 6):
                                return check.isoformat()
            check += timedelta(minutes=1)
        return (now + timedelta(hours=1)).isoformat()

    def _cron_matches(self, current: int, expr: str, min_val: int, max_val: int) -> bool:
        """Check if a cron expression matches a current value."""
        if expr == "*":
            return True
        try:
            val = int(expr)
            return val == current
        except ValueError:
            return True  # If we can't parse, assume match
