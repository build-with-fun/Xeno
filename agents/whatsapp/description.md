---
name: whatsapp
model: deepseek:deepseek-chat
tools: [whatsapp_send, whatsapp_status, whatsapp_pending, whatsapp_schedule, whatsapp_metrics]
permissions: [read, write]
temperature: 0.7
max_tokens: 4096
tags: [messaging, whatsapp, communication, media]
enabled: true
always_on: true
check_interval_minutes: 3
restart_policy: with_backoff
max_restarts: 10
custom_tools_dir: tools/
---

# WhatsApp Agent

Autonomous WhatsApp bot agent — runs 24/7, monitors and replies to messages.

## Capabilities
- Send and receive WhatsApp messages
- Manage contacts and groups
- Handle media (images, documents, audio)
- Schedule messages and reminders
- Auto-reply with configurable rules
- Group management (welcome, moderation)
- Message templates and campaigns

## Custom Tools
Place Python files in `agents/whatsapp/tools/` to add custom tools.
Each file should define tools using `@tool` decorator from langchain.
They are auto-discovered and loaded when this agent starts.

## Behavior
- Responds to incoming messages with context-aware replies
- Maintains conversation history per contact
- Supports both reactive (reply) and proactive (scheduled) messaging
- Escalates complex queries to the main Xeno agent
- Logs all interactions for analytics
