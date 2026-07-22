"""End-to-end demo: shows the before/after work + middle query pattern.

Run: python scripts/demo_before_after.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


async def main():
    from xeno.middle.classifier import InputClassifier
    from xeno.middle.acknowledger import TaskAcknowledger
    from xeno.middle.agent import MiddleAgent
    from xeno.middle.orchestrator import (
        ConversationalOrchestrator, ConversationEventType,
    )

    print("=" * 70)
    print("  Xeno 2.0 — Before/After Work + Middle Query Demo")
    print("=" * 70)
    print()
    print("  This demo simulates a full conversation:")
    print("  1. User asks a quick question → instant answer")
    print("  2. User gives a long task → 'I'll do this' ack + task starts")
    print("  3. While task runs, user asks middle queries → answered in parallel")
    print("  4. Task completes → 'Done! Here's the result' ack")
    print("  5. New task starts (queued earlier) → 'Now starting queued task'")
    print()
    print("-" * 70)

    # Fake LLM that simulates a real agent's responses
    async def fake_llm(prompt: str) -> str:
        prompt_lower = prompt.lower()
        if "weather" in prompt_lower:
            return "It's currently 72°F and sunny in your area, with light wind from the west."
        if "memory" in prompt_lower and "results" in prompt_lower:
            return "Based on memory: you prefer dark themes, work mainly in Python, and like minimal design."
        if "assistant:" in prompt_lower:
            return "Hi there! I'm still working on your task in the background. What else can I help with?"
        if "question:" in prompt_lower:
            return "Python is a high-level programming language known for its readability and versatility."
        # Task responses
        if "build" in prompt_lower and "website" in prompt_lower:
            return "I've created a 4-page portfolio website with dark theme. Pages: index, about, projects, contact. CSS uses a modern minimal aesthetic. JavaScript adds smooth scrolling and form validation."
        if "report" in prompt_lower:
            return "I've written a 5-page report on AI, covering: history, current state, key technologies, ethical considerations, and future directions."
        return "OK"

    async def fake_web_search(query: str, n: int) -> str:
        return "Weather: 72°F sunny. News: tech industry growing. Stock: AAPL up 2%."

    async def fake_memory_recall(query: str) -> str:
        return "Memory: user prefers dark themes, uses Python, likes minimal design, works on web projects."

    classifier = InputClassifier()
    acknowledger = TaskAcknowledger(llm_generator=fake_llm, use_llm=False)
    middle_agent = MiddleAgent(
        classifier=classifier,
        acknowledger=acknowledger,
        llm=fake_llm,
        web_search_fn=fake_web_search,
        memory_recall_fn=fake_memory_recall,
    )

    # Simulate a long-running task
    async def task_runner(task_id: str, description: str) -> dict:
        # Simulate work being done — takes 2 seconds
        for i in range(4):
            await asyncio.sleep(0.5)
            # Update progress
            orch.update_task_progress(
                task_id=task_id,
                completed_step=f"Step {i+1}",
                last_action=f"working on step {i+1}",
            )
        if "website" in description.lower():
            return {
                "summary": "Created a 4-page portfolio website with dark theme. Pages: index.html, about.html, projects.html, contact.html. CSS at workspace/portfolio/css/style.css with modern minimal aesthetic. JavaScript adds smooth scrolling and form validation.",
                "artifacts": [
                    "workspace/portfolio/index.html",
                    "workspace/portfolio/about.html",
                    "workspace/portfolio/projects.html",
                    "workspace/portfolio/contact.html",
                    "workspace/portfolio/css/style.css",
                    "workspace/portfolio/js/script.js",
                ],
                "completed_steps": ["Design layout", "Write HTML", "Add CSS", "Add JS"],
            }
        elif "report" in description.lower():
            return {
                "summary": "Wrote a 5-page report on AI covering history, current state, key technologies, ethics, and future directions.",
                "artifacts": ["workspace/reports/ai_report.pdf"],
                "completed_steps": ["Research", "Outline", "Write", "Format"],
            }
        return {
            "summary": f"Task completed: {description[:100]}",
            "artifacts": [],
            "completed_steps": ["Plan", "Execute", "Verify"],
        }

    async def instant_answer(prompt: str) -> str:
        return await fake_llm(prompt)

    orch = ConversationalOrchestrator(
        classifier=classifier,
        acknowledger=acknowledger,
        middle_agent=middle_agent,
        task_runner=task_runner,
        instant_answer_fn=instant_answer,
        progress_check_interval=999,  # disable auto-progress for demo
    )

    await orch.start()
    events_q = orch.subscribe()

    # Collect + display events
    async def display_events():
        while True:
            try:
                ev = await asyncio.wait_for(events_q.get(), timeout=0.3)
                icon = {
                    ConversationEventType.BEFORE_WORK: "🚀",
                    ConversationEventType.MIDDLE_ANSWER: "💬",
                    ConversationEventType.INSTANT_ANSWER: "💬",
                    ConversationEventType.PROGRESS: "⏳",
                    ConversationEventType.AFTER_WORK: "✅",
                    ConversationEventType.AFTER_FAILURE: "❌",
                    ConversationEventType.PARTIAL_DONE: "⚠️",
                    ConversationEventType.QUEUED: "📋",
                    ConversationEventType.QUEUE_STARTED: "▶️",
                    ConversationEventType.SUBTASK_START: "→",
                    ConversationEventType.INFO: "ℹ️",
                }.get(ev.type, "•")
                print(f"\n{icon} [{ev.type.value}]")
                print(f"   {ev.message}")
                print()
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    display_task = asyncio.create_task(display_events())

    # Simulate the user conversation
    print("\n>>> USER: what's the weather?")
    await orch.handle_user_input("what's the weather?")
    await asyncio.sleep(0.5)

    print("\n>>> USER: build me a portfolio website")
    await orch.handle_user_input("build me a portfolio website")
    await asyncio.sleep(0.3)  # let BEFORE_WORK emit

    # Middle queries while task is running
    print("\n>>> USER: what do you remember about my preferences?")
    await orch.handle_user_input("what do you remember about my preferences?")
    await asyncio.sleep(0.5)

    print("\n>>> USER: what is Python?")
    await orch.handle_user_input("what is Python?")
    await asyncio.sleep(0.5)

    print("\n>>> USER: hi")
    await orch.handle_user_input("hi")
    await asyncio.sleep(0.5)

    # Queue another task while one is running
    print("\n>>> USER: also write me a report on AI when you have time")
    await orch.handle_user_input("also write me a report on AI when you have time")
    await asyncio.sleep(0.5)

    # Wait for first task to complete + second queued task to start + complete
    print("\n>>> (waiting for tasks to complete...)")
    await asyncio.sleep(5.0)

    # Stop
    display_task.cancel()
    try:
        await display_task
    except asyncio.CancelledError:
        pass
    await orch.stop()

    print("\n" + "=" * 70)
    print("  ✅ Demo complete — before/after work + middle queries all working")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
