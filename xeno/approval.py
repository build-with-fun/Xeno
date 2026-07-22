"""Human-in-the-loop approval system for Xeno.

Implements the `interrupt_on` parameter pattern from the deepagents guide.
Provides approval workflows for dangerous operations, with configurable policies.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    AUTO_APPROVED = "auto_approved"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ApprovalRequest:
    id: str
    tool_name: str
    arguments: dict[str, Any]
    risk_level: RiskLevel
    reason: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: float = field(default_factory=time.time)
    responded_at: Optional[float] = None
    responder: Optional[str] = None
    notes: str = ""


# Tools that require approval based on risk level
DEFAULT_APPROVAL_POLICY: dict[str, RiskLevel] = {
    "shell_execute": RiskLevel.HIGH,
    "shell_run_python": RiskLevel.HIGH,
    "execute_python": RiskLevel.MEDIUM,
    "self_modify": RiskLevel.CRITICAL,
    "self_heal_fix": RiskLevel.CRITICAL,
    "mouse_click": RiskLevel.MEDIUM,
    "type_text": RiskLevel.MEDIUM,
    "press_key": RiskLevel.MEDIUM,
    "browser_open": RiskLevel.LOW,
    "browser_evaluate": RiskLevel.HIGH,
    "memory_store": RiskLevel.LOW,
    "memory_delete": RiskLevel.LOW,
    "skill_create": RiskLevel.MEDIUM,
    "skill_delete": RiskLevel.MEDIUM,
    "schedule_create": RiskLevel.LOW,
    "schedule_delete": RiskLevel.LOW,
}

# Risk levels that auto-approve in non-interactive mode
AUTO_APPROVE_LEVELS = {RiskLevel.LOW, RiskLevel.MEDIUM}


class ApprovalManager:
    """Manages human-in-the-loop approval workflows.

    Supports:
    - Configurable approval policies per tool
    - Risk-based auto-approval
    - Callback-based approval (for API/server mode)
    - Timeout and expiration
    - Approval history and audit trail
    """

    def __init__(
        self,
        enabled: bool = True,
        interactive: bool = False,
        auto_approve_low_risk: bool = True,
        approval_timeout: float = 300.0,
        on_request: Optional[Callable[[ApprovalRequest], None]] = None,
    ):
        self.enabled = enabled
        self.interactive = interactive
        self.auto_approve_low_risk = auto_approve_low_risk
        self.approval_timeout = approval_timeout
        self.on_request = on_request
        self.policy: dict[str, RiskLevel] = dict(DEFAULT_APPROVAL_POLICY)
        self.pending: dict[str, ApprovalRequest] = {}
        self.history: list[ApprovalRequest] = []

    def set_policy(self, tool_name: str, risk_level: RiskLevel) -> None:
        """Set the approval policy for a tool."""
        self.policy[tool_name] = risk_level

    def get_risk_level(self, tool_name: str) -> RiskLevel:
        """Get the risk level for a tool."""
        return self.policy.get(tool_name, RiskLevel.LOW)

    def needs_approval(self, tool_name: str) -> bool:
        """Check if a tool requires approval."""
        if not self.enabled:
            return False
        risk = self.get_risk_level(tool_name)
        if self.auto_approve_low_risk and risk in AUTO_APPROVE_LEVELS:
            return False
        return risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}

    def request_approval(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        reason: str = "",
    ) -> ApprovalRequest:
        """Create an approval request."""
        risk = self.get_risk_level(tool_name)
        request = ApprovalRequest(
            id=f"apr_{uuid.uuid4().hex[:8]}",
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk,
            reason=reason or f"Tool '{tool_name}' requires approval (risk: {risk.value})",
        )

        if not self.needs_approval(tool_name):
            request.status = ApprovalStatus.AUTO_APPROVED
            self.history.append(request)
            return request

        self.pending[request.id] = request
        logger.info(f"Approval required: {request.reason}")

        if self.on_request:
            self.on_request(request)

        if self.interactive:
            return self._prompt_approval(request)

        return request

    def _prompt_approval(self, request: ApprovalRequest) -> ApprovalRequest:
        """Prompt for approval in interactive mode."""
        print(f"\n{'='*60}")
        print(f"APPROVAL REQUIRED [{request.risk_level.value.upper()}]")
        print(f"Tool: {request.tool_name}")
        print(f"Reason: {request.reason}")
        print(f"Arguments: {request.arguments}")
        print(f"{'='*60}")

        while request.status == ApprovalStatus.PENDING:
            response = input("\nApprove? (y/n/notes): ").strip().lower()
            if response in ("y", "yes"):
                request.status = ApprovalStatus.APPROVED
                request.responded_at = time.time()
                request.responder = "user"
            elif response in ("n", "no"):
                request.status = ApprovalStatus.DENIED
                request.responded_at = time.time()
                request.responder = "user"
                request.notes = "Denied by user"
            elif response:
                request.notes = response
                print("Added notes. Type 'y' to approve or 'n' to deny.")

        self.pending.pop(request.id, None)
        self.history.append(request)
        return request

    def approve(self, request_id: str, responder: str = "system", notes: str = "") -> Optional[ApprovalRequest]:
        """Approve a pending request."""
        request = self.pending.get(request_id)
        if not request:
            return None
        request.status = ApprovalStatus.APPROVED
        request.responded_at = time.time()
        request.responder = responder
        request.notes = notes
        self.pending.pop(request_id)
        self.history.append(request)
        return request

    def deny(self, request_id: str, responder: str = "system", notes: str = "") -> Optional[ApprovalRequest]:
        """Deny a pending request."""
        request = self.pending.get(request_id)
        if not request:
            return None
        request.status = ApprovalStatus.DENIED
        request.responded_at = time.time()
        request.responder = responder
        request.notes = notes
        self.pending.pop(request_id)
        self.history.append(request)
        return request

    def check_timeouts(self) -> list[ApprovalRequest]:
        """Check for timed-out requests."""
        expired = []
        now = time.time()
        for req_id, request in list(self.pending.items()):
            if now - request.requested_at > self.approval_timeout:
                request.status = ApprovalStatus.EXPIRED
                request.responded_at = now
                self.pending.pop(req_id)
                self.history.append(request)
                expired.append(request)
                logger.warning(f"Approval request expired: {request.id}")
        return expired

    def is_approved(self, request_id: str) -> bool:
        """Check if a request was approved."""
        # Check pending (might have been approved via callback)
        if request_id in self.pending:
            return self.pending[request_id].status == ApprovalStatus.APPROVED
        # Check history
        for req in self.history:
            if req.id == request_id:
                return req.status in {ApprovalStatus.APPROVED, ApprovalStatus.AUTO_APPROVED}
        return False

    def get_pending(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        return list(self.pending.values())

    def get_history(self, limit: int = 20) -> list[ApprovalRequest]:
        """Get recent approval history."""
        return self.history[-limit:]

    def stats(self) -> dict[str, int]:
        """Get approval statistics."""
        counts = {s.value: 0 for s in ApprovalStatus}
        for req in self.history:
            counts[req.status.value] += 1
        counts["pending"] = len(self.pending)
        return counts
