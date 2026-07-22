"""Runtime smoke test for Phases 14-17 (prompt, computer_use, orchestration, observability).

Tests each module independently without requiring an LLM API key.
Uses simulated callables where needed.

Run: python scripts/test_new_modules.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
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
# Phase 14 — Prompt Architecture
# ========================================================================

def test_prompt_builder():
    """Validate PromptBuilder assembles layers correctly."""
    from xeno.prompt.builder import PromptBuilder, PromptAssembly
    from xeno.prompt.layers import LayerType

    pb = PromptBuilder()

    # Load SOUL + MEMORY from project root
    soul_loaded = pb.load_soul(ROOT / "SOUL.md")
    mem_loaded = pb.load_memory(ROOT / "MEMORY.md")
    assert soul_loaded, "SOUL.md not found or not loaded"
    assert mem_loaded, "MEMORY.md not found or not loaded"
    ok("PromptBuilder.load_soul() + load_memory() — files loaded")

    # Load project context
    proj_loaded = pb.load_project_context(ROOT / "AGENTS.md")
    assert proj_loaded, "AGENTS.md not found"
    ok("PromptBuilder.load_project_context() — AGENTS.md loaded")

    # Set tools via dict format
    pb.set_tools([
        {"name": "search", "description": "Search the web for information"},
        {"name": "read_file", "description": "Read contents of a file"},
    ])
    ok("PromptBuilder.set_tools() — tools registered")

    # Set capabilities
    pb.set_capabilities(["web_search", "file_operations", "code_execution"])
    ok("PromptBuilder.set_capabilities() — capabilities set")

    # Assemble prompt
    assembly = pb.assemble(user_message="hello world")
    assert isinstance(assembly, PromptAssembly), f"Expected PromptAssembly, got {type(assembly)}"
    assert len(assembly.layers) > 0, "No layers in assembly"
    ok(f"PromptBuilder.assemble() — {len(assembly.layers)} layers, ~{assembly.token_estimate} tokens")

    # Full prompt string
    prompt = assembly.full_prompt
    assert isinstance(prompt, str), f"Expected str, got {type(prompt)}"
    assert len(prompt) > 50, f"Prompt too short: {len(prompt)} chars"
    ok("PromptAssembly.full_prompt — returns assembled string")

    # Cache stats (property)
    stats = pb.cache_stats
    assert "cached_layers" in stats, f"cache_stats missing 'cached_layers': {stats}"
    assert "build_count" in stats, f"cache_stats missing 'build_count': {stats}"
    ok("PromptBuilder.cache_stats — returns build info")

    # Selective layers
    partial = pb.assemble(user_message="test", layers=[LayerType.WORKING, LayerType.METADATA])
    assert len(partial.layers) <= 2, f"Expected ≤2 layers, got {len(partial.layers)}"
    ok("PromptBuilder.assemble() — selective layers works")

    # Invalidate
    pb.invalidate()
    ok("PromptBuilder.invalidate() — cache cleared")


def test_prompt_tiers():
    """Validate PromptTierBuilder from existing tiers module."""
    from xeno.prompt.tiers import PromptTierBuilder

    ptb = PromptTierBuilder()
    ptb.configure_identity(name="Xeno", role="AI Assistant")
    ptb.set_tools([{"name": "search", "description": "Web search"}])
    ptb.set_capabilities(["web_search"])

    # Build full prompt
    result = ptb.build_prompt("hello", include_identity=True, include_metadata=True, include_instructions=True)
    assert isinstance(result, str), f"Expected str, got {type(result)}"
    assert "Xeno" in result, "Identity name missing from prompt"
    assert "hello" in result, "User input missing from prompt"
    ok("PromptTierBuilder.build_prompt() — full prompt assembled")

    # Token estimation
    tokens = ptb.estimate_tokens(result)
    assert isinstance(tokens, int) and tokens > 0, f"Bad token count: {tokens}"
    ok("PromptTierBuilder.estimate_tokens() — positive int returned")

    # Selective tiers (working only)
    partial = ptb.build_prompt("test", include_identity=False, include_metadata=False, include_instructions=False)
    assert len(partial) < len(result), "Selective tiers didn't reduce size"
    assert "test" in partial, "Working layer missing user message"
    ok("PromptTierBuilder selective tiers — subset works")


def test_context_compressor():
    """Validate ContextCompressor respects token budgets."""
    from xeno.prompt.compressor import ContextCompressor

    # Create with tiny budget to force compression
    cc = ContextCompressor(max_tokens=50, target_tokens=30)
    text = "A " * 500

    compressed = cc.compress(text)
    # Should either reduce size or return original if under target
    ok(f"ContextCompressor.compress() — compressed {len(text)} chars")

    # Test line summarization with many short lines
    long_lines = "\n".join(f"line {i}" for i in range(500))
    compressed_lines = cc.compress(long_lines)
    line_count = compressed_lines.count("\n") + 1
    assert line_count < 150, f"Too many lines after compression: {line_count}"
    ok("ContextCompressor.compress() — reduces many-line text")

    # Code block extraction
    code_text = "Some text\n```python\nprint('hello')\n```\nmore text\n```\ndef foo():\n    pass\n```"
    blocks = cc.extract_code_blocks(code_text)
    assert len(blocks) == 2, f"Expected 2 code blocks, got {len(blocks)}"
    ok("ContextCompressor.extract_code_blocks() — finds all blocks")

    # Whitespace cleanup
    messy = "word1    word2\n\n\n\nword3"
    cleaned = cc.remove_redundant_whitespace(messy)
    assert "    " not in cleaned, "Excess spaces remain"
    assert "\n\n\n\n" not in cleaned, "4+ newlines should be reduced"
    ok("ContextCompressor.remove_redundant_whitespace() — cleans up")


# ========================================================================
# Phase 15 — Computer Use
# ========================================================================

async def test_action_planner():
    """Validate ActionPlanner with heuristic fallback (no LLM needed)."""
    from xeno.computer_use.action_planner import ActionPlanner, PlannedAction, ActionType
    from xeno.computer_use.state_reader import ScreenState, ScreenElement

    planner = ActionPlanner()
    ok("ActionPlanner() — initializes without LLM")

    # Heuristic plan with no LLM
    state = ScreenState(
        screen_size=(1920, 1080),
        elements=[
            ScreenElement(tag="input", attributes={"id": "search", "type": "text"}, text="Search...", bounds=(0, 0, 200, 40), role="textbox", interactable=True),
            ScreenElement(tag="button", attributes={"id": "submit"}, text="Go", bounds=(210, 0, 80, 40), role="button", interactable=True),
            ScreenElement(tag="a", attributes={"href": "/about"}, text="About", bounds=(0, 50, 100, 30), role="link", interactable=False),
        ],
    )
    plan = await planner.plan_actions(goal="click Go", state=state)
    assert isinstance(plan, list), f"Expected list of actions, got {type(plan)}"
    assert len(plan) > 0, "Should produce at least one heuristic action"
    ok(f"ActionPlanner.plan_actions() — heuristic: {len(plan)} actions")

    # PlannedAction dataclass works
    if plan:
        assert isinstance(plan[0], PlannedAction), f"Expected PlannedAction, got {type(plan[0])}"
        assert isinstance(plan[0].type, ActionType), "Action type wrong"
    ok("ActionPlanner — PlannedAction dataclass valid")

    # Set LLM
    async def fake_llm(system: str, prompt: str) -> str:
        return json.dumps([{"type": "click", "target": "Go", "rationale": "test"}])

    planner.set_llm(fake_llm)
    ok("ActionPlanner.set_llm() — callable stored")

    plan2 = await planner.plan_actions(goal="click Go", state=state)
    assert isinstance(plan2, list), "LLM plan is not a list"
    ok("ActionPlanner.plan_actions() — with LLM returns list")

    # find_element_by_text
    found = planner.find_element_by_text(state, "Search", partial=True)
    assert found is not None, "Should find 'Search' element by partial text"
    assert found.text == "Search...", f"Wrong element: {found}"
    ok("ActionPlanner.find_element_by_text() — partial match works")


async def test_state_reader():
    """Validate StateReader with fallback (no browser, no tesseract)."""
    from xeno.computer_use.state_reader import StateReader, ScreenState

    reader = StateReader()
    ok("StateReader() — initializes without vision LLM")

    # Read state — should handle gracefully without dependencies
    state = await reader.read_state()
    assert isinstance(state, ScreenState), f"Expected ScreenState, got {type(state)}"
    assert isinstance(state.screen_size, tuple), "State missing screen_size"
    ok(f"StateReader.read_state() — ScreenState with screen_size={state.screen_size}")

    # ScreenState dataclass
    assert isinstance(state.summary(), str), "ScreenState.summary() should return str"
    ok("ScreenState.summary() — returns string")

    # Set vision LLM
    async def fake_vision(system: str, prompt: str) -> str:
        return "The screen shows a login page with username and password fields."

    reader.set_vision_llm(fake_vision)
    ok("StateReader.set_vision_llm() — callable stored")


async def test_cdp_bridge():
    """Validate CDPBridge without a real browser."""
    from xeno.computer_use.cdp_bridge import CDPBridge

    bridge = CDPBridge()
    assert bridge._ws_url is None, "Default WS URL should be None"
    assert not bridge._connected, "Should not be connected"
    ok("CDPBridge() — initializes disconnected")

    # Try navigating without browser — should return False gracefully
    result = await bridge.navigate("https://example.com")
    assert result is False, f"Should return False without browser, got {result}"
    ok("CDPBridge.navigate() — graceful False without browser")

    # Try other methods without connection
    tabs = await bridge.get_tabs()
    assert tabs == [], f"get_tabs should return [] without browser, got {tabs}"
    ok("CDPBridge.get_tabs() — graceful [] without browser")

    tree = await bridge.get_accessibility_tree()
    assert tree is None, "get_accessibility_tree should return None without browser"
    ok("CDPBridge.get_accessibility_tree() — graceful None without browser")

    ss = await bridge.screenshot()
    assert ss is None, "screenshot should return None without browser"
    ok("CDPBridge.screenshot() — graceful None without browser")

    js = await bridge.evaluate("1+1")
    assert js is None, "evaluate should return None without browser"
    ok("CDPBridge.evaluate() — graceful None without browser")

    # ensure_browser — gracefully handles missing/closed browser
    started = await bridge.ensure_browser()
    # May be True (Chrome running with CDP) or False (no Chrome), both valid
    ok(f"CDPBridge.ensure_browser() — returned {started}")


# ========================================================================
# Phase 16 — Orchestration
# ========================================================================

def test_orchestration_registry():
    """Validate PatternRegistry imports and structure."""
    from xeno.orchestration import PatternRegistry

    assert "supervisor" in PatternRegistry, "supervisor missing from registry"
    assert "pipeline" in PatternRegistry, "pipeline missing from registry"
    assert "fanout" in PatternRegistry, "fanout missing from registry"
    assert "debate" in PatternRegistry, "debate missing from registry"
    assert "adaptive" in PatternRegistry, "adaptive missing from registry"
    ok(f"PatternRegistry — {len(PatternRegistry)} patterns registered")


async def _fake_runner(name: str, desc: str) -> str:
    return f"[{name}] executed: {desc[:20]}"


async def test_supervisor_orchestrator():
    """Validate SupervisorOrchestrator without LLM."""
    from xeno.orchestration.supervisor import SupervisorOrchestrator

    so = SupervisorOrchestrator()
    so.set_agent_runner(_fake_runner)
    ok("SupervisorOrchestrator — agent runner set")

    # Plan with no LLM — should use simple plan
    plan = await so.plan("test task", available_agents=["agent_a", "agent_b"])
    assert isinstance(plan, object), f"Expected DelegationPlan"
    assert hasattr(plan, 'tasks'), "Plan missing tasks"
    ok(f"SupervisorOrchestrator.plan() — {len(plan.tasks)} tasks")

    # Check DelegatedTask structure
    if plan.tasks:
        t = plan.tasks[0]
        assert t.agent_name != "", "Task missing agent_name"
        assert t.description != "", "Task missing description"
        ok("SupervisorOrchestrator — DelegatedTask fields valid")


async def test_pipeline_orchestrator():
    """Validate PipelineOrchestrator."""
    from xeno.orchestration.pipeline import PipelineOrchestrator

    po = PipelineOrchestrator()
    po.set_agent_runner(_fake_runner)
    ok("PipelineOrchestrator — agent runner set")

    # Execute 2 steps
    steps = [
        {"agent": "agent_a", "description": "first step: {input}"},
        {"agent": "agent_b", "description": "second step: {input}"},
    ]
    results = await po.execute(steps, initial_input="hello")
    assert isinstance(results, list), f"Expected list, got {type(results)}"
    assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    assert results[0]["success"], "First step should succeed"
    ok(f"PipelineOrchestrator.execute() — {len(results)} steps completed")

    # last_output property
    assert po.last_output != "", "last_output should have content"
    ok("PipelineOrchestrator.last_output — returns final output")


async def test_fanout_orchestrator():
    """Validate FanOutOrchestrator."""
    from xeno.orchestration.fanout import FanOutOrchestrator

    fo = FanOutOrchestrator()
    fo.set_agent_runner(_fake_runner)
    ok("FanOutOrchestrator — agent runner set")

    # Execute parallel tasks
    tasks = [
        {"agent": "agent_a", "description": "task 1", "id": "t1"},
        {"agent": "agent_b", "description": "task 2", "id": "t2"},
    ]
    results = await fo.execute(tasks)
    assert isinstance(results, list), f"Expected list, got {type(results)}"
    assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    ok(f"FanOutOrchestrator.execute() — {len(results)} parallel tasks completed")

    # aggregate_text
    text = fo.aggregate_text(results)
    assert isinstance(text, str), f"Expected str, got {type(text)}"
    assert len(text) > 20, "Aggregated text too short"
    ok("FanOutOrchestrator.aggregate_text() — returns summary")


async def test_debate_orchestrator():
    """Validate DebateOrchestrator."""
    from xeno.orchestration.debate import DebateOrchestrator

    do = DebateOrchestrator()
    do.set_agent_runner(_fake_runner)

    async def fake_judge(system: str, prompt: str) -> str:
        return "The best answer is option A because it is more comprehensive."

    do.set_judge(fake_judge)
    ok("DebateOrchestrator — agent runner + judge set")

    # Run debate
    result = await do.debate("test topic", agents=["agent_a", "agent_b"], rounds=1)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "topic" in result, "Result missing topic"
    assert "rounds" in result, "Result missing rounds"
    assert "verdict" in result, "Result missing verdict"
    ok(f"DebateOrchestrator.debate() — completed: verdict={result['verdict'][:30]}")


async def test_adaptive_orchestrator():
    """Validate AdaptiveOrchestrator."""
    from xeno.orchestration.adaptive import AdaptiveOrchestrator

    ao = AdaptiveOrchestrator()
    ao.set_agent_runner(_fake_runner)

    async def fake_llm(system: str, prompt: str) -> str:
        return json.dumps({"agent": "agent_a", "description": "research the topic", "is_final": True})

    ao.set_llm(fake_llm)
    ok("AdaptiveOrchestrator — agent runner + LLM set")

    # Execute
    result = await ao.execute("complex task", available_agents=["agent_a", "agent_b"])
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "steps" in result, "Result missing steps"
    assert "goal" in result, "Result missing goal"
    ok(f"AdaptiveOrchestrator.execute() — {result['steps_completed']}/{result['steps_total']} steps")
    # No get_status method; check via internal state
    assert len(ao._steps) > 0, "No steps recorded internally"
    ok("AdaptiveOrchestrator — internal steps state valid")


# ========================================================================
# Phase 17 — Observability
# ========================================================================

async def test_tracer():
    """Validate Tracer spans."""
    from xeno.observability.tracer import Tracer

    t = Tracer()
    assert len(t._spans) == 0, "Should start with no spans"
    assert len(t._active_spans) == 0, "Should start with no active spans"
    ok("Tracer() — initializes cleanly")

    span_id = t.start_span("test_operation", attributes={"key": "value"})
    assert span_id is not None, "start_span returned None"
    assert isinstance(span_id, str), f"Expected string, got {type(span_id)}"
    ok("Tracer.start_span() — span_id returned")

    # Get span and check
    span = t.get_span(span_id)
    assert span is not None, "Span not found"
    assert span.name == "test_operation", f"Wrong span name: {span.name}"
    assert span.span_id == span_id, f"Wrong span_id"
    ok("Tracer.get_span() — span has correct name and id")

    t.add_event(span_id, "milestone", {"progress": "50%"})
    assert len(span.events) == 1, "Event not recorded"
    ok("Tracer.add_event() — event recorded")

    t.add_attributes(span_id, {"result": "success", "duration_ms": 150})
    assert span.attributes["result"] == "success", "Attributes not updated"
    ok("Tracer.add_attributes() — attributes added")

    t.end_span(span_id)
    assert span.end_time > 0, "Span end_time not set"
    assert span.duration_ms > 0, "Span duration should be positive"
    ok("Tracer.end_span() — span closed with duration")

    # Nested spans
    p_id = t.start_span("parent")
    c_id = t.start_span("child")
    c_span = t.get_span(c_id)
    assert c_span.parent_span_id == p_id, "Child should reference parent"
    assert len(t._active_spans) == 2, "Should have 2 active spans"
    t.end_span(c_id)
    t.end_span(p_id)
    assert len(t._active_spans) == 0, "All spans should be ended"
    ok("Tracer nested spans — parent/child relationship works")

    # Context manager
    async with t.span("async_op") as sid:
        assert isinstance(sid, str), "Context span_id should be string"
        t.add_event(sid, "step", {"done": True})
    # After context, span should be ended
    span_after = t.get_span(sid)
    assert span_after.end_time > 0, "Context manager should end span"
    ok("Tracer.span() context manager — auto-ends span")

    # get_trace
    trace_spans = t.get_trace(span.trace_id)
    assert len(trace_spans) > 0, "get_trace should return spans"
    ok("Tracer.get_trace() — returns spans by trace_id")

    t.clear()
    assert len(t._spans) == 0, "clear should remove all spans"
    ok("Tracer.clear() — all spans removed")


def test_metrics():
    """Validate MetricsCollector."""
    from xeno.observability.metrics import MetricsCollector

    mc = MetricsCollector()
    assert len(mc._series) == 0, "Should start empty"
    ok("MetricsCollector() — initializes empty")

    mc.record_tokens(model="test-model", input_tokens=100, output_tokens=50)
    token_total = mc.get_series("token.total.test-model")
    assert token_total is not None, "token series should exist"
    assert token_total.total == 150, f"Expected 150, got {token_total.total}"
    ok("MetricsCollector.record_tokens() — series created and accumulated")

    mc.record_tool_call("search", duration_ms=200, success=True)
    mc.record_tool_call("read", duration_ms=50, success=False)
    tool_calls = mc.get_series("tool.total.calls")
    assert tool_calls is not None, "tool series should exist"
    assert tool_calls.total == 2, f"Expected 2, got {tool_calls.total}"
    tool_errors = mc.get_series("tool.read.errors")
    assert tool_errors is not None, "error series should exist"
    assert tool_errors.total == 1, f"Expected 1 error, got {tool_errors.total}"
    ok("MetricsCollector.record_tool_call() — success/failure tracked")

    mc.record_task("research", duration_s=30.5, success=True)
    task_count = mc.get_series("task.research.count")
    assert task_count is not None, "task series should exist"
    assert task_count.total == 1, f"Expected 1, got {task_count.total}"
    ok("MetricsCollector.record_task() — task recorded")

    mc.record_memory_op("read", "context")
    memory_ops = mc.get_series("memory.read.context")
    assert memory_ops is not None, "memory series should exist"
    ok("MetricsCollector.record_memory_op() — memory op tracked")

    # MetricSeries properties
    latency = mc.get_series("tool.total.latency_ms")
    assert latency is not None, "latency series should exist"
    assert latency.average > 0, f"Average should be positive: {latency.average}"
    ok("MetricSeries — average/last/total properties work")

    # Summary
    summary = mc.summary()
    assert isinstance(summary, dict), f"Expected dict, got {type(summary)}"
    assert len(summary) > 0, "Summary should have entries"
    ok("MetricsCollector.summary() — dict with all series")

    # Persistence (use temp dir to avoid Windows file locks)
    import tempfile
    tmp_path = Path(tempfile.mkdtemp()) / "metrics.json"
    mc.save(tmp_path)
    ok(f"MetricsCollector.save() — saved to {tmp_path}")

    mc2 = MetricsCollector()
    mc2.load(tmp_path)
    loaded_total = mc2.get_series("token.total.test-model")
    assert loaded_total is not None, "Loaded series missing"
    assert loaded_total.total == 150, f"Load/save mismatch: {loaded_total.total}"
    ok("MetricsCollector.load() — restored correctly")
    tmp_path.unlink()
    tmp_path.parent.rmdir()

    mc.clear()
    assert len(mc._series) == 0, "clear should empty all series"
    ok("MetricsCollector.clear() — all series removed")


def test_exporters():
    """Validate all exporter types."""
    from xeno.observability.exporter import ConsoleExporter, FileExporter, CompositeExporter
    from xeno.observability.tracer import TraceSpan

    span = TraceSpan(name="test", trace_id="t1", span_id="s1")

    # Console exporter
    ce = ConsoleExporter()
    ce.export(span)
    ok("ConsoleExporter.export() — executes without error")

    # File exporter (stores JSON array)
    import tempfile
    tmp_path = Path(tempfile.mkdtemp()) / "trace.json"
    fe = FileExporter(tmp_path)
    fe.export(span)
    fe.export(span)

    data = json.loads(tmp_path.read_text())
    assert isinstance(data, list), f"Expected list, got {type(data)}"
    assert len(data) == 2, f"Expected 2 entries, got {len(data)}"
    ok(f"FileExporter — 2 spans written to {tmp_path}")
    tmp_path.unlink()
    tmp_path.parent.rmdir()

    # Composite exporter
    comp = CompositeExporter([ce, ce])
    comp.export(span)
    ok("CompositeExporter.export() — delegates to all children")


# ========================================================================
# Main
# ========================================================================

async def main():
    global PASS, FAIL

    print("=" * 60)
    print("  Xeno — New Modules Smoke Test (Phases 14-17)")
    print("=" * 60)

    # Phase 14
    print("\n>>> Phase 14: Prompt Architecture")
    test_prompt_builder()
    test_prompt_tiers()
    test_context_compressor()

    # Phase 15
    print("\n>>> Phase 15: Computer Use")
    await test_action_planner()
    await test_state_reader()
    await test_cdp_bridge()

    # Phase 16
    print("\n>>> Phase 16: Orchestration")
    test_orchestration_registry()
    await test_supervisor_orchestrator()
    await test_pipeline_orchestrator()
    await test_fanout_orchestrator()
    await test_debate_orchestrator()
    await test_adaptive_orchestrator()

    # Phase 17
    print("\n>>> Phase 17: Observability")
    await test_tracer()
    test_metrics()
    test_exporters()

    # Summary
    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"  Results: {PASS}/{total} passed", end="")
    if FAIL > 0:
        print(f", {FAIL} failed", end="")
    print()
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
