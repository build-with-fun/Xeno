"""Legacy classifier — kept for compat (brain replaces this)."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class InputType(str, Enum):
    GENERAL_TALK = "general_talk"
    MEMORY_STORE = "memory_store"
    MEMORY_QUERY = "memory_query"
    QUICK_RESEARCH = "quick_research"
    SHORT_QUESTION = "short_question"
    SCHEDULING = "scheduling"
    TASK = "task"
    COMMAND = "command"


@dataclass
class ClassificationResult:
    input_type: InputType
    confidence: float
    reason: str = ""
    estimated_seconds: int = 0
    suggested_tools: list[str] = field(default_factory=list)
    is_interrupting: bool = False
    extracted_info: dict = field(default_factory=dict)


class InputClassifier:
    """Legacy classifier — brain replaces this entirely."""

    def __init__(self, llm_classifier=None):
        self.llm = llm_classifier

    async def classify(self, user_input: str, has_running_task: bool = False) -> ClassificationResult:
        if user_input.startswith("/"):
            return ClassificationResult(InputType.COMMAND, 1.0, "slash command")
        return ClassificationResult(
            InputType.GENERAL_TALK, 0.5, "legacy classifier default"
        )

    def is_quick_reply(self, result: ClassificationResult) -> bool:
        return result.input_type != InputType.TASK
