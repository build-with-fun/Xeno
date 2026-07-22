"""Smoke test for Phase 1 (Harness) and Phase 2 (Memory Reconciliation).

Run: python scripts/test_phase_1_2.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_phase1_harness():
    print("\n=== Phase 1: Harness ===")
    from xeno.harness.feature_list import (
        FeatureListManager, Feature, FeatureStatus,
    )
    from xeno.harness.progress import ProgressTracker
    from xeno.harness.git_checkpoint import GitCheckpointer
    from xeno.harness.loop import HarnessLoop, Heartbeat
    from xeno.harness.initializer import HarnessInitializer, SessionContext

    tmp = ROOT / "data" / "_test_harness"
    # Clean prior test state
    import shutil
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    # Feature list
    fl = FeatureListManager(tmp)
    fl.load()
    feat = fl.add_feature(
        name="Test feature",
        description="A test feature for the harness",
        files=["test.py"],
    )
    assert feat.id.startswith("f_")
    fl.add_sub_step(feat.id, "Step 1")
    fl.add_sub_step(feat.id, "Step 2")
    fl.complete_sub_step(feat.id, "Step 1")
    fl.set_user_intent("Testing the harness")
    assert fl.state.user_intent_summary == "Testing the harness"
    print(f"  ✓ FeatureList: created feature {feat.id}, 2 sub-steps, 1 completed")

    # Progress tracker
    pt = ProgressTracker(tmp)
    pt.record("write_file", "wrote 100 bytes to test.py", feature_id=feat.id, step="Step 1", duration_ms=50)
    pt.record("shell_execute", "ran 'python test.py'", feature_id=feat.id, step="Step 2", success=False)
    recent = pt.recent(5)
    assert len(recent) == 2
    stats = pt.stats()
    assert stats["total"] == 2
    assert stats["success_rate"] == 0.5
    print(f"  ✓ ProgressTracker: 2 entries, success_rate={stats['success_rate']}")

    # Git checkpointer (will use sidecar — tmp dir not a git repo)
    cp = GitCheckpointer(tmp, tmp / "checkpoints")
    checkpoint = cp.checkpoint("Before risky op", tool="write_file", files_changed=["test.py"])
    assert checkpoint.id.startswith("cp_")
    recent_cps = cp.list_recent(5)
    assert len(recent_cps) == 1
    print(f"  ✓ GitCheckpointer: created {checkpoint.id}, is_git={cp.is_git()}")

    # Session context
    ctx = SessionContext(
        user_intent="Testing the harness",
        environment_summary="OS=Linux, Python=3.13",
        recent_progress=pt.tail(5),
        active_features=[{"name": "Test feature", "status": "planning", "description": "test"}],
        pending_tasks=[],
        suggested_next_action="Continue testing",
    )
    prompt_block = ctx.to_prompt_block()
    assert "SESSION CONTEXT" in prompt_block
    assert "Testing the harness" in prompt_block
    print(f"  ✓ SessionContext: prompt block {len(prompt_block)} chars")

    print("Phase 1: PASS")


def test_phase2_memory():
    print("\n=== Phase 2: Memory Reconciliation ===")
    from xeno.memory.reconcile import (
        MemoryReconciler, ReconcileAction, MemoryTier,
    )
    from xeno.memory.forgetting import (
        ForgettingEngine, ForgettingState, MemoryDurability,
    )
    from xeno.memory.reranker import (
        HybridRetriever, HeuristicReranker, RetrievalResult,
    )

    tmp = ROOT / "data" / "_test_memory"
    import shutil
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    # Forgetting curves
    engine = ForgettingEngine()
    # Volatile memory: should decay fast
    volatile = ForgettingState(
        importance=0.9,
        durability=MemoryDurability.VOLATILE,
        created_at=time.time(),
        last_accessed=time.time(),
    )
    # Long-term memory: should decay slowly
    long_term = ForgettingState(
        importance=0.9,
        durability=MemoryDurability.LONG_TERM,
        created_at=time.time(),
        last_accessed=time.time(),
    )
    now_strength = engine.strength(volatile)
    future_volatile = engine.decay_over_time(volatile, days=7)
    future_long = engine.decay_over_time(long_term, days=7)
    assert future_volatile < future_long, "Volatile should decay faster than long-term"
    print(f"  ✓ Forgetting: volatile 7d={future_volatile:.3f} < long_term 7d={future_long:.3f}")

    # Spaced repetition
    assert not engine.should_review(volatile)  # just created, no review due
    volatile.last_review_at = time.time() - 2 * 86400  # 2 days ago
    assert engine.should_review(volatile)  # 1-day interval passed
    engine.mark_reviewed(volatile)
    assert volatile.review_stage == 1
    print(f"  ✓ Spaced repetition: review_stage={volatile.review_stage}")

    # Hybrid retrieval with RRF
    reranker = HeuristicReranker()
    hybrid = HybridRetriever(
        vector_fn=lambda q, n: [
            RetrievalResult(id="v1", content=f"vector match: {q}", score=0.9, source="vector"),
            RetrievalResult(id="v2", content="other vector result", score=0.5, source="vector"),
        ][:n],
        bm25_fn=lambda q, n: [
            RetrievalResult(id="b1", content=f"bm25 match: {q}", score=0.8, source="bm25"),
            RetrievalResult(id="v1", content=f"vector match: {q}", score=0.7, source="bm25"),  # overlap
        ][:n],
        kg_fn=lambda q, n: [
            RetrievalResult(id="k1", content="kg fact", score=0.6, source="kg"),
        ][:n],
        rerank_fn=reranker,
    )
    results = hybrid.search("test query", limit=3)
    assert len(results) > 0
    # v1 should rank high due to appearing in 2 sources (RRF bonus)
    top_ids = [r.id for r in results[:3]]
    print(f"  ✓ Hybrid retrieval: top results={top_ids}")
    assert "v1" in top_ids, "v1 should be boosted by RRF (appears in 2 sources)"

    # Reconciler
    class FakeBackend:
        def __init__(self):
            self.stored = []
            self.updated = []
            self.deleted = []
            self.invalidated = []
        def store(self, content, **kw):
            self.stored.append(content)
            from dataclasses import dataclass
            @dataclass
            class R: id: str; content: str
            return R(id=f"r_{len(self.stored)}", content=content)
        def update(self, entry_id, content, **kw):
            self.updated.append((entry_id, content))
            return True
        def delete(self, entry_id):
            self.deleted.append(entry_id)
            return True
        def invalidate(self, entry_id, reason=""):
            self.invalidated.append((entry_id, reason))
            return True
        def search(self, query, limit=5):
            return []  # no existing

    backend = FakeBackend()
    rec = MemoryReconciler(data_dir=tmp)
    rec.register_backend(MemoryTier.SEMANTIC, backend)

    import asyncio
    async def run():
        # First write: ADD
        d1 = await rec.reconcile("User likes Python", suggested_tier=MemoryTier.SEMANTIC)
        assert d1.action == ReconcileAction.ADD
        assert len(backend.stored) == 1
        # Stats
        s = rec.stats()
        assert s["total_decisions"] == 1
        assert s["by_action"]["add"] == 1
        return d1

    d1 = asyncio.run(run())
    print(f"  ✓ Reconciler: ADD decision={d1.action.value}, confidence={d1.confidence}")

    print("Phase 2: PASS")


if __name__ == "__main__":
    test_phase1_harness()
    test_phase2_memory()
    print("\n✅ All Phase 1+2 tests passed")
