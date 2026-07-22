"""Ollama Embedding Function for ChromaDB.

Uses a local Ollama model to generate embeddings.
Falls back to a zero-vector if Ollama is down so the system never crashes.

NOTE: Ollama's /api/embed endpoint may return 400 under concurrent load or
when the model is busy. We serialize calls with a lock and add retry logic.
If all retries fail, we return zero vectors so the system never crashes.
"""

from __future__ import annotations

import hashlib
import logging
import struct
import threading
import time
from typing import Any, Dict, List

import httpx

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3-embedding:8b"
_DIM = 4096


def _hash_fallback(text: str, dim: int = _DIM) -> list[float]:
    """Deterministic hash-based pseudo-embedding when Ollama is unavailable."""
    h = hashlib.sha512((text or "empty").encode("utf-8")).digest()
    values = list(struct.unpack(f"{len(h)//8}d", h))
    # Pad or trim to desired dim
    while len(values) < dim:
        values.extend(struct.unpack(f"{min(8, dim-len(values))}d", h[:min(8, dim-len(values))*8]))
    return values[:dim]


class OllamaEmbeddingFunction:
    """ChromaDB-compatible embedding function backed by Ollama."""

    def __init__(self, model: str = DEFAULT_MODEL, base_url: str = OLLAMA_BASE_URL):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self._dim: int | None = None
        self._lock = threading.Lock()
        self._fail_count = 0
        self._last_fail = 0.0

    def _embed_one(self, text: str, retries: int = 2) -> list[float] | None:
        """Embed a single string with retry. Returns None on failure."""
        dim = self._dim or _DIM
        clean = (text or "").strip()
        if not clean:
            clean = "empty"

        # Skip if recently failed (cooldown 30s)
        if self._fail_count > 3 and (time.time() - self._last_fail) < 30:
            return None

        for attempt in range(retries):
            try:
                resp = httpx.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": clean},
                    timeout=60.0,
                )
                if resp.status_code == 200:
                    vec = resp.json().get("embeddings", [[]])[0]
                    if vec:
                        if self._dim is None:
                            self._dim = len(vec)
                        self._fail_count = 0
                        return vec
                logger.debug(f"Embed attempt {attempt+1}: status={resp.status_code}")
            except Exception as e:
                logger.debug(f"Embed attempt {attempt+1}: {e}")
            if attempt < retries - 1:
                time.sleep(1.0 * (attempt + 1))

        self._fail_count += 1
        self._last_fail = time.time()
        return None

    def __call__(self, input: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts, one by one, serialized."""
        dim = self._dim or _DIM
        if not input:
            return []
        embeddings: list[list[float]] = []
        with self._lock:
            for text in input:
                vec = self._embed_one(text)
                if vec is None:
                    vec = _hash_fallback(text, dim)
                embeddings.append(vec)
        return embeddings

    def embed_query(self, input: list[str], **kwargs) -> list[list[float]]:
        return self(input)

    def embed_documents(self, input: list[str], **kwargs) -> list[list[float]]:
        return self(input)

    @staticmethod
    def name() -> str:
        return "ollama"

    def get_config(self) -> Dict[str, Any]:
        return {"model": self.model, "base_url": self.base_url}

    @staticmethod
    def build_from_config(config: Dict[str, Any]) -> "OllamaEmbeddingFunction":
        return OllamaEmbeddingFunction(
            model=config.get("model", DEFAULT_MODEL),
            base_url=config.get("base_url", OLLAMA_BASE_URL),
        )

    @property
    def dimensions(self) -> int | None:
        return self._dim


def get_embedding_function(
    model: str | None = None,
    base_url: str | None = None,
) -> OllamaEmbeddingFunction:
    """Get an Ollama embedding function."""
    import os
    model = model or os.environ.get("XENO_EMBEDDING_MODEL", DEFAULT_MODEL)
    base_url = base_url or os.environ.get("OLLAMA_BASE_URL", OLLAMA_BASE_URL)
    return OllamaEmbeddingFunction(model=model, base_url=base_url)
