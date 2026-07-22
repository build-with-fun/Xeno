"""Sub-agent registry — uses REAL deepagents SubAgent TypedDicts.

Each sub-agent is a SubAgent TypedDict with:
- name, description, system_prompt (required)
- model: the LLM to use (optional — inherits parent's if omitted)
- tools: OPTIONAL — if omitted, sub-agent INHERITS the parent's tools

This is the CORRECT way to use deepagents sub-agents:
the parent's tools are automatically available to sub-agents.
Only declare tools that are UNIQUE to a sub-agent.
"""

from __future__ import annotations

import logging
from typing import Any

from deepagents import SubAgent

logger = logging.getLogger(__name__)


def get_research_subagent(config=None) -> SubAgent:
    """Research agent — deep web research. Inherits parent's tools."""
    model = config.model if config else None
    return SubAgent(
        name="research-agent",
        description=(
            "Deep research agent for web searches, fact-finding, analysis, and knowledge synthesis. "
            "Use for: researching topics, finding facts, comparing sources, "
            "building knowledge bases, competitive analysis, market research, academic research."
        ),
        system_prompt=(
            "You are an expert research agent. Your job is thorough, accurate research.\n\n"
            "WORKFLOW:\n"
            "1. Search broadly first with web_search, then dive deep with web_fetch\n"
            "2. Cross-reference information from multiple sources\n"
            "3. Store key findings in memory with memory_store_knowledge\n"
            "4. Write comprehensive reports with write_file\n"
            "5. Always cite sources with URLs\n\n"
            "Never make up facts. If you can't find information, say so."
        ),
        **({"model": model} if model else {}),
        # No tools= → inherits parent's tools
    )


def get_coder_subagent(config=None) -> SubAgent:
    """Coder agent — expert coding. Inherits parent's tools."""
    model = config.model if config else None
    return SubAgent(
        name="coder-agent",
        description=(
            "Expert software engineering agent for writing, debugging, reviewing, refactoring, "
            "and testing code in ANY programming language. "
            "Use for: building apps, fixing bugs, code reviews, refactoring, "
            "creating scripts, automation, API integration, database work."
        ),
        system_prompt=(
            "You are an expert software engineer with full system access.\n\n"
            "WORKFLOW:\n"
            "1. Plan the solution before writing code\n"
            "2. Write clean, well-structured code with error handling\n"
            "3. Test after every change with shell_execute or execute_python\n"
            "4. If errors occur, read the error message and fix it\n"
            "5. Create reusable skills for repeated coding patterns\n\n"
            "Always use type hints, docstrings, and follow language conventions."
        ),
        **({"model": model} if model else {}),
    )


def get_browser_subagent(config=None) -> SubAgent:
    """Browser agent — web automation. Inherits parent's tools."""
    model = config.model if config else None
    return SubAgent(
        name="browser-agent",
        description=(
            "Browser automation agent for web navigation, form filling, screenshots, "
            "web scraping, and online interactions. "
            "Use for: opening websites, filling forms, taking screenshots, "
            "scraping data, web testing, online research, social media."
        ),
        system_prompt=(
            "You are a browser automation expert.\n\n"
            "WORKFLOW:\n"
            "1. Open the target URL with browser_open\n"
            "2. Navigate and interact as needed\n"
            "3. Take screenshots at key points with browser_screenshot\n"
            "4. Extract and save important information\n\n"
            "Handle popups, wait for page loads, and be thorough."
        ),
        **({"model": model} if model else {}),
    )


def get_planner_subagent(config=None) -> SubAgent:
    """Planner agent — strategic planning. Inherits parent's tools."""
    model = config.model if config else None
    return SubAgent(
        name="planner-agent",
        description=(
            "Strategic planning and project management agent. "
            "Use for: creating plans, breaking down goals, organizing tasks, "
            "scheduling, project roadmaps, dependency analysis, risk assessment."
        ),
        system_prompt=(
            "You are a strategic planning and project management expert.\n\n"
            "WORKFLOW:\n"
            "1. Understand the goal and constraints\n"
            "2. Break into phases with clear milestones\n"
            "3. Create todos for each action item\n"
            "4. Add dependencies and timelines\n"
            "5. Monitor progress and adapt\n\n"
            "Be methodical. Every plan needs phases, tasks, and timelines."
        ),
        **({"model": model} if model else {}),
    )


def get_analyst_subagent(config=None) -> SubAgent:
    """Analyst agent — data analysis. Inherits parent's tools."""
    model = config.model if config else None
    return SubAgent(
        name="analyst-agent",
        description=(
            "Data analysis and insights agent. Analyzes data, finds patterns, "
            "creates visualizations, and generates reports. "
            "Use for: analyzing data, creating charts, statistical analysis, "
            "data processing, generating insights, trend analysis."
        ),
        system_prompt=(
            "You are a data analysis expert.\n\n"
            "WORKFLOW:\n"
            "1. Understand the data and what insights are needed\n"
            "2. Use Python (pandas, matplotlib, numpy) via execute_python\n"
            "3. Create visualizations and save them\n"
            "4. Write analysis reports to workspace/\n"
            "5. Store key findings in memory\n\n"
            "Always explain your methodology and findings clearly."
        ),
        **({"model": model} if model else {}),
    )


def get_whatsapp_subagent(config=None) -> SubAgent:
    """WhatsApp agent — messaging automation. Inherits parent's tools."""
    model = config.model if config else None
    return SubAgent(
        name="whatsapp-agent",
        description=(
            "WhatsApp messaging agent for sending messages, checking status, "
            "and managing WhatsApp communications. "
            "Use for: sending WhatsApp messages, checking connection, broadcasting."
        ),
        system_prompt=(
            "You are a WhatsApp messaging assistant.\n\n"
            "Always be polite and confirm before sending important messages."
        ),
        **({"model": model} if model else {}),
    )


def get_all_subagents(config=None) -> list[SubAgent]:
    """Get all hardcoded sub-agents as real SubAgent TypedDicts.

    Sub-agents inherit the parent's tools by default (deepagents behavior).
    """
    return [
        get_whatsapp_subagent(config),
        get_research_subagent(config),
        get_coder_subagent(config),
        get_browser_subagent(config),
        get_planner_subagent(config),
        get_analyst_subagent(config),
    ]


def get_subagent_definitions(config=None) -> list[SubAgent]:
    """Return sub-agent definitions for deepagents.

    This is what create_deep_agent(subagents=[...]) expects.
    Each sub-agent inherits the parent's tools (deepagents default behavior).
    """
    agents = get_all_subagents(config)

    # Add dynamically discovered agents from agents/ directory
    try:
        from xeno.dynamic.discovery import AgentDiscovery
        if config is None:
            from xeno.config import XenoConfig
            config = XenoConfig.from_env()
        discovery = AgentDiscovery(scan_dirs=config.agent_dirs)
        discovered = discovery.scan()
        for desc in discovered:
            agents.append(SubAgent(
                name=desc.name,
                description=desc.description,
                system_prompt=desc.system_prompt or desc.description,
                # No tools= → inherits parent's tools
                # No model= → inherits parent's model
            ))
    except Exception as e:
        logger.warning(f"Failed to load discovered agents: {e}")

    return agents


def get_discovered_agents(config=None):
    """Get all dynamically discovered agents."""
    try:
        from xeno.dynamic.discovery import AgentDiscovery
        if config is None:
            from xeno.config import XenoConfig
            config = XenoConfig.from_env()
        discovery = AgentDiscovery(scan_dirs=config.agent_dirs)
        return discovery.scan()
    except Exception:
        return []
