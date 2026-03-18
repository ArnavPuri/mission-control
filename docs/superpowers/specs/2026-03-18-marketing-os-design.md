# Marketing OS — Design Spec

## Problem

Marketing agents (reddit-scout, feedback-collector, idea-validator) currently write output to generic `tasks` and `ideas` tables. Marketing insights get mixed with operational work. There is no dedicated place to see market signals, manage content drafts, or coordinate marketing efforts across products.

## Goal

Add a Marketing Operating System to Mission Control — a dedicated tab with its own data model, agent integrations, and dashboard page. The system serves indie makers marketing SaaS/app products through organic channels (Reddit, HN, Twitter/X, communities).

## Design Principles

- **Agents write to marketing-specific tables** — no tag-based filtering on shared tables.
- **Copy-paste workflow for now** — agents draft, user manually posts. Data model supports future API-based auto-posting.
- **Product-agnostic** — works across any number of products via `project_id` foreign key.
- **Signal → Content pipeline** — intelligence feeds into content creation with explicit linking.

---

## Data Model

### MarketingSignal

Market intelligence discovered by agents or added manually.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| title | String(500) | Short summary of the signal |
| body | Text | Full description / context |
| source | String(50) | Provenance: `manual`, `telegram`, `agent:<slug>` |
| source_type | String(50) | `reddit`, `hackernews`, `twitter`, `producthunt`, `other` |
| source_url | String(2048) | Link to the original thread/post |
| relevance_score | Float | Agent-assigned 0.0–1.0 relevance score |
| signal_type | String(50) | `opportunity`, `competitor`, `feedback`, `trend` |
| status | Enum | `new` → `reviewed` → `acted_on` → `dismissed` |
| channel_metadata | JSON | Source-specific data (subreddit, author, upvotes, etc.) |
| project_id | UUID FK | Linked project (nullable) |
| agent_id | UUID FK | Agent that created this signal (nullable) |
| tags | ARRAY(String) | Flexible tagging |
| created_at | DateTime | |
| updated_at | DateTime | |

**Indexes:** `status`, `source_type`, `signal_type`, `project_id`, `created_at`.

**Enum — SignalStatus:** `new`, `reviewed`, `acted_on`, `dismissed`

### MarketingContent

Content drafts for marketing channels.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| title | String(500) | Internal title for the content piece |
| body | Text | The actual content (tweet, Reddit comment, post body) |
| channel | String(50) | `reddit_comment`, `reddit_post`, `twitter_tweet`, `twitter_thread`, `hn_comment`, `other` |
| status | Enum | `draft` → `approved` → `posted` → `archived` |
| source | String(50) | Provenance: `manual`, `telegram`, `agent:<slug>` |
| signal_id | UUID FK | Signal that inspired this content (nullable) |
| project_id | UUID FK | Linked project (nullable) |
| agent_id | UUID FK | Agent that drafted this (nullable) |
| posted_url | String(2048) | URL where it was actually posted (filled after posting) |
| posted_at | DateTime | When it was posted (nullable) |
| notes | Text | User notes / edits rationale |
| tags | ARRAY(String) | |
| created_at | DateTime | |
| updated_at | DateTime | |

**Indexes:** `status`, `channel`, `project_id`, `signal_id`, `created_at`.

**Enum — ContentStatus:** `draft`, `approved`, `posted`, `archived`

### MarketingCampaign (v1.1 — deferred)

Campaigns are deferred to a follow-up iteration. The `tags` field on signals and content provides lightweight grouping for v1. The campaign model is documented here for future reference but will not be implemented in this phase.

<details>
<summary>Campaign model (future)</summary>

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | String(500) | Campaign name |
| description | Text | What this campaign is about |
| status | Enum | `planning` → `active` → `completed` → `paused` |
| start_date | DateTime | Planned start (nullable) |
| end_date | DateTime | Planned end (nullable) |
| goals | JSON | Freeform goals list |
| project_id | UUID FK | Linked project (nullable) |
| tags | ARRAY(String) | |
| created_at | DateTime | |
| updated_at | DateTime | |

Plus a `MarketingCampaignItem` join table linking campaigns to signals and content.
</details>

---

## API Endpoints

Mounted as separate routers following the existing flat convention:
- `/api/mkt-signals` — signals router
- `/api/mkt-content` — content router
- `/api/mkt-stats` — stats endpoint

### Signals

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/mkt-signals` | List signals. Filters: `status`, `source_type`, `signal_type`, `project_id`. Params: `limit` (default 50), `offset` (default 0) |
| GET | `/api/mkt-signals/{id}` | Get signal detail |
| POST | `/api/mkt-signals` | Create signal (manual or agent) |
| PATCH | `/api/mkt-signals/{id}` | Update signal (status, tags, etc.) |
| DELETE | `/api/mkt-signals/{id}` | Delete signal |

### Content

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/mkt-content` | List content. Filters: `status`, `channel`, `project_id`. Params: `limit` (default 50), `offset` (default 0) |
| GET | `/api/mkt-content/{id}` | Get content detail |
| POST | `/api/mkt-content` | Create content draft (accepts optional `signal_id` to link) |
| PATCH | `/api/mkt-content/{id}` | Update content (edit body, change status, set `posted_url`/`posted_at`) |
| DELETE | `/api/mkt-content/{id}` | Delete content |

Status transitions (draft → approved → posted) are handled via PATCH with `{"status": "approved"}` or `{"status": "posted", "posted_url": "..."}`, following the existing CRUD-only API pattern.

### Stats

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/mkt-stats` | Aggregate stats: signal count by status/type, content count by status/channel |

---

## Agent Integration

### New data_reads and data_writes targets

Agents can declare these in their YAML skill files:

- `marketing_signals` — read/write MarketingSignal records
- `marketing_content` — read/write MarketingContent records

### New build_context readers in AgentRunner

Add readers following the existing pattern in `runner.py`:

```python
if "marketing_signals" in (agent.data_reads or []):
    result = await db.execute(
        select(MarketingSignal)
        .where(MarketingSignal.status == SignalStatus.NEW)
        .order_by(MarketingSignal.created_at.desc())
        .limit(50)
    )
    context["marketing_signals"] = [
        {"id": str(s.id), "title": s.title, "body": s.body[:200],
         "source_type": s.source_type, "source_url": s.source_url,
         "relevance_score": s.relevance_score, "signal_type": s.signal_type}
        for s in result.scalars().all()
    ]

if "marketing_content" in (agent.data_reads or []):
    result = await db.execute(
        select(MarketingContent)
        .where(MarketingContent.status == ContentStatus.DRAFT)
        .order_by(MarketingContent.created_at.desc())
        .limit(20)
    )
    context["marketing_content"] = [
        {"id": str(c.id), "title": c.title, "body": c.body[:500],
         "channel": c.channel, "status": c.status.value}
        for c in result.scalars().all()
    ]
```

### New action types in AgentRunner._process_actions()

```json
{
  "type": "create_signal",
  "title": "Reddit thread asking about SEO tools",
  "body": "User in r/SaaS asking for affordable SEO tool recommendations...",
  "source_type": "reddit",
  "source_url": "https://reddit.com/r/SaaS/...",
  "relevance_score": 0.85,
  "signal_type": "opportunity",
  "channel_metadata": {"subreddit": "SaaS", "upvotes": 23, "comment_count": 12}
}
```

```json
{
  "type": "create_content",
  "title": "Reply to r/SaaS SEO tools thread",
  "body": "Hey! I built RankPilot Studio exactly for this...",
  "channel": "reddit_comment",
  "signal_id": "<uuid of the signal>"
}
```

Both action handlers must emit events to `event_log` with `entity_type: signal` / `entity_type: content` and broadcast via WebSocket for real-time dashboard updates.

### Updated agents

**reddit-scout.yaml** — Change `data_writes` from `tasks` to `marketing_signals, marketing_content`. Update prompt to output `create_signal` actions instead of `create_task`. Optionally also generate draft reply content.

**feedback-collector.yaml** — Change `data_writes` from `tasks, ideas` to `marketing_signals`. Feedback becomes signals with `signal_type: feedback`.

**New agent: content-drafter** — Takes new signals and generates content drafts. Reads `marketing_signals`, writes `marketing_content`. Schedule: manual trigger. Can be connected to signal creation via `AgentTrigger` (entity_type: `signal`, event: `created`) for automatic drafting.

### Search integration

Update `backend/app/api/search.py` to include `marketing_signals` (search title + body) and `marketing_content` (search title + body) in search results. Results should appear in the command palette with appropriate type icons.

---

## Dashboard Page

New nav item: **Marketing** (between Projects and Agents), keyboard shortcut `g m`.

**Note:** The mobile nav in `nav.tsx` currently shows the first 4 items. With Marketing added (6 total), update the mobile nav to show all items via horizontal scroll or a "more" menu instead of slicing to 4.

### Layout: 2-panel page with tabs

**Top bar:** Stats row showing:
- New signals (count with badge)
- Drafts ready for review (count)
- Posted this week (count)

**Left panel — Signals (50% width)**
- Filterable by: status, source type, signal type, project
- Each signal card shows: title, source icon + type badge, relevance score bar, time ago
- Status actions: review → act/dismiss
- "Create Draft" button on each signal to generate linked content
- Color-coded relevance: green (>0.7), amber (0.4-0.7), gray (<0.4)

**Right panel — Content (50% width)**
- Tab switcher: Drafts | Approved | Posted
- Each content card shows: title, channel icon, body preview, linked signal (if any)
- Inline edit for body text
- Approve button (PATCH status to approved)
- "Mark Posted" — input for posted URL, sets status to posted
- Copy-to-clipboard button for the body text

### Mobile layout
- Single column, tab switcher: Signals | Content

---

## Migration

Generate via `alembic revision --autogenerate -m "add marketing os"`. The revision ID will be auto-generated. Creates:
- `marketing_signals` table with all columns and indexes
- `marketing_content` table with all columns and indexes
- Enums: `signalstatus`, `contentstatus`

---

## Out of Scope (Future)

- Auto-posting via Reddit/Twitter APIs (design supports it via `posted_url` + `posted_at`)
- Content scheduling (post at specific time)
- Analytics/metrics tracking (impressions, clicks, conversions)
- A/B testing of content variants
- Email/newsletter channel
- Paid ads management
- Campaigns (v1.1 — model documented above)

---

## Files to Create/Modify

### New files
- `backend/app/db/migrations/versions/<auto>_add_marketing_os.py` — Migration (autogenerated)
- `backend/app/api/marketing_signals.py` — Signals API routes
- `backend/app/api/marketing_content.py` — Content API routes
- `backend/skills/content-drafter.yaml` — New agent
- `dashboard/app/marketing/page.tsx` — Marketing dashboard page

### Modified files
- `backend/app/db/models.py` — Add 2 new models (MarketingSignal, MarketingContent) + 2 enums (SignalStatus, ContentStatus)
- `backend/app/main.py` — Mount marketing_signals and marketing_content routers
- `backend/app/orchestrator/runner.py` — Add `create_signal` and `create_content` action handlers + `build_context` readers
- `backend/app/api/search.py` — Add marketing_signals and marketing_content to search
- `backend/skills/reddit-scout.yaml` — Update data_writes and prompt
- `backend/skills/feedback-collector.yaml` — Update data_writes and prompt
- `dashboard/app/components/nav.tsx` — Add Marketing nav item, fix mobile nav
- `dashboard/app/lib/api.ts` — Add marketing API client functions
