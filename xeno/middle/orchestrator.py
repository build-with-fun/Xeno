"""Legacy orchestrator — kept for compat. Brain orchestrator is the new main."""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class ConversationEventType(str, Enum):
    BEFORE_WORK = "before_work"
    MIDDLE_ANSWER = "middle_answer"
    INSTANT_ANSWER = "instant_answer"
    PROGRESS = "progress"
    AFTER_WORK = "after_work"
    AFTER_FAILURE = "after_failure"
    PARTIAL_DONE = "partial_done"
    QUEUED = "queued"
    QUEUE_STARTED = "queue_started"
    SUBTASK_START = "subtask_start"
    INFO = "info"


@dataclass
class ConversationEvent:
    type: ConversationEventType
    message: str
    task_id: str = ""
    task_label: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d


class ConversationalOrchestrator:
    """Legacy orchestrator — brain orchestrator is the new main."""

    def __init__(
        self,
        classifier,
        acknowledger,
        middle_agent,
        task_runner: Optional[Callable] = None,
        instant_answer_fn: Optional[Callable] = None,
        progress_check_interval: float = 30.0,
    ):
        self.classifier = classifier
        self.acknowledger = acknowledger
        self.middle_agent = middle_agent
        self.task_runner = task_runner
        self.instant_answer_fn = instant_answer_fn
        self.progress_interval = progress_check_interval
        self._running_task = None
        self._queue: list = []
        self._subscribers: list[asyncio.Queue] = []
        self._started = False

    async def start(self) -> None:
        self._started = True
        logger.info("Conversational orchestrator started")

    async def stop(self) -> None:
        self._started = False
        logger.info("Conversational orchestrator stopped")

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue[ConversationEvent] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    @property
    def has_running_task(self) -> bool:
        return self._running_task is not None

    async def handle_user_input(self, user_input: str) -> None:
        if self.instant_answer_fn:
            try:
                answer = await self.instant_answer_fn(user_input)
            except Exception as e:
                answer = f"Error: {e}"
            for q in self._subscribers:
                try:
                    q.put_nowait(ConversationEvent(ConversationEventType.INSTANT_ANSWER, answer))
                except asyncio.QueueFull:
                    pass

    def status(self) -> dict:
        return {
            "started": self._started,
            "running_task": None,
            "queue_size": len(self._queue),
        }
