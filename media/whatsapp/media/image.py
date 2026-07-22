"""Image processing: Gemini vision + OCR fallback.

Uses the AI router to pick a vision-capable provider. Each provider handles
its own vision API format internally.
"""
from __future__ import annotations

import base64
import io
from typing import Optional

from media.whatsapp.ai.base import ProviderCapability, registry
from media.whatsapp.ai.router import router
from media.whatsapp.config import settings
from media.whatsapp.media.downloader import media_downloader
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics

logger = get_logger(__name__)

_IMAGE_ANALYSIS_PROMPT = """Analyze this image in detail and extract:
1. Full scene description (people, objects, setting, actions, colors)
2. ALL text visible in the image (preserve exact script and language, do NOT translate)
3. Any numbers, dates, URLs, addresses, phone numbers
4. What the image is communicating or showing
5. Caption context: {caption}

Be thorough and specific."""


class ImageProcessor:
    """Image analysis with multi-provider fallback."""

    def analyze(self, page, msg_id: str, caption: str = "") -> tuple[str, Optional[bytes], str]:
        """Analyze an image. Returns (description, image_bytes, mimetype)."""
        raw = media_downloader.download(page, msg_id)
        if not raw or not raw.get("bytes"):
            logger.warning(f"[Image] No bytes for {msg_id}")
            return ("[Image received but unavailable]", None, "image/jpeg")

        image_bytes = raw["bytes"]
        mime = raw.get("mimetype", "image/jpeg")

        # Try AI vision providers
        description = self._analyze_via_ai(image_bytes, mime, caption)
        if not description:
            description = self._ocr_fallback(image_bytes)

        cap_prefix = f"Caption: {caption}\n" if caption else ""
        content = f"{cap_prefix}[Image Description] {description}"
        metrics.inc("image_processed")
        return (content, image_bytes, mime)

    def _analyze_via_ai(
        self, image_bytes: bytes, mime: str, caption: str,
    ) -> Optional[str]:
        """Try Gemini (best for vision) then OpenAI-compatible providers."""
        prompt = _IMAGE_ANALYSIS_PROMPT.format(caption=caption or "none provided")
        b64 = base64.b64encode(image_bytes).decode()

        providers = router._available(ProviderCapability.VISION)
        for p in providers:
            try:
                text = self._call_provider_vision(p, prompt, b64, mime)
                if text:
                    return text
            except Exception as e:
                if registry.classify_error(e):
                    # Rate limited — set cooldown and skip this provider
                    p_instance_key = getattr(p, "_api_key", "")
                    if p_instance_key:
                        registry.set_cooldown(p_instance_key)
                    logger.warning(f"[Image] {p.name} vision rate-limited: {e}")
                else:
                    logger.warning(f"[Image] {p.name} vision failed: {e}")
                continue
        return None

    def _call_provider_vision(
        self, provider, prompt: str, b64: str, mime: str,
    ) -> Optional[str]:
        """Call a single provider's vision API. Returns text or None."""
        if provider.name == "gemini":
            return self._call_gemini_vision(provider, prompt, b64, mime)
        elif provider.name == "openai":
            return self._call_openai_vision(provider, prompt, b64, mime)
        # Groq doesn't currently support vision in our config
        return None

    def _call_gemini_vision(
        self, provider, prompt: str, b64: str, mime: str,
    ) -> Optional[str]:
        """Call Gemini's vision API — uses Xeno vision model if available."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=provider._api_key)
            model = genai.GenerativeModel(
                settings.xeno_vision_model if "gemini" in settings.xeno_vision_model.lower() else settings.gemini_model
            )
            r = model.generate_content([
                prompt,
                {"mime_type": mime, "data": b64},
            ])
            return (r.text or "").strip() or None
        except Exception as e:
            if registry.classify_error(e):
                registry.set_cooldown(provider._api_key)
            raise

    def _call_openai_vision(
        self, provider, prompt: str, b64: str, mime: str,
    ) -> Optional[str]:
        """Call an OpenAI-compatible vision API — uses Xeno vision model if available."""
        try:
            client = provider._client()
            model = settings.xeno_vision_model if settings.openai_base_url else settings.openai_model
            r = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url",
                         "image_url": {"url": f"data:{mime};base64,{b64}"}},
                    ],
                }],
                temperature=0.3,
            )
            return (r.choices[0].message.content or "").strip() or None
        except Exception as e:
            if registry.classify_error(e):
                registry.set_cooldown(provider._api_key)
            raise

    def _ocr_fallback(self, image_bytes: bytes) -> str:
        """Last-resort OCR via pytesseract."""
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(img)
            return f"[OCR] {text.strip()}" if text.strip() else "[Image: no text detected]"
        except ImportError:
            logger.warning("[Image] pytesseract/Pillow not installed for OCR fallback")
            return "[Image received]"
        except Exception as e:
            logger.warning(f"[Image] OCR failed: {e}")
            return "[Image received]"


# Singleton
image_processor = ImageProcessor()
