"""Xeno — autonomous AI agent built CORRECTLY on the real deepagents library.

Uses create_deep_agent() the right way:
- skills=["./skills/"] for SKILL.md progressive disclosure
- memory=["./AGENTS.md"] for persistent project context
- checkpointer=MemorySaver() for multi-turn chat history
- subagents=[SubAgent(...)] that inherit parent's tools
- MCP tools via langchain-mcp-adapters

Enhanced with:
- Hermes-style prompt architecture (SOUL.md + layered prompts)
- Agent-native computer use (CDP + structured state)
- Multi-agent orchestration patterns (supervisor, pipeline, fanout, debate, adaptive)
- Observability (tracing, metrics, exporters)

NO react agents. NO fake shims.
"""

# Set up Windows asyncio policy BEFORE any other imports
# Python 3.14+ uses Proactor by default; 3.16+ deprecates set_event_loop_policy
import sys
if sys.platform == "win32" and sys.version_info < (3, 14):
    import asyncio
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

from xeno.agent import create_xeno_agent, XenoAgent, XenoAgentWrapper
from xeno.config import XenoConfig
from xeno.prompt import PromptBuilder, PromptTierBuilder, ContextCompressor
from xeno.orchestration import (
    SupervisorOrchestrator,
    PipelineOrchestrator,
    FanOutOrchestrator,
    DebateOrchestrator,
    AdaptiveOrchestrator,
    PatternRegistry,
)
from xeno.computer_use import CDPBridge, StateReader, ActionPlanner
from xeno.observability import Tracer, MetricsCollector, get_tracer, get_metrics

__all__ = [
    "create_xeno_agent", "XenoAgent", "XenoAgentWrapper", "XenoConfig",
    "PromptBuilder", "PromptTierBuilder", "ContextCompressor",
    "SupervisorOrchestrator", "PipelineOrchestrator", "FanOutOrchestrator",
    "DebateOrchestrator", "AdaptiveOrchestrator", "PatternRegistry",
    "CDPBridge", "StateReader", "ActionPlanner",
    "Tracer", "MetricsCollector", "get_tracer", "get_metrics",
]
