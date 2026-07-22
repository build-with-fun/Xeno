"""Risk classifier + bash allowlist."""
from __future__ import annotations
import re, logging
from dataclasses import dataclass, field
from enum import Enum
logger = logging.getLogger(__name__)

class RiskLevel(str, Enum):
    SAFE="safe"; MODERATE="moderate"; RISKY="risky"; DESTRUCTIVE="destructive"

@dataclass
class RiskAssessment:
    level: RiskLevel; score: float; reason: str = ""
    auto_approve: bool = False; requires_confirmation: bool = False
    matched_patterns: list[str] = field(default_factory=list)

class RiskClassifier:
    SAFE_TOOLS = {"read_file","list_files","file_exists","web_search","web_fetch",
                  "memory_search","memory_store","memory_recall","skill_search","skill_list",
                  "tool_list","status","help","tasks","threads"}
    RISKY_TOOLS = {"shell_execute","shell_run_python","execute_python","self_modify"}
    DESTRUCTIVE_PATTERNS = [
        (r"\brm\s+-rf?\s+/(?:\s|$)", "rm -rf root"),
        (r"\bmkfs\b", "format"), (r"\bdd\s+if=.*\s+of=/dev/", "dd to device"),
        (r":\(\)\{.*\|\:&\};", "fork bomb"),
        (r"\bgit\s+push\s+--force\b", "git force push"),
        (r"\bdrop\s+(?:table|database)\b", "SQL drop"),
        (r"\bshutdown\b", "shutdown"), (r"\breboot\b", "reboot"),
    ]
    RISKY_PATTERNS = [
        (r"\bpip\s+install\b", "pip install"),
        (r"\bnpm\s+install\b", "npm install"),
        (r"\bsudo\b", "sudo"),
        (r"\bcurl\s+.*\|\s*(?:bash|sh)\b", "curl|bash"),
    ]
    def classify(self, tool_name, tool_args=None, workspace_root=None):
        tool_args = tool_args or {}
        if tool_name in self.SAFE_TOOLS:
            return RiskAssessment(RiskLevel.SAFE, 0.1, f"safe tool: {tool_name}", auto_approve=True)
        if tool_name in self.RISKY_TOOLS:
            args_str = " ".join(str(v) for v in tool_args.values())
            for p, desc in self.DESTRUCTIVE_PATTERNS:
                if re.search(p, args_str, re.IGNORECASE):
                    return RiskAssessment(RiskLevel.DESTRUCTIVE, 1.0, f"destructive: {desc}",
                                          matched_patterns=[desc])
            for p, desc in self.RISKY_PATTERNS:
                if re.search(p, args_str, re.IGNORECASE):
                    return RiskAssessment(RiskLevel.RISKY, 0.8, f"risky: {desc}",
                                          requires_confirmation=True, matched_patterns=[desc])
            return RiskAssessment(RiskLevel.RISKY, 0.7, f"risky tool: {tool_name}", requires_confirmation=True)
        if tool_name in ("write_file","create_pdf","generate_image"):
            return RiskAssessment(RiskLevel.MODERATE, 0.3, "write op", auto_approve=True)
        if tool_name in ("browser_open","browser_click","mouse_click","take_screenshot"):
            return RiskAssessment(RiskLevel.MODERATE, 0.4, "automation", auto_approve=True)
        return RiskAssessment(RiskLevel.RISKY, 0.6, f"unknown: {tool_name}", requires_confirmation=True)

class BashAllowlist:
    DENYLIST = [
        (r"\brm\s+-rf?\s+/(?:\s|$|\*)", "rm -rf root"),
        (r"\bmkfs\b", "format"), (r"\bdd\s+if=.*\s+of=/dev/", "dd"),
        (r"\bshutdown\b", "shutdown"), (r"\breboot\b", "reboot"),
    ]
    def check(self, command):
        for p, desc in self.DENYLIST:
            if re.search(p, command, re.IGNORECASE):
                return False, f"BLOCKED: {desc}"
        return True, ""
