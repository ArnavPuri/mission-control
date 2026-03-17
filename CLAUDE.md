# CLAUDE.md - Mission Control

## What is this?

Mission Control is a personal AI-powered command center. One PostgreSQL database
is the single source of truth. Agents (defined as YAML skill files) read from
and write to the database. A dashboard shows the status. A Telegram bot and
MCP server provide additional input channels.

## Architecture

- **Backend**: Python/FastAPI at `backend/app/`
- **Dashboard**: Next.js/TypeScript at `dashboard/`
- **Agent Skills**: YAML files at `backend/skills/`
- **Database**: PostgreSQL with pgvector
- **Agent Runtime**: Claude Agent SDK (supports API key + OAuth)

## Key Files

- `backend/app/main.py` — FastAPI app entry point
- `backend/app/db/models.py` — All database models (SQLAlchemy)
- `backend/app/config.py` — Settings with multi-auth support
- `backend/app/orchestrator/runner.py` — Agent execution engine
- `backend/app/orchestrator/scheduler.py` — Interval-based scheduler
- `backend/app/agents/skill_loader.py` — YAML → DB sync
- `backend/app/integrations/telegram.py` — Telegram bot
- `backend/app/integrations/mcp_server.py` — MCP server for Claude Code
- `dashboard/app/page.tsx` — Main dashboard UI
- `dashboard/app/lib/api.ts` — API client

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

## Auth

The system supports multiple LLM auth methods (see `.env.example`):
1. `ANTHROPIC_API_KEY` — Standard API (recommended)
2. `CLAUDE_CODE_OAUTH_TOKEN` — Pro/Max subscription
3. `OPENROUTER_API_KEY` — Multi-provider via OpenRouter
4. `OLLAMA_BASE_URL` — Local/self-hosted
