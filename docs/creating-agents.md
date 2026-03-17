# Creating Agents

## Quick Start

```bash
cp backend/skills/_template.yaml backend/skills/my-agent.yaml
# Edit the file, then restart the backend or call the sync API
```

## Anatomy of a Skill File

```yaml
name: my-agent              # Human-readable name
description: What it does   # One-liner shown in dashboard
version: "1.0"
type: marketing             # marketing | research | content | ops | general

model: claude-haiku-4-5     # Which LLM to use
max_budget_usd: 0.10        # Cost cap per run

tools:                       # What the agent can do beyond thinking
  - web_search              # Search the web
  - bash                    # Run shell commands (careful!)
  - write                   # Write files to workdir

data:
  reads: [projects, tasks]  # DB tables it gets as context
  writes: [tasks, ideas]    # DB tables it can write to

schedule:
  type: interval            # interval | cron | manual
  every: 4h                 # For interval type

prompt_template: |
  Your prompt here with {{variables}} for injected data.

requires_approval: false    # Queue actions for manual review
max_actions_per_run: 10     # Safety limit
```

## Available Context Variables

Based on what's in `data.reads`, these variables are available in your prompt template:

| Variable | Source | Contents |
|----------|--------|----------|
| `{{projects}}` | `reads: [projects]` | JSON array of all projects |
| `{{tasks}}` | `reads: [tasks]` | JSON array of open tasks |
| `{{ideas}}` | `reads: [ideas]` | JSON array of recent ideas |
| `{{reading}}` | `reads: [reading]` | JSON array of unread items |
| `{{project}}` | Auto (if `project_id` set) | JSON object of the bound project |

## Output Actions

Agents respond with structured JSON. The runner processes the `actions` array:

```json
{
  "summary": "What the agent accomplished",
  "actions": [
    {"type": "create_task", "text": "...", "priority": "high", "tags": ["tag"]},
    {"type": "create_idea", "text": "...", "tags": ["tag"]},
    {"type": "add_reading", "title": "...", "url": "https://..."},
    {"type": "update_task", "task_id": "uuid", "status": "done", "priority": "low"}
  ]
}
```

## Model Selection Guide

| Model | Cost | Best For |
|-------|------|----------|
| `claude-haiku-4-5` | ~$0.01-0.03/run | Scanning, classifying, simple generation |
| `claude-sonnet-4-6` | ~$0.05-0.20/run | Analysis, strategy, complex writing |

Rule of thumb: Start with Haiku. Only upgrade to Sonnet if the output quality isn't sufficient.

## Tips

1. **Keep prompts focused.** One agent, one job. Don't make a "do everything" agent.
2. **Use tags.** They help filter in the dashboard and prevent duplicate work.
3. **Set budget caps.** Always set `max_budget_usd` to avoid surprises.
4. **Test manually first.** Use `/run agent-name` via Telegram or the API before enabling schedules.
5. **Check the event log.** Every action is logged. Use it to debug agent behavior.
