# Agent Runtime Improvements

**Date:** 2026-03-20
**Status:** Approved

## Problem

Agents start fresh every run — they have no memory of previous conversations, lose full reasoning transcripts, and don't inherit project conventions. This limits their effectiveness for recurring tasks like scouting Reddit threads or weekly reviews.

## Solution

Three improvements to the agent runtime:

1. **CLAUDE.md auto-loading** — agents inherit project/user instructions via SDK `settingSources`
2. **Session persistence** — agents resume SDK conversations across runs within a configurable window
3. **Transcript archival** — full agent conversations saved to the run record for debugging and audit

---

## 1. CLAUDE.md Auto-Loading

Add `settingSources: ['project', 'user']` to `ClaudeAgentOptions` in `execute_with_agent_sdk`. The SDK automatically loads CLAUDE.md files from the working directory and user config.

No schema changes. One line in runner.py.

---

## 2. Session Persistence

### Schema: New columns on `agent_configs`

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| session_id | String(255), nullable | None | SDK session ID from last run |
| last_message_uuid | String(255), nullable | None | Last assistant message UUID for resumption |
| session_expires_at | DateTime(tz), nullable | None | When current session expires |
| session_window_days | Integer | 7 | Days before starting fresh (0 = no persistence) |

### Flow

1. Before executing, runner checks `session_id` exists and `session_expires_at > now`
2. If valid: pass `resume=session_id` and `resumeSessionAt=last_message_uuid` to SDK options
3. If expired or missing: start fresh (no resume options)
4. During execution: capture `session_id` from `init` system message, track last assistant message UUID
5. After execution: save `session_id`, `last_message_uuid`, `session_expires_at = now + session_window_days` to agent config

### Capturing Session Info from SDK

During the `async for message in query(...)` loop:
- `message.type == 'system'` and `message.subtype == 'init'` → extract `session_id` (available as `message.session_id` or `message.data.session_id`)
- Track the last `AssistantMessage` — its UUID is used for `resumeSessionAt`

### Agent Builder UI

Add "Session Memory (days)" field to the agent edit form. Number input, default 7, 0 = disabled.

---

## 3. Transcript Archival

### Schema: New column on `agent_runs`

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| transcript | JSON, nullable | None | Full conversation messages (capped at 50) |

### Format

Each entry in the transcript list:
```json
{"role": "system|assistant|user|result", "content": "...", "timestamp": "ISO8601"}
```

### Collection

During the `async for message in query(...)` loop, append each message to a transcript list. Cap at 50 entries.

After run completes (success or failure), save to `run.transcript`.

### API

- `GET /api/agents/{id}/runs` — list endpoint **excludes** `transcript` to avoid bloating responses
- `GET /api/agents/{id}/runs/{run_id}` — new detail endpoint, **includes** `transcript`

### UI

Extend the expandable run detail in the agents page to show a "Transcript" toggle when transcript data exists. Renders as a simple chat-style message list.

---

## 4. Files

### New files

| File | Purpose |
|------|---------|
| `backend/app/db/migrations/versions/010_agent_sessions_and_transcripts.py` | Session columns on agent_configs, transcript on agent_runs |

### Modified files

| File | Changes |
|------|---------|
| `backend/app/db/models.py` | 4 columns on AgentConfig, 1 on AgentRun |
| `backend/app/orchestrator/runner.py` | settingSources, session resume/capture, transcript collection |
| `backend/app/api/agents.py` | New run detail endpoint, exclude transcript from list |
| `dashboard/app/agents/page.tsx` | Transcript viewer in expandable run detail, fetch from detail endpoint |
