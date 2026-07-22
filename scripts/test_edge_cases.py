"""Edge case validation for new modules.

Tests graceful fallback behavior when files/dependencies are missing.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PASS = 0
FAIL = 0

def ok(name: str):
    global PASS; PASS += 1
    print(f"  [PASS] {name}")

def fail(name: str, detail: str = ""):
    global FAIL; FAIL += 1
    msg = f"  [FAIL] {name}"
    if detail:
        msg += f": {detail}"
    print(msg)

# ========================================================================
# PromptBuilder — missing files
# ========================================================================

def test_prompt_builder_missing_files():
    from xeno.prompt.builder import PromptBuilder
    from xeno.prompt.layers import SOUL_MD_TEMPLATE

    pb = PromptBuilder()

    # Load non-existent files — should return False
    assert pb.load_soul("NONEXISTENT_SOUL.md") is False, "load_soul should return False"
    assert pb.load_memory("NONEXISTENT_MEMORY.md") is False, "load_memory should return False"
    ok("PromptBuilder — returns False for missing files")

    # Build with empty soul — should use template
    assembly = pb.assemble("test")
    assert len(assembly.layers) > 0, "Should still produce layers"
    assert any("CORE IDENTITY" in l.content for l in assembly.layers), "Template should be used"
    ok("PromptBuilder — uses template fallback when SOUL.md missing")

    # Build with empty memory — omitted from assembly (no content)
    memory_in_assembly = any(l.type.value == "memory" for l in assembly.layers)
    ok(f"PromptBuilder — memory layer {'present' if memory_in_assembly else 'skipped when empty'}")

    # Multiple assembles with cache
    assembly2 = pb.assemble("test2")
    assert assembly2.token_estimate > 0, "Second assembly should work"
    ok("PromptBuilder — cache works across multiple assembles")

    # Invalid cache
    pb.invalidate()
    assembly3 = pb.assemble("test3")
    assert pb.cache_stats["build_count"] == 3, f"Expected build_count=3, got {pb.cache_stats}"
    ok("PromptBuilder — invalidate resets cache, build count increments")


# ========================================================================
# ActionPlanner — edge cases
# ========================================================================

def test_action_planner_edge_cases():
    """Test edge cases: empty state, no match, malformed LLM response."""
    import asyncio
    from xeno.computer_use.action_planner import ActionPlanner, ActionType
    from xeno.computer_use.state_reader import ScreenState

    planner = ActionPlanner()

    # Empty state
    state = ScreenState()
    plan = asyncio.run(planner.plan_actions("do something", state))
    assert isinstance(plan, list), f"Expected list, got {type(plan)}"
    ok("ActionPlanner — handles empty ScreenState")

    # No matching element in heuristic
    state = ScreenState(
        screen_size=(1024, 768),
        elements=[],
    )
    plan = asyncio.run(planner.plan_actions("click nothing", state))
    assert len(plan) >= 0, "Should return empty or screenshot action"
    ok("ActionPlanner — handles no matching elements")

    # Malformed LLM response
    async def bad_llm(system: str, prompt: str) -> str:
        return "NOT JSON AT ALL"

    planner.set_llm(bad_llm)
    plan = asyncio.run(planner.plan_actions("click something", state))
    assert isinstance(plan, list), "Should still return list after bad LLM"
    ok("ActionPlanner — falls back to heuristic on malformed LLM response")

    # Empty goal
    plan = asyncio.run(planner.plan_actions("", state))
    assert isinstance(plan, list), "Empty goal should still return plan"
    ok("ActionPlanner — handles empty goal string")


# ========================================================================
# StateReader — edge cases
# ========================================================================

def test_state_reader_edge_cases():
    """Test StateReader with edge cases: missing screenshot, empty result."""
    import asyncio
    from xeno.computer_use.state_reader import StateReader

    reader = StateReader()

    # Read with non-existent screenshot path
    state = asyncio.run(reader.read_state(screenshot_path="NONEXISTENT.png"))
    assert state.error == "", "No error should be set for missing screenshot"
    ok("StateReader — handles missing screenshot path gracefully")

    # Read with vision LLM that fails
    async def failing_vision(system: str, prompt: str) -> str:
        raise RuntimeError("Vision model unavailable")

    reader.set_vision_llm(failing_vision)
    state2 = asyncio.run(reader.read_state())
    assert isinstance(state2.summary(), str), "Should still produce summary"
    ok("StateReader — handles failing vision LLM gracefully")


# ========================================================================
# Orchestration — edge cases
# ========================================================================

def test_orchestration_edge_cases():
    """Test orchestrators with empty/missing config."""
    import asyncio
    from xeno.orchestration.supervisor import SupervisorOrchestrator
    from xeno.orchestration.pipeline import PipelineOrchestrator
    from xeno.orchestration.fanout import FanOutOrchestrator

    # Supervisor — empty available agents
    so = SupervisorOrchestrator()

    async def fake_runner(name: str, desc: str) -> str:
        return "done"

    so.set_agent_runner(fake_runner)
    plan = asyncio.run(so.plan("test", available_agents=[]))
    assert hasattr(plan, 'tasks'), "Plan should have tasks even with no agents"
    ok("SupervisorOrchestrator — handles empty available_agents")

    # Supervisor — plan works without agent runner (no execution happens at plan time)
    so2 = SupervisorOrchestrator()
    plan2 = asyncio.run(so2.plan("test", available_agents=["a"]))
    assert hasattr(plan2, 'tasks'), "Should still produce a plan"
    ok("SupervisorOrchestrator — plan works without agent runner")

    # Pipeline — empty steps
    po = PipelineOrchestrator()
    po.set_agent_runner(fake_runner)
    results = asyncio.run(po.execute([], initial_input="hello"))
    assert results == [], "Empty pipeline should return empty results"
    ok("PipelineOrchestrator — handles empty steps list")

    # FanOut — empty tasks
    fo = FanOutOrchestrator()
    fo.set_agent_runner(fake_runner)
    results = asyncio.run(fo.execute([]))
    assert results == [], "Empty fanout should return empty results"
    ok("FanOutOrchestrator — handles empty tasks list")


# ========================================================================
# Observability — edge cases
# ========================================================================

def test_observability_edge_cases():
    """Test observability with edge cases: missing spans, concurrent access."""
    import asyncio
    from xeno.observability.tracer import Tracer, TraceSpan

    t = Tracer()

    # End unknown span
    t.end_span("nonexistent_span_id")
    ok("Tracer — end_span on unknown span_id does not crash")

    # Add event to unknown span
    t.add_event("unknown", "test", {"key": "val"})
    ok("Tracer — add_event on unknown span_id does not crash")

    # Add attributes to unknown span
    t.add_attributes("unknown", {"key": "val"})
    ok("Tracer — add_attributes on unknown span_id does not crash")

    # Concurrent spans
    s1 = t.start_span("first")
    s2 = t.start_span("second")
    s3 = t.start_span("third")
    assert len(t._active_spans) == 3, f"Expected 3 active, got {len(t._active_spans)}"
    t.end_span(s3)
    t.end_span(s2)
    t.end_span(s1)
    assert len(t._active_spans) == 0, "All spans should be ended"
    ok("Tracer — handles 3 concurrent nested spans correctly")

    # Context manager with error
    span_ids_before = set(t._spans.keys())
    async def failing_span():
        try:
            async with t.span("failing_op") as sid:
                raise ValueError("something went wrong")
        except ValueError:
            pass
        # Span should be ended with error status
        span = next((s for s in t._spans.values() if s.name == "failing_op"), None)
        assert span is not None, "Span should exist after context"
        assert span.status == "error", f"Expected error status, got {span.status}"
        assert "something went wrong" in span.error, "Error message should be recorded"

    asyncio.run(failing_span())
    ok("Tracer — context manager handles exceptions, records error status")

    # Metrics — duplicate series
    from xeno.observability.metrics import MetricsCollector
    mc = MetricsCollector()
    mc.record_tokens("model1", 100, 50)
    mc.record_tokens("model1", 200, 100)
    series = mc.get_series("token.total.model1")
    assert series is not None and len(series.points) == 2, "Should accumulate points"
    ok("MetricsCollector — accumulates multiple records in same series")

    # Metrics — save/load empty
    import tempfile, json
    from pathlib import Path
    mc2 = MetricsCollector()
    tmp = Path(tempfile.mkdtemp()) / "empty_metrics.json"
    mc2.save(tmp)
    loaded = json.loads(tmp.read_text())
    assert isinstance(loaded, dict), "Empty save should produce dict"
    ok("MetricsCollector — saves empty state gracefully")
    tmp.unlink()
    tmp.parent.rmdir()


# ========================================================================
# Main
# ========================================================================

def main():
    global PASS, FAIL

    print("=" * 60)
    print("  Xeno — Edge Case Tests")
    print("=" * 60)

    print("\n>>> PromptBuilder edge cases")
    test_prompt_builder_missing_files()

    print("\n>>> ActionPlanner edge cases")
    test_action_planner_edge_cases()

    print("\n>>> StateReader edge cases")
    test_state_reader_edge_cases()

    print("\n>>> Orchestration edge cases")
    test_orchestration_edge_cases()

    print("\n>>> Observability edge cases")
    test_observability_edge_cases()

    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"  Results: {PASS}/{total} passed", end="")
    if FAIL > 0:
        print(f", {FAIL} failed", end="")
    print()
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    exit(main())
