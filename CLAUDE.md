# CLAUDE.md - Mission Control

## What is this?

Mission Control is a Telegram-first personal AI assistant. One PostgreSQL (or SQLite)
database is the single source of truth. You talk to it via Telegram — it manages tasks
and notes, delegates tasks to agents (research, writing, marketing), hands coding work
to Claude Code via GitHub issues, sends a morning briefing, and helps build your
personal brand on X, LinkedIn, Instagram, and YouTube.

Requests from chat (and `/do`) go to the coordinator agent (Ace), which splits them
into handoffs to specialists, waits for their results and answers once. Delegation
works through task threads: `/ask <agent> <request>` (or the dashboard) assigns a task
to a specific agent, which runs in the background and replies in the
task's thread (`task_comments`) and on Telegram. Replying to that Telegram message
continues the thread. `/dev <project> <request>` opens a GitHub issue mentioning
`@claude` instead; PRs and issue closure are reported back to the thread.

A simple dashboard provides an overview and lets you manage agents and scheduled tasks.

## Architecture

- **Telegram Bot**: Primary interface — natural language chat + slash commands
- **Backend**: Python/FastAPI at `backend/app/`
- **Dashboard**: Next.js/TypeScript at `dashboard/` — simple overview UI
- **Agent Skills**: YAML files at `backend/skills/`
- **Database**: PostgreSQL (or SQLite for dev). Schema is managed by Alembic and migrated on startup
- **Agent Runtime**: Claude Agent SDK, authenticated with a Claude Pro/Max subscription (OAuth)

## Key Files

- `backend/app/main.py` — FastAPI app entry point
- `backend/app/db/models.py` — All database models (SQLAlchemy)
- `backend/app/db/migrate.py` — Runs Alembic on startup (+ one-time conversion of pre-0.8 databases)
- `backend/app/db/migrations/versions/` — Alembic migrations
- `backend/app/config.py` — Settings
- `backend/app/auth.py` — Dashboard login (`DASHBOARD_PASSWORD`, signed session cookie) and `API_TOKEN` bearer auth
- `backend/app/db/backup.py` — Nightly backups (SQLite backup API or `pg_dump`), also `python -m app.db.backup`
- `backend/app/orchestrator/runner.py` — Agent execution engine (context, retry, timeout, actions, background runs)
- `backend/app/orchestrator/scheduler.py` — Interval/cron scheduler; picks up waiting assigned tasks; GitHub sync
- `backend/app/orchestrator/threads.py` — Task threads: assigning tasks to agents and replies
- `backend/app/orchestrator/handoffs.py` — Agent-to-agent handoffs (`handoff` action → linked task for a teammate; `follow_up`)
- `backend/app/orchestrator/coordinator.py` — The coordinator agent (`role: coordinator`, Ace): takes requests from chat and `/do`, delegates, answers once
- `backend/app/orchestrator/review.py` — Approvals and content drafts (shared by API, commands, Telegram buttons)
- `backend/app/orchestrator/reminders.py` — Telegram reminders (Done/Snooze buttons) and recurring tasks; complete tasks via `complete_task`
- `backend/app/timeutil.py` — Parsing "tomorrow at 9" / "every monday", recurrence steps, UTC helpers
- `backend/app/agents/skill_loader.py` — YAML → DB sync
- `backend/app/integrations/telegram.py` — Telegram bot
- `backend/app/integrations/chat.py` — LLM chat that can take actions (tasks, notes, delegation, dev tasks, drafts)
- `backend/app/integrations/commands.py` — Shared command handlers
- `backend/app/integrations/github.py` — Dev tasks as GitHub issues for Claude Code
- `backend/app/integrations/publishing.py` — Publish drafts to X (OAuth 1.0a, threads) and LinkedIn (Posts API)
- `backend/app/notifications/dispatcher.py` — Telegram notification delivery
- `backend/app/notifications/morning.py` — Morning briefing generator
- `dashboard/app/page.tsx` — Home (Today view); `tasks/`, `agents/`, `notes/`, `settings/` are the other pages
- `dashboard/app/components/app-shell.tsx` — Sidebar, ⌘K command menu, and the task/project dialogs any page can open
- `dashboard/app/components/workspace.tsx` — Shared live data (tasks, projects, agents, review items), refreshed on backend events
- `dashboard/app/components/shared.tsx` — UI primitives (Button, Badge, Avatar, PageHeader, …)
- `dashboard/app/components/task-dialog.tsx` — The task sheet (properties, handoffs, live progress, thread); `schedule.tsx` has the due/reminder pickers and badges
- `dashboard/app/components/draft-dialog.tsx` — Review, edit and publish a content draft
- `Caddyfile` — Reverse proxy: one origin for dashboard + API, automatic HTTPS when `SITE_ADDRESS` is a domain
- `docs/architecture.md` — How it all fits together; `docs/handoff.md` — current state and what's next
- `dashboard/app/globals.css` — Design tokens as CSS variables (light + dark); use `mc-*` Tailwind colors, not raw grays
- `dashboard/app/lib/api.ts` — API client

## Database Tables

- **projects** — What you're building. `github_repo` ("owner/repo") is where `/dev` opens issues
- **tasks** — Things to do (status, priority, due date, reminder, recurrence, assigned agent, `parent_task_id` for handoffs). Leads found by marketing agents are tasks tagged `lead`
- **task_comments** — A task's thread (user, agent and system messages; Telegram message ids for replies)
- **notes** — Ideas, reading notes, reflections (markdown)
- **agent_configs** — Agent definitions (from YAML skills)
- **agent_runs** — Execution log for every agent run
- **agent_memories** — Persistent per-agent memory
- **agent_approvals** — Actions queued for human approval
- **chat_sessions** — Telegram conversation history
- **brand_profile** — Personal brand (tone, topics, social handles)
- **marketing_content** — Content drafts for social platforms (`posted_url` once published)
- **notifications** — Sent via Telegram
- **event_log** — Audit trail

## Commands

```bash
# Start everything
docker compose up -d

# Backend only (dev)
cd backend && uvicorn app.main:app --reload

# Dashboard (dev)
cd dashboard && npm run dev

# Run migrations (also runs automatically on startup)
cd backend && alembic upgrade head

# New migration after changing models.py
cd backend && alembic revision --autogenerate -m "description"

# Tests
cd backend && pytest
cd dashboard && npx vitest run
```

## Conventions

- Telegram is the primary interface — most interaction happens there
- Dashboard is for overview and management (agents, scheduled tasks)
- Agent skill files are YAML in `backend/skills/`
- Agent output must be JSON with `summary` and `actions` fields; on an assigned task the agent also returns `reply` and `status` (`done` | `needs_input`; the coordinator also uses `waiting`)
- An agent hands work to a teammate with `{"type": "handoff", "agent": "<slug>", "request": "..."}`; it's an agent's turn on a task when the last comment is from the user or from another agent
- The coordinator replies with status `waiting` after handing off; it gets its turn back when all its handoffs have settled, and only it messages you (teammates working for it stay quiet on Telegram)
- The `event_log` table tracks all changes for audit
- Model columns use portable types (`Uuid`, `JSON`) so PostgreSQL and SQLite both work; never use PostgreSQL-only types
- Datetimes are stored and compared in UTC (SQLite drops offsets); user-facing times are in `NOTIFICATION_TIMEZONE`
- Mark tasks done with `reminders.complete_task` so repeating tasks create their next occurrence
- Use Haiku for cheap agents, Sonnet for smart ones
- Content is generated for: X, LinkedIn, Instagram, YouTube, blog

## Working on this repo

- Never let local or e2e runs spend the user's Claude subscription: start the backend with
  `ANTHROPIC_BASE_URL=http://127.0.0.1:9 CLAUDE_CODE_OAUTH_TOKEN=invalid` (and an empty
  `CLAUDE_CONFIG_DIR`) so agent runs fail fast. Tests stub `AgentRunner.execute_with_agent_sdk`.
- On a fresh database the scheduler starts interval agents on its first tick (60s after
  startup); set `last_run_at` when seeding demo data.
- `tests/conftest.py` clears secrets from settings so a developer's `.env` can't leak into tests.
- Background work that must start after a commit (handoffs) uses a SQLAlchemy
  `after_commit` hook (`handoffs._start_after_commit`).
- README screenshots live in `assets/screenshots/`; regenerate them from seeded demo data with
  a production dashboard build (`next build` + `next start`), not `next dev`.

## Auth

Uses Claude Code subscription (OAuth) exclusively:
- `CLAUDE_CODE_OAUTH_TOKEN` — Required. Get via `claude setup-token` (or `claude auth login`).
- No API key needed. Works with Claude Pro/Max subscription.
