# Morning Sequence + Lessons System

**Date:** 2026-03-21
**Status:** Approved

## Problem

Agents run independently but there's no unified morning briefing. The user must check multiple places (dashboard, Telegram, signals page) to understand the state of things. Additionally, agent failures don't compound into learning — the same mistakes repeat.

## Solution

1. **Lessons System** — auto-capture agent failures and output issues to shared memory. All agents read past lessons as context to avoid repeating mistakes.
2. **Morning Sequence** — unified briefing sent to Telegram at 8 AM (scheduled) and on demand via `/morning`. Covers priorities, agents, signals, projects, and content pipeline.

---

## 1. Lessons System

### Storage

Use existing `AgentMemory` shared scratchpad (agent_id=NULL) with key `system:lessons`.

Value is a newline-separated list of lessons, capped at 20:
```
[2026-03-21] Pulse: Output was not valid JSON — returned markdown instead of structured response
[2026-03-21] Radar: LLM auth failed — OAuth token not passed to subprocess
```

### Writing Lessons

In `runner.py`, after a failed run or a run with `raw: True` output:

- Failed: `[{date}] {agent.name}: {error[:100]}`
- Raw output: `[{date}] {agent.name}: Output was not valid JSON`

Read existing lessons, append new one, trim to 20 most recent, write back.

### Reading Lessons

In `build_context`, read the `system:lessons` shared memory key and inject as:
```
## Past Lessons (avoid repeating these mistakes)
- Pulse: Output was not valid JSON — returned markdown instead
- Radar: LLM auth failed — OAuth token not passed to subprocess
```

### Changes

Only `backend/app/orchestrator/runner.py` — no migration, no new files.

---

## 2. Morning Sequence

### Briefing Generator

New module `backend/app/notifications/morning.py` with function `generate_morning_briefing()`:

1. Queries DB for:
   - Recent agent runs (last 12h)
   - New signals (last 24h), top 3 by relevance
   - High/critical open tasks + overdue tasks
   - Projects with open task and signal counts
   - Content drafts + recently posted
2. Formats a single Telegram message (~30 lines)
3. Returns the formatted text

### Message Format

```
Morning Briefing — Mar 21

Priorities
• 3 critical/high tasks open
• 1 overdue: "Submit ODSC talk proposal"

Agents (last 12h)
• 4 ran: 3 completed, 1 failed (Radar)

Signals (24h)
• 8 new leads, 3 high relevance
• Top: r/SideProject — "AI design tools" (92%)
• Top: r/Entrepreneur — "Solo founder SEO" (88%)
• Top: HN — "Show HN: AI content tools" (85%)

Products
• Glittr: 5 open tasks, 4 signals
• RankPilot: 3 open tasks, 2 signals

Content
• 2 drafts ready for review
• 1 posted this week

Use /signals, /tasks, or /approve for details.
```

### Triggers

1. **Scheduled:** `digest_loop` in `dispatcher.py` sends the morning briefing at 8 AM. The briefing replaces the routine digest (it's a superset).
2. **On demand:** `/morning` Telegram command calls the same generator.

### Files

| File | Changes |
|------|---------|
| `backend/app/notifications/morning.py` | New — briefing generator |
| `backend/app/notifications/dispatcher.py` | Modify `digest_loop` to use morning briefing |
| `backend/app/integrations/commands.py` | Add `cmd_morning` |
| `backend/app/integrations/telegram.py` | Register `/morning` command |
| `backend/app/orchestrator/runner.py` | Write lessons on failure/raw, inject in `build_context` |

No migration, no schema changes, no dashboard changes.
