"""
Backend test suite for Mission Control API.

Uses pytest-asyncio with an in-memory SQLite for isolation.
"""

import pytest
from httpx import AsyncClient


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


# ─── Leads (tasks tagged "lead") ─────────────────────────

@pytest.mark.asyncio
async def test_leads_are_tagged_tasks(client: AsyncClient):
    await client.post("/api/tasks", json={
        "text": "r/SaaS - looking for SEO tools",
        "description": "Thread with 23 upvotes",
        "url": "https://reddit.com/r/SaaS/x",
        "tags": ["lead", "reddit"],
    })
    await client.post("/api/tasks", json={"text": "Regular task"})

    r = await client.get("/api/tasks?tag=lead")
    assert r.status_code == 200
    leads = r.json()
    assert [t["text"] for t in leads] == ["r/SaaS - looking for SEO tools"]
    assert leads[0]["url"] == "https://reddit.com/r/SaaS/x"
    assert leads[0]["description"] == "Thread with 23 upvotes"


# ─── Marketing Content ───────────────────────────────────

@pytest.mark.asyncio
async def test_content_crud(client: AsyncClient):
    lead = await client.post("/api/tasks", json={"text": "Lead", "tags": ["lead"]})
    r = await client.post("/api/mkt-content", json={
        "title": "Draft tweet",
        "body": "Check out our tool",
        "channel": "x",
        "task_id": lead.json()["id"],
    })
    assert r.status_code == 200
    content_id = r.json()["id"]
    assert r.json()["task_id"] == lead.json()["id"]

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


@pytest.mark.asyncio
async def test_activity_feed_lists_thread_messages_newest_first(client, db_session):
    from app.db.models import AgentConfig, Task, TaskComment
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    task = Task(text="Compare pricing")
    async with db_session() as db:
        db.add_all([task, AgentConfig(name="Ace (Assistant)", slug="ace-assistant", agent_type="general", prompt_template="p")])
        await db.flush()
        db.add_all([
            TaskComment(task_id=task.id, author="user", body="Assigned", created_at=now - timedelta(minutes=5)),
            TaskComment(task_id=task.id, author="agent:ace-assistant", body="Plausible is cheaper", created_at=now),
        ])
        await db.commit()

    feed = (await client.get("/api/activity")).json()
    assert [(e["author_name"], e["body"]) for e in feed] == [
        ("Ace (Assistant)", "Plausible is cheaper"), ("You", "Assigned"),
    ]
    assert feed[0]["task"]["text"] == "Compare pricing"


# ─── Auth ─────────────────────────────────────────────────

@pytest.fixture
def password(monkeypatch):
    from app.auth import _failures
    from app.config import settings
    _failures.clear()
    monkeypatch.setattr(settings, "dashboard_password", "hunter2")
    monkeypatch.setattr(settings, "api_token", "script-token")
    return "hunter2"


@pytest.mark.asyncio
async def test_api_is_open_without_a_password(client):
    assert (await client.get("/api/tasks")).status_code == 200
    assert (await client.get("/api/auth/me")).json() == {"auth_enabled": False, "authenticated": True}


@pytest.mark.asyncio
async def test_login_protects_the_api(client, password):
    assert (await client.get("/api/tasks")).status_code == 401
    assert (await client.get("/health")).status_code == 200  # healthchecks stay public

    r = await client.post("/api/auth/login", json={"password": "wrong"})
    assert r.status_code == 401

    r = await client.post("/api/auth/login", json={"password": password})
    assert r.status_code == 200 and "mc_session" in r.cookies
    assert (await client.get("/api/tasks")).status_code == 200
    assert (await client.get("/api/auth/me")).json()["authenticated"] is True

    await client.post("/api/auth/logout")
    client.cookies.clear()
    assert (await client.get("/api/tasks")).status_code == 401


@pytest.mark.asyncio
async def test_api_token_works_for_scripts(client, password):
    r = await client.get("/api/tasks", headers={"Authorization": "Bearer script-token"})
    assert r.status_code == 200
    r = await client.get("/api/tasks", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_forged_or_expired_sessions_are_rejected(client, password):
    from app.auth import make_session
    client.cookies.set("mc_session", make_session(now=0))  # expired long ago
    assert (await client.get("/api/tasks")).status_code == 401
    payload, sig = make_session().rsplit(".", 1)
    client.cookies.set("mc_session", f"{payload}.{'0' * len(sig)}")
    assert (await client.get("/api/tasks")).status_code == 401


@pytest.mark.asyncio
async def test_login_attempts_are_rate_limited(client, password):
    for _ in range(5):
        await client.post("/api/auth/login", json={"password": "wrong"})
    r = await client.post("/api/auth/login", json={"password": password})
    assert r.status_code == 429


def test_websocket_requires_login(password):
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from app.main import app
    tc = TestClient(app)  # no `with`: skip app startup (scheduler, real DB)
    with pytest.raises(WebSocketDisconnect):
        with tc.websocket_connect("/ws") as ws:
            ws.receive_text()
