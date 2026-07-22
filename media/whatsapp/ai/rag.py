"""RAG (Retrieval-Augmented Generation) knowledge base.

Allows the bot to answer factual questions from a knowledge base of
documents (FAQs, policies, product info, etc.).

How it works:
1. Documents are ingested (split into chunks, stored in DB)
2. When a message comes in, we search for relevant chunks
3. Relevant chunks are injected into the AI prompt as context
4. The AI generates a reply using both persona + knowledge context

Currently uses simple text search (ILIKE). For production scale,
upgrade to vector embeddings + cosine similarity.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Optional

from media.whatsapp.observability.logging_setup import get_logger

logger = get_logger(__name__)

# Default chunk size (characters) and overlap
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


class KnowledgeBase:
    """RAG knowledge base for factual answers."""

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def ingest_file(self, file_path: str | Path) -> int:
        """Ingest a text file into the knowledge base. Returns chunk count."""
        path = Path(file_path)
        if not path.exists():
            logger.error(f"[RAG] File not found: {path}")
            return 0

        # Read and chunk
        text = path.read_text(encoding="utf-8", errors="ignore")
        source = path.name
        return self._ingest_text(source, text)

    def ingest_text(self, source: str, text: str) -> int:
        """Ingest arbitrary text with a given source name."""
        return self._ingest_text(source, text)

    def _ingest_text(self, source: str, text: str) -> int:
        """Split text into chunks and store in DB."""
        chunks = self._split_text(text)
        if not chunks:
            return 0

        # Remove existing chunks for this source (re-ingestion)
        from media.whatsapp.db.repo import KnowledgeRepo
        KnowledgeRepo.delete_source(source)

        for i, chunk in enumerate(chunks):
            KnowledgeRepo.add_chunk(
                source=source, chunk_index=i, text=chunk,
                metadata={"char_count": len(chunk)},
            )

        logger.info(f"[RAG] Ingested {len(chunks)} chunks from '{source}'")
        return len(chunks)

    def _split_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks."""
        if len(text) <= self.chunk_size:
            return [text] if text.strip() else []

        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]

            # Try to break at a sentence/paragraph boundary
            if end < len(text):
                # Look for the last period/newline before the end
                for sep in ["\n\n", "\n", ". ", "? ", "! "]:
                    last_sep = chunk.rfind(sep)
                    if last_sep > self.chunk_size // 2:
                        end = start + last_sep + len(sep)
                        chunk = text[start:end]
                        break

            chunks.append(chunk.strip())
            start = end - self.overlap
            if start >= len(text):
                break

        return [c for c in chunks if c]

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """Search the knowledge base for relevant chunks.

        Returns list of {"source": str, "text": str, "score": float}.
        """
        from media.whatsapp.db.repo import KnowledgeRepo

        # Simple text search — split query into terms and score by match count
        terms = [t for t in re.split(r"\s+", query) if len(t) > 2]
        if not terms:
            return []

        # Get all chunks matching any term
        results = []
        seen_ids = set()
        for term in terms[:5]:  # Limit to first 5 terms
            chunks = KnowledgeRepo.search(term, limit=10)
            for chunk in chunks:
                if chunk.id in seen_ids:
                    continue
                seen_ids.add(chunk.id)
                # Score: how many query terms appear in the chunk
                chunk_lower = chunk.text.lower()
                score = sum(1 for t in terms if t.lower() in chunk_lower)
                results.append({
                    "source": chunk.source,
                    "text": chunk.text,
                    "score": score,
                })

        # Sort by score and return top N
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:limit]

    def build_context(self, query: str, max_chars: int = 3000) -> str:
        """Build a context string from relevant knowledge chunks.

        Returns an empty string if no relevant chunks found.
        """
        results = self.search(query, limit=3)
        if not results:
            return ""

        parts = []
        total = 0
        for r in results:
            chunk_text = r["text"][:max_chars - total]
            if not chunk_text:
                break
            parts.append(f"[From {r['source']}]\n{chunk_text}")
            total += len(chunk_text) + 20  # +20 for the header

        if not parts:
            return ""
        return "KNOWLEDGE BASE CONTEXT (use this to inform your reply):\n" + "\n\n".join(parts)

    def list_sources(self) -> list[str]:
        """List all ingested sources."""
        from media.whatsapp.db.repo import KnowledgeRepo
        return KnowledgeRepo.list_sources()

    def delete_source(self, source: str) -> int:
        """Delete a source and all its chunks. Returns deleted count."""
        from media.whatsapp.db.repo import KnowledgeRepo
        return KnowledgeRepo.delete_source(source)

    def ingest_directory(self, dir_path: str | Path) -> dict:
        """Ingest all text files in a directory. Returns {filename: chunk_count}."""
        path = Path(dir_path)
        if not path.is_dir():
            logger.error(f"[RAG] Not a directory: {path}")
            return {}

        results = {}
        for f in path.iterdir():
            if f.suffix.lower() in (".txt", ".md", ".json", ".csv"):
                count = self.ingest_file(f)
                results[f.name] = count
        return results


# Singleton
knowledge_base = KnowledgeBase()
