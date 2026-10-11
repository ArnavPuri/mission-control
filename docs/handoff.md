# Handoff: where Mission Control stands

_Last updated October 2026. Read [CLAUDE.md](../CLAUDE.md) and [architecture.md](architecture.md) first._

## What it is now

A Telegram-first personal assistant with a small team of agents. You message it; quick things (tasks, notes, reminders) happen right away, and real work goes to **Ace, the coordinator**, which splits it across specialists (Navigator researches, Echo writes, Pulse finds leads, …) and sends back one answer. Coding work goes to Claude Code as GitHub issues. Drafts can be published to X and LinkedIn. A dashboard shows everything, live.

## What was built in the latest round

In order, one commit each:

1. **Cleanup and bug fixes.** Removed unused features, migrations and docs; one Alembic baseline (`0001`) plus a converter for pre-Alembic databases.
2. **Task threads and delegation.** `/ask`, Telegram reply-to-continue, inline Approve/Reject and draft buttons, `/dev` → GitHub issue for Claude Code with PR/close sync.
3. **Dashboard redesign.** Today view, task board with drag and drop, task sheet, ⌘K, dark mode.
4. **Deployable and private.** Login (`DASHBOARD_PASSWORD`, `API_TOKEN`), Caddy with automatic HTTPS, nightly backups.
5. **Reminders, due dates, repeating tasks.** `/remind`, `/today`, Done/Snooze buttons, recurrence, due badges, morning briefing shows due and overdue.
6. **Agent handoffs and live progress.** `handoff` action, linked tasks (`parent_task_id`), tool-call progress streamed to the dashboard.
7. **Publishing.** X (OAuth 1.0a, threads) and LinkedIn (Posts API), with a confirm step.
8. **The coordinator.** Ace (`role: coordinator`) takes chat requests and `/do`, hands out pieces, waits until all have settled, answers once; `follow_up` action; one voice on Telegram.

## How it was verified

- Backend: `cd backend && pytest` (120 tests). Dashboard: `cd dashboard && npx vitest run` (33 tests) and `npx next build`.
- The dashboard was driven in a real browser (Playwright) against a local backend with seeded data, for each feature; the Docker stack (SQLite + Caddy) was brought up and checked end to end, including login and live updates.
- Agent runs in tests are stubbed. Local end-to-end runs used a dead `ANTHROPIC_BASE_URL`, so nothing spent the subscription.

## Not yet tried against the real services

These are covered by tests against fakes, but haven't run for real:

- A coordinated request with real agents. Watch whether Ace's plans and final answers read well, and how many rounds it uses; tune `coordinator.SYSTEM_PROMPT` and Ace's skill file if not.
- Telegram reminders and the Done/Snooze buttons on a real bot.
- Publishing to X and LinkedIn with real keys. X charges for API posts; LinkedIn tokens expire after 60 days.
- The Docker deployment on a real server with a domain (HTTPS via Caddy).

## Known limits and good next steps

See also [research.md](research.md): eight papers with concrete ideas for what to build next (prompt-injection safety for web-reading agents, making the coordinator more reliable, agents that learn from your feedback, long-term memory).

- **Ace works on one request at a time** (one run per agent). Others queue and are picked up within a minute. If that's too slow, allow a coordinator several concurrent runs (runs are keyed by agent id in `runner._active_runs`).
- **Posts are text only.** Images and video, and scheduling a post for later, are the natural next publishing features.
- **X thread splitting** counts characters as written (X counts links as 23), so it errs on the short side.
- **No calendar or email integration** yet; reminders are the only time-based feature.
- The dashboard has no page for content drafts beyond "Needs you" (drafts and approved posts); a content calendar would be the next UI step.

## Running it locally

```bash
cp .env.example .env            # set CLAUDE_CODE_OAUTH_TOKEN, TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USERS
make up                          # Docker: http://localhost
# or, for development:
make dev                         # uvicorn --reload on :8000 and next dev on :3000
```
