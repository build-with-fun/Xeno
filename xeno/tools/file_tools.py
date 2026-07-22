"""File read/write/create tools for Xeno."""

import os
from pathlib import Path
from typing import Optional


def read_file(path: str) -> str:
    """Read the contents of a file and return them as text."""
    try:
        p = Path(path)
        if not p.exists():
            return f"File not found: {path}"
        if p.stat().st_size > 1_000_000:
            return f"File too large ({p.stat().st_size} bytes). Use shell_execute to read portions."
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """Write content to a file. Creates parent directories if needed. Overwrites existing files."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} bytes to {p.resolve()}"
    except Exception as e:
        return f"Error writing file: {e}"


def list_files(directory: str = ".", pattern: str = "*") -> str:
    """List files in a directory. Returns file names, sizes, and modification times."""
    try:
        d = Path(directory)
        if not d.exists():
            return f"Directory not found: {directory}"
        if not d.is_dir():
            return f"Not a directory: {directory}"

        files = sorted(d.glob(pattern), key=lambda x: (x.is_dir(), x.name))
        if not files:
            return f"No files matching '{pattern}' in {d.resolve()}"

        lines = [f"Files in {d.resolve()} ({len(files)} total):\n"]
        for f in files[:200]:
            if f.is_dir():
                lines.append(f"  {f.name}/")
            else:
                size = f.stat().st_size
                if size < 1024:
                    size_str = f"{size}B"
                elif size < 1024 * 1024:
                    size_str = f"{size / 1024:.1f}KB"
                else:
                    size_str = f"{size / (1024 * 1024):.1f}MB"
                lines.append(f"  {f.name}  ({size_str})")
        if len(files) > 200:
            lines.append(f"  ... and {len(files) - 200} more")
        return "\n".join(lines)
    except Exception as e:
        return f"Error listing files: {e}"


def file_exists(path: str) -> str:
    """Check if a file or directory exists and return its info."""
    p = Path(path)
    if not p.exists():
        return f"Path does not exist: {path}"
    if p.is_dir():
        count = sum(1 for _ in p.iterdir())
        return f"Directory: {p.resolve()} ({count} items)"
    else:
        size = p.stat().st_size
        return f"File: {p.resolve()} ({size} bytes, modified: {p.stat().st_mtime})"
