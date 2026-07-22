"""Rich-based TUI."""
from __future__ import annotations
import logging, os, sys, time
from dataclasses import dataclass, field
from typing import Optional
logger = logging.getLogger(__name__)

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.text import Text
    from rich.rule import Rule
    from rich.table import Table
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    logger.warning("Rich not installed")

def _make_console() -> Console:
    """Create a Rich Console suitable for the current platform.

    On Windows legacy terminal, tries to enable VT processing and
    use modern rendering to avoid cp1252 emoji encoding errors.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                new_mode = mode.value | 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
                kernel32.SetConsoleMode(handle, new_mode)
        except Exception:
            pass
        return Console(legacy_windows=False, force_terminal=True)
    return Console()

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import InMemoryHistory
    from prompt_toolkit.completion import WordCompleter
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False

@dataclass
class ToolCallCard:
    name: str; args: dict; result: Any = None
    duration_ms: int = 0; success: bool = True; risk_level: str = "safe"

class RichTUI:
    SLASH_COMMANDS = ["/plan","/act","/reflect","/chat","/undo","/agents","/tasks",
                      "/memory","/skills","/checkpoint","/status","/help","/quit",
                      "/profile","/sleep","/cancel"]
    def __init__(self):
        if not RICH_AVAILABLE: raise RuntimeError("Rich not available")
        self.console = _make_console()
        self._history = InMemoryHistory() if PROMPT_TOOLKIT_AVAILABLE else None
        self._completer = WordCompleter(self.SLASH_COMMANDS) if PROMPT_TOOLKIT_AVAILABLE else None
        self.mode = "CHAT"; self.feature_label = ""
    def set_mode(self, mode, feature=""):
        self.mode = mode.upper(); self.feature_label = feature
    def header(self):
        self.console.print(Rule(style="cyan"))
        self.console.print(Text("  Xeno 2.0 — Advanced Agent System", style="bold white"))
        if self.feature_label:
            self.console.print(Text(f"  ⚡ {self.feature_label}", style="yellow"))
        self.console.print(Rule(style="cyan"))
        self.console.print()
    async def user_prompt(self, prompt="you> "):
        """ASYNC user prompt — uses run_in_executor so the event loop isn't blocked.

        This is CRITICAL: while waiting for user input, the event loop can still
        process background tasks (showing AFTER_WORK events when tasks complete,
        firing reminders, etc.)
        """
        import asyncio
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, lambda: input(prompt))
        except (EOFError, KeyboardInterrupt):
            return "/quit"
    def thinking(self, msg="thinking..."):
        self.console.print(Text(f"  {msg}", style="dim italic"), end="\r")
    def clear_thinking(self):
        self.console.print(" "*80, end="\r")
    def assistant_response(self, text, render_markdown=True):
        if render_markdown:
            try:
                self.console.print(Panel(Markdown(text), border_style="green", title="xeno", title_align="left"))
            except: self.console.print(text)
        else: self.console.print(text)
    def info(self, msg):
        self.console.print(Text(f"  ℹ {msg}", style="blue"))
    def warning(self, msg):
        self.console.print(Text(f"  ⚠ {msg}", style="yellow"))
    def error(self, msg):
        self.console.print(Text(f"  ✗ {msg}", style="red"))
    def success(self, msg):
        self.console.print(Text(f"  ✓ {msg}", style="green"))
    def divider(self):
        self.console.print(Rule(style="dim"))
    def status_panel(self, status):
        table = Table(show_header=False, box=box.SIMPLE)
        table.add_column("Key", style="cyan"); table.add_column("Value", style="white")
        for k,v in status.items():
            if isinstance(v, dict): v = ", ".join(f"{kk}={vv}" for kk,vv in list(v.items())[:5])
            table.add_row(k, str(v)[:80])
        self.console.print(Panel(table, border_style="blue", title="status", title_align="left"))
    def slash_command_help(self):
        table = Table(show_header=True, box=box.SIMPLE, title="Slash Commands")
        table.add_column("Command", style="cyan"); table.add_column("Description")
        for cmd, desc in [("/status","Show system status"),("/memory","Memory summary"),
                          ("/profile","Show user profile"),("/tasks","List tasks"),
                          ("/cancel","Cancel running task"),("/sleep","Memory sleep cycle"),
                          ("/help","Show help"),("/quit","Exit")]:
            table.add_row(cmd, desc)
        self.console.print(table)

def make_tui():
    if not RICH_AVAILABLE: return None
    return RichTUI()
