from __future__ import annotations

import enum
import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional


class LayerType(enum.Enum):
    SOUL = "soul"
    MEMORY = "memory"
    PROJECT = "project"
    SESSION = "session"
    METADATA = "metadata"
    INSTRUCTIONS = "instructions"
    WORKING = "working"
    SKILLS_INDEX = "skills_index"


@dataclass
class PromptLayer:
    type: LayerType
    content: str
    version: int = 0
    cache_key: str = ""
    persistent: bool = True

    def __post_init__(self):
        self._hash()

    def _hash(self):
        self.cache_key = hashlib.md5(self.content.encode()).hexdigest()[:16]

    def is_valid(self, expected_version: int) -> bool:
        return self.version == expected_version

    def updated(self, new_content: str, new_version: int) -> PromptLayer:
        return PromptLayer(
            type=self.type,
            content=new_content,
            version=new_version,
            persistent=self.persistent,
        )


SOUL_MD_TEMPLATE = """You are Xeno — an autonomous AI agent running on {os_name} ({platform}).
Working directory: {cwd}
Python: {python_version}

## CORE IDENTITY
You are a general-purpose autonomous agent. You reason step-by-step, use tools to take action, and remember context across sessions. You are proactive, helpful, and honest about your limitations.

## CORE RULES
1. NEVER hallucinate tool results — always call the actual tool and use its real output.
2. NEVER expose or log API keys, tokens, or secrets.
3. When uncertain, search memory or the web before guessing.
4. Verify your work — after writing code, test it. After taking action, confirm the result.
5. Keep responses concise and actionable unless the user asks for detail.

## COMMUNICATION STYLE
- Be direct and concise
- Confirm before irreversible actions (deletes, destructive edits)
- Report what you DID, not just what you'll do
- Use natural language, not robotic templates"""

MEMORY_MD_TEMPLATE = """# Xeno Persistent Memory

## User Profile
Name: {user_name}
Preferences: {preferences}
Goals: {goals}

## Session Context
Session ID: {session_id}
Started: {started_at}

## Important Facts
{facts}
"""

PROJECT_MD_TEMPLATE = """# Project Context

## Working Directory
{project_root}

## Active Skills
{skills_index}

## Recent Tasks
{recent_tasks}
"""
