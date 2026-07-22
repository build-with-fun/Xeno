"""Contact filter — allowlist/blocklist for selective auto-reply.

Allows the main agent to control which contacts the WhatsApp bot replies to:
- "ans my all whatsapp chat from kamran haider only" → set mode=allowlist
- "ans everyone except ms hela and rago" → set mode=blocklist
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from media.whatsapp.config import settings

logger = logging.getLogger(__name__)


class ContactFilter:
    """Controls which contacts the bot auto-replies to."""

    MODE_ALL = "all"
    MODE_ALLOWLIST = "allowlist"
    MODE_BLOCKLIST = "blocklist"

    def __init__(self, state_path: Optional[Path] = None):
        self._state_path = state_path or settings.data_dir / "contact_filter.json"
        self._mode: str = self.MODE_ALL
        self._contacts: list[str] = []
        self._load()

    # ── Public API ───────────────────────────────────────────────────────────

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def contacts(self) -> list[str]:
        return list(self._contacts)

    def set_filter(self, mode: str, contacts: Optional[list[str]] = None) -> str:
        """Set the filter mode and optionally a list of contact names.
        
        Modes:
          "all"       — reply to all contacts (no filtering).
          "allowlist" — ONLY reply to the specified contacts.
          "blocklist" — reply to EVERYONE EXCEPT the specified contacts.
        """
        mode = mode.lower().strip()
        if mode not in (self.MODE_ALL, self.MODE_ALLOWLIST, self.MODE_BLOCKLIST):
            return f"Invalid mode '{mode}'. Use: all, allowlist, or blocklist."

        self._mode = mode
        self._contacts = [c.strip() for c in (contacts or []) if c.strip()]
        self._save()

        if mode == self.MODE_ALL:
            return "WhatsApp filter: replying to ALL contacts."
        elif mode == self.MODE_ALLOWLIST:
            names = ", ".join(self._contacts) if self._contacts else "(none)"
            return f"WhatsApp filter: ONLY replying to: {names}"
        else:  # blocklist
            names = ", ".join(self._contacts) if self._contacts else "(none)"
            return f"WhatsApp filter: replying to EVERYONE except: {names}"

    def is_allowed(self, contact_name: str) -> bool:
        """Check whether a contact is allowed through the filter."""
        if self._mode == self.MODE_ALL:
            return True

        lower_name = contact_name.lower().strip()

        if self._mode == self.MODE_ALLOWLIST:
            return any(c.lower() == lower_name for c in self._contacts)

        if self._mode == self.MODE_BLOCKLIST:
            return not any(c.lower() == lower_name for c in self._contacts)

        return True

    def get_status(self) -> dict:
        return {
            "mode": self._mode,
            "contacts": list(self._contacts),
            "is_filtering": self._mode != self.MODE_ALL,
        }

    def reset(self) -> str:
        """Reset to default — reply to all contacts."""
        return self.set_filter(self.MODE_ALL)

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            if self._state_path.exists():
                data = json.loads(self._state_path.read_text(encoding="utf-8"))
                self._mode = data.get("mode", self.MODE_ALL)
                self._contacts = data.get("contacts", [])
                logger.info(f"[Filter] Loaded: mode={self._mode}, {len(self._contacts)} contacts")
        except Exception as e:
            logger.warning(f"[Filter] Load failed (using defaults): {e}")

    def _save(self) -> None:
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(json.dumps({
                "mode": self._mode,
                "contacts": self._contacts,
            }, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"[Filter] Save failed: {e}")


# Singleton
contact_filter = ContactFilter()
