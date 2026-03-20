# Telegram Notifications + Personal Brand Profile

**Date:** 2026-03-20
**Status:** Approved

## Problem

Agents run autonomously but complete silently. The user must manually check the dashboard to see results. Additionally, marketing agents draft content without knowing the user's personal brand, voice, or talking points — producing generic output.

## Solution

Two features:

1. **Notification dispatcher** — routes agent-generated notifications to Telegram with priority-based delivery (urgent = immediate, routine = morning digest).
2. **Personal brand profile** — a structured identity record agents reference when drafting content.

---

## 1. Personal Brand Profile

### Schema: `brand_profile` table (single row)

| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| name | String(255) | Display name, e.g. "Arnav Puri" |
| bio | Text | Short bio for agent context |
| tone | String(255) | Voice descriptor, e.g. "casual, direct, helpful, founder-voice" |
| social_handles | JSON | `{"twitter": "@x", "reddit": "u/x", "linkedin": "..."}` |
| topics | JSON | Topics to be known for, e.g. `["AI tools", "indie hacking"]` |
| talking_points | JSON | Per-product key messages, e.g. `{"glittr": ["AI design for non-designers"], "rankpilot": ["SEO + GEO"]}` |
| avoid | JSON | Things to never say, e.g. `["don't trash competitors", "no hype language"]` |
| example_posts | JSON | 3-5 example posts for voice matching, `[{"platform": "reddit", "text": "..."}]` |
| created_at | DateTime | |
| updated_at | DateTime | |

All list fields use JSON (not ARRAY) for SQLite compatibility.

### API: `/api/brand-profile`

- `GET /api/brand-profile` — returns the profile (or empty defaults if none exists)
- `PUT /api/brand-profile` — upsert (query first row; insert if missing, update if exists)

No list endpoint — single row design. No DB constraint enforcing single-row; the API handles it via upsert logic.

### Agent Integration

The runner's `build_context` injects the brand profile into agent context for agents whose `data_reads` includes `marketing_signals` or `marketing_content`. If no brand profile exists, this section is omitted (agents work without it). The context section looks like:

```
## Your Brand Voice
Name: Arnav Puri
Tone: casual, direct, helpful, founder-voice
Topics: AI tools, indie hacking, SaaS growth
Talking Points (Glittr): AI design for non-designers, stop designing start publishing
Talking Points (RankPilot): SEO + GEO, auto-publish to any CMS
Avoid: don't trash competitors, no hype language
Example posts: [...]
```

Non-marketing agents do not receive brand context.

### Telegram

`/brand` command — displays current brand profile summary (read-only). Editing via dashboard or API. Implemented as `cmd_brand` in `commands.py` following the established command pattern.

---

## 2. Notification System

### Notification Table Changes

Add two columns to the existing `notifications` table:

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| priority | Enum(urgent, routine) | routine | Delivery urgency |
| telegram_sent | Boolean | false | Prevents re-sending |

### Config Changes

Add to `config.py`:
- `TELEGRAM_NOTIFICATION_CHAT_ID` — the chat ID to send notifications to (defaults to first entry in `telegram_allowed_users` if not set)
- `NOTIFICATION_TIMEZONE` — timezone for digest scheduling, e.g. `"Asia/Kolkata"` (defaults to UTC)

### Priority Rules (hardcoded in runner)

**Urgent** (sent to Telegram within seconds):
- Marketing signal with `relevance_score > 0.8`
- Agent run failure/error
- Approval request pending

**Routine** (batched into morning digest):
- Agent run completed successfully
- Content draft created
- Signal with `relevance_score <= 0.8`

### Notification Creation

The agent runner creates notifications after processing actions. Decision logic lives in the runner — no new agent action type needed. The runner evaluates what happened during the run (created signals? failed? needs approval?) and creates appropriate notification rows.

The existing `create_notification` helper in `notifications.py` is updated to accept an optional `priority` parameter. Response serialization updated to include `priority`.

### Telegram Dispatcher

The dispatcher uses direct `httpx` calls to the Telegram Bot API (`POST /bot<token>/sendMessage`) rather than depending on the `python-telegram-bot` Application instance. This keeps it decoupled from the bot's command handler lifecycle.

**Urgent dispatch** — a polling loop registered in the scheduler, runs every 30 seconds:

1. Query `notifications` where `priority = 'urgent'` AND `telegram_sent = false`
2. Send each via Telegram Bot API to `TELEGRAM_NOTIFICATION_CHAT_ID`
3. Set `telegram_sent = true`
4. If Telegram token is not configured, log a warning and skip (no crash)

Lives in `backend/app/notifications/dispatcher.py`.

### Daily Digest

A cron job at 8:00 AM in configured timezone (runs from the same dispatcher module):

1. Query `notifications` where `priority = 'routine'` AND `telegram_sent = false` (no time window — catches any unsent routine notifications)
2. Group by category (agent runs, signals, content, tasks)
3. Format as single Telegram message
4. Set `telegram_sent = true` on all included notifications
5. If nothing to report, skip (no empty digest)

**Digest format:**
```
Morning Briefing

Agents: 4 completed, 0 failed
Signals: 6 new (2 high relevance)
Content: 2 drafts ready for review
Tasks: 3 created by agents

Top signal: r/SideProject — "AI tools for designers" (92%)

Use /approve to review pending actions.
```

---

## 3. New Files

| File | Purpose |
|------|---------|
| `backend/app/notifications/__init__.py` | Package init |
| `backend/app/notifications/dispatcher.py` | Telegram dispatch loop (urgent polling + daily digest) |
| `backend/app/api/brand.py` | Brand profile CRUD router |
| `backend/app/db/migrations/versions/008_brand_and_notifications.py` | brand_profile table + notification columns |

## 4. Modified Files

| File | Changes |
|------|---------|
| `backend/app/db/models.py` | Add `BrandProfile` model, `NotificationPriority` enum, new columns on `Notification` |
| `backend/app/config.py` | Add `TELEGRAM_NOTIFICATION_CHAT_ID` and `NOTIFICATION_TIMEZONE` settings |
| `backend/app/orchestrator/runner.py` | Create notifications after action processing; inject brand profile into marketing agent context |
| `backend/app/orchestrator/scheduler.py` | Register dispatcher loop (30s) and digest loop (cron 8:00 AM) |
| `backend/app/integrations/telegram.py` | Register `/brand` command handler |
| `backend/app/integrations/commands.py` | Add `cmd_brand` function |
| `backend/app/api/notifications.py` | Add `priority` param to `create_notification` helper; update response serialization |
| `backend/app/main.py` | Mount `/api/brand-profile` router; start dispatcher in lifespan |

## 5. No Dashboard Changes

Brand profile management via API and Telegram for now. Dashboard UI deferred.

## 6. Migration: `008_brand_and_notifications`

- Create `brand_profile` table (all list fields as JSON for SQLite compatibility)
- Add `priority` enum column to `notifications` (default: `'routine'`)
- Add `telegram_sent` boolean column to `notifications` (default: `false`)
