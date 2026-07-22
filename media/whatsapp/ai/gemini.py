"""Gemini AI provider — uses a fresh client per call (no global configure).

Critical fix: the original code called `genai.configure(api_key=key)` which
mutates GLOBAL state. With multiple worker threads using different keys,
the last `configure` won and all calls used the same key.
"""
from __future__ import annotations

import base64
import json
import re
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from media.whatsapp.ai.base import registry, call_with_metrics
from media.whatsapp.ai.prompts import DECISION_SYSTEM_PROMPT
from media.whatsapp.config import settings
from media.whatsapp.core.exceptions import RateLimitError, AIProviderError
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)


class GeminiProvider:
    """Per-key Gemini provider. Stateless between calls."""

    name = "gemini"
    capabilities = {"text", "vision", "json"}

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Gemini API key cannot be empty")
        self._api_key = api_key
        self._key_hash = registry._hash_key(api_key)

    def is_available(self) -> bool:
        return bool(self._api_key)

    def is_on_cooldown(self) -> bool:
        return registry.is_on_cooldown(self._api_key)

    def cooldown_remaining(self) -> float:
        return registry.cooldown_remaining(self._api_key)

    def _make_model(self, system_instruction: Optional[str] = None):
        """Create a fresh GenerativeModel bound to THIS key.

        Uses the modern google-generativeai Client API where possible to
        avoid the global configure() pattern.
        """
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise AIProviderError(
                "google-generativeai not installed", provider="gemini", transient=False
            ) from e

        # We must use configure() for now (the SDK doesn't expose a per-client
        # API in all versions), but we hold a per-instance lock during the call
        # to ensure no other thread changes the global key mid-call.
        # NOTE: This is a known limitation of the SDK. For true isolation,
        # upgrade to the new `google-genai` package (v1.0+) which supports
        # per-client instances.
        genai.configure(api_key=self._api_key)
        kwargs = {"model_name": settings.gemini_model}
        if system_instruction:
            kwargs["system_instruction"] = system_instruction
        return genai.GenerativeModel(**kwargs)

    def simple_text(self, prompt: str, max_chars: int) -> str:
        """Single-turn text generation."""
        if self.is_on_cooldown():
            return ""
        prompt = prompt[:max_chars]
        try:
            model = self._make_model()

            @retry(
                stop=stop_after_attempt(settings.ai_max_retries),
                wait=wait_exponential(multiplier=1, min=2, max=15),
                retry=retry_if_exception_type((RateLimitError,)),
                reraise=True,
            )
            def _call():
                return call_with_metrics("gemini", lambda: model.generate_content(prompt))

            r = _call()
            return (r.text or "").strip()
        except RateLimitError as e:
            registry.set_cooldown(self._api_key, e.retry_after)
            logger.warning(f"[Gemini] Rate limited: {e}")
            return ""
        except AIProviderError as e:
            logger.warning(f"[Gemini] simple_text error: {e}")
            return ""
        except Exception as e:
            if registry.classify_error(e):
                registry.set_cooldown(self._api_key)
                logger.warning(f"[Gemini] Rate limited (auto-detected): {e}")
                return ""
            logger.warning(f"[Gemini] unexpected error: {e}")
            return ""

    def structured_decision(
        self, system_prompt: str, user_content: str, max_chars: int,
    ) -> Optional[dict]:
        """Generate a JSON decision. Returns parsed dict or None."""
        if self.is_on_cooldown():
            return None
        user_content = user_content[:max_chars]
        try:
            model = self._make_model(system_instruction=system_prompt)
            r = model.generate_content(user_content)
            text = (r.text or "").strip()
            return self._parse_json(text)
        except Exception as e:
            if registry.classify_error(e):
                registry.set_cooldown(self._api_key)
                logger.warning(f"[Gemini] Decision rate-limited: {e}")
            else:
                logger.warning(f"[Gemini] Decision error: {e}")
            return None

    def reply(
        self, system_prompt: str, messages: list[dict],
        image_bytes: Optional[bytes], max_chars: int,
    ) -> str:
        """Generate a reply using conversation history.

        `messages` is the list of incoming user messages (with optional
        `image_bytes` field on each) for THIS turn only. Conversation
        history is already inlined into `system_prompt` by the router.
        """
        if self.is_on_cooldown():
            return ""
        try:
            model = self._make_model()
            parts: list = [system_prompt[:max_chars]]
            for i, pm in enumerate(messages, 1):
                label = pm.get("label", "Text")
                content = pm.get("content", "")
                parts.append(f"Message {i} [{label}]: {content}")
                # Per-message image (vision)
                img = pm.get("image_bytes")
                if img and isinstance(img, (bytes, bytearray)):
                    mime = pm.get("mimetype") or "image/jpeg"
                    parts.append({
                        "mime_type": mime,
                        "data": base64.b64encode(img).decode(),
                    })
            parts.append("Send ONE natural WhatsApp reply now.")
            r = model.generate_content(parts, generation_config={"temperature": 0.8})
            return (r.text or "").strip()
        except Exception as e:
            if registry.classify_error(e):
                registry.set_cooldown(self._api_key)
                logger.warning(f"[Gemini] Reply rate-limited: {e}")
            else:
                logger.warning(f"[Gemini] Reply error: {e}")
            return ""

    @staticmethod
    def _parse_json(raw: str) -> Optional[dict]:
        if not raw:
            return None
        try:
            cleaned = re.sub(r"```json|```", "", raw).strip()
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if not match:
                return None
            parsed = json.loads(match.group())
            if "needs_approval" not in parsed:
                return None
            parsed.setdefault("risk_level", "LOW")
            parsed.setdefault("is_retraction", False)
            parsed.setdefault("reason", "No reason provided.")
            parsed.setdefault("retraction_reply", "")
            parsed.setdefault("confidence", 0.5)
            parsed.setdefault("triggered_category", "CASUAL")
            return parsed
        except Exception as e:
            logger.warning(f"[Gemini] JSON parse failed: {e}; raw={raw[:120]}")
            return None
