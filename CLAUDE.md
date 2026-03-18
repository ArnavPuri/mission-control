# CLAUDE.md - Mission Control

## What is this?

Mission Control is a personal AI-powered command center (v0.4, 65/145 features).
One PostgreSQL database is the single source of truth. Agents (defined as YAML
skill files) read from and write to the database. A dashboard shows the status.
Telegram/Discord bots, MCP server, and push notifications provide input channels.

## Architecture

- **Backend**: Python/FastAPI at `backend/app/` — 30 API routers
- **Dashboard**: Next.js/TypeScript at `dashboard/` — 5 pages, fully complete
- **Agent Skills**: YAML files at `backend/skills/`
- **Database**: PostgreSQL with pgvector — 25 tables, 6 migrations
- **Agent Runtime**: Claude Agent SDK (supports API key + OAuth)

## Key Files

- `backend/app/main.py` — FastAPI app entry point (30 routers mounted)
- `backend/app/db/models.py` — All 25 database models (SQLAlchemy)
- `backend/app/config.py` — Settings with multi-auth support
- `backend/app/orchestrator/runner.py` — Agent execution engine (retry, timeout, chaining, approval)
- `backend/app/orchestrator/scheduler.py` — Interval-based scheduler
- `backend/app/agents/skill_loader.py` — YAML → DB sync
- `backend/app/api/workflows.py` — Agent workflow DAGs with dependency resolution
- `backend/app/api/routines.py` — Routine builder API (morning/evening checklists)
- `backend/app/api/dedup.py` — Deduplication detection for tasks/ideas
- `backend/app/api/smart_priority.py` — Smart prioritization suggestions
- `backend/app/api/push.py` — Browser push notification subscriptions
- `backend/app/api/journal.py` — Journal CRUD + semantic search
- `backend/app/integrations/telegram.py` — Telegram bot
- `backend/app/integrations/discord_bot.py` — Discord bot
- `backend/app/integrations/mcp_server.py` — MCP server for Claude Code
- `dashboard/app/page.tsx` — Main dashboard UI (tasks, calendar, routines, etc.)
- `dashboard/app/lib/api.ts` — API client (all endpoints)

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

# Create a migration
cd backend && alembic revision --autogenerate -m "description"
```

## Conventions

- All API routes are at `/api/<resource>`
- WebSocket at `/ws` for live dashboard updates
- Agent skill files are YAML in `backend/skills/`
- Agent output must be JSON with `summary` and `actions` fields
- The `event_log` table tracks all changes for audit
- Use Haiku for cheap agents, Sonnet for smart ones
- Migrations numbered sequentially: `001_initial_schema.py` through `006_workflows_and_sort_order.py`

## Completed Sprints

- **Sprint 5**: Inline editing, filters, habit analytics, responsive design, dark mode
- **Sprint 6**: pgvector, auto-tagging, triggers, agent memory, analytics
- **Sprint 7**: GitHub integration, RSS feeds, notes, API keys, Discord bot
- **Sprint 8**: Multi-page layout, Kanban board, bulk actions, keyboard shortcuts, project dashboards
- **Sprint 9**: Test suites, Alembic migrations, seed data, agent timeout, error handling
- **Sprint 10**: Agent learning loop, shared scratchpad, daily standup, output validation, retry logic
- **Sprint 11**: Routine builder, project health scoring, calendar view, quick capture, deduplication
- **Sprint 12**: Workflow DAGs, smart prioritization, drag-and-drop, push notifications, journal search

## Auth

The system supports multiple LLM auth methods (see `.env.example`):
1. `ANTHROPIC_API_KEY` — Standard API (recommended)
2. `CLAUDE_CODE_OAUTH_TOKEN` — Pro/Max subscription
3. `OPENROUTER_API_KEY` — Multi-provider via OpenRouter
4. `OLLAMA_BASE_URL` — Local/self-hosted
