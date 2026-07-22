"""Text manipulation helpers."""
from __future__ import annotations

import re
import unicodedata

# Strict: only allow alphanumeric + underscore. Replaces everything else.
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_]+")


def safe_filename(name: str, max_len: int = 80) -> str:
    """Convert an arbitrary contact name into a safe filename component.

    Defends against path traversal (`../`), null bytes, and overlong names.
    The original code's regex `[^a-zA-Z0-9]` allowed `.` which permitted `../`.
    """
    if not name:
        return "unknown"
    # Normalize unicode (decomposes accents)
    name = unicodedata.normalize("NFKD", name)
    # Drop path separators and null bytes explicitly first
    name = name.replace("\x00", "").replace("/", "_").replace("\\", "_").replace("..", "_")
    # Replace any remaining non-safe char with underscore, collapse runs
    name = _SAFE_NAME_RE.sub("_", name).strip("_")
    if not name:
        name = "unknown"
    return name[:max_len]


def truncate(text: str, max_chars: int, suffix: str = "…") -> str:
    """Truncate text to max_chars, appending suffix if shortened."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)] + suffix


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace into single spaces."""
    return re.sub(r"\s+", " ", text).strip()


def strip_markdown(text: str) -> str:
    """Remove common markdown formatting (for sending plain text)."""
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}([^*]+)\*{1,3}", r"\1", text)
    text = re.sub(r"_{1,3}([^_]+)_{1,3}", r"\1", text)
    # Remove markdown links, keep text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove list markers
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    return text.strip()
