"""XenoAtlas end-to-end smoke test — validates all new subsystems.

Run: uv run python scripts/test_xenoatlas.py
"""

from __future__ import annotations

import asyncio
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


async def test_pattern_registry():
    """Validate metacognition patterns are registered and callable."""
    from xeno.patterns.registry import register_default_patterns, list_patterns, call_pattern

    register_default_patterns()
    patterns = list_patterns()
    assert len(patterns) >= 4, f"Expected >=4 patterns, got {len(patterns)}"
    ok(f"Pattern registry: {len(patterns)} patterns ({', '.join(patterns.keys())})")

    # Call with dummy callables for structural validation
    async def dummy_gen(q): return f"Answer to: {q}"
    async def dummy_eval(q, a): return (0.9, "looks good")
    result = await call_pattern("reflexion", query="test", max_iterations=1,
                                improvement_threshold=0.9,
                                generate_fn=dummy_gen, critique_fn=dummy_eval)
    assert "iterations" in result, "Reflexion missing iterations"
    ok(f"Reflexion callable, keys: {list(result.keys())}")


async def test_temporal_kg():
    """Validate Temporal Knowledge Graph storage and query."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from xeno.memory.temporal import get_temporal_kg
        kg = get_temporal_kg("test", storage_path=Path(tmpdir))
        kg.add_fact("user", "name", "Ammar", source="test")
        kg.add_fact("user", "language", "Python", source="test")
        assert len(kg.facts) == 2, f"Expected 2 facts, got {len(kg.facts)}"
        ctx = kg.export_context()
        assert "Ammar" in ctx
        ok(f"TemporalKG: {len(kg.facts)} facts, context={len(ctx)} chars")

        # Versioning
        kg.add_fact("user", "name", "Ammar Ahmer", source="test")
        assert len(kg.facts) >= 3, "Versioning should add new fact"
        ok("TemporalKG: fact versioning works")


async def test_chat_store():
    """Validate ChatStore session creation, messages, and retrieval."""
    with tempfile.TemporaryDirectory() as tmpdir:
        from xeno.chat.store import ChatStore
        from xeno.config import XenoConfig
        cfg = XenoConfig()
        cfg.data_dir = Path(tmpdir)
        store = ChatStore(config=cfg)
        sess = store.create_session(model="test")
        sid = sess.id
        assert sid, "No session ID"
        await store.add_message(sid, role="user", content="hello")
        await store.add_message(sid, role="assistant", content="hi there")
        msgs = store.get_context(sid, last_n=10)
        total = sum(1 for _ in msgs) if isinstance(msgs, list) else 0
        assert total >= 2, f"Expected >=2 messages, got {total}"
        sessions = store.list_sessions()
        assert len(sessions) == 1, f"Expected 1 session, got {len(sessions)}"
        ok(f"ChatStore: messages stored, {len(sessions)} session(s)")


async def test_security_gateway():
    """Validate security gateway permission checks."""
    from xeno.security.gateway import get_gateway
    from xeno.security.permissions import PermissionModel, PermissionLevel

    gateway = get_gateway()
    perm = PermissionModel(base_level=PermissionLevel.STANDARD)
    perm.grant("read_file")
    allowed, reason, level = await gateway.check("agent", "read_file", {}, perm)
    assert allowed, f"read_file should be allowed: {reason}"
    ok("Security: STANDARD can read_file")

    # ELEVATED tool from STANDARD should be denied
    blocked, reason, level = await gateway.check("agent", "pip_install", {}, perm)
    assert not blocked, "pip_install should be blocked for STANDARD"
    ok(f"Security: pip_install denied for STANDARD: {reason}")


async def test_skill_synthesiser():
    """Validate skill synthesiser pattern detection."""
    from xeno.skills.synthesiser import SkillSynthesiser
    syn = SkillSynthesiser()
    for _ in range(10):
        syn.record_tool_call("read_file", "test")
        syn.record_tool_call("write_file", "test")
    candidates = syn.get_candidate_patterns()
    ok(f"SkillSynthesiser: {len(candidates)} candidates after 10 tool pairs")


async def test_agent_pool():
    """Validate AgentPool creation and status."""
    from xeno.pool.agent_pool import AgentPool
    pool = AgentPool(max_workers=10, max_per_type=5)
    st = pool.stats()
    assert isinstance(st, dict), "stats() should return dict"
    ok(f"AgentPool: stats={st}")


async def test_always_on_manager():
    """Validate AlwaysOnManager creation."""
    from xeno.always_on.manager import AlwaysOnManager
    mgr = AlwaysOnManager()
    mgr._auto_resume = False
    st = mgr.get_status()
    ok(f"AlwaysOnManager: {st['total']} agents registered, {st['active']} active")


async def test_mcp_gateway():
    """Validate MCPGateway creation and audit logging."""
    from xeno.mcp.gateway import MCPGateway
    mg = MCPGateway()
    audit = mg.get_audit_log()
    assert isinstance(audit, list)
    ok(f"MCPGateway: audit log initialized ({len(audit)} entries)")


async def test_config_has_new_fields():
    """Validate XenoConfig has the new XenoAtlas fields."""
    from xeno.config import XenoConfig
    cfg = XenoConfig()
    assert hasattr(cfg, "pool_max_workers"), "Missing pool_max_workers"
    assert hasattr(cfg, "pool_semaphore_limit"), "Missing pool_semaphore_limit"
    assert hasattr(cfg, "pool_per_type_caps"), "Missing pool_per_type_caps"
    assert hasattr(cfg, "chat_store_enabled"), "Missing chat_store_enabled"
    assert hasattr(cfg, "mcp_enabled"), "Missing mcp_enabled"
    assert hasattr(cfg, "always_on_enabled"), "Missing always_on_enabled"
    ok("XenoConfig has all XenoAtlas fields")


async def test_tools_registry_has_new_tools():
    """Validate registry.py has the new XenoAtlas tool entries."""
    from xeno.tools.registry import TOOL_MAP
    required = [
        "use_pattern", "pool_run", "pool_cancel", "pool_list",
        "temporal_add_fact", "temporal_query", "temporal_history",
        "chat_session_create", "chat_session_list", "chat_message_add",
        "always_on_list", "always_on_status", "always_on_start", "always_on_stop",
        "security_check", "security_audit_log", "security_stats",
    ]
    missing = [n for n in required if n not in TOOL_MAP]
    assert not missing, f"Missing tools: {missing}"
    ok(f"Tool registry: {len(required)} XenoAtlas tools registered")


async def test_chat_context_compactor():
    """Validate context compactor."""
    from xeno.chat.context_compactor import ContextCompactor
    cc = ContextCompactor(max_messages_before_compact=50, target_tokens=50)
    assert cc.should_compact(100), "Should need compaction at 100 messages"
    assert not cc.should_compact(10), "Should not need compaction at 10 messages"
    messages = [{"role": "user", "content": f"msg {i}"} for i in range(100)]
    summary = cc.compact_messages(messages)
    assert len(summary) > 0, "Summary should not be empty"
    ok(f"ContextCompactor: summary={len(summary)} chars from 100 messages")


async def test_unified_mcp_server():
    """Validate MemoryMCPServer creation."""
    from xeno.memory.mcp_server import MemoryMCPServer, create_memory_mcp_server
    srv = MemoryMCPServer()
    ok("MemoryMCPServer: created successfully")
    srv2 = create_memory_mcp_server()
    ok("create_memory_mcp_server: factory works")


async def test_orchestrator_v2():
    """Validate OrchestratorV2 creation."""
    from xeno.orchestrator.v2 import OrchestratorV2
    orch = OrchestratorV2()
    # Test that it has the expected interface
    assert hasattr(orch, "to_plan"), "Missing to_plan"
    assert hasattr(orch, "execute"), "Missing execute"
    assert hasattr(orch, "synthesize"), "Missing synthesize"
    ok("OrchestratorV2: created with to_plan, execute, synthesize")


async def main():
    global PASS, FAIL
    print("=" * 60)
    print("  XenoAtlas — End-to-End Smoke Test")
    print("=" * 60)

    tests = [
        ("Config fields", test_config_has_new_fields),
        ("Tool registry", test_tools_registry_has_new_tools),
        ("Pattern registry", test_pattern_registry),
        ("Temporal KG", test_temporal_kg),
        ("ChatStore", test_chat_store),
        ("Context compactor", test_chat_context_compactor),
        ("Security gateway", test_security_gateway),
        ("Skill synthesiser", test_skill_synthesiser),
        ("AgentPool", test_agent_pool),
        ("AlwaysOn manager", test_always_on_manager),
        ("MCP gateway", test_mcp_gateway),
        ("Memory MCP server", test_unified_mcp_server),
        ("OrchestratorV2", test_orchestrator_v2),
    ]

    import inspect
    for name, test_fn in tests:
        print(f"\n>>> {name}")
        try:
            if inspect.iscoroutinefunction(test_fn):
                await test_fn()
            else:
                test_fn()
        except Exception as e:
            fail(name, str(e))

    total = PASS + FAIL
    print("\n" + "=" * 60)
    print(f"  Results: {PASS}/{total} passed", end="")
    if FAIL > 0:
        print(f", {FAIL} failed", end="")
    print()
    print("=" * 60)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
