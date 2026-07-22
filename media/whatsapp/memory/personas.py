"""Persona management with per-contact overrides and hot-reload."""
from __future__ import annotations

import os
import threading
from typing import Optional

from media.whatsapp.core.types import Persona
from media.whatsapp.memory.store import store
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.utils.text import safe_filename

logger = get_logger(__name__)

_DEFAULT_GLOBAL_PERSONA = Persona(
    name="Alex",
    age=25,
    language="English",
    style="casual",
    system_prompt_extra=(
        "You are a real person texting on WhatsApp — NOT an AI. "
        "Match the energy of whoever is texting you."
    ),
    fallback_reply="Hey! Talk later :)",
)


class PersonaManager:
    """Manages global and per-contact personas with mtime-based caching."""

    COLLECTION = "personas"
    GLOBAL_KEY = "_global"

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, Persona]] = {}
        self._lock = threading.RLock()
        self._ensure_global()

    def _ensure_global(self) -> None:
        existing = store.read(self.COLLECTION, self.GLOBAL_KEY)
        if existing is None:
            store.write(self.COLLECTION, self.GLOBAL_KEY, _DEFAULT_GLOBAL_PERSONA.to_dict())
            logger.info("[Persona] Created default global persona")

    def get(self, contact: Optional[str] = None) -> Persona:
        """Return the effective persona for a contact.

        Merges global persona with per-contact overrides (contact wins).
        """
        # Global persona (always loaded fresh if file changed)
        global_persona = self._load_with_cache(self.GLOBAL_KEY, _DEFAULT_GLOBAL_PERSONA)
        if not contact:
            return global_persona

        contact_key = safe_filename(contact)
        contact_persona = self._load_with_cache(contact_key, None)
        if contact_persona is None:
            return global_persona

        # Merge: start from global, override with contact-specific fields
        merged = Persona(
            name=contact_persona.name or global_persona.name,
            age=contact_persona.age or global_persona.age,
            language=contact_persona.language or global_persona.language,
            style=contact_persona.style or global_persona.style,
            system_prompt_extra=(
                contact_persona.system_prompt_extra
                if contact_persona.system_prompt_extra
                else global_persona.system_prompt_extra
            ),
            fallback_reply=(
                contact_persona.fallback_reply
                if contact_persona.fallback_reply
                else global_persona.fallback_reply
            ),
        )
        return merged

    def set_global(self, persona: Persona) -> None:
        store.write(self.COLLECTION, self.GLOBAL_KEY, persona.to_dict())
        with self._lock:
            self._cache.pop(self.GLOBAL_KEY, None)

    def set_contact(self, contact: str, persona: Persona) -> None:
        key = safe_filename(contact)
        store.write(self.COLLECTION, key, persona.to_dict())
        with self._lock:
            self._cache.pop(key, None)

    def _load_with_cache(self, key: str, default: Optional[Persona]) -> Optional[Persona]:
        path = store.path_for(self.COLLECTION, key)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return default
        with self._lock:
            cached = self._cache.get(key)
            if cached and cached[0] == mtime:
                return cached[1]
        data = store.read(self.COLLECTION, key)
        if data is None:
            return default
        persona = Persona.from_dict(data)
        with self._lock:
            self._cache[key] = (mtime, persona)
        return persona


# Singleton
persona_manager = PersonaManager()
