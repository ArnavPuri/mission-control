# Creating Agents

An agent is a YAML file in `backend/skills/`. On startup, the backend syncs every skill file into the database. You can also create and edit agents in the dashboard (**Agents → Create Agent**). Agents created there live only in the database.

## Quick start

```bash
cp backend/skills/_template.yaml backend/skills/my-agent.yaml
# edit it, then restart the backend so it's loaded:
docker compose restart backend
```

- Files whose name starts with `_` are ignored, so the template itself never becomes an agent.
- An agent's **slug** comes from its `name`. For example, `Navigator (Web Researcher)` becomes `navigator-web-researcher`.
- `/run` and `/ask` accept the slug or any unique part of the name.

## Anatomy of a skill file

```yaml
name: Sage (Learning Coach)    # display name; the slug is derived from it
description: Finds one good resource a day for what I'm learning
version: "1.0"
type: research                 # marketing | research | content | ops | general

persona: A patient coach who curates instead of overwhelming   # who the agent is
tone: Warm and brief                                           # how it writes

model: claude-haiku-4-5        # or claude-sonnet-4-6
max_budget_usd: 0.10           # per-run cap (see below)

tools:                         # beyond reading files in its own workdir
  - web_search                 # WebSearch + WebFetch
  # - bash                     # shell commands in its workdir
  # - write                    # create/edit files in its workdir

data:
  reads: [projects, notes]     # what goes into its context
  writes: [notes]              # what its actions may change

schedule:
  type: cron                   # interval | cron | manual
  every: "0 7 * * *"           # 07:00 daily in NOTIFICATION_TIMEZONE

prompt_template: |
  Projects: {{projects}}
  Recent notes: {{notes}}
  ...
  Respond with JSON: {"summary": "...", "actions": [...]}

requires_approval: false       # true: actions wait for Approve/Reject on Telegram
max_actions_per_run: 5         # extra actions are dropped
timeout_seconds: 300           # optional, default 300
# role: coordinator            # only for the one agent that runs the team (Ace)
```

You don't need to put identity in the prompt. The runner builds the system prompt automatically from the agent's `name`, `description`, `persona` and `tone`, the contents of `workspace/identity.md` (about you), and the JSON output rules. Your `prompt_template` only needs to describe the job and the data.

## Schedules

| Type | `every` | Example |
|------|---------|---------|
| `interval` | `30m`, `4h`, `1d` | Runs that long after the previous run started |
| `cron` | 5-field cron | `"0 10 * * 0"` means Sundays at 10:00, in `NOTIFICATION_TIMEZONE` |
| `manual` | — | Only runs with `/run`, from the dashboard, or when given a task |

Every agent can be given tasks with `/ask`, whatever its schedule.

## Context variables

Each entry in `data.reads` adds a variable you can use in `prompt_template`:

| `reads` entry | Variable | Contents |
|---------------|----------|----------|
| `projects` | `{{projects}}` | All projects (id, name, description, status) |
| `tasks` | `{{tasks}}` | Open tasks (leads excluded). Limited to the agent's project if it's bound to one |
| `notes` | `{{notes}}` | The 20 most recently updated notes (content truncated) |
| `leads` | `{{leads}}` | Up to 50 open leads (title, body, url, priority, tags) |
| `marketing_content` | `{{marketing_content}}` | The 20 newest content drafts |

These variables are added automatically:

| Variable | When | Contents |
|----------|------|----------|
| `{{memory}}` | The agent has saved memory | Key/value pairs saved with `save_memory` |
| `{{past_runs}}` | The agent has completed runs | Summaries of its last 5 runs |
| `{{project}}` | The agent is bound to a project (`project_id`, settable through the API) | That project |
| `{{brand}}` | `reads` includes `leads` or `marketing_content` | Your brand profile: tone, topics, talking points, things to avoid, example posts |

Data variables (`{{projects}}`, `{{tasks}}`, ...) only appear where you put them in the template. `{{project}}`, `{{brand}}`, `{{memory}}`, `{{past_runs}}` and `{{teammates}}` are always included: if the template doesn't place them, they're appended after it. On **assigned tasks**, the whole context is included automatically.

## Actions

The agent responds with JSON:

```json
{
  "summary": "What I did, in one or two lines",
  "actions": [
    {"type": "create_task", "text": "...", "description": "...", "priority": "high", "tags": ["tag"]},
    {"type": "update_task", "task_id": "<id>", "status": "done", "priority": "low"},
    {"type": "create_note", "title": "...", "content": "markdown", "tags": ["tag"]},
    {"type": "create_lead", "title": "...", "body": "...", "url": "https://...", "source_type": "reddit", "relevance_score": 0.8, "tags": ["tag"]},
    {"type": "create_content", "title": "...", "body": "...", "channel": "x", "task_id": "<lead id>"},
    {"type": "save_memory", "key": "...", "value": "..."},
    {"type": "handoff", "agent": "<teammate slug>", "request": "everything they need to know", "task_id": "<related task>"},
    {"type": "follow_up", "task_id": "<a task you handed out>", "request": "..."}
  ]
}
```

| Action | Needs in `writes` | Notes |
|--------|-------------------|-------|
| `create_task` | `tasks` | Priority is `critical`, `high`, `medium` or `low` |
| `update_task` | `tasks` | Changes status (`todo`, `in_progress`, `blocked`, `done`) and/or priority |
| `create_lead` | `tasks` | Creates a task tagged `lead` (plus `source_type` and `tags`). `relevance_score` ≥ 0.8 gives high priority, < 0.5 gives low |
| `create_note` | `notes` | Markdown content |
| `create_content` | `marketing_content` | `channel` is one of `x`, `linkedin`, `instagram`, `youtube` or `blog`. `task_id` can point to the lead it responds to |
| `save_memory` | — | Always allowed. Stores a value under the key, overwriting any existing value for that key |
| `handoff` | — | Always allowed. Creates a task for a teammate (by slug), linked to `task_id` (on an assigned task, the current task). The teammate starts right away. At most 3 per run; chains are at most 3 tasks deep |
| `follow_up` | — | Only on a task this agent handed out. Adds the request to that task's thread, so the teammate continues |

Actions the agent isn't allowed to take, and malformed actions, are skipped with a warning. The rest are still applied. Tasks, notes and content created by an agent are marked with `source: agent:<slug>`.

## Assigned tasks

When a task is assigned to the agent (via `/ask`, chat, or the dashboard), its `prompt_template` is **not** used. Instead the agent receives the task, its thread so far, and its full context. It's asked to answer in this format:

```json
{
  "summary": "one line on what you did",
  "reply": "the actual deliverable, in markdown",
  "status": "done",
  "actions": []
}
```

- Use `"status": "needs_input"` when the agent has asked you a question. The task is then marked blocked until you reply.
- The `reply` is posted in the task thread and sent to Telegram. When the task was handed out by the coordinator, the reply goes to the coordinator instead, and it answers you.
- When a teammate handed the task over, the prompt says who, and what the task is part of.
- Agents meant mainly for delegation, like Navigator or Echo, should have a short scheduled prompt (or `manual`), a clear `description`, and the tools they need. The coordinator and the chat use the description to pick an agent.

## The coordinator

One agent can have `role: coordinator` (Ace, in `assistant.yaml`). Requests from the Telegram chat and `/do` go to it. On top of the usual rules it's told to do small things itself, split bigger requests into handoffs, reply with `"status": "waiting"` while teammates work, and combine their results into one answer. Its prompt lists the work it handed out and where each piece stands. It may hand out up to 6 pieces per round, for at most 5 rounds. See [architecture.md](architecture.md#handoffs-and-the-coordinator).

Give the coordinator `web_search` and Sonnet, and a `max_actions_per_run` of about 10 so a round of handoffs isn't cut short. Only one agent should have the role.

## Choosing a model

| Model | Good for |
|-------|----------|
| `claude-haiku-4-5` | Scanning, classifying, simple generation |
| `claude-sonnet-4-6` | Research, analysis, strategy, writing |

Start with Haiku and only switch to Sonnet if the output isn't good enough. `max_budget_usd` caps a single run, using the cost the SDK estimates for it. See [cost-and-requirements.md](cost-and-requirements.md).

## Testing an agent

1. Preview the rendered prompt without calling the model:
   ```bash
   curl -s localhost:8000/api/agents | python -m json.tool          # find the agent id
   curl -s -X POST "localhost:8000/api/agents/<id>/run?dry_run=true" | python -m json.tool
   ```
2. Run it once with `/run <agent>` on Telegram, or with the Run button on the dashboard Agents page.
3. Check the result on the Agents page, which shows the run's summary, how many actions it took, its cost and the full transcript.
4. Turn on its schedule once you're happy with it.

## Tips

1. **One agent, one job.**
2. **Grant the fewest tools and writes possible.** Use `requires_approval: true` for anything you want to check first.
3. **Spell out the JSON you expect** in the prompt, including the action fields.
4. **Use tags and memory** so the agent doesn't repeat work from earlier runs. Its memory and last 5 runs are always in its prompt; place `{{memory}}` / `{{past_runs}}` in the template only if you want them somewhere specific.
5. **Check `event_log` and the run transcript** when something looks wrong.
