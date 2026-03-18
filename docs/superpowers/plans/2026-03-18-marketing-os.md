# Marketing OS Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Marketing OS to Mission Control with dedicated data models, API endpoints, agent integration, and a dashboard page for managing marketing signals and content drafts.

**Architecture:** Two new DB models (MarketingSignal, MarketingContent) with dedicated API routers, two new action types in the agent runner, updated marketing agents, and a new Marketing dashboard page with 2-panel layout.

**Tech Stack:** Python/FastAPI, SQLAlchemy, Alembic, Next.js/React, Tailwind CSS, Radix UI, Lucide icons

**Spec:** `docs/superpowers/specs/2026-03-18-marketing-os-design.md`

---

## File Structure

### New files
| File | Responsibility |
|------|---------------|
| `backend/app/api/marketing_signals.py` | CRUD API for marketing signals |
| `backend/app/api/marketing_content.py` | CRUD API for marketing content |
| `backend/skills/content-drafter.yaml` | Content drafting agent skill |
| `dashboard/app/marketing/page.tsx` | Marketing dashboard page |

### Modified files
| File | Changes |
|------|---------|
| `backend/app/db/models.py` | Add MarketingSignal, MarketingContent models + SignalStatus, ContentStatus enums |
| `backend/app/main.py` | Mount 2 new routers |
| `backend/app/orchestrator/runner.py` | Add `create_signal`/`create_content` actions + `build_context` readers |
| `backend/app/api/search.py` | Add signals and content to search |
| `backend/skills/reddit-scout.yaml` | Update data_writes and prompt for signals |
| `backend/skills/feedback-collector.yaml` | Update data_writes and prompt for signals |
| `dashboard/app/components/nav.tsx` | Add Marketing nav item |
| `dashboard/app/lib/api.ts` | Add marketing API client functions |
| `backend/tests/test_api.py` | Add marketing API tests |

---

### Task 1: Add Models and Enums

**Files:**
- Modify: `backend/app/db/models.py:494` (before pgvector block)

- [ ] **Step 1: Add SignalStatus and ContentStatus enums**

Add after `MoodLevel` enum (line 94):

```python
class SignalStatus(str, PyEnum):
    NEW = "new"
    REVIEWED = "reviewed"
    ACTED_ON = "acted_on"
    DISMISSED = "dismissed"


class ContentStatus(str, PyEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    POSTED = "posted"
    ARCHIVED = "archived"
```

- [ ] **Step 2: Add MarketingSignal model**

Add before the pgvector block (before `# Optional: Embedding column`):

```python
# ---------- Marketing ----------

class MarketingSignal(Base):
    """Market intelligence discovered by agents or added manually."""
    __tablename__ = "marketing_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    body = Column(Text, default="")
    source = Column(String(50), default="manual")
    source_type = Column(String(50), nullable=False)  # reddit, hackernews, twitter, producthunt, other
    source_url = Column(String(2048), nullable=True)
    relevance_score = Column(Float, default=0.5)
    signal_type = Column(String(50), nullable=False)  # opportunity, competitor, feedback, trend
    status = Column(Enum(SignalStatus), default=SignalStatus.NEW, nullable=False)
    channel_metadata = Column(JSON, default=dict)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id"), nullable=True)
    tags = Column(ARRAY(String), default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", foreign_keys=[project_id])
    agent = relationship("AgentConfig", foreign_keys=[agent_id])

    __table_args__ = (
        Index("idx_mkt_signals_status", "status"),
        Index("idx_mkt_signals_source_type", "source_type"),
        Index("idx_mkt_signals_signal_type", "signal_type"),
        Index("idx_mkt_signals_project", "project_id"),
        Index("idx_mkt_signals_created", "created_at"),
    )


class MarketingContent(Base):
    """Content drafts for marketing channels."""
    __tablename__ = "marketing_content"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    channel = Column(String(50), nullable=False)  # reddit_comment, reddit_post, twitter_tweet, twitter_thread, hn_comment, other
    status = Column(Enum(ContentStatus), default=ContentStatus.DRAFT, nullable=False)
    source = Column(String(50), default="manual")
    signal_id = Column(UUID(as_uuid=True), ForeignKey("marketing_signals.id"), nullable=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id"), nullable=True)
    posted_url = Column(String(2048), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    tags = Column(ARRAY(String), default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    signal = relationship("MarketingSignal", foreign_keys=[signal_id])
    project = relationship("Project", foreign_keys=[project_id])
    agent = relationship("AgentConfig", foreign_keys=[agent_id])

    __table_args__ = (
        Index("idx_mkt_content_status", "status"),
        Index("idx_mkt_content_channel", "channel"),
        Index("idx_mkt_content_project", "project_id"),
        Index("idx_mkt_content_signal", "signal_id"),
        Index("idx_mkt_content_created", "created_at"),
    )
```

- [ ] **Step 3: Verify models parse**

Run: `cd backend && python3 -c "from app.db.models import MarketingSignal, MarketingContent, SignalStatus, ContentStatus; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/models.py
git commit -m "feat(marketing): add MarketingSignal and MarketingContent models"
```

---

### Task 2: Create Alembic Migration

**Files:**
- Create: `backend/app/db/migrations/versions/<auto>_add_marketing_os.py`

- [ ] **Step 1: Generate migration**

Run: `cd backend && source .venv/bin/activate && alembic revision --autogenerate -m "add marketing os"`

If autogenerate fails (common with SQLite test setup), create the migration manually following the pattern in `001_initial_schema.py`. The migration must create `marketing_signals` and `marketing_content` tables with all columns and indexes from Task 1.

- [ ] **Step 2: Review generated migration**

Read the generated file. Verify it creates both tables with correct columns, enums (`signalstatus`, `contentstatus`), foreign keys, and indexes.

- [ ] **Step 3: Run migration (if real database is available)**

Run: `cd backend && source .venv/bin/activate && alembic upgrade head`
(Skip if no database running — test suite uses `Base.metadata.create_all`)

- [ ] **Step 4: Commit**

```bash
git add backend/app/db/migrations/versions/
git commit -m "feat(marketing): add migration for marketing tables"
```

---

### Task 3: Signals API

**Files:**
- Create: `backend/app/api/marketing_signals.py`
- Modify: `backend/app/main.py:16` (add import) and line 92 (mount router)
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Write tests for signals CRUD**

Add to `backend/tests/test_api.py`:

```python
# --- Marketing Signals ---

@pytest.mark.asyncio
async def test_create_signal(client):
    resp = await client.post("/api/mkt-signals", json={
        "title": "Reddit opportunity in r/SaaS",
        "body": "User asking about SEO tools",
        "source_type": "reddit",
        "signal_type": "opportunity",
        "source_url": "https://reddit.com/r/SaaS/123",
        "relevance_score": 0.85,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Reddit opportunity in r/SaaS"
    assert data["status"] == "new"
    assert "id" in data


@pytest.mark.asyncio
async def test_list_signals(client):
    await client.post("/api/mkt-signals", json={
        "title": "Signal 1", "source_type": "reddit", "signal_type": "opportunity",
    })
    await client.post("/api/mkt-signals", json={
        "title": "Signal 2", "source_type": "twitter", "signal_type": "trend",
    })
    resp = await client.get("/api/mkt-signals")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_list_signals_filter_status(client):
    await client.post("/api/mkt-signals", json={
        "title": "New signal", "source_type": "reddit", "signal_type": "opportunity",
    })
    resp = await client.get("/api/mkt-signals?status=reviewed")
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_update_signal_status(client):
    create = await client.post("/api/mkt-signals", json={
        "title": "To review", "source_type": "reddit", "signal_type": "opportunity",
    })
    signal_id = create.json()["id"]
    resp = await client.patch(f"/api/mkt-signals/{signal_id}", json={"status": "reviewed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "reviewed"


@pytest.mark.asyncio
async def test_delete_signal(client):
    create = await client.post("/api/mkt-signals", json={
        "title": "Delete me", "source_type": "reddit", "signal_type": "feedback",
    })
    signal_id = create.json()["id"]
    resp = await client.delete(f"/api/mkt-signals/{signal_id}")
    assert resp.status_code == 200
    listing = await client.get("/api/mkt-signals")
    assert len(listing.json()) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_api.py -k "signal" -v`
Expected: FAIL (routes don't exist yet)

- [ ] **Step 3: Create marketing_signals.py**

Create `backend/app/api/marketing_signals.py`:

```python
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.db.models import MarketingSignal, SignalStatus, EventLog
from app.api.ws import broadcast

router = APIRouter()


class SignalCreate(BaseModel):
    title: str
    body: str = ""
    source_type: str
    signal_type: str
    source_url: str | None = None
    relevance_score: float = Field(default=0.5, ge=0.0, le=1.0)
    channel_metadata: dict = {}
    project_id: str | None = None
    tags: list[str] = []


class SignalUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    status: str | None = None
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)
    tags: list[str] | None = None
    project_id: str | None = None


def _serialize(s: MarketingSignal) -> dict:
    return {
        "id": str(s.id),
        "title": s.title,
        "body": s.body,
        "source": s.source,
        "source_type": s.source_type,
        "source_url": s.source_url,
        "relevance_score": s.relevance_score,
        "signal_type": s.signal_type,
        "status": s.status.value,
        "channel_metadata": s.channel_metadata or {},
        "project_id": str(s.project_id) if s.project_id else None,
        "agent_id": str(s.agent_id) if s.agent_id else None,
        "tags": s.tags or [],
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }


@router.get("")
async def list_signals(
    status: str | None = None,
    source_type: str | None = None,
    signal_type: str | None = None,
    project_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(MarketingSignal).order_by(MarketingSignal.created_at.desc())
    if status:
        query = query.where(MarketingSignal.status == SignalStatus(status))
    if source_type:
        query = query.where(MarketingSignal.source_type == source_type)
    if signal_type:
        query = query.where(MarketingSignal.signal_type == signal_type)
    if project_id:
        query = query.where(MarketingSignal.project_id == UUID(project_id))
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return [_serialize(s) for s in result.scalars().all()]


@router.get("/{signal_id}")
async def get_signal(signal_id: UUID, db: AsyncSession = Depends(get_db)):
    signal = await db.get(MarketingSignal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return _serialize(signal)


@router.post("")
async def create_signal(data: SignalCreate, db: AsyncSession = Depends(get_db)):
    signal = MarketingSignal(
        title=data.title,
        body=data.body,
        source_type=data.source_type,
        signal_type=data.signal_type,
        source_url=data.source_url,
        relevance_score=data.relevance_score,
        channel_metadata=data.channel_metadata,
        project_id=UUID(data.project_id) if data.project_id else None,
        tags=data.tags,
    )
    db.add(signal)
    await db.flush()
    event = EventLog(
        event_type="signal.created", entity_type="signal",
        entity_id=signal.id, source=signal.source,
        data={"title": signal.title, "signal_type": signal.signal_type},
    )
    db.add(event)
    await broadcast("signal.created", {"id": str(signal.id), "title": signal.title})
    return _serialize(signal)


@router.patch("/{signal_id}")
async def update_signal(signal_id: UUID, data: SignalUpdate, db: AsyncSession = Depends(get_db)):
    signal = await db.get(MarketingSignal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    updates = data.model_dump(exclude_unset=True)
    if "status" in updates:
        updates["status"] = SignalStatus(updates["status"])
    if "project_id" in updates:
        updates["project_id"] = UUID(updates["project_id"]) if updates["project_id"] else None
    for key, val in updates.items():
        setattr(signal, key, val)
    await db.flush()
    return _serialize(signal)


@router.delete("/{signal_id}")
async def delete_signal(signal_id: UUID, db: AsyncSession = Depends(get_db)):
    signal = await db.get(MarketingSignal, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    await db.delete(signal)
    return {"deleted": True}
```

- [ ] **Step 4: Mount router in main.py**

In `backend/app/main.py`:
- Add `marketing_signals` to the import on line 16
- Add `app.include_router(marketing_signals.router, prefix="/api/mkt-signals", tags=["marketing"])` after line 92

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_api.py -k "signal" -v`
Expected: All 5 signal tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/marketing_signals.py backend/app/main.py backend/tests/test_api.py
git commit -m "feat(marketing): add signals API with CRUD endpoints"
```

---

### Task 4: Content API

**Files:**
- Create: `backend/app/api/marketing_content.py`
- Modify: `backend/app/main.py` (add import + mount)
- Test: `backend/tests/test_api.py`

- [ ] **Step 1: Write tests for content CRUD**

Add to `backend/tests/test_api.py`:

```python
# --- Marketing Content ---

@pytest.mark.asyncio
async def test_create_content(client):
    resp = await client.post("/api/mkt-content", json={
        "title": "Reply to SEO thread",
        "body": "Hey, I built a tool for exactly this...",
        "channel": "reddit_comment",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Reply to SEO thread"
    assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_create_content_linked_to_signal(client):
    signal = await client.post("/api/mkt-signals", json={
        "title": "Opportunity", "source_type": "reddit", "signal_type": "opportunity",
    })
    signal_id = signal.json()["id"]
    resp = await client.post("/api/mkt-content", json={
        "title": "Reply draft",
        "body": "Content body",
        "channel": "reddit_comment",
        "signal_id": signal_id,
    })
    assert resp.status_code == 200
    assert resp.json()["signal_id"] == signal_id


@pytest.mark.asyncio
async def test_approve_content(client):
    create = await client.post("/api/mkt-content", json={
        "title": "Draft tweet", "body": "Check out our tool", "channel": "twitter_tweet",
    })
    content_id = create.json()["id"]
    resp = await client.patch(f"/api/mkt-content/{content_id}", json={"status": "approved"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_mark_content_posted(client):
    create = await client.post("/api/mkt-content", json={
        "title": "Tweet", "body": "Content", "channel": "twitter_tweet",
    })
    content_id = create.json()["id"]
    await client.patch(f"/api/mkt-content/{content_id}", json={"status": "approved"})
    resp = await client.patch(f"/api/mkt-content/{content_id}", json={
        "status": "posted",
        "posted_url": "https://twitter.com/user/status/123",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "posted"
    assert resp.json()["posted_url"] == "https://twitter.com/user/status/123"


@pytest.mark.asyncio
async def test_list_content_filter_channel(client):
    await client.post("/api/mkt-content", json={
        "title": "Tweet", "body": "...", "channel": "twitter_tweet",
    })
    await client.post("/api/mkt-content", json={
        "title": "Reddit", "body": "...", "channel": "reddit_comment",
    })
    resp = await client.get("/api/mkt-content?channel=twitter_tweet")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["channel"] == "twitter_tweet"


@pytest.mark.asyncio
async def test_delete_content(client):
    create = await client.post("/api/mkt-content", json={
        "title": "Delete me", "body": "...", "channel": "twitter_tweet",
    })
    content_id = create.json()["id"]
    resp = await client.delete(f"/api/mkt-content/{content_id}")
    assert resp.status_code == 200
    listing = await client.get("/api/mkt-content")
    assert len(listing.json()) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_api.py -k "content" -v`
Expected: FAIL

- [ ] **Step 3: Create marketing_content.py**

Create `backend/app/api/marketing_content.py`:

```python
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db
from app.db.models import MarketingContent, ContentStatus, EventLog
from app.api.ws import broadcast

router = APIRouter()


class ContentCreate(BaseModel):
    title: str
    body: str
    channel: str
    signal_id: str | None = None
    project_id: str | None = None
    tags: list[str] = []
    notes: str | None = None


class ContentUpdate(BaseModel):
    title: str | None = None
    body: str | None = None
    status: str | None = None
    posted_url: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    project_id: str | None = None


def _serialize(c: MarketingContent) -> dict:
    return {
        "id": str(c.id),
        "title": c.title,
        "body": c.body,
        "channel": c.channel,
        "status": c.status.value,
        "source": c.source,
        "signal_id": str(c.signal_id) if c.signal_id else None,
        "project_id": str(c.project_id) if c.project_id else None,
        "agent_id": str(c.agent_id) if c.agent_id else None,
        "posted_url": c.posted_url,
        "posted_at": c.posted_at.isoformat() if c.posted_at else None,
        "notes": c.notes,
        "tags": c.tags or [],
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


@router.get("")
async def list_content(
    status: str | None = None,
    channel: str | None = None,
    project_id: str | None = None,
    signal_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(MarketingContent).order_by(MarketingContent.created_at.desc())
    if status:
        query = query.where(MarketingContent.status == ContentStatus(status))
    if channel:
        query = query.where(MarketingContent.channel == channel)
    if project_id:
        query = query.where(MarketingContent.project_id == UUID(project_id))
    if signal_id:
        query = query.where(MarketingContent.signal_id == UUID(signal_id))
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return [_serialize(c) for c in result.scalars().all()]


@router.get("/{content_id}")
async def get_content(content_id: UUID, db: AsyncSession = Depends(get_db)):
    content = await db.get(MarketingContent, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    return _serialize(content)


@router.post("")
async def create_content(data: ContentCreate, db: AsyncSession = Depends(get_db)):
    content = MarketingContent(
        title=data.title,
        body=data.body,
        channel=data.channel,
        signal_id=UUID(data.signal_id) if data.signal_id else None,
        project_id=UUID(data.project_id) if data.project_id else None,
        tags=data.tags,
        notes=data.notes,
    )
    db.add(content)
    await db.flush()
    event = EventLog(
        event_type="content.created", entity_type="content",
        entity_id=content.id, source=content.source,
        data={"title": content.title, "channel": content.channel},
    )
    db.add(event)
    await broadcast("content.created", {"id": str(content.id), "title": content.title})
    return _serialize(content)


@router.patch("/{content_id}")
async def update_content(content_id: UUID, data: ContentUpdate, db: AsyncSession = Depends(get_db)):
    content = await db.get(MarketingContent, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    updates = data.model_dump(exclude_unset=True)
    if "status" in updates:
        new_status = ContentStatus(updates["status"])
        updates["status"] = new_status
        if new_status == ContentStatus.POSTED and not content.posted_at:
            updates["posted_at"] = datetime.now(timezone.utc)
    if "project_id" in updates:
        updates["project_id"] = UUID(updates["project_id"]) if updates["project_id"] else None
    for key, val in updates.items():
        setattr(content, key, val)
    await db.flush()
    return _serialize(content)


@router.delete("/{content_id}")
async def delete_content(content_id: UUID, db: AsyncSession = Depends(get_db)):
    content = await db.get(MarketingContent, content_id)
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    await db.delete(content)
    return {"deleted": True}
```

- [ ] **Step 4: Mount router in main.py**

Add `marketing_content` to the import line and add:
`app.include_router(marketing_content.router, prefix="/api/mkt-content", tags=["marketing"])`

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_api.py -k "content" -v`
Expected: All 5 content tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/marketing_content.py backend/app/main.py backend/tests/test_api.py
git commit -m "feat(marketing): add content API with CRUD endpoints"
```

---

### Task 5: Marketing Stats Endpoint

**Files:**
- Create: `backend/app/api/marketing_stats.py`
- Modify: `backend/app/main.py` (add import + mount)

- [ ] **Step 1: Create marketing_stats.py**

Create `backend/app/api/marketing_stats.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import MarketingSignal, MarketingContent, SignalStatus, ContentStatus

router = APIRouter()


@router.get("")
async def marketing_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate stats for the marketing dashboard."""
    # Signal counts by status
    signal_status_counts = {}
    for status in SignalStatus:
        count = await db.scalar(
            select(func.count(MarketingSignal.id)).where(MarketingSignal.status == status)
        )
        signal_status_counts[status.value] = count or 0

    # Signal counts by type
    signal_type_counts = {}
    for signal_type in ["opportunity", "competitor", "feedback", "trend"]:
        count = await db.scalar(
            select(func.count(MarketingSignal.id)).where(MarketingSignal.signal_type == signal_type)
        )
        signal_type_counts[signal_type] = count or 0

    # Content counts by status
    content_status_counts = {}
    for status in ContentStatus:
        count = await db.scalar(
            select(func.count(MarketingContent.id)).where(MarketingContent.status == status)
        )
        content_status_counts[status.value] = count or 0

    # Content counts by channel
    content_channel_result = await db.execute(
        select(MarketingContent.channel, func.count(MarketingContent.id))
        .group_by(MarketingContent.channel)
    )
    content_channel_counts = {row[0]: row[1] for row in content_channel_result.all()}

    return {
        "signals": {
            "by_status": signal_status_counts,
            "by_type": signal_type_counts,
            "total": sum(signal_status_counts.values()),
        },
        "content": {
            "by_status": content_status_counts,
            "by_channel": content_channel_counts,
            "total": sum(content_status_counts.values()),
        },
    }
```

- [ ] **Step 2: Mount router in main.py**

Add `marketing_stats` to import and add:
`app.include_router(marketing_stats.router, prefix="/api/mkt-stats", tags=["marketing"])`

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/marketing_stats.py backend/app/main.py
git commit -m "feat(marketing): add stats endpoint"
```

---

### Task 6: Agent Runner Integration

**Files:**
- Modify: `backend/app/orchestrator/runner.py`

- [ ] **Step 1: Add build_context readers**

Add after the `journal` reader block (around line 102) in `build_context()`:

```python
if "marketing_signals" in (agent.data_reads or []):
    from app.db.models import MarketingSignal, SignalStatus
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
    from app.db.models import MarketingContent, ContentStatus
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

- [ ] **Step 2: Add action handlers in _process_actions()**

Add after the `create_goal` handler block (end of the method):

```python
elif action_type == "create_signal" and "marketing_signals" in (agent.data_writes or []):
    from app.db.models import MarketingSignal
    signal = MarketingSignal(
        title=action.get("title", "Untitled signal"),
        body=action.get("body", ""),
        source=f"agent:{agent.slug}",
        source_type=action.get("source_type", "other"),
        source_url=action.get("source_url"),
        relevance_score=min(max(action.get("relevance_score", 0.5), 0.0), 1.0),
        signal_type=action.get("signal_type", "opportunity"),
        channel_metadata=action.get("channel_metadata", {}),
        project_id=agent.project_id,
        agent_id=agent.id,
        tags=action.get("tags", []),
    )
    db.add(signal)
    await db.flush()
    db.add(EventLog(
        event_type="signal.created", entity_type="signal",
        entity_id=signal.id, source=f"agent:{agent.slug}",
        data={"title": signal.title, "signal_type": signal.signal_type},
    ))
    await broadcast("signal.created", {"id": str(signal.id), "title": signal.title, "source": signal.source})

elif action_type == "create_content" and "marketing_content" in (agent.data_writes or []):
    from app.db.models import MarketingContent
    content = MarketingContent(
        title=action.get("title", "Untitled content"),
        body=action.get("body", ""),
        channel=action.get("channel", "other"),
        source=f"agent:{agent.slug}",
        signal_id=UUID(action["signal_id"]) if action.get("signal_id") else None,
        project_id=agent.project_id,
        agent_id=agent.id,
        tags=action.get("tags", []),
    )
    db.add(content)
    await db.flush()
    db.add(EventLog(
        event_type="content.created", entity_type="content",
        entity_id=content.id, source=f"agent:{agent.slug}",
        data={"title": content.title, "channel": content.channel},
    ))
    await broadcast("content.created", {"id": str(content.id), "title": content.title, "source": content.source})
```

- [ ] **Step 3: Verify runner parses**

Run: `cd backend && python3 -c "from app.orchestrator.runner import AgentRunner; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/app/orchestrator/runner.py
git commit -m "feat(marketing): add signal/content actions and context readers to agent runner"
```

---

### Task 7: Update Agent Skill Files

**Files:**
- Modify: `backend/skills/reddit-scout.yaml`
- Modify: `backend/skills/feedback-collector.yaml`
- Create: `backend/skills/content-drafter.yaml`

- [ ] **Step 1: Update reddit-scout.yaml**

Replace the full file:

```yaml
name: reddit-scout
description: Finds promotional opportunities on Reddit for your products
version: "2.0"
type: marketing

model: claude-sonnet-4-6
max_budget_usd: 0.25

tools:
  - web_search

data:
  reads: [projects, tasks]
  writes: [marketing_signals, marketing_content]

schedule:
  type: interval
  every: 6h

prompt_template: |
  You are a Reddit marketing scout. Your job is to find Reddit threads
  where the following products could be naturally and helpfully mentioned.

  PROJECTS:
  {{projects}}

  EXISTING TASKS (avoid duplicates):
  {{tasks}}

  Instructions:
  1. For each active project, think about what subreddits and types of
     threads would be relevant (people asking for recommendations,
     complaining about competitors, discussing the problem space).
  2. Search for recent threads that match.
  3. For each opportunity found, create a signal AND optionally a draft reply.

  Respond with JSON:
  {
    "summary": "Found N opportunities across M subreddits",
    "actions": [
      {
        "type": "create_signal",
        "title": "r/SaaS - Looking for SEO tool alternatives",
        "body": "User asking for affordable SEO tool recommendations. Thread has 23 upvotes and 12 comments. Good engagement opportunity.",
        "source_type": "reddit",
        "source_url": "https://reddit.com/r/SaaS/...",
        "relevance_score": 0.85,
        "signal_type": "opportunity",
        "channel_metadata": {"subreddit": "SaaS", "upvotes": 23, "comment_count": 12},
        "tags": ["reddit", "seo"]
      },
      {
        "type": "create_content",
        "title": "Reply to r/SaaS SEO tools thread",
        "body": "Hey! I actually built something for exactly this use case...",
        "channel": "reddit_comment",
        "tags": ["reddit", "seo"]
      }
    ]
  }

requires_approval: false
max_actions_per_run: 10
```

- [ ] **Step 2: Update feedback-collector.yaml**

Replace the full file:

```yaml
name: feedback-collector
description: Scrapes and analyzes user feedback from public sources for your products
version: "2.0"
type: marketing

model: claude-haiku-4-5
max_budget_usd: 0.10

tools:
  - web_search

data:
  reads: [projects]
  writes: [marketing_signals]

schedule:
  type: interval
  every: 1d

prompt_template: |
  You are a feedback collection agent. Search public sources for mentions
  of and feedback about these products:

  PROJECTS:
  {{projects}}

  Search for:
  1. Reddit mentions and discussions
  2. Twitter/X mentions
  3. Hacker News discussions
  4. GitHub issues (if applicable)
  5. Product Hunt comments (if applicable)

  For each piece of feedback found, create a signal categorized by type.

  Respond with JSON:
  {
    "summary": "Found N mentions. Key themes: ...",
    "actions": [
      {
        "type": "create_signal",
        "title": "User feedback: [source] - [short summary]",
        "body": "Full context of the feedback...",
        "source_type": "reddit",
        "source_url": "https://...",
        "relevance_score": 0.7,
        "signal_type": "feedback",
        "channel_metadata": {"subreddit": "startups"},
        "tags": ["feedback", "feature-request"]
      }
    ]
  }

requires_approval: false
max_actions_per_run: 8
```

- [ ] **Step 3: Create content-drafter.yaml**

```yaml
name: content-drafter
description: Generates marketing content drafts from signals
version: "1.0"
type: marketing

model: claude-sonnet-4-6
max_budget_usd: 0.20

tools: []

data:
  reads: [projects, marketing_signals]
  writes: [marketing_content]

schedule:
  type: manual

prompt_template: |
  You are a marketing content writer for indie SaaS products.
  Your job is to turn marketing signals into draft content for
  Reddit comments, tweets, and community posts.

  PROJECTS:
  {{projects}}

  NEW SIGNALS TO ACT ON:
  {{marketing_signals}}

  Instructions:
  1. Review each signal and decide if it warrants a content draft.
  2. For each signal worth acting on, generate a draft that is:
     - Authentic and helpful (NOT spammy or salesy)
     - Tailored to the platform (casual for Reddit, concise for Twitter)
     - Genuinely useful to the reader while naturally mentioning the product
  3. Match the channel to the signal source (reddit signal → reddit_comment, twitter signal → twitter_tweet)

  Respond with JSON:
  {
    "summary": "Created N drafts from M signals",
    "actions": [
      {
        "type": "create_content",
        "title": "Reply to [thread topic]",
        "body": "The actual draft content...",
        "channel": "reddit_comment",
        "signal_id": "<uuid of the source signal>",
        "tags": ["reddit"]
      }
    ]
  }

requires_approval: false
max_actions_per_run: 5
```

- [ ] **Step 4: Commit**

```bash
git add backend/skills/reddit-scout.yaml backend/skills/feedback-collector.yaml backend/skills/content-drafter.yaml
git commit -m "feat(marketing): update agents to use signals/content, add content-drafter"
```

---

### Task 8: Search Integration

**Files:**
- Modify: `backend/app/api/search.py`

- [ ] **Step 1: Add marketing signals and content to search**

In `backend/app/api/search.py`:

Add to imports (line 13):
```python
from app.db.models import Task, Idea, ReadingItem, Goal, JournalEntry, Habit, Project, MarketingSignal, MarketingContent
```

Update the `types` default set (line 30-32) to include `"signals"` and `"content"`.

Add before the `return` block (before line 112):

```python
if "signals" in types:
    stmt = select(MarketingSignal).where(
        or_(func.lower(MarketingSignal.title).like(query_lower),
            func.lower(MarketingSignal.body).like(query_lower))
    ).order_by(MarketingSignal.created_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    results.extend([
        {"type": "signal", "id": str(s.id), "title": s.title,
         "status": s.status.value, "source_type": s.source_type,
         "created_at": s.created_at.isoformat()}
        for s in rows
    ])

if "content" in types:
    stmt = select(MarketingContent).where(
        or_(func.lower(MarketingContent.title).like(query_lower),
            func.lower(MarketingContent.body).like(query_lower))
    ).order_by(MarketingContent.created_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    results.extend([
        {"type": "content", "id": str(c.id), "title": c.title,
         "status": c.status.value, "channel": c.channel,
         "created_at": c.created_at.isoformat()}
        for c in rows
    ])
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/api/search.py
git commit -m "feat(marketing): add signals and content to search"
```

---

### Task 9: Dashboard Nav Update

**Files:**
- Modify: `dashboard/app/components/nav.tsx`

- [ ] **Step 1: Add Marketing nav item**

In `dashboard/app/components/nav.tsx`:

Add `Megaphone` to the lucide-react import (line 7):
```typescript
import {
  LayoutDashboard, FolderOpen, Zap, PenLine, Settings, Keyboard,
  Sun, Moon, Megaphone,
} from 'lucide-react';
```

Add Marketing to `navItems` array after Projects (line 16):
```typescript
{ href: '/marketing', label: 'Marketing', icon: Megaphone, shortcut: 'g m' },
```

- [ ] **Step 2: Fix mobile nav to show all items**

Change `navItems.slice(0, 4)` on line 140 to `navItems` to show all nav items on mobile:
```typescript
{navItems.map((item) => {
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/components/nav.tsx
git commit -m "feat(marketing): add Marketing to dashboard nav"
```

---

### Task 10: API Client Functions

**Files:**
- Modify: `dashboard/app/lib/api.ts`

- [ ] **Step 1: Add marketing types and API functions**

Add to the end of `dashboard/app/lib/api.ts` (before the `connectWebSocket` function):

```typescript
// --- Marketing Signals ---

export interface MarketingSignal {
  id: string;
  title: string;
  body: string;
  source: string;
  source_type: string;
  source_url: string | null;
  relevance_score: number;
  signal_type: string;
  status: 'new' | 'reviewed' | 'acted_on' | 'dismissed';
  channel_metadata: Record<string, unknown>;
  project_id: string | null;
  agent_id: string | null;
  tags: string[];
  created_at: string;
  updated_at: string | null;
}

export function fetchSignals(params?: { status?: string; source_type?: string; signal_type?: string; project_id?: string }) {
  const qs = new URLSearchParams();
  if (params?.status) qs.set('status', params.status);
  if (params?.source_type) qs.set('source_type', params.source_type);
  if (params?.signal_type) qs.set('signal_type', params.signal_type);
  if (params?.project_id) qs.set('project_id', params.project_id);
  const query = qs.toString();
  return request<MarketingSignal[]>(`/api/mkt-signals${query ? `?${query}` : ''}`);
}

export function createSignal(data: Partial<MarketingSignal>) {
  return request<MarketingSignal>('/api/mkt-signals', { method: 'POST', body: JSON.stringify(data) });
}

export function updateSignal(id: string, data: Partial<MarketingSignal>) {
  return request<MarketingSignal>(`/api/mkt-signals/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export function deleteSignal(id: string) {
  return request<{ deleted: boolean }>(`/api/mkt-signals/${id}`, { method: 'DELETE' });
}

// --- Marketing Content ---

export interface MarketingContent {
  id: string;
  title: string;
  body: string;
  channel: string;
  status: 'draft' | 'approved' | 'posted' | 'archived';
  source: string;
  signal_id: string | null;
  project_id: string | null;
  agent_id: string | null;
  posted_url: string | null;
  posted_at: string | null;
  notes: string | null;
  tags: string[];
  created_at: string;
  updated_at: string | null;
}

export function fetchContent(params?: { status?: string; channel?: string; project_id?: string }) {
  const qs = new URLSearchParams();
  if (params?.status) qs.set('status', params.status);
  if (params?.channel) qs.set('channel', params.channel);
  if (params?.project_id) qs.set('project_id', params.project_id);
  const query = qs.toString();
  return request<MarketingContent[]>(`/api/mkt-content${query ? `?${query}` : ''}`);
}

export function createContent(data: Partial<MarketingContent>) {
  return request<MarketingContent>('/api/mkt-content', { method: 'POST', body: JSON.stringify(data) });
}

export function updateContent(id: string, data: Partial<MarketingContent>) {
  return request<MarketingContent>(`/api/mkt-content/${id}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export function deleteContent(id: string) {
  return request<{ deleted: boolean }>(`/api/mkt-content/${id}`, { method: 'DELETE' });
}
```

- [ ] **Step 2: Commit**

```bash
git add dashboard/app/lib/api.ts
git commit -m "feat(marketing): add marketing API client functions"
```

---

### Task 11: Marketing Dashboard Page

**Files:**
- Create: `dashboard/app/marketing/page.tsx`

- [ ] **Step 1: Create the Marketing page**

Create `dashboard/app/marketing/page.tsx` — a 2-panel page (signals left, content right) with:

**Stats bar:** New signals count, drafts count, posted this week count.

**Signals panel (left 50%):**
- List of signal cards with title, source_type badge, relevance score color bar, signal_type badge, time ago
- Filter dropdown for status (new/reviewed/acted_on/dismissed)
- Each card has status action buttons (mark reviewed, dismiss)
- "Create Draft" button that opens inline form to create linked content

**Content panel (right 50%):**
- Tab switcher: Drafts | Approved | Posted
- Content cards with title, channel badge, body preview (truncated), linked signal title
- Approve button on drafts
- "Mark Posted" button with URL input on approved items
- Copy-to-clipboard button for body text
- Inline body editing on drafts

Follow the existing page patterns from `dashboard/app/agents/page.tsx` for:
- Shared components (`Card`, `Badge`, `SectionHeader` from `./components/shared`)
- Data fetching pattern (useEffect + useState)
- Dark mode support (Tailwind `dark:` classes)
- Radix UI components (Tooltip, Tabs)
- Lucide icons
- Responsive layout (stack columns on mobile)

- [ ] **Step 2: Verify page loads**

Start the dashboard: `cd dashboard && npm run dev`
Navigate to `http://localhost:3000/marketing`
Expected: Page loads with empty state, no errors in console.

- [ ] **Step 3: Commit**

```bash
git add dashboard/app/marketing/page.tsx
git commit -m "feat(marketing): add Marketing dashboard page with signals and content panels"
```

---

### Task 12: Run Full Test Suite

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_api.py -v`
Expected: All tests pass (existing + 10 new marketing tests)

- [ ] **Step 2: Fix any failures**

If tests fail, fix them before proceeding.

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: resolve test failures from marketing OS integration"
```
