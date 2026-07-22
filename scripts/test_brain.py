"""Test the new LLM-driven Brain with birthday auto-scheduling.

Run: python scripts/test_brain.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


# A fake LLM that simulates what a real LLM would return for each message
# (so we can test without needing an API key)
FAKE_LLM_RESPONSES = {
    # "i am Ammar Ahmer"
    "i am Ammar Ahmer": json.dumps({
        "intent_type": "memory_store",
        "confidence": 0.95,
        "reasoning": "User is introducing themselves by name",
        "draft_response": "Nice to meet you, Ammar Ahmer! I'll remember your name.",
        "facts": [{
            "subject": "user.name",
            "predicate": "is",
            "object": "Ammar Ahmer",
            "category": "identity",
            "confidence": 0.99,
            "raw": "i am Ammar Ahmer",
        }],
        "schedule_suggestions": [],
        "estimated_seconds": 0,
        "task_approach": "",
        "self_mod_target": "",
        "self_mod_description": "",
        "emotion": "neutral",
        "needs_full_agent": False,
        "spawn_background_task": False,
    }),

    # "my birthday is on 21st april at 12am"
    "my birthday is on 21st april at 12am": json.dumps({
        "intent_type": "auto_schedule",
        "confidence": 0.95,
        "reasoning": "User is telling us their birthday — should be remembered AND auto-scheduled",
        "draft_response": "Got it! I'll remember your birthday is April 21 at midnight, and I'll wish you happy birthday every year. 🎂",
        "facts": [{
            "subject": "user.birthday",
            "predicate": "is_on",
            "object": "April 21 at 00:00",
            "category": "schedule",
            "confidence": 0.99,
            "raw": "my birthday is on 21st april at 12am",
        }],
        "schedule_suggestions": [{
            "name": "Ammar's birthday wish",
            "prompt": "It's Ammar's birthday today! Wish him a warm, personal happy birthday message. Be creative — vary the message each year. Mention something you appreciate about him based on your memory.",
            "schedule_type": "yearly",
            "config": {"month": 4, "day": 21, "hour": 0, "minute": 0},
            "reason": "User told us their birthday is April 21 at midnight",
            "auto_create": True,
        }],
        "estimated_seconds": 0,
        "task_approach": "",
        "self_mod_target": "",
        "self_mod_description": "",
        "emotion": "neutral",
        "needs_full_agent": False,
        "spawn_background_task": False,
    }),

    # "build me a website"
    "build me a website": json.dumps({
        "intent_type": "task",
        "confidence": 0.95,
        "reasoning": "User wants a website built — this is real work",
        "draft_response": "",
        "facts": [],
        "schedule_suggestions": [],
        "estimated_seconds": 180,
        "task_approach": "1. Plan site structure 2. Generate HTML 3. Write CSS 4. Add JS 5. Test",
        "self_mod_target": "",
        "self_mod_description": "",
        "emotion": "neutral",
        "needs_full_agent": True,
        "spawn_background_task": True,
    }),

    # "what's my name?"
    "what's my name?": json.dumps({
        "intent_type": "memory_query",
        "confidence": 0.95,
        "reasoning": "User is asking what we remember about them",
        "draft_response": "",
        "facts": [],
        "schedule_suggestions": [],
        "estimated_seconds": 2,
        "task_approach": "",
        "self_mod_target": "",
        "self_mod_description": "",
        "emotion": "neutral",
        "needs_full_agent": False,
        "spawn_background_task": False,
    }),

    # "i'm tired"
    "i'm tired": json.dumps({
        "intent_type": "emotional",
        "confidence": 0.85,
        "reasoning": "User is expressing fatigue",
        "draft_response": "Sorry to hear that. Take a break — I'll keep working on your stuff in the background if you need me to.",
        "facts": [],
        "schedule_suggestions": [],
        "estimated_seconds": 2,
        "task_approach": "",
        "self_mod_target": "",
        "self_mod_description": "",
        "emotion": "tired",
        "needs_full_agent": False,
        "spawn_background_task": False,
    }),
}


async def make_fake_llm():
    """Create a fake LLM that returns canned responses for known inputs,
    and natural-language responses for reply-generation prompts."""
    async def fake_llm(system_prompt: str, user_message: str) -> str:
        # 1. For intent analysis: return the JSON intent
        # (the user_message contains "User message: X")
        if "User message:" in user_message:
            for key, response in FAKE_LLM_RESPONSES.items():
                if key in user_message:
                    return response
            # Default intent
            return json.dumps({
                "intent_type": "quick_reply",
                "confidence": 0.5,
                "reasoning": "default",
                "draft_response": "I hear you.",
                "facts": [],
                "schedule_suggestions": [],
                "estimated_seconds": 2,
                "task_approach": "",
                "self_mod_target": "",
                "self_mod_description": "",
                "emotion": "neutral",
                "needs_full_agent": False,
                "spawn_background_task": False,
            })

        # 2. For response generation: return natural language
        if "Your reply:" in user_message:
            return "Got it — thanks for sharing that with me."
        if "Your acknowledgment:" in user_message:
            return "On it — starting now. Will let you know when it's done."
        if "Your completion message:" in user_message:
            return "Done! I've finished what you asked."
        if "Your progress update:" in user_message:
            return "Still working — making good progress."
        if "Your message:" in user_message:
            return "Couldn't finish that, but I can try a different approach."
        if "Memory results:" in user_message:
            return "Based on what I remember, your name is Ammar Ahmer."

        # 3. For self-mod code generation
        if "Output the full file content:" in user_message:
            return "def new_tool():\n    return 'hello'\n"

        return "OK"
    return fake_llm


async def test_brain_analyze():
    print("\n=== Test 1: Brain analyzes 'i am Ammar Ahmer' ===")
    from xeno.brain import Brain, IntentType

    fake_llm = await make_fake_llm()
    brain = Brain(llm=fake_llm)

    intent = await brain.analyze("i am Ammar Ahmer")
    print(f"  Intent: {intent.intent_type.value} (conf={intent.confidence:.2f})")
    print(f"  Reasoning: {intent.reasoning}")
    print(f"  Facts: {len(intent.facts)}")
    for f in intent.facts:
        print(f"    - {f.subject} {f.predicate} {f.object} ({f.category})")
    print(f"  Draft: {intent.draft_response}")

    assert intent.intent_type == IntentType.MEMORY_STORE
    assert len(intent.facts) == 1
    assert intent.facts[0].object == "Ammar Ahmer"
    print("  [PASS] PASS")


async def test_brain_birthday():
    print("\n=== Test 2: Brain auto-detects birthday -> schedules yearly wish ===")
    from xeno.brain import Brain, IntentType

    fake_llm = await make_fake_llm()
    brain = Brain(llm=fake_llm)

    intent = await brain.analyze("my birthday is on 21st april at 12am")
    print(f"  Intent: {intent.intent_type.value}")
    print(f"  Facts: {len(intent.facts)}")
    for f in intent.facts:
        print(f"    - {f.subject} {f.predicate} {f.object} ({f.category})")
    print(f"  Schedule suggestions: {len(intent.schedule_suggestions)}")
    for s in intent.schedule_suggestions:
        print(f"    - {s.name} | {s.schedule_type} | auto_create={s.auto_create}")
        print(f"      config: {s.config}")
        print(f"      prompt: {s.prompt[:80]}...")

    assert intent.intent_type == IntentType.AUTO_SCHEDULE
    assert len(intent.schedule_suggestions) == 1
    sched = intent.schedule_suggestions[0]
    assert sched.schedule_type == "yearly"
    assert sched.config["month"] == 4
    assert sched.config["day"] == 21
    assert sched.auto_create is True
    print("  [PASS] PASS — birthday detected + yearly wish scheduled")


async def test_profile_persistence():
    print("\n=== Test 3: User Profile stores facts + persists to disk ===")
    from xeno.profile import UserProfile

    tmp = ROOT / "data" / "_test_brain"
    import shutil
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    profile = UserProfile(tmp / "profile.json")

    # Initially empty
    assert profile.get("identity.name") == ""
    print("  [OK] Initial profile is empty")

    # Store a fact
    profile.update_from_fact(
        subject="user.name",
        predicate="is",
        obj="Ammar Ahmer",
        category="identity",
    )
    assert profile.get("identity.name") == "Ammar Ahmer"
    print(f"  [OK] Stored name: {profile.get('identity.name')}")

    # Store birthday
    profile.update_from_fact(
        subject="user.birthday",
        predicate="is_on",
        obj="April 21 at 00:00",
        category="schedule",
    )
    print(f"  [OK] Stored birthday: {profile.get('schedule_events')}")

    # Reload from disk
    profile2 = UserProfile(tmp / "profile.json")
    assert profile2.get("identity.name") == "Ammar Ahmer"
    print(f"  [OK] Reloaded from disk: name={profile2.get('identity.name')}")

    # Summary
    summary = profile.summary()
    assert "Ammar Ahmer" in summary
    print(f"\n  Profile summary:\n{summary}")
    print("  [PASS] PASS")


async def test_auto_executor():
    print("\n=== Test 4: AutoExecutor stores facts + creates schedules ===")
    from xeno.brain import Brain
    from xeno.profile import UserProfile
    from xeno.auto import AutoExecutor

    tmp = ROOT / "data" / "_test_brain"
    profile = UserProfile(tmp / "profile.json")
    fake_llm = await make_fake_llm()
    brain = Brain(llm=fake_llm)

    # Track memory stores + schedule creates
    stored = []
    scheduled = []

    async def fake_memory_store(content: str, metadata: dict) -> bool:
        stored.append(content)
        return True

    async def fake_schedule_create(name: str, prompt: str, sched_type: str, config_json: str) -> str:
        scheduled.append({"name": name, "type": sched_type, "config": config_json})
        return f"Scheduled {name}"

    executor = AutoExecutor(
        profile=profile,
        memory_store_fn=fake_memory_store,
        schedule_create_fn=fake_schedule_create,
    )

    # Analyze + execute the birthday message
    intent = await brain.analyze("my birthday is on 21st april at 12am")
    result = await executor.execute(intent)

    print(f"  Facts stored: {len(result['facts_stored'])}")
    for f in result["facts_stored"]:
        print(f"    - {f['subject']} {f['predicate']} {f['object']}")
    print(f"  Schedules created: {len(result['schedules_created'])}")
    for s in result["schedules_created"]:
        print(f"    - {s['name']} ({s['schedule_type']})")

    assert len(result["facts_stored"]) == 1
    assert len(result["schedules_created"]) == 1
    assert "birthday" in result["schedules_created"][0]["name"].lower()
    print("  [PASS] PASS")


async def test_self_modifier_create_file():
    print("\n=== Test 5: SelfModifier can create new tool files ===")
    from xeno.self_mod import SelfModifier

    tmp = ROOT / "data" / "_test_self_mod"
    import shutil
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    # Create a fake project root
    project_root = tmp / "project"
    (project_root / "xeno" / "tools").mkdir(parents=True, exist_ok=True)

    modifier = SelfModifier(project_root=project_root)

    # Create a new tool
    result = await modifier.create_file(
        "xeno/tools/stock_prices.py",
        '''"""Stock price tool."""
def get_stock_price(symbol: str) -> str:
    """Get the current stock price for a symbol."""
    return f"Price for {symbol}: $100.00"
''',
        description="Fetch stock prices",
    )
    print(f"  Create file: success={result.success}, message={result.message}")
    assert result.success

    # Verify file exists
    assert (project_root / "xeno" / "tools" / "stock_prices.py").exists()
    print("  [PASS] PASS — new tool file created")


async def test_end_to_end_brain_orchestrator():
    print("\n=== Test 6: End-to-end BrainOrchestrator ===")
    from xeno.brain import Brain, ResponseGenerator, BrainOrchestrator, BrainEventType
    from xeno.profile import UserProfile
    from xeno.auto import AutoExecutor

    tmp = ROOT / "data" / "_test_brain_e2e"
    import shutil
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)

    fake_llm = await make_fake_llm()
    profile = UserProfile(tmp / "profile.json")
    brain = Brain(llm=fake_llm)
    response_gen = ResponseGenerator(llm=fake_llm, profile=profile)

    stored = []
    scheduled = []

    async def fake_memory_store(content: str, metadata: dict) -> bool:
        stored.append(content)
        return True

    async def fake_schedule_create(name: str, prompt: str, sched_type: str, config_json: str) -> str:
        scheduled.append(name)
        return f"OK: {name}"

    async def fake_memory_recall(query: str) -> str:
        return profile.summary()

    executor = AutoExecutor(
        profile=profile,
        memory_store_fn=fake_memory_store,
        schedule_create_fn=fake_schedule_create,
    )

    async def fake_task_runner(task_id, description, intent):
        await asyncio.sleep(0.1)
        return {
            "summary": f"Did: {description[:50]}",
            "artifacts": ["output.txt"],
            "completed_steps": ["step1", "step2"],
        }

    orch = BrainOrchestrator(
        brain=brain,
        response_gen=response_gen,
        profile=profile,
        auto_executor=executor,
        task_runner=fake_task_runner,
        memory_recall_fn=fake_memory_recall,
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

    # Scenario 1: "i am Ammar Ahmer"
    print("\n>>> USER: i am Ammar Ahmer")
    await orch.handle_user_input("i am Ammar Ahmer")
    await asyncio.sleep(0.5)

    # Scenario 2: "my birthday is on 21st april at 12am"
    print(">>> USER: my birthday is on 21st april at 12am")
    await orch.handle_user_input("my birthday is on 21st april at 12am")
    await asyncio.sleep(0.5)

    # Scenario 3: "what's my name?"
    print(">>> USER: what's my name?")
    await orch.handle_user_input("what's my name?")
    await asyncio.sleep(0.5)

    # Scenario 4: "build me a website" (task)
    print(">>> USER: build me a website")
    await orch.handle_user_input("build me a website")
    await asyncio.sleep(1.5)  # wait for task to complete

    # Stop collector
    collector.cancel()
    try:
        await collector
    except asyncio.CancelledError:
        pass

    # Print all events
    print(f"\n  Events emitted: {len(events)}")
    for ev in events:
        print(f"    [{ev.type.value}] {ev.message[:80]}")

    # Verify — all intents now go through BEFORE_WORK + task (memory_query, quick_reply, emotional only are instant)
    types_seen = [e.type for e in events]
    assert BrainEventType.BEFORE_WORK in types_seen, "Should have before_work events for all queries"

    # Verify profile was updated
    assert profile.get("identity.name") == "Ammar Ahmer"
    print(f"\n  Profile: name={profile.get('identity.name')}")

    # Verify schedules were created
    assert len(scheduled) >= 1
    print(f"  Schedules created: {scheduled}")

    # Verify memory was stored
    assert len(stored) >= 2
    print(f"  Memories stored: {len(stored)}")

    await orch.stop()
    print("\n  [PASS] PASS — full brain-driven conversation works")


async def main():
    print("=" * 70)
    print("  Xeno 2.0 — Brain-Driven Agent Test Suite")
    print("  (No regex, no hardcoded patterns — LLM is the brain)")
    print("=" * 70)

    await test_brain_analyze()
    await test_brain_birthday()
    await test_profile_persistence()
    await test_auto_executor()
    await test_self_modifier_create_file()
    await test_end_to_end_brain_orchestrator()

    print("\n" + "=" * 70)
    print("  [PASS] ALL BRAIN TESTS PASSED")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
