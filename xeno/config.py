import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
MEMORY_DIR = DATA_DIR / "memory"
VECTOR_DB_DIR = DATA_DIR / "vector_db"
SKILLS_DIR = PROJECT_ROOT / "skills"
SESSIONS_DIR = DATA_DIR / "sessions"
CONTEXT_MEMORY_FILE = MEMORY_DIR / "context.json"
SCHEDULES_FILE = DATA_DIR / "schedules.json"
AGENTS_MD = PROJECT_ROOT / "AGENTS.md"
AGENTS_DIR = PROJECT_ROOT / "agents"
PLUGINS_DIR = PROJECT_ROOT / "plugins"

for d in [DATA_DIR, MEMORY_DIR, VECTOR_DB_DIR, SESSIONS_DIR, SKILLS_DIR, AGENTS_DIR, PLUGINS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


@dataclass
class XenoConfig:
    model: str = "deepseek:deepseek-chat"
    small_model: str | None = None
    vision_model: str | None = None
    api_keys: dict[str, str] = field(default_factory=dict)
    data_dir: Path = DATA_DIR
    memory_dir: Path = MEMORY_DIR
    vector_db_dir: Path = VECTOR_DB_DIR
    skills_dir: Path = SKILLS_DIR
    sessions_dir: Path = SESSIONS_DIR
    project_root: Path = PROJECT_ROOT
    max_concurrent_agents: int = 5
    agent_timeout_seconds: int = 300
    recursion_limit: int = 50
    enable_browser: bool = True
    enable_desktop_control: bool = True
    enable_voice: bool = False
    whatsapp_enabled: bool = True
    whatsapp_module_path: str = str(PROJECT_ROOT / "media" / "whatsapp")
    mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)

    # AgentPool config
    pool_max_workers: int = 50
    pool_per_type_caps: dict[str, int] = field(default_factory=lambda: {
        "research": 10, "coder": 10, "browser": 5, "planner": 5,
        "analyst": 5, "whatsapp": 3, "default": 10,
    })
    pool_semaphore_limit: int = 30
    pool_default_timeout: int = 300

    # MCP config
    mcp_enabled: bool = True
    mcp_port: int = 8100
    mcp_host: str = "127.0.0.1"

    # ChatStore config
    chat_store_enabled: bool = True
    chat_store_max_context_messages: int = 50
    chat_store_compaction_interval: int = 20

    # Always-on agents config
    always_on_enabled: bool = True

    # Dynamic system config
    agents_dir: Path = AGENTS_DIR
    plugins_dir: Path = PLUGINS_DIR
    agent_dirs: list[str] = field(default_factory=lambda: [str(AGENTS_DIR), str(PROJECT_ROOT / "media")])
    plugin_dirs: list[str] = field(default_factory=lambda: [str(PLUGINS_DIR)])
    skill_dirs: list[str] = field(default_factory=lambda: [str(SKILLS_DIR)])
    enable_hot_reload: bool = True
    hot_reload_interval: float = 2.0
    enable_dynamic_agents: bool = True
    enable_dynamic_plugins: bool = True
    enable_dynamic_tools: bool = True
    enable_dynamic_mcp: bool = True
    dynamic_config_file: Path = DATA_DIR / "dynamic_config.json"

    # Setup wizard + key rotation
    provider: str = ""
    key_rotation_enabled: bool = True
    rotation_strategy: str = "round_robin"
    max_retries: int = 3
    rate_limit_backoff: float = 60.0
    selected_keys: dict[str, list[str]] = field(default_factory=dict)
    # Per-agent model overrides: {agent_type: "provider:model"}
    agent_models: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "XenoConfig":
        api_keys = {}
        for key in ["DEEPSEEK_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]:
            val = os.environ.get(key)
            if val:
                api_keys[key] = val

        # Load setup.json if it exists
        setup_data = {}
        setup_file = DATA_DIR / "setup.json"
        if setup_file.exists():
            try:
                setup_data = json.loads(setup_file.read_text())
            except Exception:
                pass

        # Load API keys from setup.json if not already in env
        provider_map = {
            "deepseek": "DEEPSEEK_API_KEY",
            "gemini": "GOOGLE_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "groq": "GROQ_API_KEY",
            "qwen": "QWEN_API_KEY",
            "ollama": "",
        }
        for prov, env_key in provider_map.items():
            if env_key not in api_keys:
                keys = setup_data.get("selected_keys", {}).get(prov, [])
                if keys:
                    api_keys[env_key] = keys[0]

        # Derive model from setup
        setup_model = ""
        setup_provider = setup_data.get("provider", "")
        if setup_provider and setup_data.get("model"):
            from xeno.setup import PROVIDERS
            prov = PROVIDERS.get(setup_provider)
            if prov:
                setup_model = f"{prov.langchain_prefix}:{setup_data['model']}"
            else:
                setup_model = setup_data.get("model", "")

        # Parse dynamic dirs from env
        agent_dirs_env = os.environ.get("XENO_AGENT_DIRS", "")
        agent_dirs = [d.strip() for d in agent_dirs_env.split(",") if d.strip()] if agent_dirs_env else [str(AGENTS_DIR), str(PROJECT_ROOT / "media")]

        plugin_dirs_env = os.environ.get("XENO_PLUGIN_DIRS", "")
        plugin_dirs = [d.strip() for d in plugin_dirs_env.split(",") if d.strip()] if plugin_dirs_env else [str(PLUGINS_DIR)]

        skill_dirs_env = os.environ.get("XENO_SKILL_DIRS", "")
        skill_dirs = [d.strip() for d in skill_dirs_env.split(",") if d.strip()] if skill_dirs_env else [str(SKILLS_DIR)]

        # Load dynamic config overrides
        dynamic_config = {}
        dynamic_config_path = DATA_DIR / "dynamic_config.json"
        if dynamic_config_path.exists():
            try:
                dynamic_config = json.loads(dynamic_config_path.read_text())
            except Exception:
                pass

        # Env model takes highest priority, then setup.json, then default
        env_model = os.environ.get("XENO_MODEL", "")

        # Inject API keys as env vars for deepagents compatibility
        for env_key, val in api_keys.items():
            if val and not os.environ.get(env_key):
                os.environ[env_key] = val

        return cls(
            model=env_model or setup_model or "deepseek:deepseek-chat",
            small_model=setup_data.get("small_model") or os.environ.get("XENO_SMALL_MODEL"),
            vision_model=setup_data.get("vision_model") or os.environ.get("XENO_VISION_MODEL") or env_model or setup_model or "google_genai:gemini-2.0-flash",
            api_keys=api_keys,
            max_concurrent_agents=int(os.environ.get("XENO_MAX_AGENTS", "5")),
            agent_timeout_seconds=int(os.environ.get("XENO_TIMEOUT", "300")),
            recursion_limit=int(os.environ.get("XENO_RECURSION_LIMIT", "50")),
            enable_browser=os.environ.get("XENO_ENABLE_BROWSER", "true").lower() == "true",
            enable_desktop_control=os.environ.get("XENO_ENABLE_DESKTOP", "true").lower() == "true",
            enable_voice=os.environ.get("XENO_ENABLE_VOICE", "false").lower() == "true",
            whatsapp_enabled=os.environ.get("XENO_WHATSAPP_ENABLED", "true").lower() == "true",
            agent_dirs=agent_dirs,
            plugin_dirs=plugin_dirs,
            skill_dirs=skill_dirs,
            enable_hot_reload=os.environ.get("XENO_HOT_RELOAD", "true").lower() == "true",
            hot_reload_interval=float(os.environ.get("XENO_HOT_RELOAD_INTERVAL", "2.0")),
            enable_dynamic_agents=os.environ.get("XENO_DYNAMIC_AGENTS", "true").lower() == "true",
            enable_dynamic_plugins=os.environ.get("XENO_DYNAMIC_PLUGINS", "true").lower() == "true",
            enable_dynamic_tools=os.environ.get("XENO_DYNAMIC_TOOLS", "true").lower() == "true",
            enable_dynamic_mcp=os.environ.get("XENO_DYNAMIC_MCP", "true").lower() == "true",
            provider=setup_provider,
            key_rotation_enabled=setup_data.get("key_rotation", True),
            rotation_strategy=setup_data.get("rotation_strategy", "round_robin"),
            max_retries=int(setup_data.get("max_retries", 3)),
            rate_limit_backoff=float(setup_data.get("rate_limit_backoff", 60.0)),
            selected_keys=setup_data.get("selected_keys", {}),
            agent_models=setup_data.get("agent_models", {}),
            pool_max_workers=int(os.environ.get("XENO_POOL_WORKERS", setup_data.get("pool_max_workers", "50"))),
            pool_semaphore_limit=int(os.environ.get("XENO_POOL_SEMAPHORE", setup_data.get("pool_semaphore_limit", "30"))),
            chat_store_enabled=os.environ.get("XENO_CHAT_STORE", "true").lower() == "true",
            mcp_enabled=os.environ.get("XENO_MCP_ENABLED", "true").lower() == "true",
            always_on_enabled=os.environ.get("XENO_ALWAYS_ON", "true").lower() == "true",
            **{k: v for k, v in dynamic_config.items() if k in cls.__dataclass_fields__},
        )
