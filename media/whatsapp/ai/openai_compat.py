"""OpenAI-compatible provider.

Works with OpenAI, Azure OpenAI, Together, Anyscale, Ollama, vLLM, LM Studio,
and any other service that implements the OpenAI Chat Completions API.
"""
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


class OpenAICompatProvider:
    """Per-key OpenAI-compatible provider."""

    name = "openai"
    capabilities = {"text", "vision", "json"}

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OpenAI API key cannot be empty")
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
            from openai import OpenAI
        except ImportError as e:
            raise AIProviderError(
                "openai not installed", provider="openai", transient=False
            ) from e
        return OpenAI(
            api_key=self._api_key,
            base_url=settings.openai_base_url,
            timeout=settings.ai_request_timeout,
        )

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
                return call_with_metrics("openai", lambda: client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                ))

            r = _call()
            return (r.choices[0].message.content or "").strip()
        except RateLimitError as e:
            registry.set_cooldown(self._api_key, e.retry_after)
            logger.warning(f"[OpenAI] Rate limited: {e}")
            return ""
        except AIProviderError as e:
            logger.warning(f"[OpenAI] simple_text error: {e}")
            return ""
        except Exception as e:
            if registry.classify_error(e):
                registry.set_cooldown(self._api_key)
                logger.warning(f"[OpenAI] Rate limited (auto-detected): {e}")
                return ""
            logger.warning(f"[OpenAI] unexpected error: {e}")
            return ""

    def structured_decision(
        self, system_prompt: str, user_content: str, max_chars: int,
    ) -> Optional[dict]:
        if self.is_on_cooldown():
            return None
        user_content = user_content[:max_chars]
        client = self._client()
        # Try with response_format first (OpenAI-compatible), fallback to plain text
        for use_json_mode in (True, False):
            try:
                kwargs = dict(
                    model=settings.openai_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=0.1,
                )
                if use_json_mode:
                    kwargs["response_format"] = {"type": "json_object"}
                r = client.chat.completions.create(**kwargs)
                text = (r.choices[0].message.content or "").strip()
                parsed = self._parse_json(text)
                if parsed:
                    return parsed
            except Exception as e:
                if use_json_mode and ("not supported" in str(e).lower() or "invalid" in str(e).lower()):
                    logger.debug(f"[OpenAI] JSON mode not supported, falling back: {e}")
                    continue
                if registry.classify_error(e):
                    registry.set_cooldown(self._api_key)
                    logger.warning(f"[OpenAI] Decision rate-limited: {e}")
                else:
                    logger.warning(f"[OpenAI] Decision error: {e}")
                return None
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
            for pm in messages:
                content = pm.get("content", "")
                img = pm.get("image_bytes")
                if img and isinstance(img, (bytes, bytearray)):
                    import base64
                    mime = pm.get("mimetype") or "image/jpeg"
                    b64 = base64.b64encode(img).decode()
                    msgs.append({
                        "role": "user",
                        "content": [
                            {"type": "text", "text": f"[{pm.get('label','Image')}]: {content}"},
                            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                        ],
                    })
                else:
                    msgs.append({"role": "user", "content": f"[{pm.get('label','Text')}]: {content}"})
            r = client.chat.completions.create(
                model=settings.openai_model,
                messages=msgs,
                temperature=0.8,
            )
            return (r.choices[0].message.content or "").strip()
        except Exception as e:
            if registry.classify_error(e):
                registry.set_cooldown(self._api_key)
                logger.warning(f"[OpenAI] Reply rate-limited: {e}")
            else:
                logger.warning(f"[OpenAI] Reply error: {e}")
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
            logger.warning(f"[OpenAI] JSON parse failed: {e}; raw={raw[:120]}")
            return None
