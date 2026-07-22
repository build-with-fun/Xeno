"""Legacy acknowledger — kept for compat."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AcknowledgmentType(str, Enum):
    BEFORE_WORK = "before_work"
    PROGRESS = "progress"
    AFTER_WORK = "after_work"
    AFTER_FAILURE = "after_failure"
    PARTIAL_DONE = "partial_done"
    SUBTASK_START = "subtask_start"


@dataclass
class Acknowledgment:
    type: AcknowledgmentType
    message: str
    task_id: str = ""
    task_label: str = ""
    estimated_seconds: int = 0
    elapsed_seconds: int = 0
    artifacts: list = None
    metadata: dict = None

    def __post_init__(self):
        if self.artifacts is None:
            self.artifacts = []
        if self.metadata is None:
            self.metadata = {}

    def format(self) -> str:
        return self.message


class TaskAcknowledger:
    """Legacy acknowledger — brain's ResponseGenerator replaces this."""

    def __init__(self, llm_generator=None, use_llm: bool = False):
        self.llm = llm_generator
        self.use_llm = use_llm

    async def acknowledge_start(
        self,
        task_id: str,
        task_label: str,
        description: str,
        estimated_seconds: int,
        subtasks: list = None,
    ) -> Acknowledgment:
        return Acknowledgment(
            AcknowledgmentType.BEFORE_WORK,
            f"On it — starting {task_label}.",
            task_id, task_label, estimated_seconds,
        )

    async def acknowledge_complete(
        self,
        task_id: str,
        task_label: str,
        summary: str,
        artifacts: list,
        elapsed_seconds: int,
        completed_steps: list = None,
        remaining_steps: list = None,
    ) -> Acknowledgment:
        return Acknowledgment(
            AcknowledgmentType.AFTER_WORK,
            f"Done with {task_label}!",
            task_id, task_label, 0, elapsed_seconds, artifacts,
        )

    async def acknowledge_failure(
        self,
        task_id: str,
        task_label: str,
        error: str,
        partial_result: str = "",
        elapsed_seconds: int = 0,
        completed_steps: list = None,
    ) -> Acknowledgment:
        return Acknowledgment(
            AcknowledgmentType.AFTER_FAILURE,
            f"Failed: {error[:100]}",
            task_id, task_label, 0, elapsed_seconds,
        )
