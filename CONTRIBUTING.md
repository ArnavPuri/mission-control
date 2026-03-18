# Contributing to Mission Control

Thanks for your interest in contributing! Mission Control is an open-source personal AI command center, and we welcome contributions of all kinds.

---

## Ways to Contribute

### 1. Create Agent Skill Files (Easiest)

The lowest-barrier way to contribute is writing new YAML agent skill files. No backend code needed.

```bash
cp backend/skills/_template.yaml backend/skills/your-agent.yaml
```

Agent ideas we'd love to see:
- **Learning path agent** — curate resources for a skill
- **Content creation agent** — draft blog posts, tweets, newsletters
- **Health check-in agent** — daily wellness prompts
- **Competitor monitoring agent** — track competitor news
- **Meeting prep agent** — gather context before calendar events

### 2. Dashboard Improvements

The Next.js dashboard (`dashboard/`) always needs love:
- New visualizations (calendar view, Gantt chart)
- Accessibility improvements
- Performance optimization
- Mobile UX refinements

### 3. Integration Connectors

Connect Mission Control to more services:
- Calendar (Google Calendar, CalDAV)
- Linear, Notion, Todoist
- Slack bot
- Email ingestion

### 4. Backend Features

Check the [ROADMAP.md](ROADMAP.md) for open features across all phases.

### 5. Testing

More tests are always welcome:
- Backend: `backend/tests/` (pytest + pytest-asyncio)
- Dashboard: `dashboard/tests/` (Vitest + React Testing Library)

---

## Development Setup

```bash
# Clone the repo
git clone https://github.com/yourname/mission-control.git
cd mission-control

# Backend
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Dashboard
cd dashboard
npm install
npm run dev

# Run tests
cd backend && pytest
cd dashboard && npx vitest
```

### With Docker

```bash
docker compose up -d
```

---

## Pull Request Process

1. **Fork the repo** and create a feature branch from `main`
2. **Make your changes** — keep PRs focused on one feature/fix
3. **Add tests** if you're adding new functionality
4. **Run the test suites** before submitting:
   ```bash
   cd backend && pytest
   cd dashboard && npx vitest run
   cd dashboard && npx next build
   ```
5. **Write a clear PR description** explaining what and why
6. **Link to a ROADMAP item** if applicable (e.g., "Implements Phase 3.4 — Calendar integration")

---

## Code Conventions

### Backend (Python/FastAPI)
- All API routes at `/api/<resource>`
- WebSocket at `/ws` for live dashboard updates
- Agent output must be JSON with `summary` and `actions` fields
- Use Haiku model for cheap agents, Sonnet for smart ones
- The `event_log` table tracks all changes for audit

### Dashboard (Next.js/TypeScript)
- App Router with pages under `app/`
- Shared components in `app/components/shared.tsx`
- API client in `app/lib/api.ts`
- Tailwind CSS for styling
- Radix UI primitives for accessible components

### Agent Skill Files (YAML)
- Place in `backend/skills/`
- Follow the `_template.yaml` structure
- Include clear `description` and `prompt_template`
- Specify `data_reads` and `data_writes` explicitly
- Set reasonable `max_budget_usd` (start with 0.05 for Haiku)

---

## Architecture Decisions

- **PostgreSQL is the single source of truth** — no hidden state
- **Agents are config, not code** — YAML files define behavior
- **Multi-auth by design** — support API keys, OAuth, OpenRouter, Ollama
- **Event-driven** — all mutations log to `event_log` and broadcast via WebSocket
- **Human-in-the-loop** — agents requiring approval queue actions for review

---

## Getting Help

- Open an issue for bugs or feature discussions
- Check existing issues before creating new ones
- Reference specific ROADMAP phases when proposing features

---

## Priority Areas

Where help is most needed right now:

| Area | Skills | Impact |
|------|--------|--------|
| Agent skill files | YAML, prompt engineering | High — every new agent adds value |
| Dashboard views | React, Next.js, TypeScript | High — daily driver improvements |
| Integration connectors | Python, API experience | Medium — connect more services |
| Testing | pytest, Vitest | Medium — reliability and confidence |
| Documentation | Technical writing | Medium — lower barrier to entry |

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
