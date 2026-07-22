import json
from pathlib import Path
from datetime import datetime
from typing import Any

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

from xeno.config import XenoConfig


class VectorMemory:
    """ChromaDB-backed vector memory for long-term semantic search."""

    def __init__(self, config: XenoConfig):
        self.config = config
        self.db_path = str(config.vector_db_dir)
        self._client = None
        self._collection = None

    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        if not CHROMA_AVAILABLE:
            raise RuntimeError("chromadb not installed. Run: pip install chromadb")
        from xeno.memory.ollama_embed import get_embedding_function
        ef = get_embedding_function()
        self._client = chromadb.PersistentClient(path=self.db_path, settings=ChromaSettings(anonymized_telemetry=False))
        self._collection = self._client.get_or_create_collection(
            name="xeno_memory",
            metadata={"hnsw:space": "cosine"},
            embedding_function=ef,
        )
        return self._collection

    def store(self, content: str, metadata: dict[str, Any] | None = None) -> str:
        collection = self._get_collection()
        doc_id = f"doc_{collection.count() + 1}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        meta = metadata or {}
        meta["timestamp"] = datetime.now().isoformat()
        meta["content_preview"] = content[:200]
        collection.add(documents=[content], metadatas=[meta], ids=[doc_id])
        return f"Stored document {doc_id} ({len(content)} chars)"

    def search(self, query: str, n_results: int = 5) -> str:
        collection = self._get_collection()
        if collection.count() == 0:
            return "No documents in vector memory yet."
        results = collection.query(query_texts=[query], n_results=min(n_results, collection.count()))
        if not results["documents"][0]:
            return f"No results found for '{query}'"
        output = []
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            dist = results["distances"][0][i] if results["distances"] else "N/A"
            output.append(f"[{i+1}] (score: {dist})\n{doc[:500]}")
        return "\n\n".join(output)

    def delete(self, doc_id: str) -> str:
        collection = self._get_collection()
        try:
            collection.delete(ids=[doc_id])
            return f"Deleted document {doc_id}"
        except Exception as e:
            return f"Error deleting: {str(e)}"

    def update(self, doc_id: str, content: str, metadata: dict[str, Any] | None = None) -> str:
        collection = self._get_collection()
        meta = metadata or {}
        meta["timestamp"] = datetime.now().isoformat()
        meta["content_preview"] = content[:200]
        try:
            collection.update(documents=[content], metadatas=[meta], ids=[doc_id])
            return f"Updated document {doc_id}"
        except Exception:
            collection.add(documents=[content], metadatas=[meta], ids=[doc_id])
            return f"Created document {doc_id} (was not found for update)"

    def count(self) -> int:
        return self._get_collection().count()

    def list_all(self, limit: int = 20) -> str:
        collection = self._get_collection()
        if collection.count() == 0:
            return "No documents in vector memory."
        results = collection.get(limit=min(limit, collection.count()))
        output = []
        for i, doc in enumerate(results["documents"]):
            doc_id = results["ids"][i]
            meta = results["metadatas"][i] if results["metadatas"] else {}
            preview = meta.get("content_preview", doc[:100])
            output.append(f"[{doc_id}] {preview}")
        return "\n".join(output)
