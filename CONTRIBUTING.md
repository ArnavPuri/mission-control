# Contributing to Mission Control

Thanks for your interest! Mission Control is a small, Telegram-first personal assistant.
Contributions that keep it small and focused are the most welcome.

## Ways to contribute

- **Agent skill files.** This is the easiest way to contribute and needs no backend code.
  Copy `backend/skills/_template.yaml`, then see [docs/creating-agents.md](docs/creating-agents.md).
- **Bug fixes and tests.** Backend tests are in `backend/tests/` (pytest + pytest-asyncio).
  Dashboard tests are in `dashboard/tests/` (Vitest + React Testing Library).
- **Dashboard and Telegram UX.** Look for small improvements to everyday flows: capturing
  tasks, delegating, reviewing drafts and approvals.
- **Docs.** Fix anything in the docs that doesn't match how the app actually behaves.

For anything bigger, open an issue first so we can agree on the approach.

## Development setup

```bash
git clone https://github.com/ArnavPuri/mission-control.git
cd mission-control
cp .env.example .env    # set CLAUDE_CODE_OAUTH_TOKEN; USE_SQLITE=true is easiest locally

# Backend
cd backend
pip install -e ".[dev]"
uvicorn app.main:app --reload

# Dashboard (in another terminal)
cd dashboard
npm install
npm run dev
```

Or run everything with `docker compose up -d`.

## Pull requests

1. Branch from `main` and keep each PR to one change.
2. Add tests for new behavior.
3. Run the checks:
   ```bash
   cd backend && pytest
   cd dashboard && npx vitest run
   cd dashboard && npx next build
   ```
4. If you changed `backend/app/db/models.py`, add a migration with
   `cd backend && alembic revision --autogenerate -m "description"`.
5. Explain what changed and why in the PR description.

## Conventions

**Backend (Python/FastAPI)**
- API routes live under `/api/<resource>`. There's a WebSocket at `/ws` for live dashboard updates.
- Write changes to `event_log` so there's an audit trail.
- Model columns must use portable types (`Uuid`, `JSON`) so PostgreSQL and SQLite both work.
- All LLM calls go through the Claude Agent SDK with the subscription token. Don't add API-key code paths.

**Dashboard (Next.js/TypeScript)**
- Pages use the App Router under `app/`. Shared components are in `app/components/` and the API client is in `app/lib/api.ts`.
- Style with Tailwind CSS. Use Radix UI primitives for dialogs and menus.

**Agent skill files (YAML)**
- One agent, one job.
- List `data.reads` and `data.writes` explicitly. Only grant the tools the agent needs.
- Use Haiku for scanning and classifying, and Sonnet for analysis and writing.
- Set a modest `max_budget_usd`.

## Principles

- **The database is the single source of truth.** No hidden state.
- **Agents are config.** You define them in YAML, not code.
- **A human stays in the loop.** Agents suggest. Approval-gated actions and drafts wait for you.
- **Simple over clever.** Ship the small version first.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
