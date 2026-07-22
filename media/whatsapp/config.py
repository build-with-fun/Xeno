"""Centralized configuration management using pydantic-settings.

All environment variables are loaded once at startup and exposed as a singleton
`settings`. This avoids the original code's pattern of calling `os.getenv()`
scattered across 50+ call sites, which made it impossible to know the full
configuration surface or validate it.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve project root (the directory containing config.py)
PROJECT_ROOT = Path(__file__).resolve().parent

load_dotenv(PROJECT_ROOT / ".env", override=False)


class Settings(BaseSettings):
    """Strongly-typed application configuration."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── AI provider keys (collected into lists) ──────────────────────────────
    gemini_api_keys: List[str] = Field(default_factory=list)
    groq_api_keys: List[str] = Field(default_factory=list)
    openai_api_keys: List[str] = Field(default_factory=list)
    openai_base_url: str = ""
    openai_model: str = ""
    anthropic_api_keys: List[str] = Field(default_factory=list)

    # ── Models ───────────────────────────────────────────────────────────────
    gemini_model: str = "gemini-3.1-flash-lite"
    gemini_image_model: str = "gemini-3.1-flash-lite-image"
    groq_model: str = "llama-3.3-70b-versatile"

    # Xeno vision model override — if set, WhatsApp uses the same vision model as Xeno
    @property
    def xeno_vision_model(self) -> str:
        """Get the Xeno vision model from env, falling back to XENO_MODEL."""
        v = os.getenv("XENO_VISION_MODEL", "").strip()
        if v:
            return v.split(":", 1)[-1] if ":" in v else v
        m = os.getenv("XENO_MODEL", "").strip()
        if m and ":" in m:
            return m.split(":", 1)[1]
        return self.gemini_model

    # ── STT ──────────────────────────────────────────────────────────────────
    stt_server_url: str = "http://localhost:8080"
    stt_timeout: int = 30
    stt_fallback_local: bool = True

    # ── Admin API ────────────────────────────────────────────────────────────
    admin_host: str = "127.0.0.1"
    admin_port: int = 5000
    admin_api_token: str = Field(default="change-this-to-a-long-random-string")

    # ── Human behavior ───────────────────────────────────────────────────────
    reply_delay_min: float = 2.5
    reply_delay_max: float = 6.0
    typing_speed_wpm_min: int = 55
    typing_speed_wpm_max: int = 85
    reading_speed_cpm_min: int = 400
    reading_speed_cpm_max: int = 900
    batch_window_secs: float = 4.0

    # ── Scanner ──────────────────────────────────────────────────────────────
    scan_interval_min: float = 1.5
    scan_interval_max: float = 3.0
    scan_sidebar_limit: int = 50

    # ── Workers ──────────────────────────────────────────────────────────────
    auto_sender_interval: int = 2
    retry_worker_interval: int = 5
    max_concurrent_sends: int = 1

    # ── AI tuning ────────────────────────────────────────────────────────────
    gemini_max_chars: int = 80_000
    groq_max_chars: int = 24_000
    openai_max_chars: int = 60_000
    summary_threshold: int = 60
    summary_keep: int = 30
    summary_min_interval_secs: int = 600
    ai_request_timeout: int = 60
    ai_max_retries: int = 3

    # ── Retry queue ──────────────────────────────────────────────────────────
    retry_max_attempts: int = 4
    retry_backoff_base: int = 5
    retry_backoff_max: int = 600

    # ── Safety ───────────────────────────────────────────────────────────────
    rate_limit_per_hour: int = 20
    rate_limit_cooldown: int = 900

    # ── Webhook ──────────────────────────────────────────────────────────────
    webhook_url: str = ""
    webhook_secret: str = ""

    # ── Observability ────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_file_max_bytes: int = 10_485_760
    log_file_backup_count: int = 10
    metrics_enabled: bool = True

    # ── Browser ──────────────────────────────────────────────────────────────
    browser_headless: bool = False
    browser_user_data_dir: str = ""
    browser_proxy: str = ""
    browser_timezone: str = "Asia/Karachi"
    browser_locale: str = "en-US"

    # ── WPP.js ───────────────────────────────────────────────────────────────
    wpp_js_url: str = (
        "https://github.com/wppconnect-team/wa-js/releases/download/nightly/wppconnect-wa.js"
    )
    wpp_js_local_cache: str = "data/wppconnect-wa.js"
    wpp_injection_timeout: int = 30

    # ── Derived paths (computed at runtime) ──────────────────────────────────
    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def session_dir(self) -> Path:
        if self.browser_user_data_dir:
            return Path(self.browser_user_data_dir).absolute()
        # Use dedicated WhatsApp profile — never share Xeno's profile
        # (separate profile avoids Chrome lock conflicts when both run simultaneously)
        return (PROJECT_ROOT / "data" / "whatsapp_profile").resolve()

    @property
    def data_dir(self) -> Path:
        return PROJECT_ROOT / "data"

    @property
    def chats_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "chats"

    @property
    def pending_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "pending"

    @property
    def personas_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "personas"

    @property
    def alerts_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "alerts"

    @property
    def analytics_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "analytics"

    @property
    def retry_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "retry"

    @property
    def media_cache_dir(self) -> Path:
        return PROJECT_ROOT / "data" / "media_cache"

    @property
    def logs_dir(self) -> Path:
        return PROJECT_ROOT / "logs"

    @property
    def seen_ids_path(self) -> Path:
        return PROJECT_ROOT / "data" / "seen_ids.json"

    @property
    def pending_state_path(self) -> Path:
        return PROJECT_ROOT / "data" / "pending_contacts_state.json"

    @property
    def stop_signal_path(self) -> Path:
        return PROJECT_ROOT / "data" / "STOP_SIGNAL"

    # ── Validators: collect numbered env vars into lists ─────────────────────
    @field_validator("gemini_api_keys", mode="before")
    @classmethod
    def _collect_gemini(cls, v):
        if v:
            return v if isinstance(v, list) else [v]
        return cls._collect_numbered("GEMINI_API_KEY")

    @field_validator("groq_api_keys", mode="before")
    @classmethod
    def _collect_groq(cls, v):
        if v:
            return v if isinstance(v, list) else [v]
        return cls._collect_numbered("GROQ_API_KEY")

    @field_validator("openai_api_keys", mode="before")
    @classmethod
    def _collect_openai(cls, v):
        if v:
            return v if isinstance(v, list) else [v]
        keys = cls._collect_numbered("OPENAI_API_KEY")
        if not keys:
            # Fallback: use bare OPENAI_API_KEY (set by Xeno for Ollama)
            fallback = os.getenv("OPENAI_API_KEY", "").strip()
            if fallback:
                keys = [fallback]
                # Auto-detect Ollama from base_url and set model
                base = os.getenv("OPENAI_BASE_URL", "").strip()
                if base and "localhost" in base and "11434" in base:
                    os.environ["OPENAI_BASE_URL"] = base
        return keys

    @field_validator("anthropic_api_keys", mode="before")
    @classmethod
    def _collect_anthropic(cls, v):
        if v:
            return v if isinstance(v, list) else [v]
        return cls._collect_numbered("ANTHROPIC_API_KEY")

    @staticmethod
    def _collect_numbered(prefix: str) -> List[str]:
        keys = []
        for i in range(1, 9):
            val = os.getenv(f"{prefix}_{i}", "").strip()
            if val:
                keys.append(val)
        return keys

    @classmethod
    def _is_ollama_mode(cls) -> bool:
        base = os.getenv("OPENAI_BASE_URL", "").strip()
        return bool(base and "localhost" in base and "11434" in base)

    @classmethod
    def _detect_ollama_model(cls) -> str:
        return os.getenv("XENO_MODEL", "").split(":", 1)[-1] or ""

    def ensure_directories(self) -> None:
        """Create all required directories. Safe to call multiple times."""
        for d in (
            self.session_dir, self.chats_dir, self.pending_dir,
            self.personas_dir, self.alerts_dir, self.analytics_dir,
            self.retry_dir, self.media_cache_dir, self.logs_dir,
            self.data_dir,
        ):
            d.mkdir(parents=True, exist_ok=True)

    def _fill_openai_from_env(self) -> None:
        """Fill OpenAI settings from env if not set in .env."""
        if not self.openai_base_url:
            self.openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        if not self.openai_model:
            env_model = os.getenv("XENO_MODEL", "")
            if env_model and ":" in env_model:
                self.openai_model = env_model.split(":", 1)[1]
            else:
                self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def _has_keys_or_ollama(self) -> bool:
        """Check if we have API keys or can use Ollama."""
        if self.gemini_api_keys or self.groq_api_keys or self.openai_api_keys or self.anthropic_api_keys:
            return True
        return bool(self._is_ollama_mode())

    def validate(self) -> List[str]:
        """Return a list of configuration problems. Empty list = OK."""
        self._fill_openai_from_env()
        problems = []
        if not self._has_keys_or_ollama():
            problems.append(
                "No AI API keys configured. Set at least one of: "
                "GEMINI_API_KEY_1, GROQ_API_KEY_1, OPENAI_API_KEY_1, ANTHROPIC_API_KEY_1"
            )
        if self.admin_api_token in ("change-this-to-a-long-random-string", "", "changeme"):
            problems.append(
                "ADMIN_API_TOKEN is using the default value. "
                "Set a long random string in .env for security."
            )
        if self.reply_delay_max < self.reply_delay_min:
            problems.append("REPLY_DELAY_MAX must be >= REPLY_DELAY_MIN")
        if self.scan_interval_min < 0.5:
            problems.append(
                "SCAN_INTERVAL_MIN below 0.5s will likely trigger WhatsApp rate limits"
            )
        return problems


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    s = Settings()
    s._fill_openai_from_env()
    s.ensure_directories()
    return s


settings = get_settings()
