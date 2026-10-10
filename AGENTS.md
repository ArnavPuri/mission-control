# AGENTS.md - Mission Control

Instructions for coding agents live in [CLAUDE.md](CLAUDE.md). Read it first and keep
this file consistent with it. The essentials:

- **What it is:** a Telegram-first personal AI assistant. One database (PostgreSQL, or
  SQLite with `USE_SQLITE=true`) is the single source of truth. A FastAPI backend
  (`backend/app/`) runs the Telegram bot, the scheduler and the agent runner. The
  Next.js dashboard (`dashboard/`) shows the overview.
- **Agents** are YAML files in `backend/skills/`, synced to `agent_configs` on startup
  (files starting with `_` are skipped). They run through the Claude Agent SDK on a
  Claude Pro/Max subscription (`CLAUDE_CODE_OAUTH_TOKEN`). No API key is used.
- **Agent output** is JSON with `summary` and `actions`. Allowed actions: `create_task`,
  `update_task`, `create_note`, `create_lead`, `create_content`, `save_memory`. On an
  assigned task the agent also returns `reply` and `status` (`done` | `needs_input`).
- **Delegation:** tasks assigned to an agent get a thread in `task_comments`. The agent
  replies there and on Telegram, and a Telegram reply continues the thread.
  `/dev` turns coding work into a GitHub issue for Claude Code.
- **Schema changes** go through Alembic (`backend/app/db/migrations/versions/`). Migrations
  run automatically on startup. Use portable column types (`Uuid`, `JSON`), never
  PostgreSQL-only types.
- **Audit:** changes are logged to `event_log`.
- **Tests:** `cd backend && pytest` and `cd dashboard && npx vitest run`.
