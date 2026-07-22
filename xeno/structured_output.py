"""Structured output schemas for agent responses.

Implements:
- Pydantic-based response schemas for typed outputs
- Schema registry for registering custom output formats
- Validation and parsing of LLM outputs against schemas
- JSON mode and function calling schemas
- Response format specification
"""

from __future__ import annotations

import json
from typing import Any, Optional, Type

from pydantic import BaseModel, Field, create_model, field_validator


# --- Built-in response schemas ---

class AgentResponse(BaseModel):
    """Standard agent response."""
    content: str = Field(description="The agent's response text")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    reasoning: str = Field(default="", description="Chain of thought reasoning")
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCallResult(BaseModel):
    """Result from a tool call."""
    tool_name: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0


class PlanResult(BaseModel):
    """Structured plan output."""
    goal: str
    steps: list[str]
    estimated_time_minutes: float = 0.0
    priority: str = "medium"
    dependencies: list[str] = Field(default_factory=list)


class ResearchResult(BaseModel):
    """Research output with sources."""
    answer: str
    sources: list[dict[str, str]] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    key_findings: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)


class CodeResult(BaseModel):
    """Code generation output."""
    code: str
    language: str = "python"
    explanation: str = ""
    tests: str = ""
    dependencies: list[str] = Field(default_factory=list)


class MemoryExtraction(BaseModel):
    """Extracted memory from a conversation."""
    action: str = Field(description="add, update, delete, or noop")
    content: str = Field(default="", description="Memory content to store")
    memory_id: str = Field(default="", description="ID for update/delete operations")
    category: str = Field(default="general")
    importance: float = Field(default=5.0, ge=1.0, le=10.0)


class TodoExtraction(BaseModel):
    """Extracted todo items from conversation."""
    action: str = Field(description="create, update, complete, or none")
    title: str = Field(default="")
    description: str = Field(default="")
    priority: str = Field(default="medium")
    due_date: str = Field(default="")
    tags: list[str] = Field(default_factory=list)
    todo_id: str = Field(default="", description="For update/complete operations")


class VerificationResult(BaseModel):
    """Chain of verification output."""
    claim: str
    verified: bool
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0)


class ConsensusResult(BaseModel):
    """Self-consistency voting result."""
    answer: str
    vote_count: int
    total_solutions: int
    confidence: float = Field(ge=0.0, le=1.0)
    alternative_answers: list[str] = Field(default_factory=list)


class ErrorDiagnosis(BaseModel):
    """Self-healing diagnosis output."""
    error_type: str
    severity: str = "medium"
    root_cause: str = ""
    suggested_fixes: list[str] = Field(default_factory=list)
    auto_fixable: bool = False
    affected_files: list[str] = Field(default_factory=list)


class ScheduleInfo(BaseModel):
    """Schedule information."""
    name: str
    task: str
    schedule_type: str
    next_run: str = ""
    enabled: bool = True


class AgentStatus(BaseModel):
    """Full agent status."""
    agent_name: str
    model: str
    uptime_seconds: float = 0.0
    requests_handled: int = 0
    memory_stats: dict[str, Any] = Field(default_factory=dict)
    active_tasks: int = 0
    health: str = "healthy"


class SchemaRegistry:
    """Registry of structured output schemas."""

    def __init__(self):
        self._schemas: dict[str, Type[BaseModel]] = {
            "agent_response": AgentResponse,
            "tool_call_result": ToolCallResult,
            "plan_result": PlanResult,
            "research_result": ResearchResult,
            "code_result": CodeResult,
            "memory_extraction": MemoryExtraction,
            "todo_extraction": TodoExtraction,
            "verification_result": VerificationResult,
            "consensus_result": ConsensusResult,
            "error_diagnosis": ErrorDiagnosis,
            "schedule_info": ScheduleInfo,
            "agent_status": AgentStatus,
        }

    def register(self, name: str, schema: Type[BaseModel]) -> None:
        self._schemas[name] = schema

    def get(self, name: str) -> Optional[Type[BaseModel]]:
        return self._schemas.get(name)

    def list_schemas(self) -> dict[str, str]:
        return {name: schema.__doc__ or name for name, schema in self._schemas.items()}

    def to_json_schema(self, name: str) -> Optional[dict]:
        schema = self._schemas.get(name)
        if schema:
            return schema.model_json_schema()
        return None

    def validate(self, name: str, data: dict) -> tuple[bool, Any]:
        schema = self._schemas.get(name)
        if not schema:
            return False, f"Schema '{name}' not found"
        try:
            validated = schema.model_validate(data)
            return True, validated
        except Exception as e:
            return False, str(e)

    def parse_llm_output(self, name: str, text: str) -> tuple[bool, Any]:
        """Try to parse LLM output text into a structured schema."""
        schema = self._schemas.get(name)
        if not schema:
            return False, f"Schema '{name}' not found"
        # Try JSON parsing
        try:
            data = json.loads(text)
            validated = schema.model_validate(data)
            return True, validated
        except json.JSONDecodeError:
            pass
        # Try extracting JSON from markdown code blocks
        import re
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                validated = schema.model_validate(data)
                return True, validated
            except (json.JSONDecodeError, Exception):
                pass
        return False, f"Could not parse output into schema '{name}'"


# Global registry
schema_registry = SchemaRegistry()
