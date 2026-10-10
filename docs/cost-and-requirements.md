# Cost & Requirements

## What you pay for

| Item | Needed? | Notes |
|------|---------|-------|
| **Claude Pro or Max subscription** | Yes | Every agent run, chat message and agent-builder prompt goes through the Claude Agent SDK, using your subscription (`CLAUDE_CODE_OAUTH_TOKEN`). No Anthropic API key or API billing is involved |
| **A machine to run it on** | Yes | Your own computer, a home server, or a small VPS. See the hardware section below |
| OpenAI API | Optional | Only for transcribing Telegram voice messages (Whisper). Billed by OpenAI |
| Claude Code on GitHub | Optional | `/dev` issues are implemented by the Claude GitHub app, which runs in GitHub, not in Mission Control. Its usage, and any GitHub Actions minutes, depend on how you set up that app in your repo |

Telegram and the GitHub API (for `/dev`) cost nothing.

## How usage works on a subscription

Mission Control doesn't spend money per run. Its usage counts toward your Claude plan's usage limits, which are shared with your other Claude and Claude Code use. Heavy schedules can therefore eat into the limits you have for your own work.

For each run, the SDK reports a **dollar figure** (`total_cost_usd`). Mission Control records it on the run (`agent_runs.cost_usd`) and shows it in `/agents` (last run) and on each run in the dashboard Agents page. Read it as the SDK's estimate of what the run would cost at API prices, not as a charge. It's useful for comparing agents and spotting expensive ones.

`max_budget_usd` in a skill file (default `MAX_AGENT_BUDGET_USD`, 0.50) caps a single run against that same estimate. When the cap is reached, the SDK stops the run.

What uses the subscription:

- **Scheduled agent runs.** These are the steady background load (see the table below).
- **Delegated tasks.** Each turn in a task thread is one run.
- **Telegram chat.** Each plain message is one model call with `CHAT_MODEL` (Sonnet by default).
- **Morning briefing.** This is built from the database and doesn't use the model.

Usage per run varies a lot. A Haiku agent with no tools is light. A Sonnet agent that searches the web for several turns is much heavier. Check the recorded per-run figures to see what your agents actually use.

## Default agent schedules

| Agent | Model | Schedule | Scheduled runs |
|-------|-------|----------|----------------|
| Pulse (Reddit Scout) | Sonnet + web search | every 12h | ~60/month |
| Scout (Opportunity Finder) | Sonnet + web search | every 24h | ~30/month |
| Radar (Feedback Monitor) | Haiku + web search | daily | ~30/month |
| Atlas (Weekly Review) | Sonnet | Sundays 10:00 | ~4/month |
| Ace, Navigator, Echo | Sonnet | manual | only when you use them |

## Keeping usage down

- **Run scouts less often.** For example, change Pulse's `every: 12h` to `24h` in `reddit-scout.yaml`.
- **Make agents manual.** Set `schedule.type: manual`. Delegation (`/ask`) and `/run` still work.
- **Disable agents you don't use** from the dashboard, or delete their YAML file. Agents whose file is gone are disabled on the next startup.
- **Use Haiku** for scanning and classifying.
- **Lower `max_budget_usd`** to cap individual runs.
- **Grant `web_search` only where it's needed.** Searching and fetching pages adds turns.

## Hardware

Everything runs on one machine with Docker Compose:

| Service | Notes |
|---------|-------|
| PostgreSQL 16 | Not needed in SQLite mode (`docker-compose.sqlite.yml`) |
| Backend | Python 3.12 + the Claude Code CLI (Node.js), which the Agent SDK uses. Agent runs happen in this container |
| Dashboard | Next.js |

The work is mostly waiting on the network, so a small machine is enough for personal use. A 2-core machine with about 2 GB of RAM is a reasonable starting point. SQLite mode needs less, because it has no database container. If several agents run at the same time, each one starts its own Claude Code process, so leave some memory headroom.

**Storage:** The database grows slowly. `event_log` and `agent_runs` grow the fastest, because each run stores its output and a truncated transcript. Nothing is deleted automatically.

## Network

Mission Control only makes outbound connections. Telegram uses long polling, so you don't need to open a port to the internet.

| Destination | Why |
|-------------|-----|
| Anthropic (via the Claude Code CLI) | Agent runs and chat |
| `api.telegram.org` | The bot and notifications |
| `api.github.com` | `/dev` issues and the 10-minute sync (optional) |
| `api.openai.com` | Voice transcription (optional) |
| The web | Agents with the `web_search` tool |

Your browser reaches everything through Caddy on ports 80/443 (the backend and database ports are bound to localhost). Set `DASHBOARD_PASSWORD` before exposing it, and `SITE_ADDRESS` to your domain for automatic HTTPS.
