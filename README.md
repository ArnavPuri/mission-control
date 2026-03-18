<p align="center">
  <img src="assets/banner.png" alt="Mission Control — Your AI-Powered Command Center" width="100%" />
</p>

<h3 align="center">Your personal AI-powered command center</h3>
<p align="center">One PostgreSQL database. Many AI agents. One dashboard.<br/>Organize life, work, learning, and side projects from a single pane of glass.</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="ROADMAP.md">Roadmap</a> ·
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="#creating-agents">Agents</a>
</p>

---

## What is Mission Control?

Mission Control is an open-source personal productivity system powered by AI agents. Define agents as simple YAML files, and they read from and write to your database on a schedule — triaging tasks, validating ideas, reviewing your week, scouting opportunities, and more.

**Built with:** Python/FastAPI · Next.js · PostgreSQL + pgvector · Claude Agent SDK

### What's included (v0.3)

- **19 database tables** — Projects, tasks, ideas, reading list, habits, goals, journal, notes, and more
- **9 AI agents** — Reddit Scout, Idea Validator, Weekly Prioritizer, Daily Check-in, Goal Decomposer, Evening Reflection, Weekly Review, and more
- **5-page dashboard** — Dashboard, Projects, Agents, Journal, Settings with Kanban board, bulk actions, keyboard shortcuts
- **4 input channels** — Telegram bot (11 commands + chat), Discord bot, MCP server (17 tools), REST API
- **Multi-auth** — Anthropic API, OAuth, OpenRouter, Ollama (fully local)
- **Agent intelligence** — Memory, chaining, conditional triggers, approval queue, auto-tagging, analytics
- **Full test suites** — 14 backend (pytest) + 21 frontend (Vitest) tests

```
┌──────────────────┐     ┌──────────────┐     ┌──────────────┐
│  Telegram         │────▶│  Orchestrator │────▶│  Agent Pool   │
│  Discord          │     │  (scheduler)  │     │  (9 agents)   │
│  MCP / Claude Code│     └──────┬───────┘     └──────┬───────┘
│  REST API         │            │                     │
└──────────────────┘      ┌─────▼─────────────────────▼──────┐
                          │       PostgreSQL + pgvector       │
                          │  19 tables · event log · vectors  │
                          └──────────────┬──────────────────┘
                                         │
                                  ┌──────▼──────┐
                                  │  Dashboard   │
                                  │  (Next.js)   │
                                  └─────────────┘
```

---

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/yourname/mission-control.git
cd mission-control
cp .env.example .env
# Edit .env with your API key

# 2. Start everything
docker compose up -d

# 3. Open the dashboard
open http://localhost:3000
```

### Seed data for new installations

```bash
cd backend && python -m app.db.seed
```

This creates example projects, tasks, habits, goals, journal entries, and notes so you can explore immediately.

---

## Authentication Options

| Method | Env Variable | Notes |
|--------|-------------|-------|
| Anthropic API Key | `ANTHROPIC_API_KEY` | **Recommended.** Pay-per-token, no expiry. |
| Claude Subscription | `CLAUDE_CODE_OAUTH_TOKEN` | Uses Pro/Max plan. May expire. |
| OpenRouter | `OPENROUTER_API_KEY` | Access to many models via one key. |
| Ollama (local) | `OLLAMA_BASE_URL` | Free, private, runs on your hardware. |

---

## Creating Agents

Agents are YAML skill files in `backend/skills/`. Copy `_template.yaml` to get started:

```bash
cp backend/skills/_template.yaml backend/skills/my-agent.yaml
```

Each skill file defines:
- **What the agent does** (prompt template with `{{context}}` variables)
- **What data it reads** (projects, tasks, ideas, reading, habits, goals, journal)
- **What data it writes** (create tasks, ideas, reading items, journal entries, goals)
- **When it runs** (interval, cron, or manual trigger)
- **Which model to use** (haiku for cheap/fast, sonnet for smart)
- **Budget cap** per run
- **Timeout** per execution (default 300s)

See `backend/skills/` for examples: `reddit-scout.yaml`, `idea-validator.yaml`, `weekly-prioritizer.yaml`, `feedback-collector.yaml`, `daily-checkin.yaml`, `goal-decomposer.yaml`, `evening-reflection.yaml`, `weekly-review.yaml`.

---

## Input Channels

### Telegram Bot

Set `TELEGRAM_BOT_TOKEN` in `.env`:

```
/task Fix the login bug
/idea AI-powered meal planner #saas #ai
/read Tauri 2.0 Guide https://tauri.app/guide
/note Meeting Notes — discussed Q2 roadmap
/status
/run reddit-scout
```

### Discord Bot

Set `DISCORD_BOT_TOKEN` in `.env`:

```
!task Deploy v2 to production
!idea Voice-controlled dashboard
!status
!run weekly-prioritizer
```

### MCP Server (Claude Code)

```json
{
  "mcpServers": {
    "mission-control": {
      "command": "python",
      "args": ["-m", "app.integrations.mcp_server"],
      "cwd": "/path/to/mission-control/backend"
    }
  }
}
```

### REST API

API key authentication with scoped access (read/write/admin):

```bash
# Create an API key via the dashboard Settings page, then:
curl -H "X-API-Key: mc_..." http://localhost:8000/api/tasks
```

---

## Dashboard

The Next.js dashboard includes 5 pages:

| Page | Features |
|------|----------|
| **Dashboard** | Task list + Kanban board, ideas, reading, habits, goals, activity heatmap, agent status |
| **Projects** | Project list with per-project dashboards (tasks, goals, agents, notes) |
| **Agents** | Agent overview, per-agent detail with schedule, cost charts, recent runs |
| **Journal** | Timeline grouped by date, mood tracking, wins/challenges/gratitude |
| **Settings** | System status, API key management, GitHub repos, RSS feeds |

**Power user features:** Vim-style keyboard shortcuts (`g+d/p/a/j/s` nav, `n+t/i/o` create), command palette (`Cmd+K`), bulk task actions, dark/light mode.

---

## Development

```bash
# Backend
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Dashboard
cd dashboard
npm install && npm run dev

# Run tests
cd backend && pytest          # 14 async tests
cd dashboard && npx vitest    # 21 component + API tests

# Database migrations
cd backend && alembic upgrade head
cd backend && alembic revision --autogenerate -m "description"
```

---

## Project Structure

```
mission-control/
├── docker-compose.yml
├── .env.example
├── ROADMAP.md                   # Full roadmap (51/145 features, 35%)
├── CONTRIBUTING.md              # How to contribute
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Settings + multi-auth
│   │   ├── db/
│   │   │   ├── models.py        # 19 SQLAlchemy models
│   │   │   ├── session.py       # DB connection
│   │   │   ├── seed.py          # Example data for new installs
│   │   │   └── migrations/      # Alembic migrations
│   │   ├── api/                 # REST endpoints (12 routers)
│   │   ├── orchestrator/        # Agent execution + scheduling
│   │   ├── agents/              # YAML skill loader
│   │   └── integrations/        # Telegram, Discord, MCP
│   ├── skills/                  # Agent YAML definitions
│   └── tests/                   # pytest async test suite
├── dashboard/
│   ├── app/                     # Next.js App Router (5 pages)
│   │   ├── page.tsx             # Main dashboard
│   │   ├── projects/page.tsx
│   │   ├── agents/page.tsx
│   │   ├── journal/page.tsx
│   │   ├── settings/page.tsx
│   │   ├── components/          # Shared components + nav
│   │   └── lib/api.ts           # API client
│   └── tests/                   # Vitest test suite
└── assets/
    └── banner.svg
```

---

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full roadmap. Current progress: **51/145 features (35%)**.

| Phase | Progress |
|-------|----------|
| Foundation Hardening | 53% |
| Intelligence Layer | 54% |
| Personal Productivity | 52% |
| Dashboard 2.0 | 83% |
| Integrations | 39% |
| Multi-Agent Intelligence | 13% |
| Privacy & Scale | 0% |
| Mobile & Desktop | 0% |
| Community | 0% |

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines. The easiest way to contribute is creating new YAML agent skill files — no backend code needed.

---

## Design Principles

1. **Database is truth** — All state lives in PostgreSQL. No hidden state.
2. **Agents are config** — YAML files, not code. Anyone can create one.
3. **Human in the loop** — AI suggests, humans decide. No irreversible action without approval.
4. **Local first** — Works fully offline with Ollama. Cloud is optional.
5. **Simple over clever** — Ship it, then improve.
6. **Open by default** — Open source, open APIs, open formats. No lock-in.
7. **Privacy by design** — No telemetry, no analytics, no tracking.

## License

MIT
