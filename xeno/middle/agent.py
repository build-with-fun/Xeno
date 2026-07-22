"""Legacy middle agent — kept for compat."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MiddleQueryResult:
    answered: bool
    answer: str = ""
    used_tools: list[str] = field(default_factory=list)
    duration_ms: int = 0
    queued_for_later: bool = False
    queue_reason: str = ""
    should_interrupt_main: bool = False
    interrupt_reason: str = ""


class MiddleAgent:
    """Legacy middle agent — brain orchestrator replaces this."""

    def __init__(
        self,
        classifier,
        acknowledger,
        llm=None,
        web_search_fn=None,
        memory_recall_fn=None,
        memory_store_fn=None,
        schedule_fn=None,
        progress_fn=None,
        max_response_seconds: int = 30,
    ):
        self.classifier = classifier
        self.acknowledger = acknowledger
        self.llm = llm
        self.web_search = web_search_fn
        self.memory_recall = memory_recall_fn
        self.memory_store_fn = memory_store_fn
        self.schedule = schedule_fn
        self.progress = progress_fn
        self.max_seconds = max_response_seconds

    async def handle_query(
        self,
        user_input: str,
        running_task_id: str = "",
        running_task_label: str = "",
        running_task_summary: str = "",
    ) -> MiddleQueryResult:
        return MiddleQueryResult(answered=True, answer="OK")
