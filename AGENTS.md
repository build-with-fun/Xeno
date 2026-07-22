# Xeno — Agent Instructions

## Entry points
- `python main.py` — interactive CLI (Brain orchestrator). Flags: `--check` `--scan` `--serve` `--model` `--debug` `--agent <name>`
- `python xeno2.py` — TUI mode (Rich). Flags: `--check` `--status` `--debug`
- `python -m xeno.server` — FastAPI server on `:8000`
- `python xeno/setup.py` — interactive setup wizard (writes `data/setup.json`)
- `uv run python xeno/client.py "prompt"` — send task to running server

## Package management
- **uv** only (`uv add pkg`, `uv sync`). See `uv.lock`.
- Python ≥3.11 (`.python-version` says 3.14). Optional extras: `[windows]`, `[voice]`, `[vision]`.

## Tests
- `uv run pytest tests/ -v` — unit tests. `asyncio_mode = auto` in `pytest.ini`.
- `python scripts/test_*.py` — integration/smoke tests (no framework):
  - `scripts/test_all_phases.py` — comprehensive (phases 1-11)
  - `scripts/test_brain.py` — brain orchestrator (simulated LLM, no API key needed)
  - `scripts/test_phase_1_2.py` — harness + memory
  - `scripts/demo_brain.py` — end-to-end demo (simulated LLM)
- CI runs on `windows-latest`, Python 3.11 + 3.14. Syntax check: `uv run python -m compileall xeno/ tests/`.

## Config
- **Model format:** `provider:model_name` (e.g. `google_genai:gemini-2.0-flash`). Priority: env `XENO_MODEL` > `data/setup.json` > hardcoded default (`deepseek:deepseek-chat`).
- API keys from `.env` (gitignored) + `data/setup.json` `selected_keys`. Supported providers: deepseek, google_genai, groq, openai, anthropic, qwen, ollama (local, no key needed).
- Env overrides: `XENO_MODEL`, `XENO_SMALL_MODEL`, `XENO_VISION_MODEL`, `XENO_MAX_AGENTS` (default 5), `XENO_TIMEOUT` (300s), `XENO_HOT_RELOAD`, `XENO_AGENT_DIRS`, `XENO_PLUGIN_DIRS`, `XENO_SKILL_DIRS`, etc. See `.env.example`.
- MCP servers: `data/mcp.json` (disabled by default).
- All runtime state in `data/` (memory, schedules, todos, sessions, checkpoints, profiles).

## Architecture
- Built on **real `deepagents` library** (`create_deep_agent`, `SubAgent`, `MemorySaver`). NOT shims.
- **13 phases** wired in `xeno/runtime.py:XenoRuntime.startup()`. All optional — runtime tolerates individual phase failures.
- **Brain orchestrator** (`xeno/brain/orchestrator.py`) drives conversation: intent analysis → BEFORE_WORK → background task → AFTER_WORK. Supports stop/cancel, self-healing, reminders, middle agent for quick answers during tasks.
- **Scheduler** (`xeno/scheduler.py`): supports `after_delay`, `daily`, `weekly`, `monthly`, `yearly`, `once`. Fires reminders and action tasks in background loop.
- **Dynamic discovery:** agents from `agents/` + `media/` (requires `description.md` with YAML frontmatter: `name`, `model`, `tools[]`, `permissions[]`, `enabled`, tags), plugins from `plugins/` (`__init__.py` + `plugin.json`), skills from `skills/` (SKILL.md files).
- **Tool registry:** `xeno/tools/registry.py` — `ALL_TOOLS` list + `TOOL_MAP` dict (50+ tools). Sub-agents resolve tool names via `TOOL_MAP`; omit `tools=` to inherit parent's toolset. Tools are `@tool`-decorated LangChain `BaseTool` objects.
- **Metatools** in `xeno/metatools.py`: single `call_tool` dispatcher routes all tools by name.
- **Memory (8 tiers):** unified at `xeno/memory/unified.py`. Core: context + vector (ChromaDB) + episodic + procedural + mem0 + generative agents + temporal KG + OS paging.
- **Standalone agents** in `agents/` (research, coding, automation, architecture, creator, resource_generator) routed via keyword matching in `_build_agent_router()`. Each has `run(prompt)` entry point.

## Conventions
- Never hardcode paths — use `XenoConfig` from `xeno/config.py` or env vars.
- Agent `description.md` uses `provider:model_name` format for `model`; if provider API key unset, auto-falls back to main config model.
- Plugin `register(registry)` returns `{"hooks": {...}, "tools": [...], "mcp_servers": {...}}`.
- WhatsApp agent (`media/whatsapp/`) with `description.md` — always_on agent fails gracefully if key missing.
- Windows: `ProactorEventLoopPolicy` set in `xeno/__init__.py` (only for Python <3.14). Shell tools use `cmd.exe` with `shell=False`.
- No pre-commit, linter, formatter, or typechecker configured.

## Known issues
- `data/setup.json` currently configured for Gemini (`google_genai:gemini-3.1-flash-lite`). `DEEPSEEK_API_KEY` likely unset — auto-fallback applies for agents using `deepseek:deepseek-chat`.
- WhatsApp always-on agent uses `deepseek:deepseek-chat` but may lack API key — creates placeholder non-critically.
- Ollama provider uses OpenAI-compatible API endpoint at `http://localhost:11434/v1` — no API key needed. Run `ollama serve` first, then choose "Ollama (Local)" in setup.
