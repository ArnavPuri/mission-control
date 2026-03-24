# CLAUDE.md - Mission Control

## What is this?

Mission Control is a Telegram-first personal AI assistant. One PostgreSQL (or SQLite)
database is the single source of truth. You talk to it via Telegram — it manages tasks,
spawns agents for research/coding/marketing, reminds you of things, and helps build
your personal brand on X, LinkedIn, Instagram, and YouTube.

A simple dashboard provides an overview and lets you manage agents and scheduled tasks.

## Architecture

- **Telegram Bot**: Primary interface — natural language chat + slash commands
- **Backend**: Python/FastAPI at `backend/app/`
- **Dashboard**: Next.js/TypeScript at `dashboard/` — simple overview UI
- **Agent Skills**: YAML files at `backend/skills/`
- **Database**: PostgreSQL with pgvector (or SQLite for dev)
- **Agent Runtime**: Claude Agent SDK (supports API key + OAuth)

## Key Files

- `backend/app/main.py` — FastAPI app entry point
- `backend/app/db/models.py` — All database models (SQLAlchemy)
- `backend/app/config.py` — Settings
- `backend/app/orchestrator/runner.py` — Agent execution engine (retry, timeout, chaining)
- `backend/app/orchestrator/scheduler.py` — Interval/cron-based scheduler
- `backend/app/agents/skill_loader.py` — YAML → DB sync
- `backend/app/integrations/telegram.py` — Telegram bot
- `backend/app/integrations/chat.py` — LLM chat with tool use
- `backend/app/integrations/commands.py` — Shared command handlers
- `backend/app/notifications/dispatcher.py` — Telegram notification delivery
- `backend/app/notifications/morning.py` — Morning briefing generator
- `dashboard/app/page.tsx` — Main dashboard UI
- `dashboard/app/lib/api.ts` — API client

## Database Tables

- **projects** — What you're building
- **tasks** — Things to do (status, priority, due dates)
- **notes** — Ideas, reading notes, reflections (markdown)
- **agent_configs** — Agent definitions (from YAML skills)
- **agent_runs** — Execution log for every agent run
- **agent_memories** — Persistent memory (per-agent + shared scratchpad)
- **agent_approvals** — Actions queued for human approval
- **chat_sessions** — Telegram conversation history
- **brand_profile** — Personal brand (tone, topics, social handles)
- **marketing_signals** — Leads/opportunities found by agents
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

# Run migrations
cd backend && alembic upgrade head
```

## Conventions

- Telegram is the primary interface — most interaction happens there
- Dashboard is for overview and management (agents, scheduled tasks)
- Agent skill files are YAML in `backend/skills/`
- Agent output must be JSON with `summary` and `actions` fields
- The `event_log` table tracks all changes for audit
- Use Haiku for cheap agents, Sonnet for smart ones
- Content is generated for: X, LinkedIn, Instagram, YouTube, blog

## Auth

Uses Claude Code subscription (OAuth) exclusively:
- `CLAUDE_CODE_OAUTH_TOKEN` — Required. Get via `claude auth login`.
- No API key needed. Works with Claude Pro/Max subscription.
