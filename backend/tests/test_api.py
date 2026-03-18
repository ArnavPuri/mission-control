"""
Backend test suite for Mission Control API.

Uses pytest-asyncio with an in-memory SQLite for isolation.
Tests cover core CRUD endpoints and business logic.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.main import app
from app.db.session import get_db


# Use SQLite for testing (avoids PostgreSQL dependency)
TEST_DATABASE_URL = "sqlite+aiosqlite:///file::memory:?cache=shared"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Create tables before each test, drop after."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    """Async HTTP client for testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─── Health ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


# ─── Projects ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_project_crud(client: AsyncClient):
    # Create
    r = await client.post("/api/projects", json={"name": "Test Project", "description": "A test"})
    assert r.status_code == 200
    project_id = r.json()["id"]

    # List
    r = await client.get("/api/projects")
    assert r.status_code == 200
    projects = r.json()
    assert len(projects) >= 1
    assert any(p["id"] == project_id for p in projects)

    # Update
    r = await client.patch(f"/api/projects/{project_id}", json={"description": "Updated"})
    assert r.status_code == 200

    # Delete
    r = await client.delete(f"/api/projects/{project_id}")
    assert r.status_code == 200


# ─── Tasks ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_task_crud(client: AsyncClient):
    # Create
    r = await client.post("/api/tasks", json={"text": "Buy groceries"})
    assert r.status_code == 200
    task_id = r.json()["id"]

    # List
    r = await client.get("/api/tasks")
    assert r.status_code == 200
    tasks = r.json()
    assert len(tasks) >= 1

    # Update status
    r = await client.patch(f"/api/tasks/{task_id}", json={"status": "done"})
    assert r.status_code == 200

    # Update priority
    r = await client.patch(f"/api/tasks/{task_id}", json={"priority": "high"})
    assert r.status_code == 200

    # Delete
    r = await client.delete(f"/api/tasks/{task_id}")
    assert r.status_code == 200


# ─── Ideas ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_idea_crud(client: AsyncClient):
    r = await client.post("/api/ideas", json={"text": "Build a rocket"})
    assert r.status_code == 200
    idea_id = r.json()["id"]

    r = await client.get("/api/ideas")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = await client.delete(f"/api/ideas/{idea_id}")
    assert r.status_code == 200


# ─── Reading ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reading_crud(client: AsyncClient):
    r = await client.post("/api/reading", json={"title": "How to test", "url": "https://example.com"})
    assert r.status_code == 200
    item_id = r.json()["id"]

    r = await client.get("/api/reading")
    assert r.status_code == 200

    r = await client.patch(f"/api/reading/{item_id}", json={"is_read": True})
    assert r.status_code == 200

    r = await client.delete(f"/api/reading/{item_id}")
    assert r.status_code == 200


# ─── Notes ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notes_crud(client: AsyncClient):
    r = await client.post("/api/notes", json={"title": "My Note", "content": "Some content"})
    assert r.status_code == 200
    note_id = r.json()["id"]

    r = await client.get("/api/notes")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = await client.get(f"/api/notes/{note_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "My Note"

    r = await client.patch(f"/api/notes/{note_id}", json={"is_pinned": True})
    assert r.status_code == 200

    r = await client.delete(f"/api/notes/{note_id}")
    assert r.status_code == 200


# ─── Habits ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_habit_crud(client: AsyncClient):
    r = await client.post("/api/habits", json={"name": "Exercise"})
    assert r.status_code == 200
    habit_id = r.json()["id"]

    r = await client.get("/api/habits")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    # Complete
    r = await client.post(f"/api/habits/{habit_id}/complete")
    assert r.status_code == 200

    # Uncomplete before delete to remove completions (SQLite FK cascade workaround)
    r = await client.post(f"/api/habits/{habit_id}/uncomplete")
    assert r.status_code == 200

    r = await client.delete(f"/api/habits/{habit_id}")
    assert r.status_code == 200


# ─── Goals ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_goal_crud(client: AsyncClient):
    r = await client.post("/api/goals", json={"title": "Ship product"})
    assert r.status_code == 200
    goal_id = r.json()["id"]

    r = await client.get("/api/goals")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = await client.delete(f"/api/goals/{goal_id}")
    assert r.status_code == 200


# ─── Journal ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_journal_crud(client: AsyncClient):
    r = await client.post("/api/journal", json={"content": "Today was great", "mood": "good"})
    assert r.status_code == 200
    entry_id = r.json()["id"]

    r = await client.get("/api/journal")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = await client.delete(f"/api/journal/{entry_id}")
    assert r.status_code == 200


# ─── API Keys ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_key_lifecycle(client: AsyncClient):
    # Create
    r = await client.post("/api/keys", json={"name": "Test Key", "scopes": ["read"]})
    assert r.status_code == 200
    data = r.json()
    assert "key" in data
    assert data["key"].startswith("mc_")
    key_id = data["id"]

    # List
    r = await client.get("/api/keys")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    # Revoke
    r = await client.delete(f"/api/keys/{key_id}")
    assert r.status_code == 200
    assert r.json()["revoked"] is True


# ─── RSS Feeds ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_feed_crud(client: AsyncClient):
    r = await client.post("/api/feeds", json={"title": "Test Feed", "url": "https://example.com/rss"})
    assert r.status_code == 200
    feed_id = r.json()["id"]

    r = await client.get("/api/feeds")
    assert r.status_code == 200

    r = await client.delete(f"/api/feeds/{feed_id}")
    assert r.status_code == 200


# ─── GitHub Repos ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_github_repo_crud(client: AsyncClient):
    r = await client.post("/api/github", json={"owner": "test", "repo": "project"})
    assert r.status_code == 200
    data = r.json()
    repo_id = data["id"]
    assert "webhook_secret" in data

    r = await client.get("/api/github")
    assert r.status_code == 200

    r = await client.delete(f"/api/github/{repo_id}")
    assert r.status_code == 200


# ─── Search ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search(client: AsyncClient):
    # Create some data to search
    await client.post("/api/tasks", json={"text": "Unique searchable task"})
    await client.post("/api/ideas", json={"text": "Unique searchable idea"})

    r = await client.get("/api/search?q=searchable")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1


# ─── Notifications ────────────────────────────────────────

@pytest.mark.asyncio
async def test_notifications(client: AsyncClient):
    r = await client.get("/api/notifications")
    assert r.status_code == 200

    r = await client.get("/api/notifications/count")
    assert r.status_code == 200
    assert "unread" in r.json()


# ─── Marketing Signals ───────────────────────────────────

@pytest.mark.asyncio
async def test_create_signal(client: AsyncClient):
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
async def test_list_signals(client: AsyncClient):
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
async def test_list_signals_filter_status(client: AsyncClient):
    await client.post("/api/mkt-signals", json={
        "title": "New signal", "source_type": "reddit", "signal_type": "opportunity",
    })
    resp = await client.get("/api/mkt-signals?status=reviewed")
    assert resp.status_code == 200
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_update_signal_status(client: AsyncClient):
    create = await client.post("/api/mkt-signals", json={
        "title": "To review", "source_type": "reddit", "signal_type": "opportunity",
    })
    signal_id = create.json()["id"]
    resp = await client.patch(f"/api/mkt-signals/{signal_id}", json={"status": "reviewed"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "reviewed"


@pytest.mark.asyncio
async def test_delete_signal(client: AsyncClient):
    create = await client.post("/api/mkt-signals", json={
        "title": "Delete me", "source_type": "reddit", "signal_type": "feedback",
    })
    signal_id = create.json()["id"]
    resp = await client.delete(f"/api/mkt-signals/{signal_id}")
    assert resp.status_code == 200
    listing = await client.get("/api/mkt-signals")
    assert len(listing.json()) == 0
