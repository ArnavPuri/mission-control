# Mission Control

A personal AI-powered command center. One database, many agents, one dashboard.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  Telegram    │────▶│  Orchestrator │────▶│  Agent Pool  │
│  Claude Code │     │  (scheduler)  │     │  (workers)   │
│  MCP Server  │     └──────┬───────┘     └──────┬──────┘
└─────────────┘            │                     │
                     ┌─────▼─────────────────────▼─────┐
                     │        PostgreSQL + pgvector     │
                     │  (projects, tasks, ideas, agents,│
                     │   reading list, event log)       │
                     └─────────────┬───────────────────┘
                                   │
                            ┌──────▼──────┐
                            │  Dashboard   │
                            │  (Next.js)   │
                            └─────────────┘
```

## Philosophy

- **Database is the source of truth.** Everything reads from and writes to one Postgres instance.
- **Agents are config files.** Drop a YAML in `skills/` and you have a new agent.
- **Dashboard is read-only.** It shows status, it doesn't control state.
- **Bring your own brain.** API key, OAuth token, or self-hosted LLM — your choice.

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/yourname/mission-control.git
cd mission-control
cp .env.example .env
# Edit .env with your API key and Telegram token

# 2. Start everything
docker compose up -d

# 3. Open the dashboard
open http://localhost:3000
```

## Authentication Options

| Method | Env Variable | Notes |
|--------|-------------|-------|
| Anthropic API Key | `ANTHROPIC_API_KEY` | **Recommended.** Pay-per-token, no expiry. |
| Claude Subscription | `CLAUDE_CODE_OAUTH_TOKEN` | Uses Pro/Max plan. Run `claude setup-token` to get token. May expire. |
| OpenRouter | `OPENROUTER_API_KEY` | Access to many models via one key. |
| Ollama (local) | `OLLAMA_BASE_URL` | Free, private, runs on your hardware. |

## Creating Agents

Agents are defined as YAML skill files in `backend/skills/`. Copy `_template.yaml` to get started:

```bash
cp backend/skills/_template.yaml backend/skills/my-agent.yaml
```

Each skill file defines:
- **What the agent does** (prompt template)
- **What data it reads** (projects, tasks, ideas, reading list)
- **What data it writes** (create tasks, ideas, reading items)
- **When it runs** (interval, cron, or manual trigger)
- **Which model to use** (haiku for cheap/fast, sonnet for smart)
- **Budget cap** per run

See `backend/skills/` for examples:
- `reddit-scout.yaml` — Finds Reddit promo opportunities
- `idea-validator.yaml` — Validates ideas with market research
- `weekly-prioritizer.yaml` — Suggests weekly focus areas
- `feedback-collector.yaml` — Scrapes user feedback from public sources

## Adding Items via Telegram

Set `TELEGRAM_BOT_TOKEN` in `.env` and optionally `TELEGRAM_ALLOWED_USERS`.

Commands:
- `/task Fix the login bug` — Add a task
- `/idea AI-powered meal planner #saas #ai` — Capture an idea with tags
- `/read Tauri 2.0 Guide https://tauri.app/guide` — Add to reading list
- `/status` — Get dashboard stats
- `/run reddit-scout` — Trigger an agent
- `/projects` — List all projects

Plain text messages are captured as quick tasks.

## Claude Code / MCP Integration

Add Mission Control as an MCP server in Claude Code to manage your tasks directly from the terminal:

```json
// ~/.claude/claude_desktop_config.json
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

Then in Claude Code:
```
> "What are my open tasks?"
> "Add a task: Review PR #42 for UseGlittr"
> "Run the idea validator agent"
```

## Project Structure

```
mission-control/
├── docker-compose.yml          # Full stack orchestration
├── .env.example                # Configuration template
├── backend/
│   ├── pyproject.toml          # Python dependencies
│   ├── app/
│   │   ├── main.py             # FastAPI application
│   │   ├── config.py           # Settings + multi-auth
│   │   ├── db/
│   │   │   ├── models.py       # SQLAlchemy models (the schema)
│   │   │   └── session.py      # DB connection management
│   │   ├── api/                # REST endpoints
│   │   │   ├── projects.py
│   │   │   ├── tasks.py
│   │   │   ├── ideas.py
│   │   │   ├── reading.py
│   │   │   ├── agents.py
│   │   │   └── ws.py           # WebSocket for live updates
│   │   ├── orchestrator/
│   │   │   ├── runner.py       # Agent execution engine
│   │   │   └── scheduler.py    # Cron/interval scheduler
│   │   ├── agents/
│   │   │   └── skill_loader.py # YAML skill file parser
│   │   └── integrations/
│   │       ├── telegram.py     # Telegram bot
│   │       └── mcp_server.py   # MCP server for Claude Code
│   └── skills/                 # Agent definitions
│       ├── _template.yaml
│       ├── reddit-scout.yaml
│       ├── idea-validator.yaml
│       ├── weekly-prioritizer.yaml
│       └── feedback-collector.yaml
├── dashboard/                  # Next.js frontend (TODO)
└── docs/
    ├── architecture.md
    └── creating-agents.md
```

## Development

```bash
# Backend only (without Docker)
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Run tests
pytest

# Lint
ruff check .
```

## Roadmap

- [ ] Dashboard (Next.js)
- [ ] Alembic migrations
- [ ] Agent approval queue (for `requires_approval: true`)
- [ ] pgvector semantic search on ideas/tasks
- [ ] Agent cost tracking dashboard
- [ ] Webhook integrations (GitHub, Stripe, etc.)
- [ ] Multi-user support with auth
- [ ] Helm chart for Kubernetes deployment

## License

MIT
