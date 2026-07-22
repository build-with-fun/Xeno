"""Xeno Setup TUI — Rich-based interactive setup wizard.

Flow:
  Step 1: Pick provider (Gemini / DeepSeek / Groq / etc.)
  Step 2: Fetch & display real-time models, pick one
  Step 3: Key rotation on/off, pick keys, pick strategy
  Done:   Summary + save

Run: uv run python xeno/setup.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger("xeno.setup")

SETUP_FILE = Path(__file__).parent.parent / "data" / "setup.json"

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.prompt import Prompt, Confirm
    from rich.columns import Columns
    from rich.spinner import Spinner
    from rich.live import Live
    from rich.rule import Rule
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

console = Console() if HAS_RICH else None


# ---------------------------------------------------------------------------
# Provider definitions
# ---------------------------------------------------------------------------

@dataclass
class ProviderInfo:
    name: str
    display_name: str
    api_keys: list[str]
    models_url: str
    auth_type: str
    auth_header: str = "Authorization"
    model_format: str = "openai"
    base_url: str = ""
    langchain_prefix: str = ""
    icon: str = ""
    color: str = ""
    no_key_required: bool = False

PROVIDERS: dict[str, ProviderInfo] = {
    "gemini": ProviderInfo(
        name="gemini", display_name="Google Gemini", api_keys=[],
        models_url="https://generativelanguage.googleapis.com/v1beta/models",
        auth_type="query", model_format="gemini",
        langchain_prefix="google_genai", icon="[bold blue]G[/]", color="blue",
    ),
    "deepseek": ProviderInfo(
        name="deepseek", display_name="DeepSeek", api_keys=[],
        models_url="https://api.deepseek.com/models",
        auth_type="bearer", base_url="https://api.deepseek.com/v1",
        langchain_prefix="deepseek", icon="[bold cyan]D[/]", color="cyan",
    ),
    "groq": ProviderInfo(
        name="groq", display_name="Groq (GroqCloud)", api_keys=[],
        models_url="https://api.groq.com/openai/v1/models",
        auth_type="bearer", base_url="https://api.groq.com/openai/v1",
        langchain_prefix="groq", icon="[bold yellow]Q[/]", color="yellow",
    ),
    "openai": ProviderInfo(
        name="openai", display_name="OpenAI", api_keys=[],
        models_url="https://api.openai.com/v1/models",
        auth_type="bearer", base_url="https://api.openai.com/v1",
        langchain_prefix="openai", icon="[bold green]O[/]", color="green",
    ),
    "anthropic": ProviderInfo(
        name="anthropic", display_name="Anthropic (Claude)", api_keys=[],
        models_url="https://api.anthropic.com/v1/models",
        auth_type="bearer", auth_header="x-api-key",
        base_url="https://api.anthropic.com", langchain_prefix="anthropic",
        icon="[bold magenta]A[/]", color="magenta",
    ),
    "qwen": ProviderInfo(
        name="qwen", display_name="Qwen (Alibaba)", api_keys=[],
        models_url="https://dashscope.aliyuncs.com/compatible-mode/v1/models",
        auth_type="bearer", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        langchain_prefix="openai", icon="[bold white]W[/]", color="white",
    ),
    "ollama": ProviderInfo(
        name="ollama", display_name="Ollama (Local)", api_keys=[],
        models_url="http://localhost:11434/api/tags",
        auth_type="none", base_url="http://localhost:11434/v1",
        langchain_prefix="openai", icon="[bold yellow]O[/]", color="yellow",
        no_key_required=True,
    ),
}


# Image generation providers — ONLY actual image generation models
IMAGE_PROVIDERS = {
    "pollinations": {
        "name": "Pollinations.ai",
        "description": "Free, no API key needed",
        "requires_key": False,
        "models": ["default"],
        "icon": "[bold green]P[/]",
        "color": "green",
    },
    "gemini": {
        "name": "Google Gemini (Imagen)",
        "description": "Image generation via Gemini API",
        "requires_key": True,
        "env_key": "GEMINI_API_KEY",
        "models": ["gemini-2.0-flash-exp", "imagen-3.0-generate-002", "imagen-3.0-fast-generate-001"],
        "model_descriptions": {
            "gemini-2.0-flash-exp": "Fast, experimental image gen",
            "imagen-3.0-generate-002": "High quality Imagen 3",
            "imagen-3.0-fast-generate-001": "Fast Imagen 3",
        },
        "icon": "[bold blue]G[/]",
        "color": "blue",
    },
    "openai": {
        "name": "OpenAI DALL-E",
        "description": "DALL-E 3 image generation",
        "requires_key": True,
        "env_key": "OPENAI_API_KEY",
        "models": ["dall-e-3", "dall-e-2"],
        "model_descriptions": {
            "dall-e-3": "Latest DALL-E, highest quality",
            "dall-e-2": "Previous generation, faster",
        },
        "icon": "[bold yellow]O[/]",
        "color": "yellow",
    },
}


# ---------------------------------------------------------------------------
# .env key scanning
# ---------------------------------------------------------------------------

def _scan_env_keys() -> dict[str, list[str]]:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(env_path)

    result: dict[str, list[str]] = {}
    patterns = {
        "gemini": [r"^GEMINI_API_KEY(?:_(\d+))?$", r"^GOOGLE_API_KEY(?:_(\d+))?$"],
        "deepseek": [r"^DEEPSEEK_API_KEY(?:_(\d+))?$"],
        "groq": [r"^GROQ_API_KEY(?:_(\d+))?$"],
        "openai": [r"^OPENAI_API_KEY(?:_(\d+))?$"],
        "anthropic": [r"^ANTHROPIC_API_KEY(?:_(\d+))?$"],
        "qwen": [r"^QWEN_API_KEY(?:_(\d+))?$"],
        "ollama": [r"^OLLAMA_BASE_URL$"],
    }

    for env_key, value in os.environ.items():
        for provider, regexes in patterns.items():
            for regex in regexes:
                if re.match(regex, env_key, re.IGNORECASE) and value.strip():
                    result.setdefault(provider, []).append(value.strip())

    # Deduplicate keys while preserving order
    for p in result:
        seen = set()
        unique = []
        for k in result[p]:
            if k not in seen:
                seen.add(k)
                unique.append(k)
        result[p] = unique

    return result


# ---------------------------------------------------------------------------
# Model fetching (async)
# ---------------------------------------------------------------------------

async def _fetch_models_gemini(keys: list[str]) -> list[dict[str, Any]]:
    """Fetch Gemini models with retries and better error handling."""
    for key in keys:
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.get(
                        f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
                    )
                    if resp.status_code == 429:
                        # Rate limited — try next key
                        break
                    if resp.status_code == 200:
                        data = resp.json()
                        models = []
                        for m in data.get("models", []):
                            name = m.get("name", "").replace("models/", "")
                            if not name:
                                continue
                            methods = m.get("supportedGenerationMethods", [])
                            if "generateContent" in methods:
                                models.append({
                                    "id": name,
                                    "name": m.get("displayName", name),
                                    "description": m.get("description", "")[:120],
                                    "context_window": m.get("inputTokenLimit", 0),
                                    "output_limit": m.get("outputTokenLimit", 0),
                                })
                        if models:
                            return models
                    else:
                        logger.warning(f"Gemini API returned {resp.status_code} for key ...{key[-6:]}")
            except httpx.TimeoutException:
                logger.warning(f"Gemini API timeout (attempt {attempt+1}/3)")
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Gemini API error (attempt {attempt+1}/3): {e}")
                await asyncio.sleep(1)
    return []


async def _fetch_models_openai_compat(provider: ProviderInfo, keys: list[str]) -> list[dict[str, Any]]:
    """Fetch OpenAI-compatible models with retries and better error handling."""
    for key in keys:
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    headers = {provider.auth_header: f"Bearer {key}"}
                    resp = await client.get(provider.models_url, headers=headers)
                    if resp.status_code == 429:
                        break
                    if resp.status_code == 200:
                        data = resp.json()
                        models = []
                        for m in data.get("data", []):
                            mid = m.get("id", "")
                            if not mid:
                                continue
                            models.append({
                                "id": mid, "name": mid, "description": "",
                                "context_window": 0,
                                "owned_by": m.get("owned_by", ""),
                            })
                        if models:
                            return models
                    else:
                        logger.warning(f"{provider.name} API returned {resp.status_code}")
            except httpx.TimeoutException:
                logger.warning(f"{provider.name} API timeout (attempt {attempt+1}/3)")
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"{provider.name} API error (attempt {attempt+1}/3): {e}")
                await asyncio.sleep(1)
    return []


async def fetch_models_for_provider(provider: ProviderInfo) -> list[dict[str, Any]]:
    if not provider.api_keys:
        return []
    if provider.model_format == "gemini":
        return await _fetch_models_gemini(provider.api_keys)
    return await _fetch_models_openai_compat(provider, provider.api_keys)


# ---------------------------------------------------------------------------
# Setup config
# ---------------------------------------------------------------------------

# Agent types that can have per-type model overrides
AGENT_TYPES = ["main", "coder", "research", "vision"]
AGENT_TYPE_LABELS = {
    "main": "Main (dialogue, reasoning)",
    "coder": "Coder (code generation, debugging)",
    "research": "Research (web search, analysis)",
    "vision": "Vision (screen/camera analysis)",
}


@dataclass
class SetupConfig:
    provider: str = ""
    model: str = ""
    small_model: str = ""
    vision_model: str = ""
    key_rotation: bool = True
    rotation_strategy: str = "round_robin"
    max_retries: int = 3
    rate_limit_backoff: float = 60.0
    selected_keys: dict[str, list[str]] = field(default_factory=dict)
    first_run: bool = True
    created_at: str = ""
    # Image generation config
    image_provider: str = "pollinations"
    image_model: str = ""
    image_api_key: str = ""
    # Per-agent model overrides: {agent_type: "provider:model"}
    agent_models: dict[str, str] = field(default_factory=dict)

    def save(self):
        self.first_run = False
        from datetime import datetime
        self.created_at = datetime.now().isoformat()
        SETUP_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETUP_FILE.write_text(json.dumps(self.__dict__, indent=2, default=str))

    @classmethod
    def load(cls) -> "SetupConfig":
        if SETUP_FILE.exists():
            try:
                data = json.loads(SETUP_FILE.read_text())
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception:
                pass
        return cls()

    def to_langchain_model_str(self, agent_type: str | None = None) -> str:
        if agent_type and agent_type in self.agent_models:
            return self.agent_models[agent_type]
        if agent_type == "vision" and self.vision_model:
            return self.vision_model
        prov = PROVIDERS.get(self.provider)
        prefix = prov.langchain_prefix if prov else self.provider
        return f"{prefix}:{self.model}"

    def get_model_for_agent(self, agent_type: str) -> str:
        if agent_type in self.agent_models:
            return self.agent_models[agent_type]
        if agent_type == "vision" and self.vision_model:
            return self.vision_model
        return self.to_langchain_model_str()


# ---------------------------------------------------------------------------
# Rich TUI helpers
# ---------------------------------------------------------------------------

def _tui_header():
    if not HAS_RICH:
        return
    console.clear()
    console.print()
    console.print(Panel(
        Text("X E N O   S E T U P", style="bold white", justify="center"),
        subtitle="configure your AI brain",
        border_style="bright_blue",
        padding=(0, 2),
    ))
    console.print()


def _tui_step_banner(step: int, title: str):
    console.print()
    console.print(Rule(f"[bold]Step {step}:[/] {title}", style="bright_blue"))
    console.print()


def _tui_provider_card(prov: ProviderInfo, key_count: int, index: int) -> Panel:
    lines = []
    lines.append(f"[bold {prov.color}]{prov.display_name}[/]")
    if prov.no_key_required:
        lines.append("[green]No API key needed[/]")
    elif key_count == 0:
        lines.append("[red]No API keys found[/]")
    else:
        lines.append(f"[dim]{key_count} API key{'s' if key_count != 1 else ''} found[/]")
    return Panel(
        "\n".join(lines),
        title=f"[bold]({index})[/]",
        border_style=prov.color,
        width=30,
        padding=(0, 1),
    )


def _tui_model_table(models: list[dict[str, Any]], provider_color: str = "bright_blue", show_provider: bool = True) -> Table:
    table = Table(
        title=None,
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style=f"bold {provider_color}",
        title_style=f"bold {provider_color}",
        expand=True,
        pad_edge=True,
    )
    table.add_column("#", style="bold", width=4, justify="right")
    table.add_column("Model ID", style="bold", min_width=30)
    table.add_column("Name", min_width=20)
    table.add_column("Context", justify="right", width=10)
    table.add_column("Output", justify="right", width=10)
    if show_provider:
        table.add_column("Provider", justify="center", width=14)

    for i, m in enumerate(models, 1):
        ctx = f"{m['context_window']:,}" if m.get("context_window") else "-"
        out = f"{m['output_limit']:,}" if m.get("output_limit") else "-"
        prov_display = m.get("provider", "")
        if show_provider:
            table.add_row(str(i), m["id"], m.get("name", ""), ctx, out, prov_display)
        else:
            table.add_row(str(i), m["id"], m.get("name", ""), ctx, out)

    return table


def _tui_key_table(keys: list[str], provider_color: str) -> Table:
    table = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style=f"bold {provider_color}",
        expand=True,
    )
    table.add_column("#", style="bold", width=4, justify="right")
    table.add_column("Key", style="bold")
    table.add_column("Status", justify="center", width=10)

    for i, key in enumerate(keys, 1):
        masked = key[:8] + "..." + key[-4:] if len(key) > 12 else key[:4] + "..."
        table.add_row(str(i), masked, "[green]ready[/]")

    return table


def _tui_rotation_table() -> Table:
    table = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold bright_blue",
        expand=True,
    )
    table.add_column("#", style="bold", width=4, justify="right")
    table.add_column("Strategy", style="bold")
    table.add_column("Description")

    strategies = [
        ("round_robin", "Cycle through keys in order", "[green](Recommended)[/]"),
        ("random", "Pick a random key each request", ""),
        ("least_used", "Pick the key with fewest requests", ""),
        ("fastest", "Pick the key with lowest latency", ""),
    ]
    for i, (name, desc, badge) in enumerate(strategies, 1):
        table.add_row(str(i), f"{name} {badge}", desc)
    table.add_row("0", "[dim]No rotation — use first key only[/]", "")

    return table


def _tui_summary(config: SetupConfig, keys_count: int):
    console.print()
    console.print(Rule("[bold green]Setup Complete!", style="green"))
    console.print()

    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
    table.add_column("Field", style="bold bright_blue", width=14)
    table.add_column("Value", style="bold")

    prov = PROVIDERS.get(config.provider)
    prov_name = prov.display_name if prov else config.provider
    prov_color = prov.color if prov else "white"

    table.add_row("Provider", f"[{prov_color}]{prov_name}[/]")
    table.add_row("Model", f"[bold]{config.model}[/]")
    if config.small_model:
        table.add_row("Small Model", f"[dim]{config.small_model}[/]")
    if config.vision_model:
        table.add_row("Vision Model", f"[dim]{config.vision_model}[/]")
    if config.agent_models:
        for atype, amodel in config.agent_models.items():
            label = AGENT_TYPE_LABELS.get(atype, atype)
            table.add_row(f"{label}", f"[cyan]{amodel}[/]")
    table.add_row("Keys", f"[bold]{keys_count}[/] registered" if keys_count else "[green]No key needed[/]")
    if len(config.selected_keys) > 1:
        table.add_row("Providers", f"[dim]{', '.join(config.selected_keys.keys())}[/]")
    rot_text = f"[green]ON[/] ({config.rotation_strategy})" if config.key_rotation else "[red]OFF[/]"
    table.add_row("Rotation", rot_text)
    table.add_row("Retries", str(config.max_retries))

    langchain_model = config.to_langchain_model_str()
    table.add_row("LangChain", f"[cyan]{langchain_model}[/]")

    # Image config
    img_p = IMAGE_PROVIDERS.get(config.image_provider, {})
    img_name = img_p.get("name", config.image_provider)
    table.add_row("Image Gen", f"[bold]{img_name}[/]")
    if config.image_model:
        table.add_row("Image Model", f"[dim]{config.image_model}[/]")

    console.print(Panel(table, title="[bold]Configuration[/]", border_style="green", padding=(0, 1)))
    console.print()


# ---------------------------------------------------------------------------
# Non-interactive (plain text fallback)
# ---------------------------------------------------------------------------

def _plain_wizard():
    print("\n=== XENO SETUP ===\n")
    env_keys = _scan_env_keys()
    available = [p for p in PROVIDERS if (p in env_keys and env_keys[p]) or PROVIDERS[p].no_key_required]

    if not available:
        print("No API keys found in .env!")
        sys.exit(1)

    print("Available providers:")
    for i, name in enumerate(available, 1):
        prov = PROVIDERS[name]
        print(f"  [{i}] {prov.display_name} ({len(env_keys[name])} keys)")

    choice = input("\nSelect provider [1]: ").strip() or "1"
    try:
        provider_name = available[int(choice) - 1]
    except (ValueError, IndexError):
        provider_name = available[0]

    provider = PROVIDERS[provider_name]
    provider.api_keys = env_keys.get(provider_name, [])

    print(f"\nFetching models from {provider.display_name}...")
    models = []
    if provider.no_key_required:
        try:
            import httpx
            resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("models", []):
                    name = m.get("name", "").replace(":latest", "")
                    if name:
                        models.append({"id": name, "name": name, "description": "", "context_window": 0})
        except Exception:
            pass
        if not models:
            print("Ollama not reachable. Using common model names.")
    else:
        models = asyncio.run(fetch_models_for_provider(provider))
    if not models:
        print(f"Could not fetch live models. Using built-in defaults.")
        fallback = {
            "gemini": ["gemini-2.5-flash", "gemini-2.0-flash"],
            "deepseek": ["deepseek-chat", "deepseek-reasoner"],
            "groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"],
            "openai": ["gpt-4o", "gpt-4o-mini"],
            "anthropic": ["claude-sonnet-4-20250514"],
            "qwen": ["qwen-plus", "qwen-turbo"],
            "ollama": ["llama3.2", "llama3.1", "mistral", "qwen2.5", "deepseek-r1", "phi4"],
        }
        fallback_ids = fallback.get(provider_name, [f"{provider_name}-chat"])
        models = [{"id": mid, "name": mid, "description": "", "context_window": 0} for mid in fallback_ids]

    print(f"\nAvailable models:")
    for i, m in enumerate(models, 1):
        print(f"  [{i:2d}] {m['id']}")

    if provider.no_key_required:
        model_choice = input("\nSelect model [1] (or 'custom' to type a name): ").strip() or "1"
    else:
        model_choice = input("\nSelect model [1]: ").strip() or "1"
    try:
        if model_choice == "custom" and provider.no_key_required:
            model_id = input("  Enter model name: ").strip() or (models[0]["id"] if models else "llama3.2")
        else:
            model_id = models[int(model_choice) - 1]["id"]
    except (ValueError, IndexError):
        model_id = models[0]["id"] if models else "llama3.2"

    selected_keys = env_keys.get(provider_name, [])

    if provider.no_key_required:
        print("[green]Ollama runs locally — no API key or rotation needed.[/]")
        key_rot = False
        rotation_strategy = "round_robin"
        selected_keys = []
    else:
        key_rot = input("\nEnable key rotation? [Y/n]: ").strip().lower() != "n"
        rotation_strategy = "round_robin"
        if key_rot and len(selected_keys) > 1:
            print("  1) round_robin  2) random  3) least_used  4) fastest")
            s = input("  Strategy [1]: ").strip() or "1"
            rotation_strategy = {"1": "round_robin", "2": "random", "3": "least_used", "4": "fastest"}.get(s, "round_robin")

    # Image provider
    print("\nImage generation providers:")
    img_names = list(IMAGE_PROVIDERS.keys())
    for i, name in enumerate(img_names, 1):
        p = IMAGE_PROVIDERS[name]
        print(f"  [{i}] {p['name']} — {p['description']}")
    img_choice = input("Select image provider [1]: ").strip() or "1"
    try:
        image_provider = img_names[int(img_choice) - 1]
    except (ValueError, IndexError):
        image_provider = "pollinations"

    image_model = ""
    image_api_key = ""
    img_p = IMAGE_PROVIDERS[image_provider]
    if img_p.get("requires_key"):
        env_k = img_p.get("env_key", "")
        image_api_key = input(f"  {env_key} (or press Enter to skip): ").strip() if (env_key := env_k) else ""
        if image_api_key:
            os.environ[env_k] = image_api_key
    if img_p.get("models"):
        image_model = img_p["models"][0]

    config = SetupConfig(
        provider=provider_name,
        model=model_id,
        key_rotation=key_rot,
        rotation_strategy=rotation_strategy,
        selected_keys={provider_name: selected_keys},
        image_provider=image_provider,
        image_model=image_model,
        image_api_key=image_api_key,
    )
    config.save()
    print(f"\nSaved! Model: {config.to_langchain_model_str()}")
    return config


# ---------------------------------------------------------------------------
# Rich TUI wizard
# ---------------------------------------------------------------------------

def _tui_wizard() -> SetupConfig:
    # Check existing
    existing = SetupConfig.load()
    if not existing.first_run and existing.provider and existing.model:
        _tui_header()
        console.print(Panel(
            f"Current: [bold]{existing.provider}[/]:[bold cyan]{existing.model}[/]",
            border_style="dim",
        ))
        if not Confirm.ask("[bold]Reconfigure?", default=False):
            return existing

    _tui_header()

    # Scan keys
    env_keys = _scan_env_keys()
    available = [p for p in PROVIDERS if (p in env_keys and env_keys[p]) or PROVIDERS[p].no_key_required]

    if not available:
        console.print("[bold red]No API keys found in .env![/]")
        console.print("[dim]Add at least one: DEEPSEEK_API_KEY=sk-... or GEMINI_API_KEY=AIza...[/]")
        sys.exit(1)

    # ── STEP 1: Provider ──────────────────────────────────────────────
    _tui_step_banner(1, "Choose your AI provider")

    cards = []
    for i, name in enumerate(available, 1):
        prov = PROVIDERS[name]
        key_count = len(env_keys.get(name, []))
        cards.append(_tui_provider_card(prov, key_count, i))

    console.print(Columns(cards, equal=False, expand=False))

    console.print()
    choice = Prompt.ask(
        "[bold]Select provider",
        choices=[str(i) for i in range(1, len(available) + 1)],
        default="1",
    )
    try:
        idx = int(choice) - 1
        provider_name = available[idx]
    except (ValueError, IndexError):
        provider_name = available[0]

    provider = PROVIDERS[provider_name]
    provider.api_keys = env_keys.get(provider_name, [])

    # ── Collect ALL providers (primary + optional secondary) ──────────
    all_providers: dict[str, ProviderInfo] = {provider_name: provider}
    secondary_available = [p for p in available if p != provider_name]

    if secondary_available:
        _tui_step_banner("1b", "Add secondary providers (optional)")
        console.print("[dim]You can use different providers for different agent types (coder, research, vision).[/]")
        console.print()
        for sec_name in secondary_available:
            sec_prov = PROVIDERS[sec_name]
            key_count = len(env_keys.get(sec_name, []))
            label = f"{sec_prov.display_name}"
            if sec_prov.no_key_required:
                label += " [green](no key needed)[/]"
            elif key_count > 0:
                label += f" [dim]({key_count} key{'s' if key_count > 1 else ''})[/]"
            else:
                label += " [red](no keys)[/]"
            if Confirm.ask(f"[bold]Add {label}?", default=False):
                sec_prov.api_keys = env_keys.get(sec_name, [])
                all_providers[sec_name] = sec_prov

    # ── Fetch models from ALL providers ───────────────────────────────
    _tui_step_banner(2, "Select models")

    all_models: dict[str, list[dict[str, Any]]] = {}
    for pname, pinfo in all_providers.items():
        color = pinfo.color or "bright_blue"
        if pinfo.no_key_required:
            with console.status(f"[bold {color}]Detecting {pinfo.display_name} models...", spinner="dots"):
                try:
                    import httpx
                    resp = httpx.get("http://localhost:11434/api/tags", timeout=5)
                    if resp.status_code == 200:
                        data = resp.json()
                        mods = []
                        for m in data.get("models", []):
                            name = m.get("name", "").replace(":latest", "")
                            if name:
                                caps = m.get("capabilities", [])
                                mods.append({"id": name, "name": name, "description": "", "context_window": m.get("details", {}).get("context_length", 0), "capabilities": caps})
                        all_models[pname] = mods
                    else:
                        all_models[pname] = []
                except Exception:
                    all_models[pname] = []
            if not all_models.get(pname):
                console.print(f"[yellow]{pinfo.display_name} not reachable. Using common model names.[/]")
        else:
            with console.status(f"[bold {color}]Fetching {pinfo.display_name} models...", spinner="dots"):
                all_models[pname] = asyncio.run(fetch_models_for_provider(pinfo))

    # Fallback models if any provider has empty list
    fallback_models = {
        "gemini": [
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "context_window": 1048576, "output_limit": 65536},
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "context_window": 1048576, "output_limit": 65536},
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "context_window": 1048576, "output_limit": 8192},
        ],
        "deepseek": [
            {"id": "deepseek-chat", "name": "DeepSeek Chat (V3)", "context_window": 65536, "output_limit": 8192},
            {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner (R1)", "context_window": 65536, "output_limit": 8192},
        ],
        "groq": [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B", "context_window": 128000, "output_limit": 32768},
            {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B Instant", "context_window": 128000, "output_limit": 8192},
            {"id": "mixtral-8x7b-32768", "name": "Mixtral 8x7B", "context_window": 32768, "output_limit": 32768},
        ],
        "openai": [
            {"id": "gpt-4o", "name": "GPT-4o", "context_window": 128000, "output_limit": 16384},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "context_window": 128000, "output_limit": 16384},
        ],
        "anthropic": [
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "context_window": 200000, "output_limit": 64000},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "context_window": 200000, "output_limit": 8192},
        ],
        "qwen": [
            {"id": "qwen-plus", "name": "Qwen Plus", "context_window": 131072, "output_limit": 8192},
            {"id": "qwen-turbo", "name": "Qwen Turbo", "context_window": 131072, "output_limit": 8192},
        ],
        "ollama": [
            {"id": "llama3.2", "name": "Llama 3.2", "context_window": 128000, "output_limit": 8192},
            {"id": "llama3.1", "name": "Llama 3.1", "context_window": 128000, "output_limit": 8192},
            {"id": "mistral", "name": "Mistral", "context_window": 32768, "output_limit": 8192},
            {"id": "qwen2.5", "name": "Qwen 2.5", "context_window": 32768, "output_limit": 8192},
            {"id": "deepseek-r1", "name": "DeepSeek R1", "context_window": 65536, "output_limit": 8192},
            {"id": "phi4", "name": "Phi-4", "context_window": 128000, "output_limit": 16384},
        ],
    }
    for pname in all_providers:
        if not all_models.get(pname):
            all_models[pname] = fallback_models.get(pname, [
                {"id": f"{pname}-chat", "name": f"{pname}-chat", "description": "", "context_window": 0}
            ])

    console.print(f"[dim]Models loaded for {len(all_providers)} provider(s)[/]")
    console.print()

    # Build unified model list tagged with provider info
    unified_models: list[dict[str, Any]] = []
    for pname, mods in all_models.items():
        pinfo = all_providers[pname]
        for m in mods:
            unified_models.append({**m, "provider": pname, "provider_color": pinfo.color or "white"})

    def _pick_model(prompt_text: str, default_idx: int = 1, custom_allowed: bool = False) -> tuple[str, str]:
        """Show unified model table and return (provider_name, model_id)."""
        console.print(model_table)
        console.print()
        choices = [str(i) for i in range(0, len(unified_models) + 1)]
        if custom_allowed:
            choices.append("custom")
        choice = Prompt.ask(prompt_text, choices=choices, default=str(default_idx))
        try:
            if choice == "custom" and custom_allowed:
                model_id = Prompt.ask("[bold]Enter model name", default=unified_models[0]["id"] if unified_models else "llama3.2")
                return (provider_name, model_id)
            midx = int(choice)
            if midx == 0:
                return (unified_models[0]["provider"], unified_models[0]["id"])
            m = unified_models[midx - 1]
            return (m["provider"], m["id"])
        except (ValueError, IndexError):
            return (unified_models[0]["provider"], unified_models[0]["id"])

    # Build model table with provider column
    model_table = _tui_model_table(unified_models, show_provider=True)

    console.print(f"[dim]Models available from {len(unified_models)} entries across {len(all_providers)} provider(s)[/]")
    console.print()

    # ── Select MAIN model ─────────────────────────────────────────────
    console.print("[bold]Select your main model:[/]")
    console.print()
    custom_allowed = any(p.no_key_required for p in all_providers.values())
    prov_main, model_id = _pick_model(
        "[bold]Main model number" + (" (or 'custom' to type a name)" if custom_allowed else ""),
        custom_allowed=custom_allowed,
    )

    # Optional small model (from same provider list)
    small_model = ""
    if len(unified_models) > 1 and Confirm.ask("\n[bold]Set a smaller model for quick tasks?", default=False):
        console.print(model_table)
        console.print()
        sm_choice = Prompt.ask("[bold]Small model number", default="1")
        try:
            sm_idx = int(sm_choice)
            if sm_idx > 0:
                sm_entry = unified_models[sm_idx - 1]
                small_model = sm_entry["id"]
        except (ValueError, IndexError):
            pass

    # ── STEP 2b: Per-Agent Model Overrides ────────────────────────────
    agent_models: dict[str, str] = {}
    if len(all_providers) > 1 and Confirm.ask(f"\n[bold]Configure different models per agent type?", default=False):
        for atype in AGENT_TYPES:
            if atype == "vision":
                continue  # handled in Step 5
            label = AGENT_TYPE_LABELS.get(atype, atype)
            current_model = f"{prov_main}:{model_id}" if atype == "main" else ""
            if Confirm.ask(f"\n[bold]Custom model for {label}? (current: {current_model or 'default'})", default=False):
                console.print(model_table)
                console.print()
                a_prov, a_model = _pick_model(f"[bold]Model for {label}", custom_allowed=custom_allowed)
                agent_models[atype] = f"{a_prov}:{a_model}"

    # ── STEP 3: Key Rotation ──────────────────────────────────────────
    _tui_step_banner(3, "Configure key rotation")

    selected_keys: dict[str, list[str]] = {}
    all_need_keys = [p for p in all_providers if not all_providers[p].no_key_required]
    if not all_need_keys:
        console.print("[green]All providers run locally — no API keys needed.[/]")
        key_rotation = False
        rotation_strategy = "round_robin"
        max_retries = 3
    else:
        for pname in all_need_keys:
            pinfo = all_providers[pname]
            keys = env_keys.get(pname, [])
            if not keys:
                console.print(f"[yellow]No keys found for {pinfo.display_name}. Enter one now:[/]")
                manual_key = Prompt.ask(f"[bold]{pinfo.display_name} API key", default="")
                if manual_key:
                    keys = [manual_key]
            selected_keys[pname] = keys

            if len(keys) > 1:
                console.print(f"\n[bold]{pinfo.display_name}[/] — {len(keys)} keys available")
                key_table = _tui_key_table(keys, pinfo.color)
                console.print(key_table)
                console.print()
                if not Confirm.ask(f"[bold]Use all {len(keys)} keys?", default=True):
                    key_input = Prompt.ask("[bold]Enter key numbers (comma-separated)")
                    try:
                        indices = [int(x.strip()) - 1 for x in key_input.split(",")]
                        selected_keys[pname] = [keys[i] for i in indices if 0 <= i < len(keys)]
                    except (ValueError, IndexError):
                        console.print("[yellow]Invalid, using all.[/]")

        # Rotation strategy (applies to all providers with keys)
        if any(len(v) > 1 for v in selected_keys.values()):
            console.print()
            rot_table = _tui_rotation_table()
            console.print(rot_table)
            console.print()
            strat_choice = Prompt.ask(
                "[bold]Select rotation strategy",
                choices=["1", "2", "3", "4"],
                default="1",
            )
            strategy_map = {"1": "round_robin", "2": "random", "3": "least_used", "4": "fastest"}
            rotation_strategy = strategy_map.get(strat_choice, "round_robin")
            key_rotation = True
        else:
            key_rotation = False
            rotation_strategy = "round_robin"

        max_retries_str = Prompt.ask("\n[bold]Max retries per request", default="3")
        try:
            max_retries = int(max_retries_str)
        except ValueError:
            max_retries = 3

    # ── STEP 4: Image Generation ─────────────────────────────────────
    _tui_step_banner(4, "Configure image generation")

    img_providers = list(IMAGE_PROVIDERS.keys())
    img_cards = []
    for i, name in enumerate(img_providers, 1):
        p = IMAGE_PROVIDERS[name]
        key_status = "[green]free[/]" if not p["requires_key"] else "[yellow]needs key[/]"
        img_cards.append(Panel(
            f"[bold {p['color']}]{p['name']}[/]\n{p['description']}\n{key_status}",
            title=f"[bold]({i})[/]",
            border_style=p["color"],
            width=30,
            padding=(0, 1),
        ))
    console.print(Columns(img_cards, equal=False, expand=False))
    console.print()

    img_choice = Prompt.ask(
        "[bold]Select image provider",
        choices=[str(i) for i in range(1, len(img_providers) + 1)],
        default="1",
    )
    try:
        img_idx = int(img_choice) - 1
        image_provider = img_providers[img_idx]
    except (ValueError, IndexError):
        image_provider = "pollinations"

    img_config = IMAGE_PROVIDERS[image_provider]
    image_model = ""
    image_api_key = ""

    if img_config.get("requires_key"):
        # Check if key exists in env
        env_key_name = img_config.get("env_key", "")
        existing_key = os.environ.get(env_key_name, "")
        if existing_key:
            console.print(f"[green]Found {env_key_name} in environment[/]")
            image_api_key = existing_key
        else:
            image_api_key = Prompt.ask(f"[bold]Enter {env_key_name}", default="")
            if image_api_key:
                os.environ[env_key_name] = image_api_key

        # Model selection for image providers with multiple models
        if len(img_config.get("models", [])) > 1:
            console.print()
            descs = img_config.get("model_descriptions", {})
            for i, m in enumerate(img_config["models"], 1):
                desc = descs.get(m, "")
                console.print(f"  [{i}] {m}" + (f" — {desc}" if desc else ""))
            img_model_choice = Prompt.ask(
                "[bold]Select image model",
                choices=[str(i) for i in range(1, len(img_config["models"]) + 1)],
                default="1",
            )
            try:
                image_model = img_config["models"][int(img_model_choice) - 1]
            except (ValueError, IndexError):
                image_model = img_config["models"][0]
        elif img_config.get("models"):
            image_model = img_config["models"][0]

    console.print(f"[dim]Image provider: {img_config['name']}[/]")

    # ── STEP 5: Vision Model ──────────────────────────────────────────
    _tui_step_banner(5, "Configure vision model (screen/camera analysis)")

    vision_model = f"{prov_main}:{model_id}"
    if "vision" in agent_models:
        vision_model = agent_models["vision"]
    elif Confirm.ask(f"\n[bold]Use a different model for vision? (current: {vision_model})", default=False):
        console.print(model_table)
        vm_choice = Prompt.ask("[bold]Vision model number", default="1")
        try:
            vm_idx = int(vm_choice)
            if vm_idx > 0:
                vm_entry = unified_models[vm_idx - 1]
                vision_model = f"{vm_entry['provider']}:{vm_entry['id']}"
        except (ValueError, IndexError):
            pass

    console.print(f"[dim]Vision model: {vision_model}[/]")

    # ── Summary ───────────────────────────────────────────────────────
    config = SetupConfig(
        provider=prov_main,
        model=model_id,
        small_model=small_model,
        vision_model=vision_model,
        agent_models=agent_models,
        key_rotation=key_rotation,
        rotation_strategy=rotation_strategy,
        max_retries=max_retries,
        selected_keys=selected_keys,
        image_provider=image_provider,
        image_model=image_model,
        image_api_key=image_api_key,
    )
    config.save()

    total_keys = sum(len(v) for v in selected_keys.values())
    _tui_summary(config, total_keys)
    console.print("[bold green]Saved to data/setup.json[/]")
    console.print(f"[dim]Run: python -m xeno.server[/]\n")

    return config


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_setup_wizard() -> SetupConfig:
    if HAS_RICH and sys.stdin.isatty():
        return _tui_wizard()
    return _plain_wizard()


def get_setup_config(force_noninteractive: bool = False) -> SetupConfig:
    config = SetupConfig.load()
    if config.first_run or not config.provider:
        if not force_noninteractive and sys.stdin.isatty():
            config = run_setup_wizard()
        else:
            env_keys = _scan_env_keys()
            available = [p for p in PROVIDERS if p in env_keys and env_keys[p]]
            if available:
                provider_name = available[0]
                default_models = {
                    "gemini": "gemini-2.0-flash",
                    "deepseek": "deepseek-chat",
                    "groq": "llama-3.3-70b-versatile",
                    "openai": "gpt-4o",
                    "anthropic": "claude-sonnet-4-20250514",
                    "qwen": "qwen-plus",
                    "ollama": "llama3.2",
                }
                model_id = default_models.get(provider_name, f"{provider_name}-chat")
                config = SetupConfig(
                    provider=provider_name,
                    model=model_id,
                    selected_keys={provider_name: env_keys[provider_name]},
                    key_rotation=len(env_keys[provider_name]) > 1,
                    first_run=False,
                )
                config.save()
                logger.info(f"Auto-configured: {provider_name}:{model_id} ({len(env_keys[provider_name])} keys)")
    return config


def get_model_string(setup: Optional[SetupConfig] = None) -> str:
    if setup is None:
        setup = get_setup_config()
    return setup.to_langchain_model_str()


# ---------------------------------------------------------------------------
# API helpers (non-interactive)
# ---------------------------------------------------------------------------

async def api_fetch_providers() -> list[dict[str, Any]]:
    env_keys = _scan_env_keys()
    return [
        {"name": name, "display_name": prov.display_name,
         "key_count": len(env_keys.get(name, [])), "available": bool(env_keys.get(name))}
        for name, prov in PROVIDERS.items()
    ]


async def api_fetch_models(provider_name: str) -> list[dict[str, Any]]:
    env_keys = _scan_env_keys()
    if provider_name not in PROVIDERS or provider_name not in env_keys:
        return []
    prov = PROVIDERS[provider_name]
    prov.api_keys = env_keys[provider_name]
    return await fetch_models_for_provider(prov)


async def api_save_setup(
    provider: str, model: str, small_model: str = "", vision_model: str = "",
    key_rotation: bool = True, rotation_strategy: str = "round_robin",
    max_retries: int = 3, selected_keys: Optional[list[str]] = None,
) -> SetupConfig:
    env_keys = _scan_env_keys()
    if not selected_keys:
        selected_keys = env_keys.get(provider, [])
    config = SetupConfig(
        provider=provider, model=model, small_model=small_model,
        vision_model=vision_model,
        key_rotation=key_rotation, rotation_strategy=rotation_strategy,
        max_retries=max_retries, selected_keys={provider: selected_keys},
    )
    config.save()
    return config


if __name__ == "__main__":
    run_setup_wizard()
