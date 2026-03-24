# Architecture

## Core Principle: Database as Source of Truth

Everything in Mission Control revolves around a single PostgreSQL database.
The dashboard reads from it. Agents read from and write to it. The Telegram
bot writes to it. The MCP server proxies to the API which reads/writes to it.

No component holds state independently. If you lose the dashboard, the data
is still there. If an agent crashes, the scheduler picks up where it left off.

## Data Flow

```
Input Sources                  Central DB                    Output
─────────────                  ──────────                    ──────
Telegram Bot    ──write──▶  ┌─────────────┐
Manual (Dashboard) ─write─▶ │  PostgreSQL  │ ──read──▶  Dashboard (Next.js)
MCP (Claude Code)  ─write─▶ │             │ ──read──▶  WebSocket clients
Agent outputs    ──write──▶  │  + pgvector  │ ──read──▶  Agent inputs
Scheduler       ──read───▶  └─────────────┘
                                   │
                              Event Log
                            (audit trail)
```

## Agent Execution Model

1. **Scheduler** checks `agent_configs` table every 60 seconds
2. For agents with `schedule_type = "interval"`, compares `last_run_at` + interval to now
3. If due, calls **AgentRunner.start_run()**
4. Runner:
   a. Creates an `agent_runs` record (status: running)
   b. Updates `agent_configs.status` to running
   c. Builds context by querying DB tables listed in `data_reads`
   d. Renders the prompt template with context data
   e. Calls Claude Agent SDK (or falls back to raw API)
   f. Parses structured JSON output
   g. Processes actions (create tasks, ideas, etc.)
   h. Updates run record with results
   i. Broadcasts events via WebSocket

## Authentication Architecture

Uses Claude Code subscription (OAuth) exclusively:

```
CLAUDE_CODE_OAUTH_TOKEN    → Claude Pro/Max subscription via Agent SDK
```

All LLM calls go through the Claude Agent SDK. No API key needed.

## Database Schema

### Core Tables
- **projects** — Your products/ventures
- **tasks** — Todo items, linked to projects
- **ideas** — Raw ideas with tags and optional validation scores
- **reading_list** — Articles and resources to read

### Agent Tables
- **agent_configs** — Agent definitions (synced from YAML skill files)
- **agent_runs** — Execution log for every agent run

### System Tables
- **event_log** — Central audit trail for all changes (who did what, when)

## Skill File System

Agent behavior is defined in YAML files, not code. This means:
- Non-developers can create agents by copying a template
- Agents are version-controllable (git diff your agent changes)
- The skill loader syncs YAML → DB on startup
- Hot-reload is possible via API endpoint

A skill file defines: identity, model, tools, data access, schedule, and prompt template.
The runner handles all the execution plumbing.
