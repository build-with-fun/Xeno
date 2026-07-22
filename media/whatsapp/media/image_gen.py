from __future__ import annotations

import base64
import io
import time
from typing import Optional

from media.whatsapp.config import settings
from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)


class ImageGenerator:
    """Generates images using Google Gemini Image models.

    Tracks per-key rate limit cooldowns to avoid retrying exhausted keys.
    """

    def __init__(self):
        self._cooldowns: dict[str, float] = {}  # api_key -> cooldown_until (epoch)

    def _is_key_available(self, api_key: str) -> bool:
        now = time.time()
        cooldown = self._cooldowns.get(api_key, 0)
        if now < cooldown:
            remaining = int(cooldown - now)
            logger.warning(
                f"[ImageGen] Key {api_key[:8]}... in cooldown for {remaining}s"
            )
            return False
        return True

    def _mark_key_cooldown(self, api_key: str, duration: int = 300):
        self._cooldowns[api_key] = time.time() + duration
        logger.warning(
            f"[ImageGen] Key {api_key[:8]}... rate-limited — cooldown {duration}s"
        )

    def generate(self, prompt: str, api_key: str) -> tuple[bytes, str]:
        """Generate an image from a text prompt.

        Raises:
            ValueError: If no image was returned by the model.
            RuntimeError: If the key is in cooldown.
            Exception: From the genai SDK on API errors.
        """
        if not self._is_key_available(api_key):
            raise RuntimeError(f"API key {api_key[:8]}... is in cooldown")

        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        try:
            response = client.models.generate_content(
                model=settings.gemini_image_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                ),
            )
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str:
                self._mark_key_cooldown(api_key)
            raise

        for part in response.candidates[0].content.parts:
            if part.inline_data:
                mime = part.inline_data.mime_type or "image/png"
                logger.info(
                    f"[ImageGen] Generated {len(part.inline_data.data):,} bytes ({mime})"
                )
                return (part.inline_data.data, mime)

        raise ValueError("Gemini returned no image data in the response")

    def get_available_key(self, keys: list[str]) -> Optional[str]:
        """Return the first key not in cooldown, or None."""
        for k in keys:
            if k and self._is_key_available(k):
                return k
        return None

    def any_key_available(self, keys: list[str]) -> bool:
        """Check if any key is not in cooldown."""
        return any(k and self._is_key_available(k) for k in keys)


image_generator = ImageGenerator()
