# Telegram Notifications + Brand Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable agents to notify the user via Telegram (urgent = immediate, routine = morning digest) and provide a personal brand profile that marketing agents reference when drafting content.

**Architecture:** Add a `BrandProfile` model + CRUD API. Extend the `Notification` model with priority and telegram_sent columns. A new dispatcher module uses httpx to send Telegram messages directly (decoupled from bot instance). The dispatcher runs as two async loops in the scheduler: urgent polling (30s) and daily digest (cron 8AM).

**Tech Stack:** Python, FastAPI, SQLAlchemy, httpx, Alembic

**Spec:** `docs/superpowers/specs/2026-03-20-telegram-notifications-brand-profile-design.md`

---

### Task 1: Add Config Settings

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: Add notification settings to Settings class**

In `backend/app/config.py`, add after the existing `telegram_bot_token` field (around line 46):

```python
    # Notification delivery
    telegram_notification_chat_id: str | None = None  # falls back to first telegram_allowed_users entry
    notification_timezone: str = "UTC"  # timezone for digest scheduling, e.g. "Asia/Kolkata"
```

- [ ] **Step 2: Add a property to resolve the chat ID**

Add after the existing properties (around line 154):

```python
    @property
    def telegram_target_chat_id(self) -> str | None:
        """Resolve the Telegram chat ID for sending notifications."""
        if self.telegram_notification_chat_id:
            return self.telegram_notification_chat_id
        allowed = (self.telegram_allowed_users or "").split(",")
        return allowed[0].strip() if allowed and allowed[0].strip() else None
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add telegram notification config settings"
```

---

### Task 2: Add BrandProfile Model + Notification Columns

**Files:**
- Modify: `backend/app/db/models.py`

- [ ] **Step 1: Add NotificationPriority enum**

Add after the existing enum definitions (around line 30, near other enums):

```python
class NotificationPriority(str, PyEnum):
    URGENT = "urgent"
    ROUTINE = "routine"
```

- [ ] **Step 2: Add columns to Notification model**

In the `Notification` class (around line 565), add after the `data` column and before `created_at`:

```python
    priority = Column(Enum(NotificationPriority), default=NotificationPriority.ROUTINE, nullable=False)
    telegram_sent = Column(Boolean, default=False)
```

- [ ] **Step 3: Add BrandProfile model**

Add before the `Notification` class (around line 563):

```python
class BrandProfile(Base):
    """Personal brand profile for agent content drafting."""
    __tablename__ = "brand_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, default="")
    bio = Column(Text, default="")
    tone = Column(String(255), default="")
    social_handles = Column(JSON, default=dict)
    topics = Column(JSON, default=list)  # JSON list for SQLite compat
    talking_points = Column(JSON, default=dict)
    avoid = Column(JSON, default=list)  # JSON list for SQLite compat
    example_posts = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Verify models import cleanly**

```bash
cd backend && source .venv/bin/activate && python -c "from app.db.models import BrandProfile, NotificationPriority, Notification; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models.py
git commit -m "feat: add BrandProfile model and notification priority columns"
```

---

### Task 3: Alembic Migration

**Files:**
- Create: `backend/app/db/migrations/versions/008_brand_and_notifications.py`

- [ ] **Step 1: Create migration file**

```python
"""Add brand_profile table and notification priority columns.

Revision ID: 008
Revises: 007
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = "008"
down_revision = "007"


def upgrade() -> None:
    # Brand profile table
    op.create_table(
        "brand_profile",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("bio", sa.Text, server_default=""),
        sa.Column("tone", sa.String(255), server_default=""),
        sa.Column("social_handles", JSON, server_default="{}"),
        sa.Column("topics", JSON, server_default="[]"),
        sa.Column("talking_points", JSON, server_default="{}"),
        sa.Column("avoid", JSON, server_default="[]"),
        sa.Column("example_posts", JSON, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Notification priority enum + columns
    op.execute("CREATE TYPE notificationpriority AS ENUM ('urgent', 'routine')")
    op.add_column("notifications", sa.Column(
        "priority",
        sa.Enum("urgent", "routine", name="notificationpriority", create_type=False),
        server_default="routine",
        nullable=False,
    ))
    op.add_column("notifications", sa.Column(
        "telegram_sent",
        sa.Boolean,
        server_default="false",
        nullable=False,
    ))
    op.create_index("idx_notifications_priority_sent", "notifications", ["priority", "telegram_sent"])


def downgrade() -> None:
    op.drop_index("idx_notifications_priority_sent", table_name="notifications")
    op.drop_column("notifications", "telegram_sent")
    op.drop_column("notifications", "priority")
    op.execute("DROP TYPE notificationpriority")
    op.drop_table("brand_profile")
```

- [ ] **Step 2: Run migration**

```bash
cd backend && source .venv/bin/activate && python -m alembic upgrade head
```

- [ ] **Step 3: Verify tables exist**

```bash
cd backend && source .venv/bin/activate && python -c "
from sqlalchemy import inspect, create_engine
engine = create_engine('postgresql://mc:mc@localhost:5434/mission_control')
insp = inspect(engine)
print('brand_profile' in insp.get_table_names())
cols = [c['name'] for c in insp.get_columns('notifications')]
print('priority' in cols, 'telegram_sent' in cols)
"
```

Expected: `True True True`

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/migrations/versions/008_brand_and_notifications.py
git commit -m "feat: migration 008 — brand_profile table + notification columns"
```

---

### Task 4: Brand Profile API

**Files:**
- Create: `backend/app/api/brand.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create brand profile router**

Create `backend/app/api/brand.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import BrandProfile

router = APIRouter()


class BrandProfileUpdate(BaseModel):
    name: str | None = None
    bio: str | None = None
    tone: str | None = None
    social_handles: dict | None = None
    topics: list[str] | None = None
    talking_points: dict | None = None
    avoid: list[str] | None = None
    example_posts: list[dict] | None = None


def _serialize(profile: BrandProfile) -> dict:
    return {
        "id": str(profile.id),
        "name": profile.name,
        "bio": profile.bio,
        "tone": profile.tone,
        "social_handles": profile.social_handles or {},
        "topics": profile.topics or [],
        "talking_points": profile.talking_points or {},
        "avoid": profile.avoid or [],
        "example_posts": profile.example_posts or [],
        "created_at": profile.created_at.isoformat(),
        "updated_at": profile.updated_at.isoformat(),
    }


EMPTY_PROFILE = {
    "id": None,
    "name": "",
    "bio": "",
    "tone": "",
    "social_handles": {},
    "topics": [],
    "talking_points": {},
    "avoid": [],
    "example_posts": [],
    "created_at": None,
    "updated_at": None,
}


@router.get("")
async def get_brand_profile(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BrandProfile).limit(1))
    profile = result.scalar_one_or_none()
    if not profile:
        return EMPTY_PROFILE
    return _serialize(profile)


@router.put("")
async def upsert_brand_profile(data: BrandProfileUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BrandProfile).limit(1))
    profile = result.scalar_one_or_none()

    fields = data.model_dump(exclude_unset=True)

    if profile:
        for key, val in fields.items():
            setattr(profile, key, val)
    else:
        profile = BrandProfile(**fields)
        db.add(profile)

    await db.flush()
    return _serialize(profile)
```

- [ ] **Step 2: Mount router in main.py**

In `backend/app/main.py`, add import and mount after the other router imports (around line 106):

```python
from app.api import brand
```

And in the router mounting section:

```python
app.include_router(brand.router, prefix="/api/brand-profile", tags=["brand"])
```

- [ ] **Step 3: Verify API starts**

```bash
cd backend && source .venv/bin/activate && python -c "from app.api.brand import router; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/brand.py backend/app/main.py
git commit -m "feat: add brand profile CRUD API at /api/brand-profile"
```

---

### Task 5: Update Notification Helper

**Files:**
- Modify: `backend/app/api/notifications.py`

- [ ] **Step 1: Add priority parameter to create_notification**

In `backend/app/api/notifications.py`, update the `create_notification` function (around line 70) to accept priority:

```python
async def create_notification(
    db: AsyncSession,
    title: str,
    body: str = "",
    category: str = "info",
    source: str = "system",
    action_url: str | None = None,
    data: dict | None = None,
    priority: str = "routine",
):
```

And update the Notification constructor inside it to include:

```python
    from app.db.models import NotificationPriority
    notif = Notification(
        title=title, body=body, category=category,
        source=source, action_url=action_url, data=data or {},
        priority=NotificationPriority(priority),
    )
```

- [ ] **Step 2: Update list endpoint serialization**

In the `list_notifications` endpoint (around line 19), add `priority` to the response dict:

```python
            "priority": n.priority.value if n.priority else "routine",
```

Add it after the `"action_url"` line.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/notifications.py
git commit -m "feat: add priority param to create_notification helper"
```

---

### Task 6: Notification Dispatcher

**Files:**
- Create: `backend/app/notifications/__init__.py`
- Create: `backend/app/notifications/dispatcher.py`

- [ ] **Step 1: Create package init**

Create empty `backend/app/notifications/__init__.py`.

- [ ] **Step 2: Create dispatcher module**

Create `backend/app/notifications/dispatcher.py`:

```python
"""Telegram notification dispatcher — sends urgent notifications immediately, routine ones as a morning digest."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy import select, update

from app.config import settings
from app.db.session import async_session
from app.db.models import Notification, NotificationPriority

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


async def _send_telegram(text: str) -> bool:
    """Send a message via Telegram Bot API using httpx. Returns True on success."""
    token = settings.telegram_bot_token
    chat_id = settings.telegram_target_chat_id
    if not token or not chat_id:
        logger.warning("Telegram not configured for notifications (missing token or chat_id)")
        return False

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
            })
            if resp.status_code != 200:
                logger.error(f"Telegram send failed ({resp.status_code}): {resp.text}")
                return False
            return True
    except Exception as e:
        logger.error(f"Telegram send error: {e}")
        return False


async def dispatch_urgent():
    """Send all unsent urgent notifications to Telegram."""
    async with async_session() as db:
        result = await db.execute(
            select(Notification).where(
                Notification.priority == NotificationPriority.URGENT,
                Notification.telegram_sent == False,
            ).order_by(Notification.created_at.asc())
        )
        notifications = result.scalars().all()

        for notif in notifications:
            text = f"*{notif.title}*\n{notif.body}" if notif.body else f"*{notif.title}*"
            if notif.action_url:
                text += f"\n{notif.action_url}"

            sent = await _send_telegram(text)
            if sent:
                notif.telegram_sent = True

        await db.commit()


async def dispatch_digest():
    """Send daily digest of unsent routine notifications."""
    async with async_session() as db:
        result = await db.execute(
            select(Notification).where(
                Notification.priority == NotificationPriority.ROUTINE,
                Notification.telegram_sent == False,
            ).order_by(Notification.created_at.asc())
        )
        notifications = result.scalars().all()

        if not notifications:
            return  # nothing to report

        # Group by category
        groups: dict[str, list[Notification]] = {}
        for n in notifications:
            groups.setdefault(n.category, []).append(n)

        # Build digest message
        lines = ["*Morning Briefing*", ""]

        agent_notifs = [n for n in notifications if n.source.startswith("agent:")]
        completed = sum(1 for n in agent_notifs if n.category == "success")
        failed = sum(1 for n in agent_notifs if n.category == "error")
        if agent_notifs:
            lines.append(f"Agents: {completed} completed, {failed} failed")

        signal_notifs = [n for n in notifications if "signal" in (n.category or "")]
        if signal_notifs:
            lines.append(f"Signals: {len(signal_notifs)} new")

        content_notifs = [n for n in notifications if "content" in (n.category or "")]
        if content_notifs:
            lines.append(f"Content: {len(content_notifs)} drafts ready")

        task_notifs = [n for n in notifications if "task" in (n.source or "")]
        if task_notifs:
            lines.append(f"Tasks: {len(task_notifs)} created by agents")

        # Find top signal by data
        top_signal = None
        for n in signal_notifs:
            score = (n.data or {}).get("relevance_score", 0)
            if top_signal is None or score > (top_signal.data or {}).get("relevance_score", 0):
                top_signal = n
        if top_signal:
            score_pct = int((top_signal.data or {}).get("relevance_score", 0) * 100)
            lines.append(f"\nTop signal: {top_signal.title} ({score_pct}%)")

        approval_count = sum(1 for n in notifications if n.category == "approval")
        if approval_count:
            lines.append(f"\n{approval_count} pending approvals — use /approve")

        text = "\n".join(lines)
        sent = await _send_telegram(text)

        if sent:
            for n in notifications:
                n.telegram_sent = True
            await db.commit()


async def urgent_dispatch_loop():
    """Polling loop for urgent notifications — runs every 30 seconds."""
    logger.info("Telegram urgent dispatcher started (30s interval)")
    while True:
        try:
            await dispatch_urgent()
        except Exception as e:
            logger.error(f"Urgent dispatch error: {e}")
        await asyncio.sleep(30)


async def digest_loop():
    """Daily digest loop — sends at 8:00 AM in configured timezone."""
    import zoneinfo
    logger.info(f"Telegram digest loop started (8:00 AM {settings.notification_timezone})")

    while True:
        try:
            tz = zoneinfo.ZoneInfo(settings.notification_timezone)
            now = datetime.now(tz)
            # Calculate next 8:00 AM
            target = now.replace(hour=8, minute=0, second=0, microsecond=0)
            if now >= target:
                target += timedelta(days=1)
            wait_seconds = (target - now).total_seconds()
            await asyncio.sleep(wait_seconds)

            await dispatch_digest()
        except Exception as e:
            logger.error(f"Digest loop error: {e}")
            await asyncio.sleep(3600)  # retry in 1 hour on error
```

- [ ] **Step 3: Verify module imports**

```bash
cd backend && source .venv/bin/activate && python -c "from app.notifications.dispatcher import urgent_dispatch_loop, digest_loop; print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/notifications/__init__.py backend/app/notifications/dispatcher.py
git commit -m "feat: telegram notification dispatcher with urgent polling + daily digest"
```

---

### Task 7: Register Dispatcher in Main Lifespan

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Import and start dispatcher loops in lifespan**

In `backend/app/main.py`, add import at the top:

```python
from app.notifications.dispatcher import urgent_dispatch_loop, digest_loop
```

In the `lifespan` function, after the email poller task (around line 75), add:

```python
    # Start notification dispatcher
    urgent_dispatch_task = asyncio.create_task(urgent_dispatch_loop())
    digest_dispatch_task = asyncio.create_task(digest_loop())
```

In the shutdown section (after `yield`), add:

```python
    urgent_dispatch_task.cancel()
    digest_dispatch_task.cancel()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: register notification dispatcher loops in app lifespan"
```

---

### Task 8: Agent Runner — Create Notifications + Inject Brand Profile

**Files:**
- Modify: `backend/app/orchestrator/runner.py`

- [ ] **Step 1: Update existing notification calls with priority parameter**

The runner already creates notifications for success (around line 689-701) and failure (around line 733-742) via `create_notification`. **Do not add new calls** — instead, modify the existing ones to include the `priority` parameter:

For the existing success notification call, add `priority="routine"`:
```python
await create_notification(
    db,
    title=f"{agent.name} completed",
    body=summary[:200],
    category=category,
    source=f"agent:{agent.slug}",
    priority="routine",
)
```

For the existing failure notification call, add `priority="urgent"`:
```python
await create_notification(
    db,
    title=f"{agent.name} failed",
    body=str(error)[:200],
    category="error",
    source=f"agent:{agent.slug}",
    priority="urgent",
)
```

- [ ] **Step 2: Add signal-specific urgent notifications in _process_actions**

In the `create_signal` action handler inside `_process_actions`, after the signal is created, add:

```python
relevance = action.get("relevance_score", 0.5)
if relevance > 0.8:
    await create_notification(
        db,
        title=signal.title,
        body=f"Source: {signal.source_type} | Score: {int(relevance * 100)}%",
        category="signal",
        source=f"agent:{agent.slug}",
        data={"relevance_score": relevance, "signal_id": str(signal.id)},
        priority="urgent",
    )
else:
    await create_notification(
        db,
        title=signal.title,
        category="signal",
        source=f"agent:{agent.slug}",
        data={"relevance_score": relevance, "signal_id": str(signal.id)},
        priority="routine",
    )
```

- [ ] **Step 3: Add content draft notification in _process_actions**

In the `create_content` action handler, after content is created:

```python
await create_notification(
    db,
    title=f"Draft: {content_obj.title}",
    category="content",
    source=f"agent:{agent.slug}",
    priority="routine",
)
```

- [ ] **Step 4: Inject brand profile into build_context**

In the `build_context` method, add at the end (before `return context`):

```python
        # Brand profile for marketing agents
        if any(r in (agent.data_reads or []) for r in ("marketing_signals", "marketing_content")):
            from app.db.models import BrandProfile
            bp_result = await db.execute(select(BrandProfile).limit(1))
            bp = bp_result.scalar_one_or_none()
            if bp:
                context["brand"] = {
                    "name": bp.name,
                    "tone": bp.tone,
                    "topics": bp.topics or [],
                    "talking_points": bp.talking_points or {},
                    "avoid": bp.avoid or [],
                    "example_posts": bp.example_posts or [],
                }
```

- [ ] **Step 5: Verify runner still imports cleanly**

```bash
cd backend && source .venv/bin/activate && python -c "from app.orchestrator.runner import AgentRunner; print('OK')"
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/orchestrator/runner.py
git commit -m "feat: agent runner creates notifications + injects brand profile context"
```

---

### Task 9: Telegram /brand Command

**Files:**
- Modify: `backend/app/integrations/commands.py`
- Modify: `backend/app/integrations/telegram.py`

- [ ] **Step 1: Add cmd_brand to commands.py**

In `backend/app/integrations/commands.py`, add import for BrandProfile and add the command function:

```python
from app.db.models import BrandProfile

async def cmd_brand(source: str) -> CommandResult:
    """Show current brand profile."""
    async with async_session() as db:
        result = await db.execute(select(BrandProfile).limit(1))
        profile = result.scalar_one_or_none()

    if not profile or not profile.name:
        return CommandResult("No brand profile configured yet.\nSet it up via the API: PUT /api/brand-profile")

    lines = [
        f"*{profile.name}*",
        "",
    ]
    if profile.bio:
        lines.append(profile.bio)
        lines.append("")
    if profile.tone:
        lines.append(f"Tone: {profile.tone}")
    if profile.topics:
        lines.append(f"Topics: {', '.join(profile.topics)}")
    if profile.talking_points:
        for product, points in profile.talking_points.items():
            lines.append(f"{product}: {', '.join(points)}")
    if profile.avoid:
        lines.append(f"Avoid: {', '.join(profile.avoid)}")

    return CommandResult("\n".join(lines))
```

- [ ] **Step 2: Register /brand in telegram.py**

In `backend/app/integrations/telegram.py`, add import:

```python
from app.integrations.commands import cmd_brand
```

And in `start_telegram_bot()`, add the handler alongside the other command registrations:

```python
    app.add_handler(CommandHandler("brand", _make_handler(cmd_brand, needs_args=False)))
```

- [ ] **Step 3: Add /brand to the help text**

In `commands.py`, find the `cmd_help` function and add `/brand` to the help text list:

```
/brand — View your brand profile
```

- [ ] **Step 4: Add /brand to BotCommand menu**

In `telegram.py`, find the `set_my_commands` list (around line 178-191) and add:

```python
BotCommand("brand", "View brand profile"),
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/integrations/commands.py backend/app/integrations/telegram.py
git commit -m "feat: add /brand telegram command"
```

---

### Task 10: End-to-End Verification

- [ ] **Step 1: Start the backend**

```bash
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
```

- [ ] **Step 2: Test brand profile API**

```bash
# Create profile
curl -s -X PUT http://localhost:8000/api/brand-profile \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Arnav Puri",
    "bio": "Indie maker building AI-powered SaaS products",
    "tone": "casual, direct, helpful, founder-voice",
    "topics": ["AI tools", "indie hacking", "SaaS growth"],
    "talking_points": {
      "glittr": ["AI design for non-designers", "Stop designing, start publishing"],
      "rankpilot": ["SEO + GEO", "Auto-publish to any CMS"]
    },
    "avoid": ["dont trash competitors", "no hype language", "no buzzwords"],
    "social_handles": {"twitter": "@arnavpuri", "reddit": "u/arnavpuri"}
  }' | python -m json.tool

# Read it back
curl -s http://localhost:8000/api/brand-profile | python -m json.tool
```

- [ ] **Step 3: Test notification priority via Python**

```bash
cd backend && source .venv/bin/activate && python -c "
import asyncio
from app.db.session import async_session
from app.api.notifications import create_notification

async def test():
    async with async_session() as db:
        n = await create_notification(db, title='Test urgent', category='info', priority='urgent')
        print(f'Created: {n.title}, priority={n.priority.value}')
        await db.commit()

asyncio.run(test())
"
```

- [ ] **Step 4: Verify Telegram dispatch logs**

Check backend logs for: `Telegram urgent dispatcher started (30s interval)` and `Telegram digest loop started`.

- [ ] **Step 5: Test /brand in Telegram**

Send `/brand` in the Telegram bot chat. Verify it shows the profile you created.

- [ ] **Step 6: Push all commits**

```bash
git push origin main
```
