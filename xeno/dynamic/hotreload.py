"""Hot-reload watcher for the dynamic system.

Watches configured directories for file changes and triggers reloads:
- Agent description.md changes -> reload agent
- Skill SKILL.md changes -> reload skill
- Plugin __init__.py changes -> reload plugin
- Config file changes -> reload config
- MCP config changes -> reload MCP connections
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class WatchedPath:
    path: str
    pattern: str  # filename pattern to match (e.g., "description.md", "SKILL.md")
    callback: Callable[[str, str], None]  # callback(changed_path, event_type)
    last_mtime: float = 0.0
    event_types: list[str] = field(default_factory=lambda: ["modified", "created"])
    enabled: bool = True


class HotReloadWatcher:
    """Filesystem watcher that triggers component reloads.

    Features:
    - Watch multiple directories with different patterns
    - Debounce rapid changes
    - Background polling thread
    - Manual check (non-threaded) mode
    - Change history logging
    """

    def __init__(self, poll_interval: float = 2.0):
        self.poll_interval = poll_interval
        self.watches: list[WatchedPath] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._change_log: list[dict[str, Any]] = []
        self._callbacks: dict[str, list[Callable]] = {}

    def watch(
        self, path: str, pattern: str,
        callback: Callable[[str, str], None],
        event_types: Optional[list[str]] = None,
    ) -> None:
        """Add a path to watch."""
        wp = WatchedPath(
            path=path, pattern=pattern, callback=callback,
            event_types=event_types or ["modified", "created"],
        )
        # Set initial mtime
        watch_dir = Path(path)
        if watch_dir.is_dir():
            for f in watch_dir.rglob(pattern):
                wp.last_mtime = max(wp.last_mtime, f.stat().st_mtime)
        elif watch_dir.is_file():
            wp.last_mtime = watch_dir.stat().st_mtime
        self.watches.append(wp)

    def on(self, event_name: str, callback: Callable) -> None:
        """Register a named event callback."""
        self._callbacks.setdefault(event_name, []).append(callback)

    def start(self) -> None:
        """Start the background watcher thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="hot-reload")
        self._thread.start()
        logger.info("Hot-reload watcher started")

    def stop(self) -> None:
        """Stop the watcher thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Hot-reload watcher stopped")

    def check_now(self) -> list[dict[str, Any]]:
        """Perform a single check cycle (non-threaded)."""
        changes = []
        for wp in self.watches:
            if not wp.enabled:
                continue
            watch_dir = Path(wp.path)
            if not watch_dir.exists():
                continue
            for f in watch_dir.rglob(wp.pattern):
                if not f.is_file():
                    continue
                current_mtime = f.stat().st_mtime
                if current_mtime > wp.last_mtime:
                    event_type = "created" if wp.last_mtime == 0 else "modified"
                    if event_type in wp.event_types:
                        change = {
                            "path": str(f),
                            "pattern": wp.pattern,
                            "event": event_type,
                            "timestamp": time.time(),
                        }
                        changes.append(change)
                        self._change_log.append(change)
                        try:
                            wp.callback(str(f), event_type)
                        except Exception as e:
                            logger.error(f"Watch callback error for {f}: {e}")
                        self._fire_event("change", change)
                    wp.last_mtime = current_mtime
        return changes

    def _poll_loop(self) -> None:
        """Background polling loop."""
        while self._running:
            try:
                self.check_now()
            except Exception as e:
                logger.error(f"Hot-reload poll error: {e}")
            time.sleep(self.poll_interval)

    def _fire_event(self, event_name: str, data: Any) -> None:
        for cb in self._callbacks.get(event_name, []):
            try:
                cb(data)
            except Exception as e:
                logger.error(f"Event callback error: {e}")

    def get_change_log(self, limit: int = 50) -> list[dict]:
        return self._change_log[-limit:]

    def set_enabled(self, watch_path: str, enabled: bool) -> bool:
        for wp in self.watches:
            if wp.path == watch_path:
                wp.enabled = enabled
                return True
        return False

    def remove_watch(self, watch_path: str) -> bool:
        before = len(self.watches)
        self.watches = [w for w in self.watches if w.path != watch_path]
        return len(self.watches) < before

    def summary(self) -> str:
        active = sum(1 for w in self.watches if w.enabled)
        return f"HotReload: {active}/{len(self.watches)} watches active, {len(self._change_log)} changes detected"
