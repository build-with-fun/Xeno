"""Time and date helpers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def now_iso() -> str:
    """Return current time as ISO 8601 string with timezone."""
    return datetime.now(timezone.utc).astimezone().isoformat()


def parse_iso(s: str) -> datetime | None:
    """Parse an ISO 8601 string. Returns None on failure."""
    if not s:
        return None
    try:
        # Python 3.11+ handles most ISO formats natively
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def seconds_until(target: datetime) -> float:
    """Seconds from now until target datetime. Negative if already past."""
    now = datetime.now(target.tzinfo) if target.tzinfo else datetime.now()
    return (target - now).total_seconds()


def format_duration(seconds: float) -> str:
    """Human-readable duration like '1h 23m 45s' or '45s' or '500ms'."""
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    if seconds < 60:
        return f"{int(seconds)}s"
    minutes, sec = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {sec}s"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes}m {sec}s"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h {minutes}m"
