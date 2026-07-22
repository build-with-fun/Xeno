"""Proactive event bus."""
from __future__ import annotations
import asyncio, json, logging, time, uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional
logger = logging.getLogger(__name__)

class EventPriority(str, Enum):
    CRITICAL="critical"; NORMAL="normal"; LOW="low"; BACKGROUND="background"
class EventCategory(str, Enum):
    FILE_CHANGE="file_change"; SCHEDULE="schedule"; SCREEN="screen"; BROWSER="browser"
    SUB_AGENT="sub_agent"; MEMORY="memory"; SYSTEM="system"; USER_PATTERN="user_pattern"

@dataclass
class Event:
    id: str; category: EventCategory; priority: EventPriority
    title: str; description: str = ""; source: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)
    def to_dict(self):
        d = asdict(self); d["category"]=self.category.value; d["priority"]=self.priority.value; return d

class EventBus:
    def __init__(self, log_path=None):
        self.log_path = log_path
        if log_path: log_path.parent.mkdir(parents=True, exist_ok=True)
        self._subscribers = []; self._queue = asyncio.Queue()
        self._history = []; self._running = False
    def subscribe(self, callback):
        self._subscribers.append(callback)
    def publish(self, event):
        try: self._queue.put_nowait(event)
        except: pass
    def publish_simple(self, category, priority, title, description="", source="", **kw):
        e = Event(id=f"evt_{uuid.uuid4().hex[:8]}", category=category, priority=priority,
                  title=title, description=description, source=source, **kw)
        self.publish(e); return e
    async def start(self):
        if self._running: return
        self._running = True
        asyncio.create_task(self._process_loop())
    async def stop(self): self._running = False
    async def _process_loop(self):
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError: continue
            except asyncio.CancelledError: break
            self._history.append(event)
            if self.log_path:
                try:
                    with self.log_path.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(event.to_dict(), default=str)+"\n")
                except: pass
            for sub in self._subscribers:
                try: await sub(event) if asyncio.iscoroutinefunction(sub) else sub(event)
                except: pass
    def recent(self, n=50, category=None):
        events = self._history[-n:]
        return [e for e in events if category is None or e.category == category]
    def stats(self):
        return {"total_events": len(self._history), "subscribers": len(self._subscribers)}

class NotificationQueue:
    def __init__(self):
        self._critical = []; self._normal = []; self._low = []
    async def enqueue(self, event):
        if event.priority == EventPriority.CRITICAL: self._critical.append(event)
        elif event.priority == EventPriority.NORMAL: self._normal.append(event)
        elif event.priority == EventPriority.LOW: self._low.append(event)
    async def drain_critical(self):
        e = self._critical[:]; self._critical.clear(); return e
    async def drain_normal(self):
        e = self._normal[:]; self._normal.clear(); return e
