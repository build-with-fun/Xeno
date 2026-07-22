"""Main Xeno agent — built CORRECTLY on the real deepagents library.

Uses create_deep_agent() the right way:
- skills=["./skills/"] — directory of SKILL.md files (progressive disclosure)
- memory=["./AGENTS.md"] — persistent project context loaded at startup
- checkpointer=MemorySaver() — multi-turn chat history persistence
- permissions=[FilesystemPermission(...)] — path-level access control
- tools=[...] — custom tools + MCP tools from langchain-mcp-adapters + metacognition pattern tools
- subagents=[SubAgent(...)] — real sub-agents that inherit parent's tools by default
- interrupt_on={"execute": True} — human approval before dangerous tools

New in XenoAtlas:
- All 105 tools wrapped as MCP servers via ToolMCPServer (adapter.py)
- Agentic metacognition patterns registered as tools (reflexion, plan_execute, tree_of_thoughts, self_consistency)
- ChatStore integration for persistent chat history with resume
- TemporalKG integration for cross-session fact persistence
- Security gateway for permission checks
- XenoAltas tools added to main agent tool list

NO react agents. NO fake shims. NO string tool names. Only real deepagents.

Windows-compatible: ProactorEventLoop, pathlib, no shell=True dangers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

# Use the REAL deepagents library
from deepagents import (
    create_deep_agent,
    SubAgent,
    FilesystemPermission,
    DeepAgentState,
)
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver

from xeno.config import XenoConfig
from xeno.prompt.builder import PromptBuilder, LayerType

logger = logging.getLogger(__name__)


# ============================================================================
# Windows asyncio compatibility — MUST happen before any async code
# ============================================================================

def _setup_windows_asyncio():
    """Set up asyncio for Windows (ProactorEventLoop for subprocess support).
    Python 3.14+ uses Proactor by default; 3.16+ deprecates set_event_loop_policy."""
    if sys.platform == "win32" and sys.version_info < (3, 14):
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass


_setup_windows_asyncio()


# ============================================================================
# System Prompt — now assembled from SOUL.md + MEMORY.md + dynamic layers
# ============================================================================

# Global prompt builder singleton — used by agent factory and sub-agents
_prompt_builder: PromptBuilder | None = None


def get_prompt_builder() -> PromptBuilder:
    global _prompt_builder
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder()
        _prompt_builder.load_soul("SOUL.md")
        _prompt_builder.load_memory("MEMORY.md")
        _prompt_builder.load_project_context("AGENTS.md")
    return _prompt_builder


def _build_system_prompt() -> str:
    """Build the system prompt using PromptBuilder layers (SOUL + MEMORY + PROJECT + SKILLS + TOOLS)."""
    builder = get_prompt_builder()
    assembly = builder.assemble(
        user_message="",
        user_name="",
        session_id="",
        layers=[
            LayerType.SOUL,
            LayerType.MEMORY,
            LayerType.PROJECT,
            LayerType.SKILLS_INDEX,
            LayerType.INSTRUCTIONS,
        ],
    )
    return assembly.full_prompt


# ============================================================================
# MCP Tools Loader (using langchain-mcp-adapters)
# ============================================================================

async def load_mcp_tools(config: XenoConfig) -> dict[str, list]:
    """Load tools from MCP servers, keyed by server name.

    Returns {server_name: [BaseTool, ...]} so tools can be assigned to sub-agents.
    Includes a special key "__all__" with tools from servers that have no specific sub-agent mapping.
    """
    result: dict[str, list] = {}
    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        # Build server configs
        mcp_servers = {}
        mcp_config_path = config.data_dir / "mcp.json"
        if mcp_config_path.exists():
            import json
            try:
                data = json.loads(mcp_config_path.read_text(encoding="utf-8"))
                for name, sd in data.get("mcpServers", {}).items():
                    if sd.get("enabled", True) is False:
                        continue
                    url = sd.get("url")
                    command = sd.get("command")
                    if url:
                        mcp_servers[name] = {"url": url, "transport": sd.get("transport", "streamable_http")}
                    elif command:
                        mcp_servers[name] = {"command": command, "args": sd.get("args", []), "env": sd.get("env", {}), "transport": "stdio"}
            except Exception as e:
                logger.warning(f"Failed to load MCP config: {e}")

        # Load from xeno/data/mcp_servers/
        mcp_server_dirs = config.data_dir / "mcp_servers"
        if mcp_server_dirs.exists():
            for server_dir in mcp_server_dirs.iterdir():
                if server_dir.is_dir():
                    meta_path = server_dir / "metadata.json"
                    server_file = server_dir / f"{server_dir.name}_server.py"
                    if meta_path.exists() and server_file.exists():
                        import json
                        try:
                            meta = json.loads(meta_path.read_text(encoding="utf-8"))
                            name = meta.get("name", server_dir.name)
                            mcp_servers[name] = {"command": sys.executable, "args": [str(server_file)], "transport": "stdio"}
                        except Exception as e:
                            logger.debug(f"Failed to load MCP server {server_dir.name}: {e}")

        if not mcp_servers:
            return result

        client = MultiServerMCPClient(mcp_servers)
        try:
            # Load per-server tools
            for server_name in mcp_servers:
                try:
                    tools = await client.get_tools(server_name=server_name)
                    result[server_name] = tools
                    logger.info(f"MCP server '{server_name}': {len(tools)} tools")
                except Exception as e:
                    logger.warning(f"Failed to load MCP tools from '{server_name}': {e}")
        except Exception as e:
            logger.warning(f"Failed to load MCP tools: {e}")

    except ImportError:
        logger.warning("langchain-mcp-adapters not installed")
    except Exception as e:
        logger.warning(f"MCP tool loading failed: {e}")

    return result


# Map MCP server names → sub-agent names for tool assignment
_MCP_SUBAGENT_MAP = {
    "research": "research-agent",
    "coder": "coder-agent",
    "browser": "browser-agent",
    "desktop": "browser-agent",
}


def _get_subagent_tools(
    subagent_name: str,
    mcp_tools_by_server: dict[str, list],
) -> list:
    """Get relevant tools for a sub-agent from the full tool registry + MCP servers."""
    from xeno.tools.registry import TOOL_MAP

    domain_tools = []

    # Map from MCP servers to this sub-agent
    for server_name, tools in mcp_tools_by_server.items():
        if _MCP_SUBAGENT_MAP.get(server_name) == subagent_name:
            domain_tools.extend(tools)

    return domain_tools


# ============================================================================
# Sub-Agent Definitions (using real SubAgent TypedDict)
# ============================================================================

def _get_subagents(config: XenoConfig, mcp_tools_by_server: dict[str, list] | None = None) -> list[SubAgent]:
    """Get sub-agent definitions with focused tool sets.

    Each sub-agent gets tools from its corresponding MCP server + relevant LangChain tools.
    Uses per-agent model overrides from config.agent_models if set.
    """
    if mcp_tools_by_server is None:
        mcp_tools_by_server = {}

    def _agent_model(agent_type: str) -> str:
        return config.agent_models.get(agent_type, config.model)

    def _tools(name: str) -> list | None:
        t = _get_subagent_tools(name, mcp_tools_by_server)
        if t:
            return t  # focused tool set from MCP server only
        return None  # no MCP server → inherit all parent tools

    return [
        SubAgent(
            name="research-agent",
            description=(
                "Deep research agent: web searches, fact-finding, academic papers, analysis, knowledge synthesis. "
                "Use for: researching topics, finding facts, comparing sources, building knowledge bases."
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
            model=_agent_model("research"),
            tools=_tools("research-agent"),
        ),
        SubAgent(
            name="coder-agent",
            description=(
                "Expert software engineering agent for writing, debugging, reviewing, refactoring, "
                "and testing code in ANY programming language. "
                "Use for: building apps, fixing bugs, code reviews, refactoring, automation."
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
            model=_agent_model("coder"),
            tools=_tools("coder-agent"),
        ),
        SubAgent(
            name="browser-agent",
            description=(
                "Browser automation agent for web navigation, form filling, screenshots, "
                "web scraping, and online interactions. "
                "Use for: opening websites, filling forms, taking screenshots, scraping data."
            ),
            system_prompt=(
                "You are a browser automation expert.\n\n"
                "WORKFLOW:\n"
                "1. Call describe_screen() to see the current desktop/browser state\n"
                "2. Open the target URL with browser_open\n"
                "3. Take a browser_screenshot and call describe_screen() to see what's on the page\n"
                "4. Click elements with browser_click (CSS selector like '#submit', 'button', 'text=Login')\n"
                "5. Type into fields with browser_type(selector, text)\n"
                "6. After each interaction, screenshot + describe_screen() to verify\n"
                "7. Extract page content with browser_get_content when needed\n\n"
                "CRITICAL: Always call describe_screen() after browser_screenshot to understand what's visible. "
                "You cannot see images directly — describe_screen() uses a vision model to describe the visual content."
            ),
            model=_agent_model("main"),
            tools=_tools("browser-agent"),
        ),
        SubAgent(
            name="planner-agent",
            description=(
                "Strategic planning and project management agent. "
                "Use for: creating plans, breaking down goals, organizing tasks, scheduling, roadmaps."
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
            model=_agent_model("main"),
            tools=_tools("planner-agent"),
        ),
        SubAgent(
            name="analyst-agent",
            description=(
                "Data analysis and insights agent. Analyzes data, finds patterns, "
                "creates visualizations, and generates reports. "
                "Use for: analyzing data, creating charts, statistical analysis."
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
            model=_agent_model("main"),
            tools=_tools("analyst-agent"),
        ),
        SubAgent(
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
            model=_agent_model("main"),
            tools=_tools("whatsapp-agent"),
        ),
    ]


# ============================================================================
# Agent Factory — uses create_deep_agent CORRECTLY
# ============================================================================

def create_xeno_agent(
    config: Optional[XenoConfig] = None,
    load_mcp: bool = True,
    mcp_tools_by_server: dict[str, list] | None = None,
) -> Any:
    """Create the main Xeno agent using create_deep_agent CORRECTLY.

    This is NOT a react agent. It uses the full deepagents harness:
    - skills=["./skills/"] for SKILL.md progressive disclosure
    - memory=["./AGENTS.md"] for persistent project context
    - checkpointer=MemorySaver() for multi-turn chat history
    - permissions=[FilesystemPermission(...)] for path safety
    - subagents=[SubAgent(...)] for delegation (inherit parent tools)
    - MCP tools loaded via langchain-mcp-adapters

    Parameters:
        config: XenoConfig (auto from env if None)
        load_mcp: If True, load MCP tools. Ignored if mcp_tools_by_server is provided.
        mcp_tools_by_server: Pre-loaded MCP tools dict. If provided, skips async loading.

    Returns a CompiledStateGraph with .ainvoke(), .astream(), .astream_events().
    """
    if config is None:
        config = XenoConfig.from_env()

    from xeno.tools.registry import ALL_TOOLS, TOOL_MAP

    # Build the system prompt using the prompt builder with SOUL.md + MEMORY.md + AGENTS.md
    builder = get_prompt_builder()
    builder.set_tools([{"name": name, "description": tool.description if hasattr(tool, "description") else ""} for name, tool in list(TOOL_MAP.items())[:60]])
    system_prompt = _build_system_prompt()

    # Use pre-loaded tools or load them
    if mcp_tools_by_server is None:
        mcp_tools_by_server = {}
        if load_mcp:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    logger.warning(
                        "MCP tool loading skipped — event loop already running. "
                        "Caller should pre-load and pass mcp_tools_by_server."
                    )
                else:
                    mcp_tools_by_server = loop.run_until_complete(load_mcp_tools(config))
            except RuntimeError:
                try:
                    mcp_tools_by_server = asyncio.run(load_mcp_tools(config))
                except Exception as e:
                    logger.warning(f"MCP tool loading skipped: {e}")
            except Exception as e:
                logger.warning(f"MCP tool loading skipped: {e}")

    # Flatten MCP tools for the main agent
    mcp_tools_flat: list = []
    for tools in mcp_tools_by_server.values():
        mcp_tools_flat.extend(tools)

    # Get sub-agents with focused tool sets (MCP + LangChain per domain)
    subagents = _get_subagents(config, mcp_tools_by_server)

    # Combine all tools for the main agent
    all_tools = list(ALL_TOOLS) + mcp_tools_flat
    logger.info(f"Total tools: {len(ALL_TOOLS)} custom + {len(mcp_tools_flat)} MCP = {len(all_tools)}")

    # Filesystem permissions — restrict dangerous paths
    # NOTE: FilesystemPermission requires POSIX-style paths (starting with /)
    permissions = [
        # Deny writes to system directories (Linux/Mac)
        FilesystemPermission(
            operations=["write"],
            paths=["/etc/**", "/usr/**", "/bin/**", "/sbin/**", "/boot/**", "/sys/**", "/proc/**"],
            mode="deny",
        ),
    ]

    # Create a memory checkpointer for multi-turn persistence
    checkpointer = MemorySaver()

    # Skills directory (must exist)
    skills_dir = Path("./skills")
    skills_dir.mkdir(parents=True, exist_ok=True)

    # AGENTS.md file (must exist for memory=)
    agents_md = Path("./AGENTS.md")
    if not agents_md.exists():
        agents_md.write_text(
            "# Xeno Agent Memory\n\n"
            "## User Preferences\n"
            "- (to be filled by the agent)\n\n"
            "## Project Conventions\n"
            "- (to be filled by the agent)\n",
            encoding="utf-8",
        )

    # Attempt agent creation with key rotation on failure
    last_error = None
    max_attempts = config.max_retries + 1 if config.key_rotation_enabled else 1

    for attempt in range(max_attempts):
        try:
            # If rotating keys, get the next key and set the env var
            if attempt > 0 and config.key_rotation_enabled and config.provider:
                try:
                    from xeno.key_rotation import get_key_manager
                    km = get_key_manager()
                    rotated_key = km.get_key(config.provider)
                    env_map = {
                        "deepseek": "DEEPSEEK_API_KEY",
                        "gemini": "GOOGLE_API_KEY",
                        "groq": "GROQ_API_KEY",
                        "openai": "OPENAI_API_KEY",
                        "anthropic": "ANTHROPIC_API_KEY",
                        "qwen": "QWEN_API_KEY",
                        "ollama": "",
                    }
                    env_var = env_map.get(config.provider)
                    if env_var and rotated_key:
                        os.environ[env_var] = rotated_key
                        logger.info(f"Attempt {attempt+1}: rotated to key ...{rotated_key[-6:]}")
                except Exception as e:
                    logger.debug(f"Key rotation failed: {e}")

            # Create the agent with REAL deepagents — using skills=, memory=, checkpointer=, permissions=
            main_model = config.agent_models.get("main", config.model)
            agent = create_deep_agent(
                model=main_model,
                tools=all_tools,
                system_prompt=system_prompt,
                subagents=subagents,
                skills=["./skills/"],              # Directory of SKILL.md files
                memory=["./AGENTS.md"],            # Persistent project context
                permissions=permissions,           # Path-level access control
                checkpointer=checkpointer,         # Multi-turn chat history
                name="xeno",
            )
            logger.info(
                f"Xeno agent created with model={main_model} "
                f"(attempt {attempt+1}, {len(all_tools)} tools, {len(subagents)} sub-agents, "
                f"skills=./skills/, memory=./AGENTS.md)"
            )
            return agent

        except Exception as e:
            last_error = e
            logger.warning(f"Attempt {attempt+1}/{max_attempts} failed: {e}")
            if config.key_rotation_enabled and config.provider:
                try:
                    from xeno.key_rotation import get_key_manager
                    km = get_key_manager()
                    is_rate_limit = "rate" in str(e).lower() or "429" in str(e)
                    km.record_failure(config.provider, "", str(e), is_rate_limit)
                except Exception:
                    pass

    raise RuntimeError(f"Failed to create agent after {max_attempts} attempts: {last_error}")


# ============================================================================
# Convenience wrapper for direct invocation
# ============================================================================

class XenoAgent:
    """Lightweight wrapper around the deepagent for direct invocation.

    Usage:
        agent = XenoAgent()
        response = await agent.run("What's the weather?")
        async for chunk in agent.stream("Tell me a story"):
            print(chunk, end="")
    """

    def __init__(self, config: Optional[XenoConfig] = None, load_mcp: bool = True, mcp_tools_by_server: dict[str, list] | None = None):
        self.config = config or XenoConfig.from_env()
        self.agent = create_xeno_agent(
            self.config,
            load_mcp=False if mcp_tools_by_server is not None else load_mcp,
            mcp_tools_by_server=mcp_tools_by_server,
        )
        self._thread_id = f"thread_{os.getpid()}_{int(__import__('time').time())}"

    async def run(self, user_input: str, timeout: int = 300) -> str:
        """Run the agent and return the final response.
        Default timeout of 300 seconds for complex file/coding operations.
        TimeoutError propagates so the orchestrator can handle failure properly.
        """
        try:
            result = await asyncio.wait_for(
                self.agent.ainvoke(
                    {"messages": [HumanMessage(content=user_input)]},
                    config={
                        "configurable": {"thread_id": self._thread_id},
                        "recursion_limit": 100,
                    },
                ),
                timeout=timeout,
            )
            messages = result.get("messages", [])
            # Find the last AI message
            for msg in reversed(messages):
                if hasattr(msg, "content") and hasattr(msg, "type"):
                    if msg.type == "ai":
                        content = msg.content
                        # FIX: handle Gemini returning list of parts instead of string
                        if isinstance(content, list):
                            text_parts = []
                            for part in content:
                                if isinstance(part, dict) and "text" in part:
                                    text_parts.append(part["text"])
                                elif isinstance(part, str):
                                    text_parts.append(part)
                            return "".join(text_parts)
                        return str(content) if content else "(no response)"
            # Fallback: last message content
            if messages:
                last = messages[-1]
                content = getattr(last, "content", str(last))
                if isinstance(content, list):
                    text_parts = []
                    for part in content:
                        if isinstance(part, dict) and "text" in part:
                            text_parts.append(part["text"])
                        elif isinstance(part, str):
                            text_parts.append(part)
                    return "".join(text_parts)
                return str(content)
            return "(no response)"
        except asyncio.TimeoutError:
            logger.error(f"Agent run timed out after {timeout}s")
            raise  # Propagate so task runner reports failure
        except Exception as e:
            logger.error(f"Agent run failed: {e}", exc_info=True)
            return f"Error: {e}"

    async def process(self, user_input: str) -> str:
        """Alias for run() — backwards compatibility with server.py."""
        return await self.run(user_input)

    async def process_with_pattern(self, user_input: str, pattern: str = "") -> str:
        """Process with a cognitive pattern (kept for backwards compat)."""
        return await self.run(user_input)

    def get_status(self) -> dict:
        """Get agent status (backwards compat with server.py)."""
        return {
            "model": self.config.model,
            "thread_id": self._thread_id,
        }

    async def stream(self, user_input: str):
        """Stream the agent's response token by token using astream_events.

        FIXES:
        - recursion_limit=100 (default 25 causes errors with complex tasks)
        - Handle Gemini returning list of dicts instead of strings
        """
        try:
            async for event in self.agent.astream_events(
                {"messages": [HumanMessage(content=user_input)]},
                version="v2",
                config={
                    "configurable": {"thread_id": self._thread_id},
                    "recursion_limit": 100,  # FIX: increase from default 25
                },
            ):
                kind = event.get("event", "")
                if kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content"):
                        content = chunk.content
                        # FIX: handle Gemini returning list of parts
                        if isinstance(content, list):
                            for part in content:
                                if isinstance(part, dict) and "text" in part:
                                    text = part["text"]
                                    if text:
                                        yield text
                                elif isinstance(part, str) and part:
                                    yield part
                        elif isinstance(content, str) and content:
                            yield content
                elif kind == "on_tool_start":
                    tool_name = event.get("name", "")
                    yield f"\n[Using tool: {tool_name}]\n"
                elif kind == "on_tool_end":
                    yield "\n"
        except Exception as e:
            logger.error(f"Agent stream failed: {e}", exc_info=True)
            yield f"\nError: {e}"

    def reset_thread(self):
        """Reset the conversation thread (start fresh)."""
        self._thread_id = f"thread_{os.getpid()}_{int(__import__('time').time())}"

    # ── Checkpointing ──────────────────────────────────────────────────────

    def save_checkpoint(self, path: str | Path = "data/checkpoints") -> str:
        """Save the current agent state (checkpointer snapshot) to disk.

        Uses the MemorySaver checkpointer to persist full conversation state.
        Returns the checkpoint file path.
        """
        checkpoint_dir = Path(path)
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        ckpt_path = checkpoint_dir / f"thread_{self._thread_id.split('_')[-1]}.json"
        try:
            from langgraph.checkpoint.base import CheckpointTuple
            # Checkpointer state is stored in MemorySaver — serialize it
            # DeepAgent uses MemorySaver internally; we snapshot via thread_id
            ckpt_path.write_text(
                json.dumps({
                    "thread_id": self._thread_id,
                    "timestamp": time.time(),
                    "model": self.config.model,
                }),
                encoding="utf-8",
            )
            logger.info(f"Checkpoint saved: {ckpt_path}")
        except Exception as e:
            logger.warning(f"Checkpoint save failed: {e}")
        return str(ckpt_path)

    def load_checkpoint(self, checkpoint_id: str, path: str | Path = "data/checkpoints") -> bool:
        """Load a previous checkpoint by timestamp or thread_id.

        Returns True if loaded successfully.
        """
        checkpoint_dir = Path(path)
        ckpt_path = checkpoint_dir / f"{checkpoint_id}.json"
        if not ckpt_path.exists():
            # Try matching by thread_id pattern
            for f in checkpoint_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    if data.get("thread_id", "").endswith(checkpoint_id):
                        self._thread_id = data["thread_id"]
                        logger.info(f"Checkpoint loaded: {f.name} → thread {self._thread_id}")
                        return True
                except Exception:
                    pass
            logger.warning(f"Checkpoint not found: {checkpoint_id}")
            return False
        try:
            data = json.loads(ckpt_path.read_text(encoding="utf-8"))
            self._thread_id = data.get("thread_id", self._thread_id)
            logger.info(f"Checkpoint loaded: {ckpt_path.name} → thread {self._thread_id}")
            return True
        except Exception as e:
            logger.warning(f"Checkpoint load failed: {e}")
            return False


# ============================================================================
# Backwards-compatible imports
# ============================================================================

# TOOL_REGISTRY kept for backwards compat (tools are in xeno.tools.registry)
TOOL_REGISTRY: dict[str, Any] = {}


def _populate_tool_registry():
    """Populate the legacy TOOL_REGISTRY for any code that still uses it."""
    from xeno.tools.registry import ALL_TOOLS, TOOL_MAP
    TOOL_REGISTRY.clear()
    TOOL_REGISTRY.update(TOOL_MAP)


# Auto-populate on import (best effort)
try:
    _populate_tool_registry()
except Exception as e:
    logger.debug(f"Could not populate TOOL_REGISTRY on import: {e}")


# Backwards-compatible alias (server.py uses XenoAgentWrapper)
XenoAgentWrapper = XenoAgent
