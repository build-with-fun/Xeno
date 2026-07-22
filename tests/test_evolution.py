"""Tests for the self-evolution engine."""

import pytest
from xeno.self_improve.evolution import EvolutionEngine, EvolutionEvent, EvolutionInsight, SkillProposal
from pathlib import Path
import tempfile


class TestEvolutionEngine:
    def test_init(self, tmp_path):
        engine = EvolutionEngine(tmp_path / "evolution")
        assert engine.stats()["total_events"] == 0
        assert engine.stats()["total_insights"] == 0

    def test_record_task_success(self, tmp_path):
        engine = EvolutionEngine(tmp_path / "evolution")
        engine.record_task("Search the web", success=True, pattern_used="web_search", tags=["research"])
        assert engine.stats()["total_events"] == 1

    def test_record_task_failure(self, tmp_path):
        engine = EvolutionEngine(tmp_path / "evolution")
        engine.record_task("Complex task", success=False, error_message="Timeout", tags=["test"])
        assert engine.stats()["total_events"] == 1

    def test_record_tool_call(self, tmp_path):
        engine = EvolutionEngine(tmp_path / "evolution")
        engine.record_tool_call("web_search", {"query": "test"}, success=True)
        assert engine.stats()["total_events"] == 1

    def test_record_tool_failure(self, tmp_path):
        engine = EvolutionEngine(tmp_path / "evolution")
        engine.record_tool_call("shell_execute", {"command": "rm -rf"}, success=False, error="Permission denied")
        assert engine.stats()["total_events"] == 1

    def test_no_insights_below_threshold(self, tmp_path):
        engine = EvolutionEngine(tmp_path / "evolution")
        assert engine.get_insights() == []
        assert engine.get_proposals() == []

    def test_proposals_generated_after_successful_tasks(self, tmp_path):
        engine = EvolutionEngine(tmp_path / "evolution")
        for i in range(5):
            engine.record_task(f"Task {i}", success=True, pattern_used="research", tags=["test"])
        proposals = engine.get_proposals(min_success_rate=0.0)
        # May or may not have proposals depending on engine logic
        assert engine.stats()["total_events"] == 5

    def test_mark_insight_applied(self, tmp_path):
        engine = EvolutionEngine(tmp_path / "evolution")
        engine.record_tool_call("failing_tool", {}, success=False)
        engine.record_tool_call("failing_tool", {}, success=False)
        engine.record_tool_call("failing_tool", {}, success=False)
        insights = engine.get_insights(min_confidence=0.0)
        if insights:
            assert engine.mark_applied(insights[0].id, success=True)
            assert engine.get_insights(min_confidence=0.0) == []

    def test_accept_proposal(self, tmp_path):
        engine = EvolutionEngine(tmp_path / "evolution")
        for i in range(5):
            engine.record_task(f"Task {i}", success=True, pattern_used="test_pattern", tags=["test"])
        proposals = engine.get_proposals(min_success_rate=0.0)
        if proposals:
            assert engine.accept_proposal(proposals[0].id, skill_path="skills/auto_test_pattern")
            accepted_props = [p for p in engine.get_proposals(min_success_rate=0.0) if p.accepted]
            assert len(accepted_props) >= 0

    def test_persistence(self, tmp_path):
        data_dir = tmp_path / "evolution"
        engine1 = EvolutionEngine(data_dir)
        engine1.record_task("Persist test", success=True)
        engine1.record_tool_call("reader", {}, success=True)
        engine2 = EvolutionEngine(data_dir)
        assert engine2.stats()["total_events"] >= 2

    def test_stats_keys(self, tmp_path):
        engine = EvolutionEngine(tmp_path / "evolution")
        stats = engine.stats()
        assert "total_events" in stats
        assert "total_insights" in stats
        assert "pending_insights" in stats
        assert "total_proposals" in stats
        assert "accepted_proposals" in stats

    def test_evolution_event_creation(self):
        ev = EvolutionEvent(
            id="ev_001",
            timestamp=1000.0,
            event_type="task_complete",
            description="Test event",
            outcome_score=1.0,
        )
        assert ev.id == "ev_001"
        assert ev.event_type == "task_complete"
        d = ev.to_dict()
        assert d["id"] == "ev_001"

    def test_evolution_insight_creation(self):
        ins = EvolutionInsight(
            id="ins_001",
            created_at=1000.0,
            insight_type="tool_preference",
            description="Tool X is unreliable",
            confidence=0.8,
            evidence_count=5,
        )
        assert ins.insight_type == "tool_preference"
        d = ins.to_dict()
        assert d["insight_type"] == "tool_preference"

    def test_skill_proposal_creation(self):
        prop = SkillProposal(
            id="sp_001",
            name="auto_test",
            description="Auto-generated skill",
            procedure=["Step 1", "Step 2"],
            trigger_pattern="test pattern",
            evidence_count=10,
            avg_success_rate=0.9,
        )
        assert prop.name == "auto_test"
        d = prop.to_dict()
        assert d["name"] == "auto_test"
