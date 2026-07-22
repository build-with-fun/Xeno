"""Datetime & Scheduling MCP Server for Main Agent.

Provides:
  - get_current_datetime(): current date/time with timezone info
  - schedule_reminder(): schedule a reminder that will appear in the chat
  - format_timestamp(): convert timestamps between formats
  - calculate_time_diff(): calculate time between two dates
  - get_week_info(): get current week number, day, etc.
"""
from __future__ import annotations

import os
import json
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("Datetime Server")

PROJECT_ROOT = Path(os.environ.get("XENO_PROJECT_ROOT", str(Path(__file__).resolve().parent.parent.parent.parent)))

# ── Tools ─────────────────────────────────────────────────────

@mcp.tool
def get_current_datetime(timezone_offset: str = "auto") -> dict:
    """Get the current date and time. Returns ISO format, Unix timestamp, and human-readable.

    Args:
        timezone_offset: 'auto' for local time, or like '+05:00', '-08:00', 'UTC'

    Returns:
        dict with keys: iso, unix, human, timezone, week_day, is_dst
    """
    now = datetime.now()
    utc_now = datetime.now(timezone.utc)

    tz_str = "local"
    if timezone_offset == "UTC":
        now = utc_now.replace(tzinfo=None)
    elif timezone_offset != "auto":
        try:
            hours = int(timezone_offset.replace(":", "").replace("+", "").replace("-", "").strip()[:2])
            sign = -1 if "-" in timezone_offset else 1
            offset = timedelta(hours=sign * hours)
            now = (utc_now + offset).replace(tzinfo=None)
            tz_str = timezone_offset
        except Exception:
            pass

    return {
        "iso": now.isoformat(timespec="seconds"),
        "iso_utc": utc_now.isoformat(timespec="seconds"),
        "unix": int(now.timestamp()),
        "human": now.strftime("%A, %B %d, %Y at %I:%M:%S %p"),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "timezone": tz_str,
        "week_day": now.strftime("%A"),
        "week_number": int(now.strftime("%W")),
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "hour": now.hour,
        "minute": now.minute,
        "second": now.second,
        "is_dst": bool(now.dst()) if hasattr(now, 'dst') and now.dst() else None,
    }


@mcp.tool
def schedule_reminder(
    message: str,
    delay_seconds: int = 0,
    delay_minutes: int = 0,
    delay_hours: int = 0,
    target_datetime_iso: str = "",
    chat_id: str = "",
) -> dict:
    """Schedule a reminder that will be delivered after the specified delay or at a specific time.

    Use this when the user says "remind me in X minutes/seconds/hours" or "remind me at 3pm".

    Args:
        message: The reminder message to deliver
        delay_seconds: Delay in seconds from now
        delay_minutes: Delay in minutes from now
        delay_hours: Delay in hours from now
        target_datetime_iso: ISO datetime string for exact time (e.g. '2026-07-08T15:30:00')
        chat_id: Optional chat ID for delivery (auto-detected if blank)

    Returns:
        dict with reminder_id, scheduled_time, message
    """
    now = datetime.now()

    if target_datetime_iso:
        try:
            target = datetime.fromisoformat(target_datetime_iso)
        except Exception:
            return {"error": f"Invalid datetime format: {target_datetime_iso}. Use YYYY-MM-DDTHH:MM:SS"}
    else:
        total_seconds = delay_seconds + (delay_minutes * 60) + (delay_hours * 3600)
        if total_seconds <= 0:
            total_seconds = 60  # default 1 minute
        target = now + timedelta(seconds=total_seconds)

    reminder_id = str(uuid.uuid4())[:8]
    delay_ms = int((target - now).total_seconds() * 1000)

    # Write reminder to a JSON file that the scheduler injector will pick up
    reminders_dir = PROJECT_ROOT / "logs" / "reminders"
    reminders_dir.mkdir(parents=True, exist_ok=True)
    reminder_file = reminders_dir / f"{reminder_id}.json"
    reminder_file.write_text(json.dumps({
        "id": reminder_id,
        "message": message,
        "scheduled_at_iso": target.isoformat(timespec="seconds"),
        "chat_id": chat_id,
        "created_at": now.isoformat(timespec="seconds"),
        "status": "pending",
    }, indent=2), encoding="utf-8")

    return {
        "reminder_id": reminder_id,
        "message": message,
        "scheduled_time": target.isoformat(timespec="seconds"),
        "scheduled_time_human": target.strftime("%A, %B %d at %I:%M %p"),
        "delay": f"{delay_ms // 1000}s",
        "status": "scheduled",
    }


@mcp.tool
def calculate_time_diff(
    datetime_a: str,
    datetime_b: str = "",
) -> dict:
    """Calculate the time difference between two dates/times.

    Args:
        datetime_a: First ISO datetime string (if datetime_b is empty, compares against now)
        datetime_b: Second ISO datetime string (optional, defaults to now)

    Returns:
        dict with total_seconds, years, months, days, hours, minutes, human_readable
    """
    try:
        a = datetime.fromisoformat(datetime_a.replace("Z", ""))
    except Exception:
        return {"error": f"Invalid datetime: {datetime_a}"}

    if datetime_b:
        try:
            b = datetime.fromisoformat(datetime_b.replace("Z", ""))
        except Exception:
            return {"error": f"Invalid datetime: {datetime_b}"}
    else:
        b = datetime.now()

    diff = b - a
    total_seconds = int(abs(diff.total_seconds()))
    is_past = diff.total_seconds() > 0

    parts = []
    if total_seconds >= 86400 * 365:
        years = total_seconds // (86400 * 365)
        parts.append(f"{years} year{'s' if years > 1 else ''}")
        total_seconds %= (86400 * 365)
    if total_seconds >= 86400 * 30:
        months = total_seconds // (86400 * 30)
        parts.append(f"{months} month{'s' if months > 1 else ''}")
        total_seconds %= (86400 * 30)
    if total_seconds >= 86400:
        days = total_seconds // 86400
        parts.append(f"{days} day{'s' if days > 1 else ''}")
        total_seconds %= 86400
    if total_seconds >= 3600:
        hours = total_seconds // 3600
        parts.append(f"{hours} hour{'s' if hours > 1 else ''}")
        total_seconds %= 3600
    if total_seconds >= 60:
        minutes = total_seconds // 60
        parts.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
        total_seconds %= 60
    if total_seconds > 0:
        parts.append(f"{total_seconds} second{'s' if total_seconds > 1 else ''}")

    direction = "ago" if is_past else "from now"
    return {
        "total_seconds": int(abs(diff.total_seconds())),
        "total_minutes": round(abs(diff.total_seconds()) / 60, 1),
        "total_hours": round(abs(diff.total_seconds()) / 3600, 2),
        "total_days": round(abs(diff.total_seconds()) / 86400, 2),
        "human_readable": f"{' '.join(parts) if parts else '0 seconds'} {direction}",
        "is_past": is_past,
        "is_future": not is_past,
    }


@mcp.tool
def format_timestamp(
    timestamp: str,
    output_format: str = "human",
) -> dict:
    """Format a timestamp into different formats.

    Args:
        timestamp: ISO datetime string or Unix timestamp (integer)
        output_format: 'human', 'iso', 'unix', 'date', 'time', or 'all'

    Returns:
        dict with formatted timestamps
    """
    try:
        # Try ISO first
        dt = datetime.fromisoformat(timestamp.replace("Z", "").replace("T", " "))
    except Exception:
        try:
            # Try Unix timestamp
            ts = int(timestamp)
            dt = datetime.fromtimestamp(ts)
        except Exception:
            return {"error": f"Cannot parse timestamp: {timestamp}"}

    result = {
        "iso": dt.isoformat(timespec="seconds"),
        "unix": int(dt.timestamp()),
        "human": dt.strftime("%A, %B %d, %Y at %I:%M:%S %p"),
        "date": dt.strftime("%Y-%m-%d"),
        "time": dt.strftime("%H:%M:%S"),
        "week_day": dt.strftime("%A"),
    }

    if output_format == "all":
        return result
    if output_format in result:
        return {"value": result[output_format], "original": timestamp}
    return result


@mcp.tool
def get_week_info(date_str: str = "") -> dict:
    """Get information about the current or specified week.

    Args:
        date_str: ISO date string (YYYY-MM-DD), defaults to today

    Returns:
        dict with week_number, week_day, month, year, quarter, start_of_week, end_of_week
    """
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except Exception:
            return {"error": f"Invalid date: {date_str}. Use YYYY-MM-DD"}
    else:
        dt = datetime.now()

    # Start of week (Monday)
    start = dt - timedelta(days=dt.weekday())
    end = start + timedelta(days=6)
    quarter = (dt.month - 1) // 3 + 1

    return {
        "date": dt.strftime("%Y-%m-%d"),
        "week_day": dt.strftime("%A"),
        "week_day_number": dt.weekday(),
        "week_number_iso": int(dt.strftime("%W")),
        "month": dt.strftime("%B"),
        "month_number": dt.month,
        "year": dt.year,
        "quarter": quarter,
        "start_of_week": start.strftime("%Y-%m-%d"),
        "end_of_week": end.strftime("%Y-%m-%d"),
        "days_in_month": _days_in_month(dt.year, dt.month),
        "is_weekend": dt.weekday() >= 5,
        "is_leap_year": dt.year % 4 == 0 and (dt.year % 100 != 0 or dt.year % 400 == 0),
    }


def _days_in_month(year: int, month: int) -> int:
    import calendar
    return calendar.monthrange(year, month)[1]


# ── Main ──────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
