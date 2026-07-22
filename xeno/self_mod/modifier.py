"""Self-modification — agent can edit its own code + add capabilities."""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class SelfModResult:
    success: bool
    action: str  # create_file | edit_file | add_tool | add_mcp | fix_error | install_package
    target: str
    message: str = ""
    error: str = ""
    backup_path: str = ""
    timestamp: float = field(default_factory=time.time)


class SelfModifier:
    """The agent can modify its own code.

    All operations:
    - Create a backup first
    - Make the change
    - Try to import/reload to verify it works
    - If broken, restore from backup
    """

    def __init__(
        self,
        project_root: Path,
        llm: Optional[Callable[[str, str], Awaitable[str]]] = None,
        backup_dir: Optional[Path] = None,
    ):
        self.root = project_root
        self.llm = llm
        self.backup_dir = backup_dir or (project_root / "data" / "self_mod_backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, file_path: str) -> Path:
        p = Path(file_path)
        return p if p.is_absolute() else self.root / p

    def _backup(self, file_path: str, content: str) -> str:
        ts = int(time.time())
        name = f"{Path(file_path).stem}_{ts}{Path(file_path).suffix}.bak"
        bp = self.backup_dir / name
        bp.write_text(content, encoding="utf-8")
        return str(bp)

    async def _try_import(self, file_path: str) -> None:
        """Verify a Python file is valid — check syntax + try import if root on sys.path."""
        full = self._resolve(file_path)
        code = full.read_text(encoding="utf-8")
        try:
            compile(code, str(full), "exec")
        except SyntaxError as e:
            raise RuntimeError(f"Syntax error: {e}")

        if str(self.root) not in sys.path:
            return

        try:
            rel = full.relative_to(self.root)
            parts = list(rel.parts)
            if parts[-1] == "__init__.py":
                parts = parts[:-1]
            else:
                parts[-1] = parts[-1][:-3]  # strip .py
            module_name = ".".join(parts)
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
        except Exception as e:
            raise RuntimeError(f"Import failed: {e}")

    async def create_file(self, file_path: str, content: str, description: str = "") -> SelfModResult:
        full = self._resolve(file_path)
        if full.exists():
            return SelfModResult(False, "create_file", file_path, error="File already exists")
        try:
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
            if file_path.endswith(".py"):
                await self._try_import(file_path)
            return SelfModResult(True, "create_file", file_path, f"Created {file_path}")
        except Exception as e:
            return SelfModResult(False, "create_file", file_path, error=str(e))

    async def edit_file(self, file_path: str, old: str, new: str, description: str = "") -> SelfModResult:
        full = self._resolve(file_path)
        if not full.exists():
            return SelfModResult(False, "edit_file", file_path, error="File not found")
        try:
            current = full.read_text(encoding="utf-8")
            if old not in current:
                return SelfModResult(False, "edit_file", file_path, error="old_content not found")
            backup = self._backup(file_path, current)
            new_text = current.replace(old, new, 1)
            full.write_text(new_text, encoding="utf-8")
            if file_path.endswith(".py"):
                try:
                    await self._try_import(file_path)
                except Exception as e:
                    full.write_text(current, encoding="utf-8")
                    return SelfModResult(
                        False, "edit_file", file_path,
                        error=f"Edit broke file (restored): {e}",
                        backup_path=backup,
                    )
            return SelfModResult(True, "edit_file", file_path, f"Edited {file_path}", backup_path=backup)
        except Exception as e:
            return SelfModResult(False, "edit_file", file_path, error=str(e))

    async def add_tool(self, tool_name: str, tool_description: str, tool_code: str) -> SelfModResult:
        file_path = f"xeno/tools/{tool_name}.py"
        full_code = (
            f'"""Auto-generated tool: {tool_name}\n\n{tool_description}\n"""\n'
            f"from __future__ import annotations\n\n{tool_code}\n\n"
            f'__all__ = ["{tool_name}"]\n'
        )
        result = await self.create_file(file_path, full_code, tool_description)
        if result.success:
            try:
                init_path = self.root / "xeno" / "tools" / "__init__.py"
                if init_path.exists():
                    init_content = init_path.read_text(encoding="utf-8")
                    import_line = f"from xeno.tools.{tool_name} import {tool_name}"
                    if import_line not in init_content:
                        init_path.write_text(init_content + f"\n{import_line}\n", encoding="utf-8")
            except Exception as e:
                logger.warning(f"Couldn't update tools __init__: {e}")
            result.message += " | Restart or hot-reload to activate."
        return result

    async def fix_error(self, error: str, traceback_str: str = "", context: str = "") -> SelfModResult:
        if self.llm is None:
            return SelfModResult(False, "fix_error", "", error="No LLM available for self-healing")
        matches = re.findall(r'File "([^"]+\.\w+)", line (\d+)', traceback_str or error)
        if not matches:
            return SelfModResult(False, "fix_error", "", error="Couldn't identify which file to fix")
        file_path, line_no = matches[-1][0], int(matches[-1][1])
        try:
            full = self._resolve(file_path)
            if not full.exists():
                return SelfModResult(False, "fix_error", file_path, error=f"File not found: {file_path}")
            current = full.read_text(encoding="utf-8")
            system = (
                "You are a Python expert fixing a bug in the Xeno agent codebase. "
                "Output ONLY the fixed file content — no markdown, no commentary. "
                "The entire file, with the fix applied."
            )
            user = (
                f"File: {file_path}\nError: {error}\nTraceback:\n{traceback_str[:2000]}\n\n"
                f"Current file content:\n```\n{current[:8000]}\n```\n\n"
                f"Context: {context}\n\n"
                f"Output the entire fixed file:"
            )
            fixed = await self.llm(system, user)
            if not fixed or not fixed.strip():
                return SelfModResult(False, "fix_error", file_path, error="LLM returned empty fix")
            fixed = fixed.strip()
            if fixed.startswith("```"):
                lines = fixed.split("\n")
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                fixed = "\n".join(lines)
            backup = self._backup(file_path, current)
            full.write_text(fixed, encoding="utf-8")
            try:
                await self._try_import(file_path)
            except Exception as e:
                full.write_text(current, encoding="utf-8")
                return SelfModResult(
                    False, "fix_error", file_path,
                    error=f"Fix didn't work (restored): {e}",
                    backup_path=backup,
                )
            return SelfModResult(True, "fix_error", file_path, f"Fixed {file_path}", backup_path=backup)
        except Exception as e:
            return SelfModResult(False, "fix_error", file_path, error=str(e))

    async def install_package(self, package: str) -> SelfModResult:
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install", package,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode == 0:
                return SelfModResult(True, "install_package", package, f"Installed {package}")
            return SelfModResult(False, "install_package", package, error=stderr.decode()[:500])
        except Exception as e:
            return SelfModResult(False, "install_package", package, error=str(e))

    def list_backups(self) -> list:
        return [
            {"file": f.name, "created_at": f.stat().st_mtime}
            for f in self.backup_dir.glob("*.bak")
        ]
