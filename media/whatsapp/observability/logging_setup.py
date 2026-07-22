"""Structured logging setup with rotation and rich console output.

Fixes the original code's issues:
- Mixed `print()` and `logger.info()` causing interleaved output
- No structured fields (only formatted strings)
- Console handler hardcoded to INFO, no runtime control
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

from media.whatsapp.config import settings

_INITIALIZED = False
_console = Console()


class _BotLogger(logging.Logger):
    """Logger with a `.event()` method for structured log entries."""

    def event(self, event_name: str, **fields) -> None:
        """Log a structured event at INFO level.

        Example: logger.event("reply_sent", contact="Alice", chars=42)
        """
        msg = f"[{event_name}] " + " ".join(f"{k}={v!r}" for k, v in fields.items())
        self.info(msg, extra={"event_name": event_name, **fields})


def setup_logging() -> None:
    """Initialize root and bot loggers. Safe to call multiple times."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True

    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Register our custom logger class
    logging.setLoggerClass(_BotLogger)

    # Configure the "wabot" logger
    bot_logger = logging.getLogger("wabot")
    bot_logger.setLevel(logging.DEBUG)
    # Clear any pre-existing handlers (e.g., from a re-import)
    bot_logger.handlers.clear()

    # ── Console handler (rich, INFO+) ─────────────────────────────────────
    console_handler = RichHandler(
        console=_console,
        show_path=False,
        show_time=True,
        rich_tracebacks=True,
        tracebacks_show_locals=False,
        markup=False,
    )
    console_handler.setLevel(level)
    bot_logger.addHandler(console_handler)

    # ── File handler (DEBUG+, rotating) ───────────────────────────────────
    log_path = settings.logs_dir / "bot.log"
    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=settings.log_file_max_bytes,
        backupCount=settings.log_file_backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    bot_logger.addHandler(file_handler)

    # ── Alerts file handler (WARNING+, separate file) ─────────────────────
    alerts_path = settings.logs_dir / "alerts.log"
    alerts_handler = RotatingFileHandler(
        alerts_path,
        maxBytes=settings.log_file_max_bytes // 2,
        backupCount=settings.log_file_backup_count // 2,
        encoding="utf-8",
    )
    alerts_handler.setLevel(logging.WARNING)
    alerts_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    bot_logger.addHandler(alerts_handler)

    # Quiet noisy third-party loggers
    for noisy in ("urllib3", "httpx", "httpcore", "playwright", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # Redirect stdout/stderr printing through the logger so the original code's
    # `print(...)` calls (now replaced) would still be captured if reintroduced.
    sys.stderr = _ConsoleStream(logging.ERROR)


class _ConsoleStream:
    """Redirect writes to the wabot logger (for unhandled stderr output)."""

    def __init__(self, level: int):
        self._level = level
        self._buf = ""

    def write(self, s: str) -> int:
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            if line.strip():
                logging.getLogger("wabot").log(self._level, line)
        return len(s)

    def flush(self) -> None:
        if self._buf.strip():
            logging.getLogger("wabot").log(self._level, self._buf)
            self._buf = ""


def get_logger(name: str = "wabot") -> _BotLogger:
    """Get a child logger under the main 'wabot' namespace."""
    if not _INITIALIZED:
        setup_logging()
    # Cast: setLoggerClass only affects newly-instantiated loggers
    logger = logging.getLogger(name)
    if not isinstance(logger, _BotLogger):
        # Wrap by setting our class on the manager; existing loggers keep their type
        logger.__class__ = _BotLogger
    return logger  # type: ignore[return-value]
