# Telegram Bot Expansion

**Date:** 2026-03-20
**Status:** Approved

## Problem

The Telegram bot can capture tasks/ideas and trigger agents, but can't show marketing signals, agent status, or let the user act on notifications. The user must open the dashboard for visibility.

## Solution

Three new capabilities:

1. `/signals` — view recent marketing signals with status filter
2. `/agents` — view all agents with status and last run info
3. Inline reply to signal notifications → creates content draft

---

## 1. `/signals` Command

Query `MarketingSignal` ordered by `created_at desc`, limit 5. Optional arg filters by status.

**Usage:** `/signals` (default: new), `/signals reviewed`, `/signals all`

**Format:**
```
Recent Signals

1. r/SideProject — "Show HN-style launches" (92%)
   reddit · opportunity · 2h ago

2. r/Entrepreneur — "Solo founder SEO" (80%)
   reddit · opportunity · 3h ago
```

Implementation: `cmd_signals(args, source)` in `commands.py`.

---

## 2. `/agents` Command

Query all `AgentConfig` with most recent `AgentRun` per agent.

**Format:**
```
Agents

🟢 Pulse (Reddit Scout) — idle
   Last run: 2h ago · completed · $0.003

🔴 Scout (Opportunity Finder) — error
   Last run: 1h ago · failed

🟡 Echo (Content Drafter) — running
```

Status emoji: 🟢 idle, 🟡 running, 🔴 error, ⚪ disabled

Implementation: `cmd_agents(source)` in `commands.py` (no args needed).

---

## 3. Inline Reply → Create Draft

When the user replies to a bot message in Telegram, check if the replied-to message matches a recent signal notification (by matching the signal title in the message text). If matched, create a `MarketingContent` draft.

**Flow:**
1. User receives urgent signal notification: "*r/SideProject — Show HN launches (92%)*"
2. User replies to that message: "Hey, check out Glittr for this..."
3. Bot matches replied-to text against recent signals (last 24h) by title substring
4. Creates `MarketingContent(title="Re: {signal.title}", body=user_reply, channel=inferred_from_source_type, signal_id=signal.id, status=draft)`
5. Responds: "Draft created: Re: {signal.title}"
6. If no signal match, falls through to existing chat handler

**Channel inference:** reddit → `reddit_comment`, twitter → `twitter_tweet`, else `other`

**Implementation:** In `telegram.py`, modify the existing text message handler to check `update.message.reply_to_message` before falling through to chat.

---

## Files

| File | Changes |
|------|---------|
| `backend/app/integrations/commands.py` | Add `cmd_signals`, `cmd_agents` |
| `backend/app/integrations/telegram.py` | Register `/signals`, `/agents` commands; add reply-to-signal logic in message handler |

No schema changes, no migration, no dashboard changes.
