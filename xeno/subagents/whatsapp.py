"""WhatsApp agent — messaging with its own brain and tools."""


def get_whatsapp_subagent(config=None) -> dict:
    model = config.model if config else "groq:openai/gpt-oss-120b"
    whatsapp_path = ""
    if config:
        whatsapp_path = config.whatsapp_module_path
    return {
        "name": "whatsapp-agent",
        "description": (
            "WhatsApp messaging agent for sending messages, managing contacts, "
            "reading chats, and controlling the WhatsApp bot. "
            "Use for: sending WhatsApp messages, checking message status, "
            "scheduling messages, managing broadcasts."
        ),
        "system_prompt": (
            f"You are the WhatsApp Agent controlling the bot at {whatsapp_path}.\n\n"
            "CAPABILITIES:\n"
            "- whatsapp_send: send messages to contacts or groups\n"
            "- whatsapp_status: check if the WhatsApp bot is running\n"
            "- whatsapp_pending: list pending messages\n"
            "- whatsapp_schedule: schedule future messages\n"
            "- whatsapp_metrics: get bot performance metrics\n"
            "- memory_store: save contact preferences and notes\n"
            "- todo_create / todo_complete: track messaging tasks\n\n"
            "Always confirm before sending messages to contacts.\n"
            "Format messages properly for readability."
        ),
        "model": model,
        "tools": [
            "whatsapp_send", "whatsapp_status", "whatsapp_pending",
            "whatsapp_schedule", "whatsapp_metrics",
            "memory_store",
            "todo_create", "todo_complete",
        ],
    }
