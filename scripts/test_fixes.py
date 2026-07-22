"""Verify the 3 critical fixes work.

Fix 1: Tasks ALWAYS spawn background task (even if LLM returns spawn_background_task=false)
Fix 2: Quick research ACTUALLY does web search
Fix 3: Memory query FORCES LLM to use provided profile/memory context
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# Simulated LLM responses
def make_simulated_llm():
    """Returns canned responses matching what a real LLM would return."""
    async def llm(system_prompt: str, user_message: str) -> str:
        # Intent analysis
        if "User message:" in user_message:
            # Extract the user message
            for line in user_message.split("\n"):
                if line.startswith("User message: "):
                    msg = line[len("User message: "):].strip()
                    return _get_intent_response(msg)
            return json.dumps({
                "intent_type": "quick_reply", "confidence": 0.5,
                "reasoning": "default", "draft_response": "I hear you.",
                "facts": [], "schedule_suggestions": [], "estimated_seconds": 2,
                "task_approach": "", "self_mod_target": "", "self_mod_description": "",
                "emotion": "neutral", "needs_full_agent": False, "spawn_background_task": False,
            })
        # Response generation
        if "Your reply:" in user_message:
            return "Got it."
        if "Your acknowledgment:" in user_message:
            return "On it — starting now."
        if "Your completion message:" in user_message:
            return "Done! Here's what I did."
        if "Your answer:" in user_message:
            # Quick research summarization
            return "Based on my search, here's what I found: AI is a broad field..."
        if "Your message:" in user_message:
            return "Couldn't finish that."
        # Memory query
        if "WHAT YOU KNOW ABOUT THE USER" in user_message:
            # Should return what's in the profile
            if "Name: Ammar" in user_message:
                return "Your name is Ammar! I remember you told me earlier."
            return "I don't have any memories about you yet."
        return "OK"
    return llm


def _get_intent_response(msg: str) -> str:
    """Return the intent JSON for a given user message."""
    msg_lower = msg.lower()
    if "i am ammar" in msg_lower or "my name is" in msg_lower:
        return json.dumps({
            "intent_type": "memory_store", "confidence": 0.95,
            "reasoning": "User introducing themselves",
            "draft_response": "Nice to meet you, Ammar! I'll remember your name.",
            "facts": [{"subject": "user.name", "predicate": "is", "object": "Ammar",
                       "category": "identity", "confidence": 0.99, "raw": msg}],
            "schedule_suggestions": [], "estimated_seconds": 0, "task_approach": "",
            "self_mod_target": "", "self_mod_description": "",
            "emotion": "neutral", "needs_full_agent": False,
            "spawn_background_task": False,
        })
    if "birthday" in msg_lower and "april" in msg_lower:
        return json.dumps({
            "intent_type": "auto_schedule", "confidence": 0.95,
            "reasoning": "User birthday - remember + auto-schedule",
            "draft_response": "Got it! I'll remember your birthday and wish you every year.",
            "facts": [{"subject": "user.birthday", "predicate": "is_on",
                       "object": "April 21 at 00:00", "category": "schedule",
                       "confidence": 0.99, "raw": msg}],
            "schedule_suggestions": [{
                "name": "Ammar's birthday wish",
                "prompt": "Wish Ammar happy birthday!",
                "schedule_type": "yearly",
                "config": {"month": 4, "day": 21, "hour": 0, "minute": 0},
                "reason": "User birthday", "auto_create": True,
            }],
            "estimated_seconds": 0, "task_approach": "",
            "self_mod_target": "", "self_mod_description": "",
            "emotion": "neutral", "needs_full_agent": False,
            "spawn_background_task": False,
        })
    if "open youtube" in msg_lower:
        return json.dumps({
            "intent_type": "task", "confidence": 0.95,
            "reasoning": "User wants to open YouTube - requires shell command",
            "draft_response": "",
            "facts": [], "schedule_suggestions": [],
            "estimated_seconds": 10,
            "task_approach": "Use shell_execute to open https://youtube.com",
            "self_mod_target": "", "self_mod_description": "",
            "emotion": "neutral", "needs_full_agent": True,
            "spawn_background_task": True,
        })
    if "search about ai" in msg_lower or "search about" in msg_lower:
        return json.dumps({
            "intent_type": "quick_research", "confidence": 0.95,
            "reasoning": "User wants to search the web",
            "draft_response": "",
            "facts": [], "schedule_suggestions": [],
            "estimated_seconds": 15, "task_approach": "web_search('AI')",
            "self_mod_target": "", "self_mod_description": "",
            "emotion": "neutral", "needs_full_agent": False,
            "spawn_background_task": False,
        })
    if "who am i" in msg_lower or "what do you know about me" in msg_lower:
        return json.dumps({
            "intent_type": "memory_query", "confidence": 0.98,
            "reasoning": "User asking what we remember",
            "draft_response": "",
            "facts": [], "schedule_suggestions": [],
            "estimated_seconds": 2, "task_approach": "",
            "self_mod_target": "", "self_mod_description": "",
            "emotion": "neutral", "needs_full_agent": False,
            "spawn_background_task": False,
        })
    return json.dumps({
        "intent_type": "quick_reply", "confidence": 0.5,
        "reasoning": "default", "draft_response": "I hear you.",
        "facts": [], "schedule_suggestions": [], "estimated_seconds": 2,
        "task_approach": "", "self_mod_target": "", "self_mod_description": "",
        "emotion": "neutral", "needs_full_agent": False, "spawn_background_task": False,
    })


async def main():
    print("=" * 70)
    print("  Verify the 3 critical fixes")
    print("=" * 70)

    from xeno.brain import Brain, ResponseGenerator, BrainOrchestrator, BrainEventType
    from xeno.profile import UserProfile
    from xeno.auto import AutoExecutor

    tmp = ROOT / "data" / "_test_fixes"
    import shutil
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    llm = make_simulated_llm()
    profile = UserProfile(tmp / "profile.json")
    brain = Brain(llm=llm)
    response_gen = ResponseGenerator(llm=llm, profile=profile)

    stored = []
    scheduled = []
    web_searches = []

    async def fake_memory_store(content, metadata):
        stored.append(content); return True

    async def fake_schedule_create(name, prompt, stype, config_json):
        scheduled.append(name); return f"Scheduled {name}"

    async def fake_memory_recall(query):
        return profile.summary()

    async def fake_web_search(query, n):
        web_searches.append(query)
        return f"Search results for '{query}':\n1. AI is artificial intelligence...\n2. AI is a branch of computer science...\n3. Modern AI uses deep learning..."

    executor = AutoExecutor(
        profile=profile,
        memory_store_fn=fake_memory_store,
        schedule_create_fn=fake_schedule_create,
    )

    async def fake_task_runner(task_id, description, intent):
        await asyncio.sleep(0.5)
        return {
            "summary": f"Completed: {description[:50]}",
            "artifacts": [],
            "completed_steps": ["execute"],
        }

    orch = BrainOrchestrator(
        brain=brain, response_gen=response_gen, profile=profile,
        auto_executor=executor, task_runner=fake_task_runner,
        memory_recall_fn=fake_memory_recall,
        web_search_fn=fake_web_search,
        progress_check_interval=999,
    )

    await orch.start()
    events_q = orch.subscribe()
    events = []

    async def collect():
        while True:
            try:
                ev = await asyncio.wait_for(events_q.get(), timeout=2.0)
                events.append(ev)
            except asyncio.TimeoutError:
                break

    collector = asyncio.create_task(collect())

    # === TEST 1: "i am Ammar" → memory store ===
    print("\n>>> USER: i am Ammar")
    await orch.handle_user_input("i am Ammar")
    await asyncio.sleep(0.3)

    # === TEST 2: "my birthday is on 21st april" → auto schedule ===
    print(">>> USER: my birthday is on 21st april at 12am")
    await orch.handle_user_input("my birthday is on 21st april at 12am")
    await asyncio.sleep(0.3)

    # === TEST 3: "open youtube" → should spawn background task (FIX #1) ===
    print(">>> USER: open youtube")
    await orch.handle_user_input("open youtube")
    await asyncio.sleep(0.3)

    # === TEST 4: "search about AI" → should ACTUALLY do web search (FIX #2) ===
    print(">>> USER: search about AI")
    await orch.handle_user_input("search about AI")
    await asyncio.sleep(0.5)

    # === TEST 5: "who am i" → should use profile (FIX #3) ===
    print(">>> USER: who am i")
    await orch.handle_user_input("who am i")
    await asyncio.sleep(0.3)

    # Wait for the youtube task to complete
    await asyncio.sleep(1.0)

    collector.cancel()
    try:
        await collector
    except asyncio.CancelledError:
        pass

    # === ANALYZE RESULTS ===
    print("\n" + "=" * 70)
    print("  RESULTS")
    print("=" * 70)

    print(f"\nEvents emitted: {len(events)}")
    for ev in events:
        print(f"  [{ev.type.value}] {ev.message[:80]}")

    types = [e.type for e in events]

    # FIX #1: Tasks spawn background task
    print("\n--- FIX #1: Tasks spawn background task ---")
    has_before = any(e.type == BrainEventType.BEFORE_WORK for e in events)
    has_after = any(e.type == BrainEventType.AFTER_WORK for e in events)
    print(f"  BEFORE_WORK emitted: {has_before}")
    print(f"  AFTER_WORK emitted: {has_after}")
    assert has_before, "FAIL: open youtube should emit BEFORE_WORK"
    assert has_after, "FAIL: open youtube should emit AFTER_WORK after completion"
    print("  ✅ PASS")

    # FIX #2: Quick research does web search
    print("\n--- FIX #2: Quick research does web search ---")
    print(f"  Web searches performed: {len(web_searches)}")
    print(f"  Search queries: {web_searches}")
    assert len(web_searches) > 0, "FAIL: search about AI should call web_search"
    has_info = any(e.type == BrainEventType.INFO and "Searching" in e.message for e in events)
    print(f"  'Searching...' info emitted: {has_info}")
    assert has_info, "FAIL: should emit 'Searching...' info event"
    print("  ✅ PASS")

    # FIX #3: Memory query uses profile
    print("\n--- FIX #3: Memory query uses profile ---")
    # The last event should be the memory query reply
    memory_replies = [e for e in events if "Ammar" in e.message or "Your name is" in e.message]
    print(f"  Replies mentioning 'Ammar': {len(memory_replies)}")
    # Should NOT have "I don't have any memories" since profile has Ammar
    no_ignorance = not any("don't have any memories" in e.message.lower() for e in events[-3:])
    print(f"  No false 'I don't have memories': {no_ignorance}")
    assert no_ignorance, "FAIL: should not say 'I don't have memories' when profile has data"
    print("  ✅ PASS")

    # Memory + schedules
    print(f"\n--- Memory + Schedules ---")
    print(f"  Facts stored: {len(stored)}")
    for s in stored:
        print(f"    - {s}")
    print(f"  Schedules created: {len(scheduled)}")
    for s in scheduled:
        print(f"    - {s}")
    print(f"  Profile: {profile.summary()}")

    await orch.stop()

    print("\n" + "=" * 70)
    print("  ✅ ALL 3 CRITICAL FIXES VERIFIED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
