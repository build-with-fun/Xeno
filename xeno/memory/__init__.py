from xeno.memory.context_memory import ContextMemory
from xeno.memory.vector_memory import VectorMemory
from xeno.memory.realtime_memory import RealtimeMemory
from xeno.memory.advanced import AdvancedMemoryManager, MemoryType, MemoryEntry
from xeno.config import XenoConfig


class MemoryManager:
    """Unified interface for all memory types."""

    def __init__(self, config: XenoConfig, session_id: str = "default"):
        self.config = config
        self.context = ContextMemory(config)
        self.vector = VectorMemory(config)
        self.realtime = RealtimeMemory(config, session_id)
        self.advanced = AdvancedMemoryManager(config.data_dir / "memory")

    def store_fact(self, key: str, value: str) -> str:
        return self.context.store(key, value, "facts")

    def retrieve_fact(self, key: str) -> str:
        return self.context.retrieve(key, "facts")

    def search_memory(self, query: str) -> str:
        context_results = self.context.search(query)
        vector_results = self.vector.search(query, n_results=3)
        return f"=== Context Memory ===\n{context_results}\n\n=== Vector Memory ===\n{vector_results}"

    def store_knowledge(self, content: str, metadata: dict | None = None) -> str:
        return self.vector.store(content, metadata)

    def search_knowledge(self, query: str, n: int = 5) -> str:
        return self.vector.search(query, n)

    def get_full_context(self) -> str:
        parts = []
        ctx = self.context.get_context_string()
        if ctx and "No context" not in ctx:
            parts.append(f"=== User Context ===\n{ctx}")
        history = self.realtime.get_context_string(last_n=10)
        if history:
            parts.append(f"=== Recent Conversation ===\n{history}")
        return "\n\n".join(parts) if parts else "No context available."

    def update_fact(self, key: str, value: str) -> str:
        return self.context.update(key, value, "facts")

    def list_facts(self) -> str:
        return self.context.list_all()

    def clear_all(self) -> str:
        """Clear ALL memory — context, vector, and temporal KG."""
        results = []
        try:
            self.context._data = {"facts": {}, "preferences": {}, "conversation_state": {}}
            self.context._save()
            results.append("context cleared")
        except Exception as e:
            results.append(f"context error: {e}")
        try:
            self.vector.clear()
            results.append("vector cleared")
        except Exception as e:
            results.append(f"vector error: {e}")
        try:
            from xeno.memory.temporal import get_temporal_kg
            kg = get_temporal_kg()
            if kg:
                kg.clear()
                results.append("temporal kg cleared")
        except Exception as e:
            results.append(f"temporal error: {e}")
        return "Memory cleared: " + "; ".join(results)
