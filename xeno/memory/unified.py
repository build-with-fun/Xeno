"""Unified memory manager — single write/read entry point."""
from __future__ import annotations
import asyncio, logging
from typing import Any, Optional
from xeno.memory.context_memory import ContextMemory
from xeno.memory.vector_memory import VectorMemory
from xeno.memory.realtime_memory import RealtimeMemory
from xeno.memory.advanced import AdvancedMemoryManager
from xeno.memory.reconcile import MemoryReconciler, MemoryTier
from xeno.memory.reranker import HybridRetriever, HeuristicReranker, RetrievalResult
from xeno.memory.forgetting import ForgettingEngine
from xeno.memory.sleep import MemorySleepCycle
from xeno.config import XenoConfig
logger = logging.getLogger(__name__)

class UnifiedMemoryManager:
    def __init__(self, config, session_id="default", llm=None):
        self.config = config; self.session_id = session_id; self.llm = llm
        self.context = ContextMemory(config)
        self.vector = VectorMemory(config)
        self.realtime = RealtimeMemory(config, session_id)
        self.advanced = AdvancedMemoryManager(config.data_dir / "memory")
        self.reconciler = MemoryReconciler(data_dir=config.data_dir / "memory")
        self._register_backends()
        self.reranker = HeuristicReranker()
        self.hybrid = HybridRetriever(
            vector_fn=self._vector_retrieve, bm25_fn=self._bm25_retrieve,
            rerank_fn=self.reranker)
        self.forgetting = ForgettingEngine()
        self.sleep = MemorySleepCycle(config.data_dir/"memory", self, reconciler=self.reconciler)
    def _register_backends(self):
        self.reconciler.register_backend(MemoryTier.SEMANTIC, self.advanced.semantic)
        self.reconciler.register_backend(MemoryTier.EPISODIC, self.advanced.episodic)
        self.reconciler.register_backend(MemoryTier.WORKING, self.advanced.working)
    def _vector_retrieve(self, q, n):
        try:
            raw = self.vector.search(q, n_results=n)
            out = []
            if isinstance(raw, str): return out
            for item in (raw if isinstance(raw, list) else []):
                if isinstance(item, dict):
                    out.append(RetrievalResult(id=item.get("id",""), content=item.get("content",item.get("document","")),
                              score=item.get("score",0.5), source="vector"))
                elif hasattr(item, "id"):
                    out.append(RetrievalResult(id=item.id, content=item.content, score=getattr(item,"score",0.5), source="vector"))
            return out
        except: return []
    def _bm25_retrieve(self, q, n):
        try:
            results = []
            for ep in self.advanced.episodic.recall(query=q, limit=n):
                results.append(RetrievalResult(id=ep.id, content=ep.content, score=ep.strength(), source="bm25"))
            return results
        except: return []
    async def remember(self, content, tier="semantic", subject="", importance=0.5, tags=None, metadata=None):
        try:
            tier_enum = MemoryTier(tier)
        except: tier_enum = MemoryTier.SEMANTIC
        decision = await self.reconciler.reconcile(content=content, suggested_tier=tier_enum,
            subject=subject, importance=importance, metadata=metadata or {}, tags=tags or [])
        # Also store in advanced.semantic directly for instant recall
        try:
            self.advanced.semantic.store(content, importance=importance, tags=tags or [])
        except: pass
        return f"{decision.action.value}:{decision.target_tier.value}"
    def recall(self, query, limit=10, rerank=True):
        return self.hybrid.search(query, limit=limit, rerank=rerank)
    def recall_as_text(self, query, limit=10):
        # Search ALL backends for maximum recall
        results = []
        seen = set()

        def add_result(content, source="unknown"):
            if not content or not isinstance(content, str):
                return
            content = content.strip()
            if not content:
                return
            if content not in seen:
                seen.add(content)
                results.append({"content": content, "source": source})

        # 1. ChromaDB vector search (most powerful)
        try:
            vec_results = self.vector.search(query, n_results=limit)
            if isinstance(vec_results, list):
                for item in vec_results:
                    text = item.get("content") or item.get("document") or ""
                    if text:
                        add_result(text, "vector")
            elif isinstance(vec_results, str) and "No results" not in vec_results:
                add_result(vec_results[:1000], "vector")
        except:
            pass

        # 2. Semantic memory (ChromaDB + keyword fallback)
        try:
            sem_results = self.advanced.semantic.search(query, limit=limit)
            for r in (sem_results if isinstance(sem_results, list) else []):
                text = r.content if hasattr(r, "content") else str(r)
                add_result(text, "semantic")
        except:
            pass

        # 3. Hybrid retriever (vector + BM25 + KG fusion)
        try:
            hybrid_results = self.recall(query, limit=limit)
            for r in hybrid_results:
                add_result(r.content, r.source)
        except:
            pass

        # 4. Context memory (structured facts)
        try:
            all_facts = self.context.list_all()
            for fact_key, fact_val in (all_facts.items() if isinstance(all_facts, dict) else {}):
                if query.lower() in fact_key.lower() or query.lower() in str(fact_val).lower():
                    add_result(f"{fact_key}: {fact_val}", "context")
        except:
            pass

        # 5. Realtime memory (recent conversation)
        try:
            recent = self.realtime.get_context_string(last_n=20)
            if recent and len(recent) > 10:
                add_result(recent[:2000], "recent_conversation")
        except:
            pass

        if not results:
            return "No relevant memories found."

        parts = []
        for i, r in enumerate(results[:limit], 1):
            text = r["content"][:500]
            parts.append(f"[{i}] ({r['source']}) {text}")
        return "\n\n".join(parts)
    def store_fact(self, k, v): return self.context.store(k, v, "facts")
    def retrieve_fact(self, k): return self.context.retrieve(k, "facts")
    def search_memory(self, q): return self.recall_as_text(q, limit=5)
    def store_knowledge(self, c, m=None): return self.vector.store(c, m)
    def search_knowledge(self, q, n=5): return self.vector.search(q, n)
    def get_full_context(self):
        parts = []
        ctx = self.context.get_context_string()
        if ctx and "No context" not in ctx: parts.append(f"=== User Context ===\n{ctx}")
        history = self.realtime.get_context_string(last_n=10)
        if history: parts.append(f"=== Recent Conversation ===\n{history}")
        return "\n\n".join(parts) if parts else "No context available."
    def delete_fact(self, k): return self.context.delete(k, "facts")
    def update_fact(self, k, v): return self.context.update(k, v, "facts")
    def list_facts(self): return self.context.list_all()
    async def reflect_now(self):
        return (await self.sleep.run_full_cycle()).to_dict()
    def reconcile_stats(self): return self.reconciler.stats()
    def full_summary(self):
        base = self.advanced.full_summary() if hasattr(self.advanced, "full_summary") else ""
        return f"{base}\n  Reconciler: {self.reconciler.stats()}"
    async def shutdown(self):
        try: await self.sleep.run_light_cycle()
        except: pass

MemoryManager = UnifiedMemoryManager
