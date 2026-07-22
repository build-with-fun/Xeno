"""Verify the fix: 'i am Ammar Ahmer' should NOT be classified as a task."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def test_classifier_fix():
    print("=" * 60)
    print("  Verify classifier fix")
    print("=" * 60)

    from xeno.middle.classifier import InputClassifier, InputType

    clf = InputClassifier()

    # The exact case that was broken
    cases = [
        # (input, expected_type, description)
        ("i am Ammar Ahmer", InputType.MEMORY_STORE, "user introducing themselves"),
        ("i'm Ammar", InputType.MEMORY_STORE, "user with apostrophe"),
        ("my name is Ammar Ahmer", InputType.MEMORY_STORE, "explicit name intro"),
        ("call me Ammar", InputType.MEMORY_STORE, "call me X"),
        ("i like Python", InputType.MEMORY_STORE, "preference"),
        ("i love dark themes", InputType.MEMORY_STORE, "preference"),
        ("i prefer minimal design", InputType.MEMORY_STORE, "preference"),
        ("i use Python 3.12", InputType.MEMORY_STORE, "tech stack"),
        ("i work at Google", InputType.MEMORY_STORE, "bio"),
        ("i live in Karachi", InputType.MEMORY_STORE, "bio"),
        ("i'm from Pakistan", InputType.MEMORY_STORE, "bio"),
        ("remember that I prefer tab indentation", InputType.MEMORY_STORE, "explicit remember"),
        ("note that the API key is XYZ", InputType.MEMORY_STORE, "explicit note"),
        ("my goal is to learn AI", InputType.MEMORY_STORE, "goal"),

        # These should still be TASKS
        ("build me a website", InputType.TASK, "build task"),
        ("create a portfolio project", InputType.TASK, "create task"),
        ("write me a report on AI", InputType.TASK, "write task"),
        ("debug this code", InputType.TASK, "debug task"),
        ("fix the login bug", InputType.TASK, "fix task"),
        ("send an email to mom", InputType.TASK, "send task"),
        ("open youtube", InputType.TASK, "open app task"),

        # These should be GENERAL_TALK (fallback is now talk, not task)
        ("the sky is blue", InputType.GENERAL_TALK, "statement of fact"),
        ("python is great", InputType.GENERAL_TALK, "opinion"),
        ("i'm tired", InputType.GENERAL_TALK, "feeling"),
        ("hello there", InputType.GENERAL_TALK, "greeting"),
        ("thanks", InputType.GENERAL_TALK, "thanks"),

        # These should be MEMORY_QUERY
        ("what's my name?", InputType.MEMORY_QUERY, "ask name"),
        ("what do you remember about me?", InputType.MEMORY_QUERY, "ask memory"),

        # These should be QUICK_RESEARCH
        ("what's the weather?", InputType.QUICK_RESEARCH, "weather"),
        ("what is Python?", InputType.QUICK_RESEARCH, "definition"),

        # These should be SCHEDULING
        ("remind me to call mom at 5pm", InputType.SCHEDULING, "remind"),
        ("every day at 8am remind me to exercise", InputType.SCHEDULING, "daily"),
    ]

    passed = 0
    failed = 0
    for text, expected, desc in cases:
        result = await clf.classify(text, has_running_task=False)
        ok = result.input_type == expected
        if ok:
            print(f"  ✓ '{text[:35]:<35}' → {result.input_type.value:<18} ({desc})")
            passed += 1
        else:
            print(f"  ✗ '{text[:35]:<35}' → {result.input_type.value:<18} (expected {expected.value}) — {desc}")
            failed += 1

    print(f"\n  Result: {passed}/{passed + failed} passed")
    if failed:
        print(f"  ❌ {failed} test(s) failed")
        return False
    print("  ✅ All classifier tests passed")
    return True


async def test_orchestrator_with_memory_store():
    """Verify 'i am Ammar Ahmer' now triggers memory store, not task spawn."""
    print("\n" + "=" * 60)
    print("  Verify orchestrator handles 'i am Ammar Ahmer' correctly")
    print("=" * 60)

    from xeno.middle.classifier import InputClassifier
    from xeno.middle.acknowledger import TaskAcknowledger
    from xeno.middle.agent import MiddleAgent
    from xeno.middle.orchestrator import (
        ConversationalOrchestrator, ConversationEventType,
    )

    classifier = InputClassifier()
    acknowledger = TaskAcknowledger()

    # Fake LLM that gives a nice reply
    async def fake_llm(prompt: str) -> str:
        if "Their name is" in prompt:
            return "Nice to meet you, Ammar Ahmer! I'll remember your name. 👋"
        if "They're sharing bio info" in prompt or "They shared" in prompt:
            return "Got it — I've noted that."
        if "They're telling you they" in prompt or "They " in prompt:
            return "Cool, I'll remember that."
        return "OK"

    # Track memory stores
    stored = []
    async def fake_memory_store(content: str, metadata: dict) -> bool:
        stored.append({"content": content, "metadata": metadata})
        return True

    middle = MiddleAgent(
        classifier=classifier,
        acknowledger=acknowledger,
        llm=fake_llm,
        memory_store_fn=fake_memory_store,
    )

    async def task_runner(task_id: str, desc: str) -> dict:
        return {"summary": "should not be called", "artifacts": [], "completed_steps": []}

    async def instant_answer(prompt: str) -> str:
        return "should not be called for memory_store"

    orch = ConversationalOrchestrator(
        classifier=classifier,
        acknowledger=acknowledger,
        middle_agent=middle,
        task_runner=task_runner,
        instant_answer_fn=instant_answer,
        progress_check_interval=999,
    )

    await orch.start()
    events_q = orch.subscribe()
    events = []

    async def collect():
        while True:
            try:
                ev = await asyncio.wait_for(events_q.get(), timeout=0.5)
                events.append(ev)
            except asyncio.TimeoutError:
                break

    collector = asyncio.create_task(collect())

    # THE TEST: send "i am Ammar Ahmer"
    print("\n>>> USER: i am Ammar Ahmer")
    await orch.handle_user_input("i am Ammar Ahmer")
    await asyncio.sleep(0.3)

    collector.cancel()
    try:
        await collector
    except asyncio.CancelledError:
        pass

    # Verify
    print(f"\n  Events emitted: {len(events)}")
    for ev in events:
        print(f"    [{ev.type.value}] {ev.message[:80]}")

    # Should be INSTANT_ANSWER (not BEFORE_WORK)
    types = [e.type for e in events]
    assert ConversationEventType.INSTANT_ANSWER in types, "Should emit INSTANT_ANSWER, not BEFORE_WORK"
    assert ConversationEventType.BEFORE_WORK not in types, "Should NOT emit BEFORE_WORK (was the bug)"

    # Memory should have been stored
    assert len(stored) == 1, f"Should have stored 1 memory, got {len(stored)}"
    print(f"\n  Memory stored: {stored[0]['content']}")
    assert "Ammar" in stored[0]["content"]

    # Reply should mention Ammar
    reply = events[0].message
    assert "Ammar" in reply or "Nice to meet" in reply, f"Reply should greet user by name, got: {reply}"
    print(f"  Reply: {reply}")

    await orch.stop()
    print("\n  ✅ 'i am Ammar Ahmer' now correctly triggers memory store + greeting")
    return True


async def main():
    success = True
    success &= await test_classifier_fix()
    success &= await test_orchestrator_with_memory_store()

    print("\n" + "=" * 60)
    if success:
        print("  ✅ ALL FIXES VERIFIED")
    else:
        print("  ❌ Some tests failed")
    print("=" * 60)
    return success


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
