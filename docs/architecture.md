# Architecture

## Overview

Mission Control is a single FastAPI process with one database. On startup it does the following, in order:

1. Migrates the database to the latest schema (`app/db/migrate.py`).
2. Marks runs that were interrupted by the last shutdown as failed.
3. Syncs agent YAML files from `backend/skills/` into `agent_configs`.
4. Starts four background loops: the **scheduler**, the **Telegram bot** (long polling), the **urgent notification dispatcher**, and the **morning briefing** loop.

The Next.js dashboard is a separate container. It talks to the REST API (`/api/...`) and gets live updates over a WebSocket (`/ws`).

```
 Telegram ─────┐                                         ┌─▶ Claude Agent SDK
 (commands,    │   ┌──────────────────────────────────┐  │   (agent runs, chat)
  chat, voice, ├──▶│ FastAPI                          │──┤
  buttons)     │   │  commands · chat · task threads  │  └─▶ GitHub API
 Dashboard ────┘   │  scheduler · runner · notifier   │      (dev-task issues)
 (REST + /ws)      └────────────────┬─────────────────┘
                                    │
                         PostgreSQL or SQLite
                     (single source of truth + event_log)
```

## The database is the source of truth

Every component reads from and writes to the same database. The process holds very little state in memory:

- A short cache of chat sessions.
- A map of which agent runs are in flight. It prevents duplicate runs of the same agent and makes "stop" possible.

If the app restarts, interrupted runs are marked failed. Tasks that are waiting for an agent are picked up again by the scheduler.

The schema is managed by Alembic (`backend/app/db/migrations/versions/`) and migrated automatically on startup. Models use portable column types, so PostgreSQL and SQLite share the same migrations. A database created by an older version of Mission Control (before Alembic was in use) is converted to the baseline schema once, then upgraded normally.

## Tables

| Table | Purpose |
|-------|---------|
| `projects` | What you're building. `github_repo` (owner/repo) is where `/dev` opens issues |
| `tasks` | Things to do: status, priority, due date, project, assigned agent. Leads are tasks tagged `lead`, with a `url` and `description` |
| `task_comments` | A task's thread: messages from you, the agent, and the system. Stores the Telegram message id so replies can be matched back |
| `notes` | Markdown notes |
| `agent_configs` | Agent definitions, from YAML or the dashboard agent builder |
| `agent_runs` | One row per run: trigger, status, output, error, cost, tokens, transcript |
| `agent_memories` | Per-agent key/value memory, kept across runs |
| `agent_approvals` | Actions from approval-gated agents waiting for you (expire after 24h) |
| `chat_sessions` | Telegram chat history |
| `brand_profile` | Name, bio, tone, topics, talking points, things to avoid, example posts, notification preferences |
| `marketing_content` | Content drafts per channel (x, linkedin, instagram, youtube, blog). Can reference a lead via `task_id` |
| `notifications` | Messages sent (or queued) to Telegram |
| `event_log` | Audit trail |

## Agent runs

An agent runs for one of three reasons:

| Trigger | How it starts | What the agent gets |
|---------|---------------|---------------------|
| **Schedule** | The scheduler finds an interval or cron schedule that is due | Its `prompt_template`, rendered with context |
| **Manual** | `/run <agent>`, chat, or the dashboard | Same as a scheduled run |
| **Task** | A task is assigned to the agent, or you reply in the thread of a task it owns | The task, its thread, and the full context |

Runs always happen in the background. `/run`, the API and the dashboard return immediately. Only one run per agent is active at a time.

For each run, the **runner** (`orchestrator/runner.py`) does the following:

1. Creates an `agent_runs` row and marks the agent as running.
2. Builds context from the tables listed in the agent's `data.reads`. It adds the agent's memory, its last 5 run summaries, the bound project (if any), and, for marketing agents, the brand profile.
3. Renders the prompt. For an assigned task, it uses the task-thread prompt instead.
4. Calls the Claude Agent SDK. The agent works in its own directory (`AGENT_WORKDIR`, by default `backend/workdir`), never in the app's source tree. It can always read files there. On top of that it only gets the tools it was granted: `web_search` (WebSearch/WebFetch), `bash`, and `write` (Write/Edit). Limits are 10 turns, the agent's `max_budget_usd`, and a timeout (300s by default). Rate-limit and overload errors are retried up to 3 times.
5. Parses and validates the JSON output. Unknown action types are dropped. Actions beyond `max_actions_per_run` are dropped.
6. If the agent has `requires_approval`, it stores the actions in `agent_approvals` and sends you a Telegram message with Approve/Reject buttons. Otherwise it applies them, checking each one against the agent's `data.writes`.
7. Records the cost and token counts the SDK reports, along with the transcript.
8. Notifies you:
   - For an assigned task, the agent's reply goes into the thread and to Telegram.
   - For a run started from Telegram (`/run` or chat), you get a Telegram message right away.
   - Scheduled completions, and runs started from the dashboard, are summarized in the morning briefing. The dashboard updates live.
   - Failures are sent immediately.

## Task threads (delegation)

`orchestrator/threads.py` implements a simple turn-taking protocol:

- Assigning a task to an agent adds a user comment and starts the agent.
- The agent answers with `{"summary", "reply", "status", "actions"}`. The `reply` becomes an agent comment and is sent to Telegram.
  - `status: "done"` marks the task done.
  - `status: "needs_input"` marks it blocked ("waiting on you").
- When the latest comment in a thread is from you, it's the agent's turn. You add a comment by replying to the Telegram message, or by commenting in the dashboard. The agent runs again with the whole thread (up to the last 20 comments).
- If the agent is busy, the scheduler starts it when it's free. Assigned tasks are picked up on each scheduler tick, before scheduled runs.
- If a run fails or is stopped, a system comment is added and the task is marked blocked. Reply to try again.

## Dev tasks (Claude Code on GitHub)

Coding work doesn't run inside Mission Control. `integrations/github.py` handles it:

1. `/dev <project> <request>`, the chat, or **Send to Claude Code** in the dashboard creates a task tagged `dev`. It then opens an issue in the project's `github_repo` with a line mentioning `@claude` (unless `GITHUB_MENTION_CLAUDE=false`). The Claude GitHub app, which must be installed on the repo, picks it up and opens a pull request.
2. Every 10 minutes, the scheduler checks open dev tasks on GitHub. It posts newly linked pull requests to the thread and Telegram. When the issue is closed, it marks the task done.
3. A reply in the thread of a dev task (from Telegram or the dashboard) is posted as an issue comment.

This needs `GITHUB_TOKEN` with Issues read/write access.

## Scheduler

`orchestrator/scheduler.py` ticks every 60 seconds. On each tick it:

1. Starts agents for assigned tasks where it's the agent's turn.
2. Starts agents whose schedule is due:
   - `interval`: for example `4h`, `30m` or `1d`, counted from the start of the last run.
   - `cron`: a 5-field expression, evaluated in `NOTIFICATION_TIMEZONE`.

   Agents whose last run failed stay on their schedule. Disabled agents never run.
3. Every 10th tick, runs the GitHub sync.

## Notifications

- **Urgent** notifications are sent to Telegram within about 30 seconds. These include failures, approvals, and results of runs you started from Telegram.
- **Routine** notifications, such as scheduled completions, new leads and new drafts, are not sent one by one. They're covered by the **morning briefing**, which is sent at 8:00 in `NOTIFICATION_TIMEZONE` and is also available on demand with `/morning`.
- In the dashboard's settings you can turn off individual categories: agent completions, agent failures, new leads, and content drafts.
- Messages go to `TELEGRAM_NOTIFICATION_CHAT_ID`, or to the first user in `TELEGRAM_ALLOWED_USERS` if that isn't set.

## Chat

Telegram messages that aren't commands go to `integrations/chat.py`. It calls the Claude Agent SDK (`CHAT_MODEL`) with a snapshot of projects, open tasks, recent notes and agents. The model can answer directly, or return actions: `create_task`, `update_task`, `create_note`, `trigger_agent`, `delegate_task`, `create_dev_task`, `create_content_draft`. A message that replies to a thread message is routed to that task's thread instead of to the chat.

## Security

- The Telegram bot only answers users listed in `TELEGRAM_ALLOWED_USERS`. Anyone else gets a refusal that includes their user ID. If the list is empty, nobody can use the bot.
- The REST API and dashboard have no authentication. Keep them on localhost or a private network.
- Agents only get the tools listed in their skill file, and they run in their own working directory.

## Skill files

Agent behavior is defined in YAML, not code (see [creating-agents.md](creating-agents.md)):

- The skill loader syncs `backend/skills/*.yaml` into `agent_configs` on startup. It matches agents by slug, which is derived from `name`.
- Files whose name starts with `_` (like `_template.yaml`) are skipped.
- If a YAML file is deleted, its agent is disabled on the next startup.
- Agents created in the dashboard agent builder live only in the database.
