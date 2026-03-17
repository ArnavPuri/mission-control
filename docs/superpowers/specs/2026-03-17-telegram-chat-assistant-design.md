# Telegram Chat Assistant

## Problem

The Telegram bot currently treats all plain text as task creation. Users expect conversational interaction — asking questions about their data, giving natural language commands, and getting intelligent responses.

## Solution

Replace `handle_plain_text` with an LLM-powered chat handler that uses Claude Sonnet to understand intent, query Mission Control data, take actions, and respond conversationally.

## Capabilities

The assistant can:
- **Read** projects, tasks, ideas, reading list, agent status
- **Write** create tasks, ideas, reading items; update task status/priority
- **Trigger agents** by name when requested
- **Chat** answer questions, summarize data, give recommendations

## Ambiguity Handling

- Clear intent ("add a task to review Stripe docs") → act immediately, confirm what was done
- Ambiguous intent ("remember to check analytics") → ask for clarification
- Destructive actions (delete, mark done) → always confirm first

## Architecture

### Message Flow

```
User sends text in Telegram
  → Send typing indicator
  → Load session history (messages within 30-min window, max 20)
  → Build DB context (projects, open tasks, recent ideas, unread reading, agents)
  → Construct system prompt with role, context, action schema
  → Call Anthropic Messages API with tool_use (claude-sonnet-4-6)
  → Process tool calls: execute actions, collect results
  → Send text reply to user in Telegram (split if >4096 chars)
  → Log actions to EventLog
```

### Session Memory

- In-memory dict keyed by Telegram user ID
- Stores both user and assistant messages as `{role, content, timestamp}`
- Prune messages older than 30 minutes on each new message
- Cap at 20 messages per session
- No persistence across restarts (acceptable for chat sessions)

### Action Execution via Tool Use

Instead of parsing freeform text for actions, use the Anthropic Messages API `tool_use` feature. Define tools that the LLM can call:

```python
tools = [
    {
        "name": "create_task",
        "description": "Create a new task in Mission Control",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Task description"},
                "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"], "default": "medium"},
                "project_name": {"type": "string", "description": "Project name to assign to (optional)"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "create_idea",
        "description": "Capture a new idea",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["text"]
        }
    },
    {
        "name": "add_reading",
        "description": "Add an item to the reading list",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "url": {"type": "string"}
            },
            "required": ["title"]
        }
    },
    {
        "name": "update_task",
        "description": "Update a task's status or priority. Match by task text (fuzzy).",
        "input_schema": {
            "type": "object",
            "properties": {
                "task_text": {"type": "string", "description": "Text of the task to match"},
                "status": {"type": "string", "enum": ["todo", "in_progress", "blocked", "done"]},
                "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]}
            },
            "required": ["task_text"]
        }
    },
    {
        "name": "trigger_agent",
        "description": "Trigger an agent to run",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_slug": {"type": "string", "description": "Slug of the agent to trigger"}
            },
            "required": ["agent_slug"]
        }
    }
]
```

The handler processes tool_use blocks from the response, executes each action against the DB, returns tool_result blocks, and continues the conversation until the LLM produces a final text response.

### Task Matching

`update_task` uses fuzzy text matching instead of UUIDs (which are unwieldy in conversation). The handler searches for tasks where `task.text ILIKE %query%` and picks the best match. If multiple matches, the LLM should ask the user to be more specific.

### DB Context

Built by `build_db_context()` with size limits to keep the prompt reasonable:

- **Projects**: all (typically <10)
- **Open tasks**: most recent 30, ordered by priority then created_at
- **Ideas**: last 15
- **Unread reading**: last 10
- **Agents**: all, with slug, description, status, schedule

Each task includes its text and a short ID prefix (first 8 chars of UUID) for reference.

### System Prompt

```
You are Mission Control, a personal AI assistant.
You help manage projects, tasks, ideas, and a reading list.

## Current Data
{db_context as JSON}

## Available Agents
{list of agents with slug, description, status, schedule}

## Behavior
- Act immediately on clear intents and confirm what you did
- Ask for clarification on ambiguous requests
- Always confirm before destructive actions (marking tasks done, changing priorities)
- Keep replies concise — this is Telegram, not email
- When listing items, use compact formatting
- Match tasks by text content, not by ID
- Check agent status before triggering (don't start already-running agents)
```

## Files Changed

| File | Change |
|---|---|
| `backend/app/db/context.py` | **New** — `build_db_context(db)` function. Not extracted from runner — different query logic (broader, with size limits). Runner keeps its own `build_context` which is agent-specific. |
| `backend/app/integrations/telegram.py` | Replace `handle_plain_text` with `handle_chat_message`. Add: session store, `build_system_prompt()`, `call_llm()`, `execute_tool_call()`, typing indicator. New `process_chat_actions()` function (no AgentConfig dependency). |
| `backend/app/config.py` | Add `chat_model` (default: `claude-sonnet-4-6`), `chat_session_timeout_minutes` (default: 30) |

## What Stays the Same

- All slash commands remain (faster for known actions)
- Agent runner keeps its own `build_context` and `_process_actions` (agent-specific, permission-gated)
- Scheduler, dashboard, API routes — untouched

## Edge Cases

- **Agent trigger from chat**: Check `agent.status != RUNNING` before starting. Run in background task, send "Starting {agent}..." immediately, reply with summary when complete.
- **Session timeout**: Messages older than 30 min are pruned. If all messages are pruned, start fresh.
- **LLM failure**: Reply with "Sorry, I couldn't process that. Try a /command instead." Log the error.
- **Telegram message limit**: Split responses >4096 chars into multiple messages.
- **EventLog**: All chat-initiated actions write to EventLog with `source="telegram:chat"`.
- **Multiple tool calls**: The LLM may call multiple tools in one turn. Execute all, return results, let it produce final text.
