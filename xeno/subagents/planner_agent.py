"""Planner agent — strategic planning and project management with its own brain."""


def get_planner_subagent(config=None) -> dict:
    model = config.model if config else "groq:openai/gpt-oss-120b"
    return {
        "name": "planner-agent",
        "description": (
            "Strategic planning and project management agent. "
            "Use for: creating plans, breaking down goals, organizing tasks, "
            "scheduling, project roadmaps, dependency analysis, risk assessment."
        ),
        "system_prompt": (
            "You are a strategic planning and project management expert.\n\n"
            "CAPABILITIES:\n"
            "- plan_create / plan_add_phase: create structured multi-phase plans\n"
            "- strategic_create_goal / strategic_decompose: break down big goals\n"
            "- todo_create / todo_complete / todo_list: track tasks and milestones\n"
            "- schedule_create / schedule_list: schedule tasks and reminders\n"
            "- memory_store / memory_search: save and recall planning context\n"
            "- read_file / write_file: write project plans to workspace/\n"
            "- skill_create: create reusable planning templates\n"
            "- todo_stats / todo_overdue: monitor progress\n\n"
            "WORKFLOW:\n"
            "1. Understand the goal and constraints\n"
            "2. Break into phases with clear milestones\n"
            "3. Create todos for each action item\n"
            "4. Add dependencies and timelines\n"
            "5. Monitor progress and adapt\n\n"
            "Be methodical. Every plan needs phases, tasks, and timelines."
        ),
        "model": model,
        "tools": [
            "plan_create", "plan_add_phase", "plan_list", "plan_summary",
            "strategic_create_goal", "strategic_decompose", "strategic_list_goals",
            "todo_create", "todo_complete", "todo_list", "todo_stats", "todo_overdue",
            "schedule_create", "schedule_list",
            "memory_store", "memory_search",
            "read_file", "write_file",
            "skill_create",
        ],
    }
