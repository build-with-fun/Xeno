"""Hybrid retrieval + reranker."""
from __future__ import annotations
import math, time, logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
logger = logging.getLogger(__name__)

@dataclass
class RetrievalResult:
    id: str; content: str; score: float; source: str
    metadata: dict = field(default_factory=dict)

class HeuristicReranker:
    def __call__(self, query, results):
        q_tokens = set(query.lower().split())
        for r in results:
            d_tokens = set(r.content.lower().split())
            jaccard = len(q_tokens & d_tokens) / max(1, len(q_tokens | d_tokens))
            r.metadata["rerank_score"] = jaccard
        return sorted(results, key=lambda r: r.metadata.get("rerank_score",0), reverse=True)

class HybridRetriever:
    def __init__(self, vector_fn=None, bm25_fn=None, kg_fn=None, rerank_fn=None, rrf_k=60):
        self.vector_fn=vector_fn; self.bm25_fn=bm25_fn; self.kg_fn=kg_fn
        self.rerank_fn=rerank_fn; self.rrf_k=rrf_k
    def search(self, query, limit=10, rerank=True):
        all_results=[]; source_results={}
        for name, fn in [("vector",self.vector_fn),("bm25",self.bm25_fn),("kg",self.kg_fn)]:
            if fn:
                try:
                    r = fn(query, max(limit*3,20)) or []
                    source_results[name]=r; all_results.extend(r)
                except: pass
        if not all_results: return []
        seen=set(); unique=[]
        for r in all_results:
            if r.id not in seen: seen.add(r.id); unique.append(r)
        scores={}; 
        for source, results in source_results.items():
            for rank, r in enumerate(results):
                if r.id in scores: scores[r.id] += 1.0/(self.rrf_k+rank+1)
                else: scores[r.id] = 1.0/(self.rrf_k+rank+1)
        ranked = sorted(unique, key=lambda r: scores.get(r.id,0), reverse=True)
        for r in ranked: r.metadata["fused_score"] = scores.get(r.id,0)
        top = ranked[:limit*2] if rerank else ranked[:limit]
        if rerank and self.rerank_fn and len(top)>1:
            reranked = self.rerank_fn(query, top)
            if reranked: top = reranked
        return top[:limit]
