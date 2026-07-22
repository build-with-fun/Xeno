import json
from pathlib import Path
from xeno.config import XenoConfig


def main():
    config = XenoConfig.from_env()
    print("=== Xeno System Health Check ===\n")

    print("=== Self-Heal Report ===")
    try:
        from xeno.self_heal import SelfHealer
        print(SelfHealer(config).get_health_report())
    except Exception as e:
        print(f"  Not available: {e}")

    print("\n=== Memory Status ===")
    from xeno.memory import MemoryManager
    mm = MemoryManager(config)
    print(f"Context facts: {len(mm.context._data.get('facts', []))}")
    try:
        print(f"Vector docs: {mm.vector.count()}")
    except Exception:
        print("Vector DB: not initialized")

    print("\n=== Schedules ===")
    from xeno.scheduler import Scheduler
    scheduler = Scheduler(config)
    print(scheduler.list_all())

    print("\n=== Skills ===")
    from xeno.skills_manager import SkillManager
    sm = SkillManager(config)
    print(sm.list_all())

    print("\n=== Available Tools ===")
    from xeno.tools.registry import ALL_TOOLS, TOOL_MAP
    print(f"Tools available: {len(ALL_TOOLS)}")
    for t in ALL_TOOLS:
        name = getattr(t, 'name', t.__name__) if hasattr(t, '__name__') else str(t)
        desc = (getattr(t, 'description', None) or getattr(t, '__doc__', '') or '').strip().split('\n')[0] if not isinstance(t, str) else ''
        print(f"  - {name}: {desc[:80]}")


if __name__ == "__main__":
    main()
