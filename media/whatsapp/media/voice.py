"""Voice note processing: STT with server + local Whisper fallback.

Uses faster-whisper (CTranslate2-based, GPU/CPU) for local transcription.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
from typing import Optional

import requests

from media.whatsapp.config import settings
from media.whatsapp.core.exceptions import STTError
from media.whatsapp.media.downloader import media_downloader
from media.whatsapp.observability.logging_setup import get_logger
from media.whatsapp.observability.metrics import metrics

logger = get_logger(__name__)

# MIME -> extension map
_EXT_MAP = {
    "audio/ogg": "ogg", "audio/opus": "ogg", "audio/mp3": "mp3",
    "audio/mpeg": "mp3", "audio/m4a": "m4a", "audio/wav": "wav",
    "audio/webm": "webm", "audio/x-m4a": "m4a", "audio/amr": "amr",
    "audio/aac": "aac", "audio/x-aac": "aac",
}

# Lazy-loaded Whisper model (loaded once, reused)
_WHISPER_MODEL = None
_WHISPER_LOCK = threading.Lock()
_WHISPER_LOADED = False


class VoiceProcessor:
    """Voice note transcription with multi-tier fallback."""

    def __init__(self) -> None:
        self._server_url = settings.stt_server_url
        self._timeout = settings.stt_timeout
        self._last_health_check: float = 0.0
        self._server_healthy: bool = False

    def _check_health(self) -> bool:
        """Throttled health check (max once per 30s)."""
        now = time.time()
        if now - self._last_health_check < 30:
            return self._server_healthy
        self._last_health_check = now
        try:
            r = requests.get(f"{self._server_url}/health", timeout=3)
            self._server_healthy = r.ok and r.json().get("status") == "ready"
        except Exception:
            self._server_healthy = False
        return self._server_healthy

    def transcribe(self, page, msg_id: str) -> str:
        """Download and transcribe a voice message. Returns transcript text."""
        raw = media_downloader.download(page, msg_id)
        if not raw or not raw.get("bytes"):
            logger.warning(f"[Voice] No audio bytes for {msg_id}")
            return "[voice message unavailable]"

        mime = (raw.get("mimetype") or "audio/ogg").split(";")[0].strip()
        ext = _EXT_MAP.get(mime, "ogg")
        audio_bytes = raw["bytes"]

        # Tier 1: remote STT server
        if self._check_health():
            text = self._transcribe_remote(audio_bytes, ext, mime)
            if text:
                metrics.inc("stt_success", tier="remote")
                return text

        # Tier 2: local faster-whisper (always on)
        text = self._transcribe_local(audio_bytes)
        if text:
            metrics.inc("stt_success", tier="local_whisper")
            return text

        metrics.inc("stt_failures")
        return "[voice message unavailable]"

    def _transcribe_remote(
        self, audio_bytes: bytes, ext: str, mime: str,
    ) -> Optional[str]:
        """Send audio to remote STT server."""
        for attempt in range(3):
            try:
                files = {"file": (f"audio.{ext}", audio_bytes, mime)}
                data = {"language": "auto", "task": "transcribe"}
                r = requests.post(
                    f"{self._server_url}/transcribe",
                    files=files, data=data, timeout=self._timeout,
                )
                if r.ok:
                    resp = r.json()
                    text = resp.get("text") or resp.get("transcription", "")
                    if text:
                        return text.strip()
                else:
                    logger.warning(
                        f"[STT-Remote] Attempt {attempt+1}: HTTP {r.status_code}"
                    )
            except Exception as e:
                logger.warning(f"[STT-Remote] Attempt {attempt+1}: {e}")
            time.sleep(1.5 * (attempt + 1))
        return None

    def _transcribe_local(self, audio_bytes: bytes) -> Optional[str]:
        """Transcribe locally using faster-whisper (lazy-loaded model)."""
        global _WHISPER_MODEL, _WHISPER_LOADED

        # Load model once (thread-safe)
        if not _WHISPER_LOADED:
            with _WHISPER_LOCK:
                if not _WHISPER_LOADED:
                    logger.info("[STT-Whisper] Loading small model (one-time, ~500MB)...")
                    from faster_whisper import WhisperModel
                    _WHISPER_MODEL = WhisperModel(
                        "small",
                        device="cpu",
                        compute_type="int8",
                        cpu_threads=4,
                        num_workers=1,
                    )
                    _WHISPER_LOADED = True
                    logger.info("[STT-Whisper] Model loaded")

        # Write audio to temp file
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name

            segments, info = _WHISPER_MODEL.transcribe(
                tmp_path,
                beam_size=5,
                vad_filter=True,
                language=None,
            )
            text = " ".join(s.text for s in segments).strip()
            return text or None
        except Exception as e:
            logger.error(f"[STT-Whisper] {e}")
            return None
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass


# Singleton
voice_processor = VoiceProcessor()
