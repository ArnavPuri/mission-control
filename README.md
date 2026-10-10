<p align="center">
  <img src="assets/banner.png" alt="Mission Control — Your AI-Powered Command Center" width="100%" />
</p>

<h3 align="center">A Telegram-first personal AI assistant</h3>
<p align="center">Tasks, notes and a small team of AI agents, all in one database.<br/>You talk to it on Telegram. A dashboard gives you the overview.</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="#telegram">Telegram</a> ·
  <a href="#agents">Agents</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="docs/creating-agents.md">Creating Agents</a> ·
  <a href="docs/cost-and-requirements.md">Cost & Requirements</a>
</p>

---

## What it does

- **Captures** tasks and notes from Telegram: slash commands, plain messages, or voice notes.
- **Delegates** work to agents. Hand any task to an agent and it works on it in the background, then replies in the task's thread and on Telegram. Reply to keep the conversation going.
- **Hands coding work to Claude Code.** `/dev` opens a GitHub issue that mentions `@claude`, and Mission Control reports the pull request back to you.
- **Runs agents on a schedule**, for example a Reddit scout every 12 hours or a weekly review on Sunday mornings.
- **Helps with your personal brand.** Marketing agents find leads and draft posts for X, LinkedIn, Instagram, YouTube and your blog. You approve, post, or discard each draft.
- **Sends a morning briefing** on Telegram at 8:00 in your timezone.

It runs on your **Claude Pro/Max subscription** through the Claude Agent SDK. You don't need an Anthropic API key.

**Stack:** Python/FastAPI · Next.js · PostgreSQL or SQLite · Claude Agent SDK · python-telegram-bot

```
 Telegram ──┐                                    ┌──▶ Claude Agent SDK
            │      ┌────────────────────────┐    │    (agents + chat)
 Dashboard ─┼────▶ │  FastAPI backend       │────┤
            │      │  scheduler · runner    │    └──▶ GitHub issues
 REST API ──┘      │  Telegram bot          │         (Claude Code)
                   └───────────┬────────────┘
                               │
                    PostgreSQL / SQLite
                  (single source of truth)
```

---

## Quick Start

You need Docker, a Claude Pro or Max subscription, and a Telegram bot token from [@BotFather](https://t.me/BotFather).

```bash
git clone https://github.com/ArnavPuri/mission-control.git
cd mission-control
cp .env.example .env
```

Fill in three values in `.env`:

| Variable | How to get it |
|----------|---------------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Run `claude setup-token` (or `claude auth login`) with the Claude Code CLI |
| `TELEGRAM_BOT_TOKEN` | Create a bot with @BotFather |
| `TELEGRAM_ALLOWED_USERS` | Your numeric Telegram user ID. Message the bot once and it replies with your ID, or ask @userinfobot |

Then start it:

```bash
docker compose up -d                                 # PostgreSQL
# or
docker compose -f docker-compose.sqlite.yml up -d    # SQLite, no database container
```

- Dashboard: http://localhost:3000
- API: http://localhost:8000 (interactive docs at `/docs`, health check at `/health`)

Prefer a guided setup? Run `./setup.sh`. It asks for the database type, token and integrations, writes `.env`, and starts the containers.

The database schema is created and migrated automatically on startup. A database from an older version of Mission Control is converted once, automatically.

> The dashboard and API have no login. Keep them on localhost or a private network. Telegram is protected by `TELEGRAM_ALLOWED_USERS`.

### Configuration

All settings live in `.env` (see `.env.example`).

| Variable | Required | Purpose |
|----------|----------|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` | yes | Claude Pro/Max subscription token used for agents and chat |
| `TELEGRAM_BOT_TOKEN` | yes | Your Telegram bot |
| `TELEGRAM_ALLOWED_USERS` | yes | Comma-separated Telegram user IDs. The bot rejects everyone else and tells them their ID |
| `TELEGRAM_NOTIFICATION_CHAT_ID` | no | Where notifications go. Defaults to the first allowed user |
| `NOTIFICATION_TIMEZONE` | no | Timezone for the 8:00 morning briefing and agent cron schedules, e.g. `Europe/Berlin` (default `UTC`) |
| `USE_SQLITE` / `SQLITE_PATH` | no | Use SQLite instead of PostgreSQL |
| `GITHUB_TOKEN` | no | Enables `/dev`. Needs Issues read/write on your repos |
| `GITHUB_MENTION_CLAUDE` | no | Mention `@claude` in dev issues (default `true`) |
| `OPENAI_API_KEY` | no | Transcribes Telegram voice messages with Whisper |
| `DEFAULT_MODEL` / `SMART_MODEL` / `CHAT_MODEL` | no | Model defaults (Haiku for cheap agents, Sonnet for chat and smart agents) |
| `MAX_AGENT_BUDGET_USD` | no | Default per-run budget cap for agents that don't set their own |
| `IDENTITY_FILE` | no | Markdown file about you, injected into every agent and chat (default `workspace/identity.md`) |

---

## Telegram

Telegram is the main interface. Send a plain message and an LLM chat handles it. It can create and update tasks, create notes, delegate a task to an agent, open a dev task, or draft content. You can also use commands:

| Command | What it does |
|---------|--------------|
| `/task <text>` | Add a task |
| `/note <title>` | Create a note |
| `/ask <agent> <request>` | Hand a task to an agent. It replies in a thread |
| `/run <agent>` | Run an agent's scheduled job now, in the background. You get a message when it finishes |
| `/dev <project> <request>` | Hand coding work to Claude Code via a GitHub issue |
| `/repo <project> <owner/repo>` | Link a project to its GitHub repo |
| `/approve` | Review pending agent actions (Approve / Reject buttons) |
| `/drafts` | Review the latest content drafts (Approve / Posted / Discard buttons) |
| `/leads` | Open leads found by marketing agents |
| `/status` | Counts of projects, tasks, notes, running agents |
| `/projects` | List projects |
| `/agents` | Agent status, last run and its cost |
| `/brand` | Your brand profile |
| `/morning` | Get the morning briefing now |
| `/help` | List commands |

Agents are matched by slug or by part of their name, so `/ask navigator compare Plausible and Fathom pricing` works.

**Voice messages** are transcribed with OpenAI Whisper and handled like text. This only works when `OPENAI_API_KEY` is set.

---

## Delegating work to agents

You can assign any task to an agent with `/ask`, by asking in chat ("have the researcher look into X"), or from the task dialog in the dashboard.

1. The agent works on the task in the background, using the tools it has been granted.
2. It posts its answer in the task's **thread** and sends it to you on Telegram.
3. **Reply to that Telegram message**, or comment in the dashboard, to continue. Each time, the agent gets the whole thread.
4. When the agent finishes, the task is marked done. If it needs something from you, it asks a question and the task is marked blocked ("waiting on you").

If the agent is busy with another run, the task waits and the scheduler starts it as soon as the agent is free.

## Coding work with Claude Code

Mission Control doesn't write code itself. Instead, it hands coding work to [Claude Code on GitHub](https://github.com/apps/claude):

1. Link a project to its repo with `/repo MyApp owner/myapp`, or in the dashboard project dialog.
2. Send `/dev MyApp add a dark mode toggle`, or click **Send to Claude Code** on a task in the dashboard.
3. Mission Control opens an issue in that repo that mentions `@claude`, and the Claude GitHub app implements it.
4. Every 10 minutes, Mission Control checks the issue. It posts linked pull requests and the issue closing to the task thread and to Telegram.
5. When you reply to those messages, your reply is posted as a comment on the issue.

This needs `GITHUB_TOKEN`, and the Claude GitHub app has to be installed on the repo.

## Reviewing agent output

- **Approvals.** An agent with `requires_approval: true` doesn't act on its own. It sends you a Telegram message listing what it wants to do, with **Approve** and **Reject** buttons. Pending approvals expire after 24 hours. `/approve` lists the ones that are open.
- **Content drafts.** `/drafts` shows the latest drafts with **Approve**, **Posted** and **Discard** buttons.
- The dashboard shows the same items in a **Needs your review** card and in the content list.

## Leads and content

Marketing agents record what they find with the `create_lead` action. A lead is a task tagged `lead`, with a link and a description. `/leads` lists the open ones. Content drafts (for X, LinkedIn, Instagram, YouTube and your blog) can reference the lead they respond to. Drafts use your **brand profile** for tone, topics and things to avoid. You set the brand profile in the dashboard settings.

---

## Agents

Agents are YAML files in `backend/skills/`. They're loaded into the database when the backend starts. You can also create and edit agents in the dashboard's agent builder.

| Agent | Model | Schedule | What it does |
|-------|-------|----------|--------------|
| **Ace** (Assistant) | Sonnet | manual | General-purpose assistant for delegated tasks |
| **Navigator** (Web Researcher) | Sonnet | manual | Researches a topic and writes up findings as notes |
| **Pulse** (Reddit Scout) | Sonnet | every 12h | Finds Reddit threads worth engaging with, and drafts replies |
| **Radar** (Feedback Monitor) | Haiku | daily | Finds public mentions and user feedback about your projects |
| **Scout** (Opportunity Finder) | Sonnet | every 24h | Finds freelance gigs, speaking slots and collaborations |
| **Echo** (Content Drafts) | Sonnet | manual | Turns leads into platform-native content drafts |
| **Atlas** (Weekly Review) | Sonnet | Sundays 10:00 | Reviews the week, re-prioritizes tasks, and writes a plan note |

Any agent can be given a task with `/ask`, including the scheduled ones.

To add your own agent, copy `backend/skills/_template.yaml` and restart the backend. See [docs/creating-agents.md](docs/creating-agents.md).

In short, a skill file declares:

- what data the agent reads (`projects`, `tasks`, `notes`, `leads`, `marketing_content`)
- what it may write (`tasks`, `notes`, `marketing_content`)
- which tools it gets (`web_search`, `bash`, `write`)
- its model, budget, schedule, and prompt

Agents answer in JSON with a `summary` and a list of `actions`. Each agent works in its own directory. It has per-agent memory and can see its last five runs. Run cost is recorded from what the SDK reports.

---

## Dashboard

The dashboard is a small Next.js app for overview and management:

| Page | What's there |
|------|--------------|
| **Overview** (`/`) | Tasks, Needs your review, projects, agents, notes, and content drafts. Clicking a task opens its thread, where you can assign an agent, reply, set the project, or **Send to Claude Code**. You can add and edit projects here, including their GitHub repo |
| **Agents** (`/agents`) | Agent list, run/stop, recent runs with cost and transcripts, and the agent builder (create/edit) |
| **Notes** (`/notes`) | Markdown notes |
| **Settings** (`/settings`) | Brand profile and Telegram notification preferences |

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

# Tests
cd backend && pytest
cd dashboard && npx vitest run

# Migrations (run automatically on startup)
cd backend && alembic upgrade head
cd backend && alembic revision --autogenerate -m "description"
```

When the backend runs outside Docker, it reads `.env` from the repo root. Set `USE_SQLITE=true` for local work without PostgreSQL.

## Project structure

```
mission-control/
├── docker-compose.yml          # PostgreSQL + backend + dashboard
├── docker-compose.sqlite.yml   # backend + dashboard on SQLite
├── setup.sh                    # interactive setup
├── workspace/identity.md       # about you, injected into agents and chat
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app; starts scheduler, Telegram bot, notifier
│   │   ├── config.py           # settings from .env
│   │   ├── api/                # REST endpoints under /api
│   │   ├── db/                 # models, Alembic migrations, startup migration
│   │   ├── orchestrator/       # runner, scheduler, task threads, approvals/drafts
│   │   ├── integrations/       # Telegram bot, chat, commands, GitHub
│   │   ├── notifications/      # Telegram delivery + morning briefing
│   │   └── agents/             # YAML skill loader
│   ├── skills/                 # agent YAML files
│   └── tests/
└── dashboard/
    ├── app/                    # Next.js App Router pages + components
    └── tests/
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The easiest contribution is a new agent YAML file, which needs no backend code.

## License

MIT
