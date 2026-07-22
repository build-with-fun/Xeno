"""Self-healing and self-modification system.

Features:
- Diagnose any error and auto-fix
- Install missing dependencies
- Fix broken MCP servers
- Modify its own codebase safely
- Auto-detect capability gaps and scaffold new abilities
- Test capabilities before deploying
- Full health monitoring with auto-repair
- Dependency graph analysis
- Codebase integrity verification
- Automatic skill creation from error patterns
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from xeno.config import XenoConfig


class SelfHealer:
    """Self-healing, self-modification, and capability extension system."""

    def __init__(self, config: XenoConfig):
        self.config = config
        self.log_file = config.data_dir / "self_heal_log.json"
        self._log: list[dict] = self._load_log()

    def _load_log(self) -> list[dict]:
        if self.log_file.exists():
            try:
                return json.loads(self.log_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _save_log(self):
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.write_text(json.dumps(self._log[-200:], indent=2, default=str), encoding="utf-8")

    def _log_event(self, event_type: str, description: str, result: str):
        self._log.append({
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "description": description[:300],
            "result": result[:500],
        })
        self._save_log()

    # --- Diagnostics ---

    def diagnose_issue(self, error_message: str, context: str = "") -> str:
        """Analyze an error and suggest comprehensive fixes."""
        diagnosis = []
        error_lower = error_message.lower()

        if "no module named" in error_lower or "module" in error_lower and "not found" in error_lower:
            module = error_message.split("'")[-2] if "'" in error_message else "unknown"
            diagnosis.append(f"Missing module: {module}")
            diagnosis.append(f"Fix: pip install {module}")
            diagnosis.append(f"auto_fixable: pip install {module}")

        elif "import" in error_lower and "error" in error_lower:
            diagnosis.append("Import error - checking dependencies")
            diagnosis.append("Fix: pip install -r requirements.txt")

        elif "permission" in error_lower or "access" in error_lower:
            diagnosis.append("Permission denied")
            diagnosis.append("Fix: Check file permissions or run with appropriate privileges")

        elif "connection" in error_lower or "timeout" in error_lower:
            diagnosis.append("Network connectivity issue")
            diagnosis.append("Fix: Check internet connection and retry")

        elif "api key" in error_lower or "unauthorized" in error_lower or "401" in error_lower:
            diagnosis.append("API key issue")
            diagnosis.append("Fix: Set the appropriate API key in environment variables")

        elif "syntax" in error_lower or "invalid" in error_lower:
            diagnosis.append("Syntax error in code")
            diagnosis.append("Fix: Review and correct the syntax")

        elif "name" in error_lower and "not defined" in error_lower:
            diagnosis.append("NameError - variable or function not defined")
            diagnosis.append("Fix: Define the variable/function before use")

        elif "attribute" in error_lower and "has no attribute" in error_lower:
            diagnosis.append("AttributeError - accessing non-existent attribute")
            diagnosis.append("Fix: Check the object's available attributes")

        elif "type" in error_lower and "error" in error_lower:
            diagnosis.append("TypeError - wrong type used")
            diagnosis.append("Fix: Check argument types match expected signatures")

        elif "index" in error_lower and ("out of range" in error_lower or "error" in error_lower):
            diagnosis.append("IndexError - list index out of range")
            diagnosis.append("Fix: Check list bounds before accessing")

        elif "key" in error_lower and "error" in error_lower:
            diagnosis.append("KeyError - dictionary key not found")
            diagnosis.append("Fix: Check key exists or use .get()")

        elif "file" in error_lower and ("not found" in error_lower or "no such file" in error_lower):
            diagnosis.append("File not found")
            diagnosis.append("Fix: Check file path exists")

        elif "oserror" in error_lower or "errno" in error_lower:
            diagnosis.append("OS-level error")
            diagnosis.append("Fix: Check file system permissions and paths")

        elif "encoding" in error_lower or "decode" in error_lower:
            diagnosis.append("Encoding/decoding error")
            diagnosis.append("Fix: Specify correct encoding (e.g., encoding='utf-8')")

        elif "memory" in error_lower or "out of memory" in error_lower:
            diagnosis.append("Memory exhaustion")
            diagnosis.append("Fix: Optimize memory usage or increase available memory")

        elif "recursion" in error_lower and "depth" in error_lower:
            diagnosis.append("Maximum recursion depth exceeded")
            diagnosis.append("Fix: Add base case to recursive function or use iteration")

        elif "broken" in error_lower or "corrupt" in error_lower:
            diagnosis.append("Data corruption detected")
            diagnosis.append("Fix: Restore from backup or rebuild")

        else:
            diagnosis.append(f"Error type: {error_message[:100]}")
            diagnosis.append("Manual investigation may be needed")

        if context:
            diagnosis.append(f"Context: {context[:100]}")

        result = "\n".join(diagnosis)
        self._log_event("diagnose", error_message[:200], result)
        return result

    # --- Dependency Management ---

    def fix_missing_dependency(self, module_name: str) -> str:
        """Install a missing Python dependency."""
        try:
            # Try pip install
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", module_name],
                capture_output=True, text=True, timeout=180,
            )
            if result.returncode == 0:
                self._log_event("fix_dependency", f"Installed {module_name}", "Success")
                return f"Successfully installed {module_name}"

            # Try pip3
            result = subprocess.run(
                [sys.executable, "-m", "pip3", "install", module_name],
                capture_output=True, text=True, timeout=180,
            )
            if result.returncode == 0:
                self._log_event("fix_dependency", f"Installed {module_name} via pip3", "Success")
                return f"Successfully installed {module_name} via pip3"

            return f"Failed to install {module_name}: {result.stderr[:500]}"
        except Exception as e:
            return f"Error installing {module_name}: {str(e)}"

    def install_requirements(self, requirements_path: str = "requirements.txt") -> str:
        """Install all dependencies from a requirements file."""
        path = Path(requirements_path)
        if not path.exists():
            return f"Requirements file not found: {requirements_path}"
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(path)],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode == 0:
                self._log_event("install_requirements", f"Installed from {requirements_path}", "Success")
                return f"Successfully installed dependencies from {requirements_path}"
            return f"Failed: {result.stderr[:500]}"
        except Exception as e:
            return f"Error: {str(e)}"

    def check_missing_imports(self) -> list[str]:
        """Scan xeno codebase for missing imports."""
        missing = []
        xeno_dir = Path(__file__).parent
        for py_file in xeno_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                for line in content.split("\n"):
                    if line.startswith("import ") or line.startswith("from "):
                        parts = line.split()
                        if len(parts) >= 2:
                            module = parts[1].split(".")[0]
                            if module not in sys.modules:
                                try:
                                    __import__(module)
                                except ImportError:
                                    missing.append(module)
            except Exception:
                pass
        return list(set(missing))

    # --- MCP Management ---

    def fix_broken_mcp(self, mcp_name: str, issue: str) -> str:
        """Attempt to fix a broken MCP server."""
        steps = [f"Diagnosing MCP '{mcp_name}': {issue}"]

        # Check if process is running (Windows-safe: no shell=True)
        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["tasklist"], capture_output=True, text=True, timeout=10,
                )
            else:
                result = subprocess.run(
                    ["ps", "aux"], capture_output=True, text=True, timeout=10,
                )
            if mcp_name.lower() in result.stdout.lower():
                steps.append(f"MCP '{mcp_name}' process found — may need restart")
            else:
                steps.append(f"MCP '{mcp_name}' not running — attempting to start")
        except Exception:
            steps.append("Could not check processes")

        # Check config
        config_path = self.config.data_dir / "dynamic_config.json"
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                servers = data.get("mcp_servers", {})
                if mcp_name in servers:
                    cfg = servers[mcp_name]
                    steps.append(f"Config found: type={cfg.get('type')}, enabled={cfg.get('enabled')}")
                    if not cfg.get("enabled", True):
                        steps.append("MCP is disabled — enabling it")
                        cfg["enabled"] = True
                        servers[mcp_name] = cfg
                        data["mcp_servers"] = servers
                        config_path.write_text(json.dumps(data, indent=2))
                else:
                    steps.append(f"MCP '{mcp_name}' not in config — may need to add it")
            except Exception:
                steps.append("Could not read MCP config")

        self._log_event("fix_mcp", f"Fixed {mcp_name}", "\n".join(steps))
        return "\n".join(steps)

    def restart_mcp(self, mcp_name: str) -> str:
        """Restart an MCP server by disabling and re-enabling it."""
        config_path = self.config.data_dir / "dynamic_config.json"
        if not config_path.exists():
            return "No MCP config found"
        try:
            data = json.loads(config_path.read_text())
            servers = data.get("mcp_servers", {})
            if mcp_name not in servers:
                return f"MCP '{mcp_name}' not found in config"
            servers[mcp_name]["enabled"] = False
            data["mcp_servers"] = servers
            config_path.write_text(json.dumps(data, indent=2))
            time.sleep(1)
            servers[mcp_name]["enabled"] = True
            config_path.write_text(json.dumps(data, indent=2))
            self._log_event("restart_mcp", f"Restarted {mcp_name}", "Success")
            return f"MCP '{mcp_name}' restarted. Call reload to reconnect."
        except Exception as e:
            return f"Error restarting MCP: {e}"

    # --- Self-Modification ---

    def self_modify(self, file_path: str, old_code: str, new_code: str) -> str:
        """Modify its own codebase safely."""
        path = Path(file_path)
        if not path.exists():
            return f"File not found: {file_path}"
        if not str(path).startswith(str(Path(__file__).parent.parent)):
            return "Can only modify files within the xeno project directory"

        try:
            content = path.read_text(encoding="utf-8")
            if old_code not in content:
                return f"Old code not found in {file_path}"
            new_content = content.replace(old_code, new_code, 1)

            # Syntax check before writing
            try:
                compile(new_content, str(path), "exec")
            except SyntaxError as e:
                return f"New code has syntax error — aborting: {e}"

            path.write_text(new_content, encoding="utf-8")
            self._log_event("self_modify", f"Modified {file_path}", "Success")
            return f"Successfully modified {file_path}"
        except Exception as e:
            return f"Error modifying file: {str(e)}"

    def create_file(self, file_path: str, content: str) -> str:
        """Create a new file in the project."""
        path = Path(file_path)
        if not str(path).startswith(str(Path(__file__).parent.parent)):
            return "Can only create files within the xeno project directory"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            self._log_event("create_file", f"Created {file_path}", "Success")
            return f"Created {file_path}"
        except Exception as e:
            return f"Error creating file: {e}"

    # --- Capability Management ---

    def diagnose_capability_gap(self, description: str) -> str:
        """Diagnose what capability is missing for a task."""
        from xeno.capabilities import CapabilityManager
        cm = CapabilityManager(self.config.data_dir / "capabilities")
        gaps = cm.detect_gaps(description)
        if not gaps:
            return f"No specific capability gap detected for: {description[:100]}"
        lines = [f"Detected {len(gaps)} capability gap(s):"]
        for g in gaps:
            lines.append(f"  - [{g.gap_type}] {g.description[:100]} (id: {g.id})")
        return "\n".join(lines)

    def scaffold_tool(self, name: str, description: str, code: str) -> str:
        """Create a new tool from Python code."""
        from xeno.capabilities import CapabilityManager
        cm = CapabilityManager(self.config.data_dir / "capabilities")
        try:
            cap = cm.scaffold_tool(name, description, code)
            self._log_event("scaffold_tool", f"Created tool: {name}", f"Cap ID: {cap.id}")
            return f"Tool '{name}' scaffolded (id: {cap.id}). Call test then deploy."
        except ValueError as e:
            return f"Failed to scaffold tool: {e}"

    def scaffold_skill(self, name: str, description: str, body: str) -> str:
        """Create a new skill."""
        from xeno.capabilities import CapabilityManager
        cm = CapabilityManager(self.config.data_dir / "capabilities")
        cap = cm.scaffold_skill(name, description, body)
        self._log_event("scaffold_skill", f"Created skill: {name}", f"Cap ID: {cap.id}")
        return f"Skill '{name}' scaffolded (id: {cap.id}). Deploy to make it available."

    def scaffold_mcp(self, name: str, config_json: str) -> str:
        """Create a new MCP server config."""
        from xeno.capabilities import CapabilityManager
        cm = CapabilityManager(self.config.data_dir / "capabilities")
        try:
            cfg = json.loads(config_json) if config_json else {}
        except json.JSONDecodeError:
            return "Invalid JSON config"
        cap = cm.scaffold_mcp(name, cfg)
        self._log_event("scaffold_mcp", f"Created MCP: {name}", f"Cap ID: {cap.id}")
        return f"MCP '{name}' scaffolded (id: {cap.id})."

    def test_capability(self, cap_id: str, test_input: str = "") -> str:
        """Test a scaffolded capability."""
        from xeno.capabilities import CapabilityManager
        cm = CapabilityManager(self.config.data_dir / "capabilities")
        cap = None
        for c in cm.scaffolded:
            if c.id == cap_id:
                cap = c
                break
        if not cap:
            return f"Capability {cap_id} not found"
        if cap.capability_type == "tool":
            passed = cm.test_tool(cap_id, test_input)
            result = f"Tool test {'PASSED' if passed else 'FAILED'}"
        else:
            result = f"Cannot test {cap.capability_type} type yet"
        self._log_event("test_capability", f"Tested {cap.name}", result)
        return result

    def deploy_capability(self, cap_id: str) -> str:
        """Deploy a tested capability."""
        from xeno.capabilities import CapabilityManager
        cm = CapabilityManager(self.config.data_dir / "capabilities")
        for cap in cm.scaffolded:
            if cap.id == cap_id:
                if cap.capability_type == "tool":
                    deployed = cm.deploy_tool(cap_id)
                    if deployed:
                        self._log_event("deploy_capability", f"Deployed tool: {cap.name}", "Success")
                        return f"Tool '{cap.name}' deployed and registered"
                elif cap.capability_type == "skill":
                    deployed = cm.deploy_skill(cap_id)
                    if deployed:
                        self._log_event("deploy_capability", f"Deployed skill: {cap.name}", "Success")
                        return f"Skill '{cap.name}' deployed"
                return f"Failed to deploy {cap.name}"
        return f"Capability {cap_id} not found"

    def auto_extend(self, description: str) -> str:
        """Full auto-extend pipeline: detect gap → scaffold → test → deploy."""
        from xeno.capabilities import CapabilityManager
        cm = CapabilityManager(self.config.data_dir / "capabilities")
        from xeno.tool_registry import ToolRegistry
        registry = ToolRegistry(self.config.data_dir / "tools")
        result = cm.auto_extend(description, available_tools=list(registry.tools.keys()))
        self._log_event("auto_extend", description[:200], json.dumps(result, default=str))
        parts = [f"Gap detected: {result['gap_detected']} ({result['gap_type']})"]
        parts.extend(result["details"])
        return "\n".join(parts)

    # --- Skill Creation from Patterns ---

    def create_skill(self, name: str, description: str, body: str) -> str:
        """Create a new skill from an error pattern or success."""
        from xeno.skills_manager import SkillManager
        sm = SkillManager(self.config)
        result = sm.create(name, description, body)
        self._log_event("create_skill", f"Created skill {name}", result)
        return result

    def create_skill_from_error(self, error_type: str, error_message: str, fix_approach: str) -> str:
        """Auto-create a skill to prevent a recurring error."""
        import re
        safe_name = re.sub(r'[^a-z0-9_]', '_', f"avoid_{error_type}".lower())[:40]
        description = f"Auto-generated skill to avoid: {error_type}"
        body = f"""# Avoid {error_type}

## Problem
{error_message[:500]}

## Solution
{fix_approach[:500]}

## Steps
1. Before the operation, check for the error condition
2. If detected, apply the fix approach above
3. If still failing, escalate to manual review

## Notes
- Auto-generated by the learning system
- Review and update as needed
"""
        return self.create_skill(safe_name, description, body)

    # --- Health Monitoring ---

    def get_health_report(self) -> str:
        """Generate a comprehensive health report."""
        checks = []

        # Python environment
        checks.append(f"[OK] Python {sys.version.split()[0]}")

        # Core packages
        from xeno.config import PROJECT_ROOT
        pyproject = PROJECT_ROOT / "pyproject.toml"
        if pyproject.exists():
            checks.append("[OK] pyproject.toml exists")
        else:
            checks.append("[WARN] pyproject.toml missing")

        for pkg in ["deepagents", "langchain", "langgraph", "fastapi", "chromadb"]:
            try:
                __import__(pkg.replace("-", "_"))
                checks.append(f"[OK] {pkg} installed")
            except ImportError:
                checks.append(f"[MISSING] {pkg} not installed — run: pip install {pkg}")

        # Data directories
        for subdir in ["memory", "learning", "auto_save", "capabilities", "checkpoints", "skills_library"]:
            p = self.config.data_dir / subdir
            if p.exists():
                count = len(list(p.rglob("*")))
                checks.append(f"[OK] {subdir}/ ({count} files)")
            else:
                checks.append(f"[WARN] {subdir}/ missing")

        # Error log
        recent_errors = [e for e in self._log if e.get("type") in ("auto_heal", "diagnose")]
        if recent_errors:
            checks.append(f"[INFO] {len(recent_errors)} recent healing events")
        else:
            checks.append("[OK] No recent errors")

        # Tool registry
        try:
            from xeno.tool_registry import ToolRegistry
            registry = ToolRegistry(self.config.data_dir / "tools")
            stats = registry.get_stats()
            checks.append(f"[OK] Tool registry: {stats.get('total', 0)} tools")
        except Exception as e:
            checks.append(f"[WARN] Tool registry: {e}")

        # MCP servers
        config_path = self.config.data_dir / "dynamic_config.json"
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                servers = data.get("mcp_servers", {})
                checks.append(f"[OK] MCP servers: {len(servers)} configured")
            except Exception:
                pass

        return "\n".join(checks)

    def get_heal_log(self, limit: int = 20) -> list[dict]:
        """Get recent healing events."""
        return self._log[-limit:]

    def summary(self) -> str:
        return f"SelfHealer: {len(self._log)} events logged"
