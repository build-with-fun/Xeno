"""Test the Conversational Orchestrator (Phase 12: middle agent + acks)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def test_classifier():
    print("\n=== Input Classifier ===")
    from xeno.middle.classifier import InputClassifier, InputType

    clf = InputClassifier()

    cases = [
        ("hi", InputType.GENERAL_TALK),
        ("hey how are you", InputType.GENERAL_TALK),
        ("thanks!", InputType.GENERAL_TALK),
        ("what's the weather?", InputType.QUICK_RESEARCH),
        ("what is Python?", InputType.QUICK_RESEARCH),
        ("what do you remember about my preferences?", InputType.MEMORY_QUERY),
        ("remind me to call mom at 5pm", InputType.SCHEDULING),
        ("every day at 8am remind me to exercise", InputType.SCHEDULING),
        ("/status", InputType.COMMAND),
        ("/help", InputType.COMMAND),
        ("build me a website", InputType.TASK),
        ("create a portfolio project", InputType.TASK),
        ("write a report on AI", InputType.TASK),
        ("debug this code", InputType.TASK),
        ("what is 2+2?", InputType.SHORT_QUESTION),
    ]

    passed = 0
    for text, expected in cases:
        result = await clf.classify(text, has_running_task=False)
        ok = result.input_type == expected
        status = "✓" if ok else "✗"
        print(f"  {status} '{text[:30]}' → {result.input_type.value} (expected {expected.value}, conf={result.confidence:.2f})")
        if ok:
            passed += 1
    print(f"\n  Classifier: {passed}/{len(cases)} passed")
    assert passed >= 12, f"Too many classifier failures: {passed}/{len(cases)}"


async def test_acknowledger():
    print("\n=== Task Acknowledger ===")
    from xeno.middle.acknowledger import TaskAcknowledger, AcknowledgmentType

    ack = TaskAcknowledger()

    # Before work
    a1 = await ack.acknowledge_start(
        task_id="t1",
        task_label="build website",
        description="build a portfolio site",
        estimated_seconds=180,
        subtasks=["Design", "HTML", "CSS", "JS"],
    )
    assert a1.type == AcknowledgmentType.BEFORE_WORK
    assert "build website" in a1.message
    assert "3min" in a1.message
    print(f"  ✓ BEFORE_WORK: {a1.message[:80]}...")

    # Progress
    a2 = await ack.acknowledge_progress(
        task_id="t1",
        task_label="build website",
        elapsed_seconds=60,
        estimated_seconds=180,
        completed_steps=["Design", "HTML"],
        remaining_steps=["CSS", "JS"],
        last_action="wrote index.html",
    )
    assert a2.type == AcknowledgmentType.PROGRESS
    assert "1min" in a2.message
    print(f"  ✓ PROGRESS: {a2.message[:80]}...")

    # After work (complete)
    a3 = await ack.acknowledge_complete(
        task_id="t1",
        task_label="build website",
        summary="Created a 4-page portfolio site with dark theme.",
        artifacts=["workspace/portfolio/index.html", "workspace/portfolio/about.html", "workspace/portfolio/css/style.css"],
        elapsed_seconds=165,
        completed_steps=["Design", "HTML", "CSS", "JS"],
    )
    assert a3.type == AcknowledgmentType.AFTER_WORK
    assert "Done" in a3.message
    assert "index.html" in a3.message
    print(f"  ✓ AFTER_WORK: {a3.message[:80]}...")

    # Partial done
    a4 = await ack.acknowledge_complete(
        task_id="t2",
        task_label="multi-part task",
        summary="Did 3 of 4 parts.",
        artifacts=["file1.txt", "file2.txt"],
        elapsed_seconds=120,
        completed_steps=["Part 1", "Part 2", "Part 3"],
        remaining_steps=["Part 4"],
    )
    assert a4.type == AcknowledgmentType.PARTIAL_DONE
    assert "Partially done" in a4.message
    print(f"  ✓ PARTIAL_DONE: {a4.message[:80]}...")

    # Failure
    a5 = await ack.acknowledge_failure(
        task_id="t3",
        task_label="failing task",
        error="ConnectionRefusedError",
        partial_result="Got halfway",
        elapsed_seconds=30,
        completed_steps=["Step 1"],
    )
    assert a5.type == AcknowledgmentType.AFTER_FAILURE
    assert "Couldn't finish" in a5.message
    print(f"  ✓ AFTER_FAILURE: {a5.message[:80]}...")


async def test_middle_agent():
    print("\n=== Middle Agent (handles queries during running tasks) ===")
    from xeno.middle.classifier import InputClassifier
    from xeno.middle.acknowledger import TaskAcknowledger
    from xeno.middle.agent import MiddleAgent

    # Fake LLM
    async def fake_llm(prompt: str) -> str:
        if "weather" in prompt.lower():
            return "It's 72°F and sunny."
        if "memory" in prompt.lower() and "results" in prompt.lower():
            return "From memory: you prefer dark themes and Python."
        if "Assistant:" in prompt:
            return "Hi there! Still working on your task."
        return "OK"

    # Fake tools
    async def fake_web_search(query: str, n: int) -> str:
        return f"Search results for {query}: 72°F, sunny, light wind."

    async def fake_memory_recall(query: str) -> str:
        return "Memory: user prefers dark themes, uses Python, likes minimal design."

    async def fake_progress(task_id: str) -> dict:
        return {
            "elapsed_seconds": 60,
            "estimated_seconds": 180,
            "completed_steps": ["Design"],
            "remaining_steps": ["HTML", "CSS", "JS"],
            "last_action": "wrote sketch",
        }

    classifier = InputClassifier()
    acknowledger = TaskAcknowledger()
    middle = MiddleAgent(
        classifier=classifier,
        acknowledger=acknowledger,
        llm=fake_llm,
        web_search_fn=fake_web_search,
        memory_recall_fn=fake_memory_recall,
        progress_fn=fake_progress,
    )

    # Test general talk
    r1 = await middle.handle_query("hi", running_task_id="t1", running_task_label="building site")
    assert r1.answered
    assert "Hi" in r1.answer or "Still working" in r1.answer
    print(f"  ✓ Greeting: {r1.answer[:60]}")

    # Test quick research
    r2 = await middle.handle_query("what's the weather?", running_task_id="t1", running_task_label="building site")
    assert r2.answered
    assert "72" in r2.answer
    assert "web_search" in r2.used_tools
    print(f"  ✓ Quick research: {r2.answer[:60]}")

    # Test memory query
    r3 = await middle.handle_query("what do you remember about my preferences?", running_task_id="t1", running_task_label="building site")
    assert r3.answered
    assert "memory_recall" in r3.used_tools
    print(f"  ✓ Memory query: {r3.answer[:60]}")

    # Test progress query
    r4 = await middle.handle_query("what's the status of my task?", running_task_id="t1", running_task_label="building site")
    assert r4.answered
    print(f"  ✓ Progress query: {r4.answer[:80]}")

    # Test that real task gets queued
    r5 = await middle.handle_query("build me another website", running_task_id="t1", running_task_label="building site")
    assert not r5.answered
    assert r5.queued_for_later
    print(f"  ✓ Task queued: {r5.queue_reason[:60]}")


async def test_orchestrator():
    print("\n=== Conversational Orchestrator (end-to-end) ===")
    from xeno.middle.classifier import InputClassifier
    from xeno.middle.acknowledger import TaskAcknowledger, AcknowledgmentType
    from xeno.middle.agent import MiddleAgent
    from xeno.middle.orchestrator import ConversationalOrchestrator, ConversationEventType

    classifier = InputClassifier()
    acknowledger = TaskAcknowledger()

    async def fake_llm(prompt: str) -> str:
        if "weather" in prompt.lower():
            return "It's 72°F and sunny."
        return "OK"

    async def fake_web_search(query: str, n: int) -> str:
        return "Search results: 72°F sunny"

    middle = MiddleAgent(
        classifier=classifier,
        acknowledger=acknowledger,
        llm=fake_llm,
        web_search_fn=fake_web_search,
    )

    # Fake task runner — simulates a 1-second task
    async def fake_task_runner(task_id: str, description: str) -> dict:
        await asyncio.sleep(1.0)
        return {
            "summary": f"Did the task: {description[:60]}",
            "artifacts": ["workspace/test/output.txt"],
            "completed_steps": ["Plan", "Execute", "Verify"],
        }

    async def fake_instant_answer(prompt: str) -> str:
        return f"Instant answer to: {prompt[:30]}"

    orch = ConversationalOrchestrator(
        classifier=classifier,
        acknowledger=acknowledger,
        middle_agent=middle,
        task_runner=fake_task_runner,
        instant_answer_fn=fake_instant_answer,
        progress_check_interval=10.0,  # don't fire progress in this short test
    )

    await orch.start()
    events_queue = orch.subscribe()
    events: list = []

    async def collect_events():
        while True:
            try:
                ev = await asyncio.wait_for(events_queue.get(), timeout=2.0)
                events.append(ev)
            except asyncio.TimeoutError:
                break

    collector = asyncio.create_task(collect_events())

    # Scenario 1: Quick reply (no running task)
    print("  Test 1: Quick reply (no task running)")
    await orch.handle_user_input("what's the weather?")
    await asyncio.sleep(0.3)

    # Scenario 2: Task → ack → middle query → completion
    print("  Test 2: Task + middle query + completion")
    await orch.handle_user_input("build me a website")
    await asyncio.sleep(0.2)  # let BEFORE_WORK emit

    # While task is running, ask a middle query
    await orch.handle_user_input("what's the weather?")
    await asyncio.sleep(0.3)

    # Wait for task to complete
    await asyncio.sleep(1.5)

    # Scenario 3: Queue a task while one is running
    print("  Test 3: Queue task while one is running")
    # Start a long task
    async def long_task(task_id: str, desc: str) -> dict:
        await asyncio.sleep(2.0)
        return {"summary": "long task done", "artifacts": [], "completed_steps": []}
    orch.task_runner = long_task
    await orch.handle_user_input("build me another website")  # starts immediately (no running task now)
    await asyncio.sleep(0.2)
    await orch.handle_user_input("build a third one")  # should be queued (task 2 still running)
    await asyncio.sleep(0.3)

    # Cancel collector
    collector.cancel()
    try:
        await collector
    except asyncio.CancelledError:
        pass

    # Verify events
    print(f"\n  Total events emitted: {len(events)}")
    types_seen = [e.type.value for e in events]
    print(f"  Event types: {types_seen}")

    assert ConversationEventType.INSTANT_ANSWER.value in types_seen, "Should have instant answer event"
    assert ConversationEventType.BEFORE_WORK.value in types_seen, "Should have before_work event"
    assert ConversationEventType.MIDDLE_ANSWER.value in types_seen, "Should have middle_answer event"
    assert ConversationEventType.AFTER_WORK.value in types_seen, "Should have after_work event"
    assert ConversationEventType.QUEUED.value in types_seen, "Should have queued event"

    # Print the actual conversation flow
    print("\n  --- Conversation Flow ---")
    for ev in events:
        print(f"  [{ev.type.value}] {ev.message[:80]}")

    await orch.stop()
    print("\n  ✅ All orchestrator scenarios passed")


async def main():
    print("=" * 60)
    print("  Phase 12: Middle Agent + Before/After Work Acknowledgments")
    print("=" * 60)

    await test_classifier()
    await test_acknowledger()
    await test_middle_agent()
    await test_orchestrator()

    print("\n" + "=" * 60)
    print("  ✅ ALL PHASE 12 TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
