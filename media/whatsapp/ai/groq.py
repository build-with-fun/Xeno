"""Groq AI provider — uses a per-call Groq client (no global state)."""
from __future__ import annotations

import json
import re
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from media.whatsapp.ai.base import registry, call_with_metrics
from media.whatsapp.config import settings
from media.whatsapp.core.exceptions import RateLimitError, AIProviderError
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)


class GroqProvider:
    """Per-key Groq provider. Each call creates a fresh `Groq` client."""

    name = "groq"
    capabilities = {"text", "json"}

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Groq API key cannot be empty")
        self._api_key = api_key
        self._key_hash = registry._hash_key(api_key)

    def is_available(self) -> bool:
        return bool(self._api_key)

    def is_on_cooldown(self) -> bool:
        return registry.is_on_cooldown(self._api_key)

    def cooldown_remaining(self) -> float:
        return registry.cooldown_remaining(self._api_key)

    def _client(self):
        try:
            from media.whatsapp.ai.groq import Groq
        except ImportError as e:
            raise AIProviderError(
                "groq not installed", provider="groq", transient=False
            ) from e
        # Each call gets a fresh client bound to THIS key — no global state.
        return Groq(api_key=self._api_key, timeout=settings.ai_request_timeout)

    def simple_text(self, prompt: str, max_chars: int) -> str:
        if self.is_on_cooldown():
            return ""
        prompt = prompt[:max_chars]
        try:

            @retry(
                stop=stop_after_attempt(settings.ai_max_retries),
                wait=wait_exponential(multiplier=1, min=2, max=15),
                retry=retry_if_exception_type((RateLimitError,)),
                reraise=True,
            )
            def _call():
                client = self._client()
                return call_with_metrics("groq", lambda: client.chat.completions.create(
                    model=settings.groq_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                ))

            r = _call()
            return (r.choices[0].message.content or "").strip()
        except RateLimitError as e:
            registry.set_cooldown(self._api_key, e.retry_after)
            logger.warning(f"[Groq] Rate limited: {e}")
            return ""
        except AIProviderError as e:
            logger.warning(f"[Groq] simple_text error: {e}")
            return ""
        except Exception as e:
            if registry.classify_error(e):
                registry.set_cooldown(self._api_key)
                logger.warning(f"[Groq] Rate limited (auto-detected): {e}")
                return ""
            logger.warning(f"[Groq] unexpected error: {e}")
            return ""

    def structured_decision(
        self, system_prompt: str, user_content: str, max_chars: int,
    ) -> Optional[dict]:
        if self.is_on_cooldown():
            return None
        user_content = user_content[:max_chars]
        try:
            client = self._client()
            r = client.chat.completions.create(
                model=settings.groq_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            text = (r.choices[0].message.content or "").strip()
            return self._parse_json(text)
        except Exception as e:
            if registry.classify_error(e):
                registry.set_cooldown(self._api_key)
                logger.warning(f"[Groq] Decision rate-limited: {e}")
            else:
                logger.warning(f"[Groq] Decision error: {e}")
            return None

    def reply(
        self, system_prompt: str, messages: list[dict],
        image_bytes: Optional[bytes], max_chars: int,
    ) -> str:
        if self.is_on_cooldown():
            return ""
        try:
            client = self._client()
            msgs: list[dict] = [{"role": "system", "content": system_prompt[:max_chars]}]
            # Combine all incoming user messages into a single user turn
            combined = "\n".join(
                f"[{pm.get('label','Text')}]: {pm.get('content','')}"
                for pm in messages
            )[:max_chars]
            msgs.append({"role": "user", "content": combined})
            r = client.chat.completions.create(
                model=settings.groq_model,
                messages=msgs,
                temperature=0.8,
            )
            return (r.choices[0].message.content or "").strip()
        except Exception as e:
            if registry.classify_error(e):
                registry.set_cooldown(self._api_key)
                logger.warning(f"[Groq] Reply rate-limited: {e}")
            else:
                logger.warning(f"[Groq] Reply error: {e}")
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
            logger.warning(f"[Groq] JSON parse failed: {e}; raw={raw[:120]}")
            return None
