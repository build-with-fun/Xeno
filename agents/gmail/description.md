---
name: gmail
model: deepseek:deepseek-chat
tools: [gmail_read, gmail_send, gmail_list, gmail_search, gmail_filter, gmail_approve]
permissions: [read, write]
temperature: 0.7
max_tokens: 4096
tags: [email, gmail, communication, productivity]
enabled: true
always_on: true
check_interval_minutes: 5
restart_policy: with_backoff
max_restarts: 10
---

# Gmail Agent

Manages your Gmail inbox automatically. Reads new emails, filters spam, flags important messages, and drafts replies for approval.

## Capabilities

- **Read Inbox**: Check for new emails every 5 minutes
- **Filter Spam**: Auto-detect spam, promotions, and low-priority emails
- **Draft Replies**: Generate contextual reply drafts for important emails
- **Approval Workflow**: Flag uncertain replies and promotional responses for user approval
- **Context Sharing**: Log all activity to the shared context bridge so the main agent can answer questions about email activity
- **Search**: Find past emails by sender, subject, or content

## Setup

1. Enable Gmail API in Google Cloud Console
2. Create OAuth 2.0 credentials (Desktop app type)
3. Download `credentials.json` to `agents/gmail/credentials.json`
4. On first run, follow the OAuth URL to authorize

## Spam Detection

- Unknown senders with promotional content → auto-mark as spam
- Known contacts → auto-reply with contextual draft
- Replies needing approval → pushed to approval queue with [PENDING] flag
- Bulk newsletters → summarize and ask if user wants to unsubscribe

## Escalation

For complex queries or messages requiring human judgment, pushes a pending approval to the context bridge. The main agent can query pending items with `agent_context_pending()`.
