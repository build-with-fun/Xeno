"""Ambient daemons."""
from __future__ import annotations
import asyncio, logging, time
from pathlib import Path
from typing import Any, Optional
from xeno.proactive.event_bus import EventBus, EventCategory, EventPriority
logger = logging.getLogger(__name__)

class BaseDaemon:
    def __init__(self, name, bus, poll_interval=60.0):
        self.name=name; self.bus=bus; self.poll_interval=poll_interval
        self._task=None; self._running=False
    async def start(self):
        if self._running: return
        self._running=True; self._task=asyncio.create_task(self._run())
    async def stop(self):
        self._running=False
        if self._task: self._task.cancel()
    async def _run(self):
        while self._running:
            try: await self.poll()
            except: pass
            try: await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError: break
    async def poll(self): pass

class FileWatcherDaemon(BaseDaemon):
    def __init__(self, bus, watch_dir, poll_interval=10.0):
        super().__init__("file_watcher", bus, poll_interval)
        self.watch_dir = watch_dir; self._snapshot = {}
    async def poll(self):
        if not self.watch_dir.exists(): return
        current = {}
        for p in self.watch_dir.rglob("*"):
            if p.is_file():
                try: current[p] = p.stat().st_mtime
                except: continue
        added = set(current.keys()) - set(self._snapshot.keys())
        for p in added:
            try: rel = str(p.relative_to(self.watch_dir))
            except: rel = str(p)
            if any(part.startswith(".") or part == "__pycache__" for part in p.parts): continue
            self.bus.publish_simple(EventCategory.FILE_CHANGE, EventPriority.LOW,
                f"file added: {rel}", source=self.name)
        self._snapshot = current

class MemoryDaemon(BaseDaemon):
    def __init__(self, bus, memory_manager, poll_interval=300.0):
        super().__init__("memory", bus, poll_interval); self.memory = memory_manager
    async def poll(self): pass

class DaemonManager:
    def __init__(self, event_bus):
        self.bus = event_bus; self._daemons = {}
    def register(self, daemon): self._daemons[daemon.name] = daemon
    async def start_all(self):
        for d in self._daemons.values(): await d.start()
    async def stop_all(self):
        for d in self._daemons.values(): await d.stop()
    def list_daemons(self):
        return [{"name":d.name,"running":d._running} for d in self._daemons.values()]
