"""
Backend test suite for Mission Control API.

Uses pytest-asyncio with an in-memory SQLite for isolation.
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.models import Base
from app.main import app
from app.db.session import get_db


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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─── Health ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ─── Projects ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_project_crud(client: AsyncClient):
    r = await client.post("/api/projects", json={"name": "Test Project", "description": "A test"})
    assert r.status_code == 200
    project_id = r.json()["id"]

    r = await client.get("/api/projects")
    assert r.status_code == 200
    assert any(p["id"] == project_id for p in r.json())

    r = await client.patch(f"/api/projects/{project_id}", json={"description": "Updated"})
    assert r.status_code == 200

    r = await client.delete(f"/api/projects/{project_id}")
    assert r.status_code == 200


# ─── Tasks ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_task_crud(client: AsyncClient):
    r = await client.post("/api/tasks", json={"text": "Buy groceries"})
    assert r.status_code == 200
    task_id = r.json()["id"]

    r = await client.get("/api/tasks")
    assert r.status_code == 200
    assert len(r.json()) >= 1

    r = await client.patch(f"/api/tasks/{task_id}", json={"status": "done"})
    assert r.status_code == 200

    r = await client.delete(f"/api/tasks/{task_id}")
    assert r.status_code == 200


# ─── Notes ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_notes_crud(client: AsyncClient):
    r = await client.post("/api/notes", json={"title": "My Note", "content": "Some content"})
    assert r.status_code == 200
    note_id = r.json()["id"]

    r = await client.get("/api/notes")
    assert r.status_code == 200

    r = await client.get(f"/api/notes/{note_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "My Note"

    r = await client.patch(f"/api/notes/{note_id}", json={"is_pinned": True})
    assert r.status_code == 200

    r = await client.delete(f"/api/notes/{note_id}")
    assert r.status_code == 200


# ─── Search ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search(client: AsyncClient):
    await client.post("/api/tasks", json={"text": "Unique searchable task"})

    r = await client.get("/api/search?q=searchable")
    assert r.status_code == 200
    assert r.json()["total"] >= 1


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
async def test_signal_crud(client: AsyncClient):
    r = await client.post("/api/mkt-signals", json={
        "title": "Reddit opportunity",
        "source_type": "reddit",
        "signal_type": "opportunity",
        "relevance_score": 0.85,
    })
    assert r.status_code == 200
    signal_id = r.json()["id"]

    r = await client.get("/api/mkt-signals")
    assert r.status_code == 200

    r = await client.patch(f"/api/mkt-signals/{signal_id}", json={"status": "reviewed"})
    assert r.status_code == 200

    r = await client.delete(f"/api/mkt-signals/{signal_id}")
    assert r.status_code == 200


# ─── Marketing Content ───────────────────────────────────

@pytest.mark.asyncio
async def test_content_crud(client: AsyncClient):
    r = await client.post("/api/mkt-content", json={
        "title": "Draft tweet",
        "body": "Check out our tool",
        "channel": "x",
    })
    assert r.status_code == 200
    content_id = r.json()["id"]

    r = await client.patch(f"/api/mkt-content/{content_id}", json={"status": "approved"})
    assert r.status_code == 200

    r = await client.delete(f"/api/mkt-content/{content_id}")
    assert r.status_code == 200


# ─── Agent CRUD ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_agent(client):
    r = await client.post("/api/agents", json={
        "name": "Test Agent",
        "description": "A test agent",
        "agent_type": "marketing",
        "model": "claude-haiku-4-5",
        "prompt_template": "You are a test agent. {{projects}}",
        "tools": ["web_search"],
        "data_reads": ["projects"],
        "data_writes": ["tasks"],
        "max_budget_usd": 0.15,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Test Agent"
    assert data["slug"] == "test-agent"


@pytest.mark.asyncio
async def test_create_agent_duplicate_name(client):
    await client.post("/api/agents", json={
        "name": "Unique Agent", "agent_type": "ops",
        "prompt_template": "test", "model": "claude-haiku-4-5",
    })
    r = await client.post("/api/agents", json={
        "name": "Unique Agent", "agent_type": "ops",
        "prompt_template": "test2", "model": "claude-haiku-4-5",
    })
    assert r.status_code == 409
