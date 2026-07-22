"""Audit log: records every admin action for compliance.

Every API call, CLI command, and dashboard action is logged with:
  - Who (actor: API token, CLI user, system)
  - What (action: approve, reject, stop, config change)
  - When (timestamp)
  - Target (msg_id, contact, campaign_id, etc.)
  - Details (full request payload)
  - Source IP (for API calls)
"""
from __future__ import annotations

from typing import Optional

from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)


class AuditLogger:
    """Audit trail for all admin actions."""

    def log(
        self, actor: str, action: str, target: str = None,
        details: dict = None, ip_address: str = None,
    ) -> None:
        """Record an audit event."""
        try:
            from media.whatsapp.db.repo import AuditLogRepo
            AuditLogRepo.record(
                actor=actor, action=action, target=target,
                details=details, ip_address=ip_address,
            )
            logger.info(
                f"[Audit] {actor} performed '{action}'"
                + (f" on {target}" if target else "")
                + (f" from {ip_address}" if ip_address else "")
            )
        except Exception as e:
            logger.warning(f"[Audit] Failed to record: {e}")

    def list_recent(self, limit: int = 100) -> list:
        """List recent audit entries."""
        from media.whatsapp.db.repo import AuditLogRepo
        return [
            {
                "id": e.id,
                "actor": e.actor,
                "action": e.action,
                "target": e.target,
                "details": e.details,
                "ip_address": e.ip_address,
                "timestamp": e.created_at.isoformat() if e.created_at else None,
            }
            for e in AuditLogRepo.list_recent(limit)
        ]

    def list_by_action(self, action: str, limit: int = 50) -> list:
        """List audit entries for a specific action."""
        from media.whatsapp.db.repo import AuditLogRepo
        return [
            {
                "id": e.id,
                "actor": e.actor,
                "action": e.action,
                "target": e.target,
                "details": e.details,
                "timestamp": e.created_at.isoformat() if e.created_at else None,
            }
            for e in AuditLogRepo.list_by_action(action, limit)
        ]


# Singleton
audit_logger = AuditLogger()
