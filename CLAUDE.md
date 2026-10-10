# CLAUDE.md - Mission Control

## What is this?

Mission Control is a Telegram-first personal AI assistant. One PostgreSQL (or SQLite)
database is the single source of truth. You talk to it via Telegram — it manages tasks
and notes, delegates tasks to agents (research, writing, marketing), hands coding work
to Claude Code via GitHub issues, sends a morning briefing, and helps build your
personal brand on X, LinkedIn, Instagram, and YouTube.

Delegation works through task threads: `/ask <agent> <request>` (or chat, or the
dashboard) assigns a task to an agent, which runs in the background and replies in the
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
- `backend/app/orchestrator/runner.py` — Agent execution engine (context, retry, timeout, actions, background runs)
- `backend/app/orchestrator/scheduler.py` — Interval/cron scheduler; picks up waiting assigned tasks; GitHub sync
- `backend/app/orchestrator/threads.py` — Task threads: assigning tasks to agents and replies
- `backend/app/orchestrator/review.py` — Approvals and content drafts (shared by API, commands, Telegram buttons)
- `backend/app/agents/skill_loader.py` — YAML → DB sync
- `backend/app/integrations/telegram.py` — Telegram bot
- `backend/app/integrations/chat.py` — LLM chat that can take actions (tasks, notes, delegation, dev tasks, drafts)
- `backend/app/integrations/commands.py` — Shared command handlers
- `backend/app/integrations/github.py` — Dev tasks as GitHub issues for Claude Code
- `backend/app/notifications/dispatcher.py` — Telegram notification delivery
- `backend/app/notifications/morning.py` — Morning briefing generator
- `dashboard/app/page.tsx` — Home (Today view); `tasks/`, `agents/`, `notes/`, `settings/` are the other pages
- `dashboard/app/components/app-shell.tsx` — Sidebar, ⌘K command menu, and the task/project dialogs any page can open
- `dashboard/app/components/workspace.tsx` — Shared live data (tasks, projects, agents, review items), refreshed on backend events
- `dashboard/app/components/shared.tsx` — UI primitives (Button, Badge, Avatar, PageHeader, …)
- `dashboard/app/globals.css` — Design tokens as CSS variables (light + dark); use `mc-*` Tailwind colors, not raw grays
- `dashboard/app/lib/api.ts` — API client

## Database Tables

- **projects** — What you're building. `github_repo` ("owner/repo") is where `/dev` opens issues
- **tasks** — Things to do (status, priority, due dates, assigned agent). Leads found by marketing agents are tasks tagged `lead`
- **task_comments** — A task's thread (user, agent and system messages; Telegram message ids for replies)
- **notes** — Ideas, reading notes, reflections (markdown)
- **agent_configs** — Agent definitions (from YAML skills)
- **agent_runs** — Execution log for every agent run
- **agent_memories** — Persistent per-agent memory
- **agent_approvals** — Actions queued for human approval
- **chat_sessions** — Telegram conversation history
- **brand_profile** — Personal brand (tone, topics, social handles)
- **marketing_content** — Content drafts for social platforms
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
- Agent output must be JSON with `summary` and `actions` fields; on an assigned task the agent also returns `reply` and `status` (`done` | `needs_input`)
- The `event_log` table tracks all changes for audit
- Model columns use portable types (`Uuid`, `JSON`) so PostgreSQL and SQLite both work; never use PostgreSQL-only types
- Use Haiku for cheap agents, Sonnet for smart ones
- Content is generated for: X, LinkedIn, Instagram, YouTube, blog

## Auth

Uses Claude Code subscription (OAuth) exclusively:
- `CLAUDE_CODE_OAUTH_TOKEN` — Required. Get via `claude setup-token` (or `claude auth login`).
- No API key needed. Works with Claude Pro/Max subscription.
