"""Dev tasks: GitHub issues for Claude Code, PR tracking, reply forwarding."""

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models import Project, Task, TaskComment, TaskStatus
from app.integrations import commands, github
from app.orchestrator import threads


@pytest.fixture
def gh(monkeypatch):
    """Fake GitHub API: records requests, serves canned responses."""
    calls = []
    state = {"issue_state": "open", "timeline": []}

    async def fake_request(method, path, json=None):
        calls.append((method, path, json))
        if method == "POST" and path.endswith("/issues"):
            return {"number": 7, "html_url": "https://github.com/acme/app/issues/7"}
        if path.endswith("/timeline?per_page=100"):
            return state["timeline"]
        if method == "GET":
            return {"state": state["issue_state"]}
        return {}

    sent = []

    async def fake_send(text, reply_markup=None):
        sent.append(text)
        return 500 + len(sent)

    monkeypatch.setattr(settings, "github_token", "ghp_test")
    monkeypatch.setattr(settings, "github_mention_claude", True)
    monkeypatch.setattr(github, "_request", fake_request)
    monkeypatch.setattr(github, "send_telegram", fake_send)
    return calls, state, sent


async def add_project(db_session, **kw) -> Project:
    project = Project(name="Acme App", description="Invoicing SaaS", **kw)
    async with db_session() as db:
        db.add(project)
        await db.commit()
    return project


def test_normalize_repo():
    assert github.normalize_repo("acme/app") == "acme/app"
    assert github.normalize_repo("https://github.com/acme/app.git") == "acme/app"
    assert github.normalize_repo("github.com/acme/app/") == "acme/app"
    assert github.normalize_repo("not a repo") is None


@pytest.mark.asyncio
async def test_repo_and_dev_commands_open_issue_for_claude(db_session, gh):
    calls, _, _ = gh
    await add_project(db_session)

    result = await commands.cmd_repo("acme app https://github.com/acme/app", "telegram")
    assert "github.com/acme/app" in result.text

    result = await commands.cmd_dev("acme app add CSV export to invoices", "telegram")
    assert result.text.startswith("Opened https://github.com/acme/app/issues/7")

    method, path, body = calls[0]
    assert (method, path) == ("POST", "/repos/acme/app/issues")
    assert body["title"] == "add CSV export to invoices"
    assert "@claude" in body["body"] and "Project: Acme App" in body["body"]

    async with db_session() as db:
        task = (await db.execute(select(Task))).scalar_one()
        comments = (await db.execute(select(TaskComment))).scalars().all()
    assert task.url == "https://github.com/acme/app/issues/7"
    assert task.status == TaskStatus.IN_PROGRESS and "dev" in task.tags
    assert "Opened issue #7" in comments[0].body


@pytest.mark.asyncio
async def test_dev_without_repo_explains_how_to_set_it(db_session, gh):
    await add_project(db_session)
    result = await commands.cmd_dev("acme app fix login", "telegram")
    assert "/repo Acme App owner/repo" in result.text


@pytest.mark.asyncio
async def test_sync_reports_pr_once_and_closes_task(db_session, gh):
    _, state, sent = gh
    project = await add_project(db_session, github_repo="acme/app")
    task = Task(text="CSV export", project_id=project.id, tags=["dev"],
                url="https://github.com/acme/app/issues/7", status=TaskStatus.IN_PROGRESS)
    async with db_session() as db:
        db.add(task)
        await db.commit()

    state["timeline"] = [{"event": "cross-referenced", "source": {"issue": {
        "html_url": "https://github.com/acme/app/pull/8", "title": "Add CSV export", "pull_request": {},
    }}}]
    async with db_session() as db:
        await github.sync_dev_tasks(db)
        await github.sync_dev_tasks(db)  # same PR again: no duplicate
    assert len(sent) == 1 and "pull/8" in sent[0]

    state["issue_state"] = "closed"
    async with db_session() as db:
        await github.sync_dev_tasks(db)
        task = await db.get(Task, task.id)
        bodies = [c.body for c in await threads.load_thread(db, task.id)]
    assert task.status == TaskStatus.DONE
    assert bodies == ["Pull request opened: Add CSV export https://github.com/acme/app/pull/8",
                      "Issue #7 was closed on GitHub."]


@pytest.mark.asyncio
async def test_thread_reply_on_dev_task_goes_to_the_issue(db_session, gh):
    calls, _, _ = gh
    task = Task(text="CSV export", tags=["dev"], url="https://github.com/acme/app/issues/7")
    async with db_session() as db:
        db.add(task)
        await db.commit()
        await threads.add_user_reply(db, await db.get(Task, task.id), "Also support XLSX")
    assert calls[-1] == ("POST", "/repos/acme/app/issues/7/comments", {"body": "@claude Also support XLSX"})


@pytest.mark.asyncio
async def test_send_existing_task_to_github_via_api(client, db_session, gh):
    project = await add_project(db_session, github_repo="acme/app")
    no_project = (await client.post("/api/tasks", json={"text": "Orphan"})).json()["id"]
    r = await client.post(f"/api/tasks/{no_project}/github")
    assert r.status_code == 400

    task_id = (await client.post("/api/tasks", json={"text": "Fix login", "project_id": str(project.id)})).json()["id"]
    r = await client.post(f"/api/tasks/{task_id}/github")
    assert r.json() == {"issue_url": "https://github.com/acme/app/issues/7"}
    detail = (await client.get(f"/api/tasks/{task_id}")).json()
    assert detail["github_issue"] == "https://github.com/acme/app/issues/7"
    assert (await client.post(f"/api/tasks/{task_id}/github")).status_code == 409
