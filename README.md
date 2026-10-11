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
- **Reminds you.** "Remind me tomorrow at 9 to call Sam" becomes a task that pings you on Telegram with Done / Snooze buttons. Tasks can have due dates and repeat daily, on weekdays, weekly or monthly.
- **Delegates** work to agents. Hand any task to an agent and it works on it in the background, then replies in the task's thread and on Telegram. Reply to keep the conversation going.
- **Hands coding work to Claude Code.** `/dev` opens a GitHub issue that mentions `@claude`, and Mission Control reports the pull request back to you.
- **Runs agents on a schedule**, for example a Reddit scout every 12 hours or a weekly review on Sunday mornings.
- **Helps with your personal brand.** Marketing agents find leads and draft posts for X, LinkedIn, Instagram, YouTube and your blog. You approve, post, or discard each draft.
- **Sends a morning briefing** on Telegram at 8:00 in your timezone, with what's due today and what's overdue.

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

Fill in these values in `.env`:

| Variable | How to get it |
|----------|---------------|
| `CLAUDE_CODE_OAUTH_TOKEN` | Run `claude setup-token` (or `claude auth login`) with the Claude Code CLI |
| `TELEGRAM_BOT_TOKEN` | Create a bot with @BotFather |
| `TELEGRAM_ALLOWED_USERS` | Your numeric Telegram user ID. Message the bot once and it replies with your ID, or ask @userinfobot |
| `DASHBOARD_PASSWORD` | Any strong password. Required unless you only open the dashboard on this machine |

Then start it:

```bash
docker compose up -d                                 # PostgreSQL
# or
docker compose -f docker-compose.sqlite.yml up -d    # SQLite, no database container
```

Open **http://localhost**. One address serves everything: Caddy serves the dashboard and passes `/api`, `/ws` and `/health` to the backend (interactive API docs at `/docs`).

Prefer a guided setup? Run `./setup.sh`. It asks for the database type, tokens, a dashboard password and an optional domain, writes `.env`, and starts the containers.

The database schema is created and migrated automatically on startup. A database from an older version of Mission Control is converted once, automatically.

### Running it on a server

1. Point a domain's DNS (A record) at the server and open ports 80 and 443.
2. In `.env`, set `SITE_ADDRESS=mc.example.com` and a `DASHBOARD_PASSWORD`.
3. `docker compose up -d`. Caddy gets an HTTPS certificate on its own; open `https://mc.example.com` and sign in.

The backend and database ports are bound to `127.0.0.1` only. Scripts can call the API with `Authorization: Bearer $API_TOKEN` if you set `API_TOKEN`. Without a `DASHBOARD_PASSWORD` the dashboard is open to anyone who reaches it, and it says so in a banner.

### Backups

The backend backs up the database every night at `BACKUP_HOUR` (default 3:00, your timezone) and keeps the last `BACKUP_KEEP` (14) in the `backend-data` volume (`/app/data/backups`). Run one now with `make backup`. To restore:

```bash
# SQLite: stop the stack, then copy a backup over the database
docker compose -f docker-compose.sqlite.yml run --rm backend cp /app/data/backups/<file>.db /app/data/mission_control.db

# PostgreSQL
docker compose exec backend sh -c 'pg_restore --clean --no-owner -h db -U $POSTGRES_USER -d $POSTGRES_DB /app/data/backups/<file>.dump'
```

Copy the backups somewhere off the server too (e.g. `docker compose cp backend:/app/data/backups ./backups`).

### Configuration

All settings live in `.env` (see `.env.example`).

| Variable | Required | Purpose |
|----------|----------|---------|
| `CLAUDE_CODE_OAUTH_TOKEN` | yes | Claude Pro/Max subscription token used for agents and chat |
| `TELEGRAM_BOT_TOKEN` | yes | Your Telegram bot |
| `TELEGRAM_ALLOWED_USERS` | yes | Comma-separated Telegram user IDs. The bot rejects everyone else and tells them their ID |
| `DASHBOARD_PASSWORD` | yes, off localhost | Password for the dashboard and API |
| `SITE_ADDRESS` | no | Your domain, for automatic HTTPS (default `:80`, plain HTTP) |
| `API_TOKEN` | no | Bearer token for scripts calling the API |
| `BACKUP_HOUR` / `BACKUP_KEEP` | no | Nightly backup time and how many to keep (3, 14) |
| `TELEGRAM_NOTIFICATION_CHAT_ID` | no | Where notifications go. Defaults to the first allowed user |
| `NOTIFICATION_TIMEZONE` | no | Your timezone, e.g. `Europe/Berlin` (default `UTC`). Used for the 8:00 morning briefing, reminders ("tomorrow at 9") and agent cron schedules |
| `USE_SQLITE` / `SQLITE_PATH` | no | Use SQLite instead of PostgreSQL |
| `GITHUB_TOKEN` | no | Enables `/dev`. Needs Issues read/write on your repos |
| `GITHUB_MENTION_CLAUDE` | no | Mention `@claude` in dev issues (default `true`) |
| `OPENAI_API_KEY` | no | Transcribes Telegram voice messages with Whisper |
| `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET` | no | Publish drafts to X (an app with read and write access, and your account's access token) |
| `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_URN` | no | Publish drafts to LinkedIn (a `w_member_social` token and your `urn:li:person:…`) |
| `DEFAULT_MODEL` / `SMART_MODEL` / `CHAT_MODEL` | no | Model defaults (Haiku for cheap agents, Sonnet for chat and smart agents) |
| `MAX_AGENT_BUDGET_USD` | no | Default per-run budget cap for agents that don't set their own |
| `IDENTITY_FILE` | no | Markdown file about you, injected into every agent and chat (default `workspace/identity.md`) |

---

## Telegram

Telegram is the main interface. Send a plain message and an LLM chat handles it. Quick things (tasks, notes, reminders, "what's due?") it does right away. Real work goes to the **coordinator**, who runs the team and gets back to you with one answer (see below). It can also open a dev task or draft content. You can also use commands:

| Command | What it does |
|---------|--------------|
| `/task <text>` | Add a task |
| `/note <title>` | Create a note |
| `/remind <when> <what>` | Add a task with a reminder, e.g. `/remind tomorrow 9am call Sam`. On its own it lists upcoming reminders |
| `/today` | What's overdue, due today, and today's reminders |
| `/do <request>` | Hand work to the coordinator, who splits it across the team and answers once |
| `/ask <agent> <request>` | Hand a task to a specific agent. It replies in a thread |
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

**Reminders.** `/remind` understands times like `in 2h`, `at 5`, `tonight`, `tomorrow 9am`, `friday 10:30`, `next monday`, `oct 12` or `2026-12-01 15:00`, before or after the text. Adding `every day`, `every weekday`, `every monday`, `weekly` or `monthly` makes the task repeat. In chat you can just say it ("remind me to send the invoice on the 1st of every month"). Times are in `NOTIFICATION_TIMEZONE`. The reminder message has **Done**, **1 hour** and **Tomorrow** buttons. Replying to it adds a note to the task. Completing a repeating task creates the next one, with its due date and reminder moved forward.

**Voice messages** are transcribed with OpenAI Whisper and handled like text. This only works when `OPENAI_API_KEY` is set.

---

## The coordinator

One agent, Ace, is the **coordinator**: you tell it what you want, and it runs the team. Send a plain message on Telegram ("compare Plausible and Fathom and draft a LinkedIn post about why we switched"), or use `/do`.

1. Ace does small things itself. Bigger requests it splits up and hands each piece to the right specialist: Navigator researches, Echo drafts. Independent pieces run in parallel; a piece that needs another's result goes out once that result is in.
2. You get one message with the plan ("On it: Navigator compares the tools, Echo drafts the post").
3. The specialists report back to Ace, not to you. If one has a question, Ace answers it from context or asks you; your reply goes back to the right agent.
4. When everything is in, Ace sends you **one finished answer**: the research and the draft, not a status report.

In the dashboard, the request is one task with its handed-off pieces underneath. Home shows who it's waiting on. Ace gets at most 5 rounds and 6 handoffs per round for a request. Set `COORDINATOR_RELAY_TEAMMATES=true` to also get each specialist's reply on Telegram.

Any agent can be the coordinator: put `role: coordinator` in its skill file (only one should have it). Naming an agent ("ask Echo to …") or `/ask echo …` still goes straight to that agent.

## Delegating work to agents

You can assign any task to an agent with `/ask`, by asking in chat ("have the researcher look into X"), or from the task dialog in the dashboard.

1. The agent works on the task in the background, using the tools it has been granted.
2. It posts its answer in the task's **thread** and sends it to you on Telegram.
3. **Reply to that Telegram message**, or comment in the dashboard, to continue. Each time, the agent gets the whole thread.
4. When the agent finishes, the task is marked done. If it needs something from you, it asks a question and the task is marked blocked ("waiting on you").

If the agent is busy with another run, the task waits and the scheduler starts it as soon as the agent is free.

While an agent works, the task sheet shows what it's doing live ("Searching the web: …", "Reading plausible.io/pricing"). The Home page shows the latest step too.

**Agents hand work to each other.** Every agent knows its teammates. When part of the job belongs to someone else, it hands it off. For example, Pulse finds a promising Reddit thread and asks Echo to draft the reply. The handoff becomes a new task assigned to the teammate and linked to the original ("Part of …"). The teammate replies in its own thread and on Telegram, and the original task's thread records the handoff and its outcome. A chain of handoffs is at most 3 tasks deep, and one run can hand off at most 3 times. Handoffs go through approval like any other action when the agent has `requires_approval` set.

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
- **Content drafts.** `/drafts` shows the latest drafts with **Approve**, **Posted** and **Discard** buttons. If X or LinkedIn is connected, there's also **🚀 Publish**. It asks once more, then posts the draft and saves the link. A draft longer than one X post goes out as a thread.
- The dashboard shows the same items under **Needs you**. Click a draft to edit it, see its length against the channel's limit, and publish it.

### Publishing to X and LinkedIn

Publishing is optional. Without it, you copy the draft yourself and tap **Posted**.

- **X:** create an app at [developer.x.com](https://developer.x.com) with *Read and write* permissions. Then generate the access token and secret for your own account. Set `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN` and `X_ACCESS_TOKEN_SECRET`. X charges for API posting, so check your plan on the developer portal.
- **LinkedIn:** you need a member access token with the `w_member_social` scope and your member URN (`urn:li:person:…`). Set `LINKEDIN_ACCESS_TOKEN` and `LINKEDIN_AUTHOR_URN`. LinkedIn tokens expire after 60 days; when publishing reports a rejected token, generate a new one. `LINKEDIN_API_VERSION` (default `202609`) pins the API version; LinkedIn retires versions after about a year.

Instagram, YouTube and blog drafts are posted by hand.

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

The dashboard is a Next.js app for overview and management, in light and dark mode. The sidebar lists your projects; **⌘K** opens a command menu that searches everything and turns what you type into a task, optionally handed straight to an agent.

| Page | What's there |
|------|--------------|
| **Home** (`/`) | Today view: what needs you (approvals, questions from agents, drafts), work delegated to agents, your own tasks, and an activity feed of agent replies |
| **Tasks** (`/tasks`) | Board by status (To do · In progress · Waiting on you · Done) with drag and drop, filters (mine, delegated, leads) and per-project views |
| **Task sheet** | Opens from anywhere: status, priority, due date, reminder, repeat, assignee, project, **Send to Claude Code**, work handed off to other agents, the agent's live progress, and the thread with the agent (rendered markdown) |
| **Agents** (`/agents`) | Agents with run/stop, 30-day runs, success rate and cost, run output and transcripts, and the agent builder |
| **Notes** (`/notes`) | Two-pane markdown notes with autosave |
| **Settings** (`/settings`) | Connection status, brand profile, Telegram notification preferences |

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

`make dev` runs both with live reload. When the backend runs outside Docker, it reads `.env` from the repo root; set `USE_SQLITE=true` for local work without PostgreSQL. In dev the dashboard (`:3000`) talks to the backend on `:8000` (see `dashboard/.env.development`).

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
