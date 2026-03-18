# Mission Control — High-Impact Feature Plan

## Current State Assessment
- 24-table Postgres schema, 9 agent skills, 26 API modules, 5-page dashboard
- Backend tests: 14+ passing (SQLite in-memory)
- Key gaps: bot code duplication, no setup wizard, no cron scheduling, MCP bugs, no agent output validation

---

## Features to Implement (Ordered by Impact)

### 1. Unified Bot Command Layer
**Why:** Telegram (468 lines) and Discord (201 lines) duplicate ~60% of logic. Every new command or integration means editing 2+ files. This is the #1 maintainability blocker.

**What:**
- Extract shared command handlers into `backend/app/integrations/commands.py`
- Define a `BotContext` dataclass (platform-agnostic) with `reply()`, `get_db()`, `user_id`
- Move all command logic (task, idea, read, note, status, run, projects) to shared module
- Telegram and Discord become thin adapters (~50 lines each)
- Any future bot (Slack, WhatsApp) just implements the adapter

**Files:**
- New: `backend/app/integrations/commands.py`
- Edit: `backend/app/integrations/telegram.py` (slim down)
- Edit: `backend/app/integrations/discord_bot.py` (slim down)

### 2. Agent Output Validation & Retry Logic
**Why:** Malformed agent JSON silently becomes `{"summary": raw_text, "actions": []}`. No retries on transient LLM failures. Silent data loss.

**What:**
- Add Pydantic models for agent output schema validation
- Validate `actions` array entries against allowed action types
- Add exponential backoff retry (3 attempts) for rate limits / 5xx errors
- Log validation errors to `agent_runs` table with clear error messages
- Add a `validation_errors` field to run results

**Files:**
- Edit: `backend/app/orchestrator/runner.py`
- New: `backend/app/orchestrator/schemas.py` (output validation models)

### 3. Cron Schedule Support
**Why:** Interval-only scheduling limits agents. Users want "run at 9am daily" or "every Monday at 8am", not "every 24h from whenever it started."

**What:**
- Add cron expression parsing to scheduler (use `croniter` library)
- Support `schedule.type: cron` with `schedule.every: "0 9 * * *"` in YAML
- Add jitter (0-60s random delay) to prevent thundering herd
- Add `next_run_at` column to `agent_configs` for efficient scheduling

**Files:**
- Edit: `backend/app/orchestrator/scheduler.py`
- Edit: `backend/app/db/models.py` (add next_run_at)
- New migration for the column

### 4. Interactive Setup Wizard
**Why:** No one-command install. Users must manually create `.env`, run Docker, run migrations. This is the #1 barrier to adoption.

**What:**
- Create `setup.sh` script that:
  - Checks for Docker + Docker Compose
  - Interactively prompts for LLM provider + API key
  - Optionally prompts for Telegram/Discord tokens
  - Generates `.env` from answers
  - Runs `docker compose up -d`
  - Waits for health check
  - Prints dashboard URL
- Add `Makefile` with common commands (`make dev`, `make test`, `make setup`)

**Files:**
- New: `setup.sh`
- New: `Makefile`

### 5. Dashboard Quick Capture + Keyboard-Driven Create
**Why:** Creating tasks/ideas requires navigating to the right section and clicking buttons. Power users want instant capture from anywhere on the dashboard.

**What:**
- Add a global quick-capture modal (triggered by `c` key or Cmd+K → "new")
- Auto-detect type from prefix: `t:` = task, `i:` = idea, `r:` = reading, `n:` = note
- Support natural language with auto-tagging (hit API `/api/autotag`)
- Add recent captures toast/feed in bottom-right

**Files:**
- Edit: `dashboard/app/page.tsx` (add QuickCapture component)
- Edit: `dashboard/app/lib/api.ts` (add autotag integration)

### 6. Fix MCP Server Bugs + Add Missing Tools
**Why:** MCP server has wrong health check path and missing tools for notes, habits management.

**What:**
- Fix `/health` → `/api/health` path
- Add `mc_add_note`, `mc_list_notes`, `mc_update_task_status` tools
- Add `mc_list_reading` tool
- Add proper error handling for HTTP failures
- Add connection retry logic

**Files:**
- Edit: `backend/app/integrations/mcp_server.py`

### 7. Persist Chat Sessions to Database
**Why:** Chat sessions (Telegram natural language) are in-memory only. Lost on restart. No conversation history.

**What:**
- Add `chat_sessions` table (user_id, messages JSON, last_active, platform)
- Load/save sessions from DB instead of in-memory dict
- Add session history endpoint `/api/chat/sessions`
- Configurable session timeout and max messages

**Files:**
- Edit: `backend/app/db/models.py`
- Edit: `backend/app/integrations/chat.py`
- New migration

### 8. Project Health Scoring
**Why:** No aggregate view of project health. Users can't tell at a glance which projects need attention.

**What:**
- Calculate per-project metrics: task completion rate, overdue count, goal progress, recent activity
- Add `/api/projects/{id}/health` endpoint
- Add health score badge to dashboard project cards
- Color-coded: green (healthy), yellow (needs attention), red (stalled)

**Files:**
- Edit: `backend/app/api/projects.py`
- Edit: `dashboard/app/projects/page.tsx`

---

## Implementation Order

We'll implement in this order, shipping each feature completely before moving on:

1. **Unified Bot Command Layer** — Foundation for all future integrations
2. **Agent Output Validation & Retry** — Reliability before new features
3. **Cron Schedule Support** — High user value, moderate effort
4. **Setup Wizard** — Unblocks adoption
5. **Quick Capture** — Dashboard power-user feature
6. **MCP Server Fixes** — Bug fixes + missing tools
7. **Chat Session Persistence** — Data durability
8. **Project Health Scoring** — Analytics layer

## Test Strategy
- Add tests for each new feature alongside implementation
- Run existing backend tests after each change to avoid regressions
- Dashboard build verification after UI changes
