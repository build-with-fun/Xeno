"""Xeno TUI Dashboard -- Rich-based live dashboard for the server.

Replaces plain log output with a visual dashboard showing:
- Agent status (discovered + 24/7 always-on)
- Active tasks with progress
- Memory system status (4 tiers + ChromaDB)
- Learning stats (lessons, errors, successes, skills created)
- User profile (name, style, interactions)
- Live log stream

Usage:
    python -m xeno.server              # TUI on by default
    python -m xeno.server --no-tui     # plain logs
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime


# Force UTF-8 for Windows console
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class LogHandler(logging.Handler):
    """Custom logging handler that feeds log records into the dashboard."""

    def __init__(self, dashboard: "Dashboard"):
        super().__init__()
        self.dashboard = dashboard

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            level = record.levelname.lower()
            self.dashboard.log(msg, level=level)
        except Exception:
            pass


class Dashboard:
    """Rich TUI dashboard for the Xeno server. ASCII-safe for Windows."""

    def __init__(self, wrapper=None):
        self.wrapper = wrapper
        # Build console that works on Windows
        self.console = Console(
            force_terminal=True,
            color_system="truecolor",
            width=min(Console().width or 120, 160),
        )
        self._log_buffer: deque[str] = deque(maxlen=80)
        self._lock = threading.Lock()
        self._running = False
        self._start_time = time.time()
        self._refresh_interval = 1.5

    def start(self):
        """Start the dashboard in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the dashboard."""
        self._running = False

    def log(self, message: str, level: str = "info"):
        """Add a log entry to the dashboard."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        # Strip any non-ASCII to prevent encoding errors on Windows
        safe_msg = message.encode("ascii", errors="replace").decode("ascii")
        with self._lock:
            self._log_buffer.append(f"{timestamp} [{level.upper():5s}] {safe_msg}")

    def _run_loop(self):
        """Main dashboard render loop using screen=True for full-screen TUI."""
        try:
            with Live(
                self._build_layout(),
                console=self.console,
                refresh_per_second=1,
                screen=True,
                transient=False,
            ) as live:
                while self._running:
                    try:
                        live.update(self._build_layout())
                    except Exception:
                        pass
                    time.sleep(self._refresh_interval)
        except Exception:
            # If Live fails (e.g. no terminal), fall back to no TUI
            self._running = False

    def _build_layout(self) -> Layout:
        """Build the full dashboard layout."""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="learning", size=4),
            Layout(name="log", size=10),
        )

        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="center", ratio=2),
            Layout(name="right", ratio=1),
        )

        layout["left"].split_column(
            Layout(name="agents", ratio=3),
            Layout(name="always_on", ratio=2),
        )

        layout["right"].split_column(
            Layout(name="memory", ratio=2),
            Layout(name="user_profile", ratio=1),
        )

        layout["header"].update(self._build_header())
        layout["agents"].update(self._build_agents_panel())
        layout["always_on"].update(self._build_always_on_panel())
        layout["center"].update(self._build_tasks_panel())
        layout["memory"].update(self._build_memory_panel())
        layout["user_profile"].update(self._build_user_panel())
        layout["learning"].update(self._build_learning_panel())
        layout["log"].update(self._build_log_panel())

        return layout

    def _build_header(self) -> Panel:
        uptime_s = time.time() - self._start_time
        h, rem = divmod(int(uptime_s), 3600)
        m, s = divmod(rem, 60)
        uptime_str = f"{h}h {m}m" if h else (f"{m}m {s}s" if m else f"{s}s")

        model = provider = "unknown"
        port = 8000
        task_count = 0

        if self.wrapper:
            try:
                model = getattr(self.wrapper.config, "model", "unknown")
                prov = getattr(self.wrapper.config, "provider", None)
                provider = prov.value if hasattr(prov, "value") else str(prov) if prov else "unknown"
            except Exception:
                pass
            try:
                task_count = len(self.wrapper._bg_tasks)
            except Exception:
                pass

        t = Text()
        t.append("  XENO AI DASHBOARD", style="bold white on blue")
        t.append(f"  :{port}  ", style="bold cyan")
        t.append(f"Up: {uptime_str}  ", style="green")
        t.append(f"Model: {model}  ", style="yellow")
        t.append(f"Provider: {provider}  ", style="magenta")
        t.append(f"Tasks: {task_count}", style="blue")

        return Panel(t, border_style="blue")

    def _build_agents_panel(self) -> Panel:
        table = Table(expand=True, show_edge=False, padding=(0, 1))
        table.add_column("S", width=3, justify="center")
        table.add_column("Agent", ratio=2)
        table.add_column("Type", ratio=1)

        agents = []
        if self.wrapper:
            try:
                dyn = getattr(self.wrapper, "_dynamic", None)
                if dyn and hasattr(dyn, "registry"):
                    for aid, desc in dyn.registry.agents.items():
                        name = getattr(desc, "name", aid)
                        atype = getattr(desc, "agent_type", "?")
                        enabled = getattr(desc, "enabled", True)
                        agents.append((name, atype, enabled))
            except Exception:
                pass

        if not agents:
            agents = [
                ("whatsapp", "messaging", True),
                ("coder", "coding", True),
                ("researcher", "research", True),
                ("browser", "automation", True),
                ("analyst", "analysis", True),
                ("planner", "planning", True),
            ]

        for name, atype, enabled in agents:
            st = Text("[+]", style="bold green") if enabled else Text("[ ]", style="dim")
            table.add_row(str(st), name, atype)

        return Panel(table, title="[bold green]Agents[/bold green]", border_style="green")

    def _build_always_on_panel(self) -> Panel:
        table = Table(expand=True, show_edge=False, padding=(0, 1))
        table.add_column("Agent", ratio=2)
        table.add_column("State", ratio=1)
        table.add_column("Tasks", width=5, justify="right")
        table.add_column("Errs", width=4, justify="right")

        agents = []
        if self.wrapper:
            try:
                ao = getattr(self.wrapper, "_always_on", None)
                if ao:
                    for a in ao.list_agents():
                        agents.append((
                            a.get("name", "?"),
                            a.get("state", "?"),
                            a.get("tasks_completed", 0),
                            a.get("errors", 0),
                        ))
            except Exception:
                pass

        if not agents:
            agents = [("whatsapp", "running", 0, 0)]

        for name, state, tasks, errors in agents:
            sc = "green" if state == "running" else "yellow" if state == "starting" else "red" if state == "failed" else "dim"
            table.add_row(name, Text(state, style=sc), str(tasks), str(errors))

        return Panel(table, title="[bold yellow]24/7 Agents[/bold yellow]", border_style="yellow")

    def _build_tasks_panel(self) -> Panel:
        table = Table(expand=True, show_edge=False, padding=(0, 1))
        table.add_column("ID", width=10)
        table.add_column("Prompt", ratio=3)
        table.add_column("Pri", width=7)
        table.add_column("Status", width=10)
        table.add_column("Time", width=6, justify="right")

        tasks = []
        if self.wrapper:
            try:
                sorted_t = sorted(
                    self.wrapper._bg_tasks.values(),
                    key=lambda t: t.get("created", 0),
                    reverse=True,
                )
                for t in sorted_t[:10]:
                    tid = t.get("id", "?")[-8:]
                    prompt = (t.get("prompt", "") or "")[:45]
                    pri = t.get("priority", "normal")
                    status = t.get("status", "?")
                    created = t.get("created", 0)
                    completed = t.get("completed")
                    if completed and created:
                        el = f"{completed - created:.1f}s"
                    elif created:
                        el = f"{time.time() - created:.0f}s"
                    else:
                        el = "-"
                    tasks.append((tid, prompt, pri, status, el))
            except Exception:
                pass

        if not tasks:
            table.add_row("-", "No tasks yet", "-", "-", "-")
        else:
            for tid, prompt, pri, status, el in tasks:
                ps = "bold red" if pri == "heavy" else "yellow" if pri == "normal" else "green"
                ss = "green" if status == "completed" else "cyan" if status in ("running", "accepted") else "red" if status == "failed" else "white"
                table.add_row(tid, prompt, Text(pri, style=ps), Text(status, style=ss), el)

        return Panel(table, title="[bold magenta]Tasks[/bold magenta]", border_style="magenta")

    def _build_memory_panel(self) -> Panel:
        lines = []
        if self.wrapper:
            try:
                summary = self.wrapper.memory.full_summary()
                for line in summary.split("\n"):
                    line = line.strip()
                    if line:
                        safe = line.encode("ascii", errors="replace").decode("ascii")
                        lines.append(f"  {safe}")
            except Exception:
                lines.append("  Memory: unavailable")

            try:
                sem = getattr(self.wrapper.memory, "_semantic", None)
                if sem and hasattr(sem, "_chroma_collection") and sem._chroma_collection:
                    lines.append(f"  ChromaDB: {sem._chroma_collection.count()} vectors")
            except Exception:
                pass
        else:
            lines.append("  Not initialized")

        return Panel("\n".join(lines) or "  No data", title="[bold cyan]Memory[/bold cyan]", border_style="cyan")

    def _build_user_panel(self) -> Panel:
        lines = []
        if self.wrapper:
            try:
                p = self.wrapper.auto_save.user_profile
                if p.get("name"):
                    lines.append(f"  Name: {p['name']}")
                if p.get("role"):
                    lines.append(f"  Role: {p['role']}")
                lines.append(f"  Style: {p.get('communication_style', '?')}")
                lines.append(f"  Interactions: {p.get('total_interactions', 0)}")
                if p.get("tech_stack"):
                    lines.append(f"  Tech: {', '.join(p['tech_stack'][:4])}")
                prefs = getattr(self.wrapper.auto_save, "preferences", [])
                facts = getattr(self.wrapper.auto_save, "facts", [])
                if prefs:
                    lines.append(f"  Prefs: {len(prefs)}")
                if facts:
                    lines.append(f"  Facts: {len(facts)}")
            except Exception:
                lines.append("  Profile: unavailable")
        else:
            lines.append("  Not initialized")

        return Panel("\n".join(lines) or "  No data", title="[bold blue]User Profile[/bold blue]", border_style="blue")

    def _build_learning_panel(self) -> Panel:
        lines = []
        if self.wrapper:
            try:
                stats = self.wrapper.learning.get_stats()
                lines.append(
                    f"  Lessons: {stats.get('total_lessons', 0)}  |  "
                    f"Errors: {stats.get('total_errors', 0)} ({stats.get('resolved_errors', 0)} resolved)  |  "
                    f"Successes: {stats.get('total_successes', 0)}  |  "
                    f"Skills: {stats.get('skills_created', 0)}"
                )
                try:
                    lessons = self.wrapper.learning.get_all_lessons(limit=1)
                    if lessons:
                        lt = getattr(lessons[0], "lesson", str(lessons[0]))[:90]
                        safe_lt = lt.encode("ascii", errors="replace").decode("ascii")
                        lines.append(f'  Latest: "{safe_lt}"')
                except Exception:
                    pass
            except Exception:
                lines.append("  Learning: unavailable")
        else:
            lines.append("  Not initialized")

        return Panel("\n".join(lines) or "  No data", title="[bold red]Learning & Self-Improvement[/bold red]", border_style="red")

    def _build_log_panel(self) -> Panel:
        with self._lock:
            log_lines = list(self._log_buffer)

        if not log_lines:
            log_lines = ["  Waiting for activity..."]

        display = log_lines[-8:]
        return Panel("\n".join(display), title="[bold white]Live Log[/bold white]", border_style="white")
