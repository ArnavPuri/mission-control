"""Assigning tasks to agents and the task thread loop (API, Telegram, scheduler)."""

import asyncio

import pytest
from sqlalchemy import select

from app.db.models import AgentConfig, AgentStatus, Task, TaskComment, TaskStatus
from app.integrations import commands
from app.orchestrator import runner as runner_mod
from app.orchestrator import threads
from app.orchestrator.runner import AgentRunner


@pytest.fixture
def telegram(monkeypatch):
    """Capture messages sent to Telegram; each gets a fresh message id."""
    sent = []

    async def fake_send(text, reply_markup=None):
        sent.append(text)
        return 1000 + len(sent)

    monkeypatch.setattr(threads, "send_telegram", fake_send)
    return sent


@pytest.fixture
def agent_replies(monkeypatch):
    """Queue of outputs the stubbed agent returns; records the prompts it got."""
    outputs, prompts = [], []

    async def fake(self, prompt, agent):
        prompts.append(prompt)
        return outputs.pop(0)

    monkeypatch.setattr(AgentRunner, "execute_with_agent_sdk", fake)
    return outputs, prompts


async def wait_for_runs():
    while runner_mod._active_runs:
        await asyncio.gather(*runner_mod._active_runs.values(), return_exceptions=True)


async def make_agent(db_session, **kw) -> AgentConfig:
    fields = dict(name="Navigator", slug="navigator", agent_type="research",
                  prompt_template="scheduled job", data_reads=["projects"], data_writes=["notes"])
    fields.update(kw)
    agent = AgentConfig(**fields)
    async with db_session() as db:
        db.add(agent)
        await db.commit()
    return agent


async def thread_of(db_session, task_id) -> list[tuple[str, str]]:
    async with db_session() as db:
        return [(c.author, c.body) for c in await threads.load_thread(db, task_id)]


@pytest.mark.asyncio
async def test_assign_runs_agent_and_replies_in_thread(client, db_session, telegram, agent_replies):
    outputs, prompts = agent_replies
    outputs.append({"summary": "compared", "reply": "Plausible is $9/mo, Fathom $15/mo.", "status": "done"})
    agent = await make_agent(db_session)
    task_id = (await client.post("/api/tasks", json={"text": "Compare analytics pricing"})).json()["id"]

    r = await client.post(f"/api/tasks/{task_id}/assign", json={"agent_id": str(agent.id)})
    assert r.json() == {"assigned": "navigator", "started": True}
    await wait_for_runs()

    detail = (await client.get(f"/api/tasks/{task_id}")).json()
    assert detail["status"] == "done"
    assert detail["assigned_agent_name"] == "Navigator"
    assert [(c["author"], c["body"]) for c in detail["comments"]] == [
        ("user", "Assigned to Navigator"),
        ("agent:navigator", "Plausible is $9/mo, Fathom $15/mo."),
    ]
    assert "TASK: Compare analytics pricing" in prompts[0]
    assert "Plausible is $9/mo" in telegram[0]


@pytest.mark.asyncio
async def test_telegram_reply_continues_the_thread(db_session, telegram, agent_replies):
    outputs, prompts = agent_replies
    outputs.append({"summary": "q", "reply": "Which region?", "status": "needs_input"})
    outputs.append({"summary": "a", "reply": "EU pricing: €9/mo.", "status": "done"})
    agent = await make_agent(db_session)

    result = await commands.cmd_ask("navigator compare analytics pricing", "telegram")
    assert result.text.startswith("Navigator is on it")
    await wait_for_runs()

    async with db_session() as db:
        task = (await db.execute(select(Task))).scalar_one()
        assert task.status == TaskStatus.BLOCKED  # waiting on the user
        agent_msg = (await db.execute(
            select(TaskComment).where(TaskComment.author == "agent:navigator")
        )).scalar_one()
        found = await threads.find_task_by_telegram_message(db, agent_msg.telegram_message_id)
        assert found.id == task.id
        replied_agent = await threads.add_user_reply(db, found, "EU", telegram_message_id=5)
    assert replied_agent.id == agent.id
    await wait_for_runs()

    assert "[You] Which region?" in prompts[1] and "[user] EU" in prompts[1]
    assert [a for a, _ in await thread_of(db_session, task.id)] == [
        "user", "agent:navigator", "user", "agent:navigator",
    ]
    async with db_session() as db:
        assert (await db.get(Task, task.id)).status == TaskStatus.DONE


@pytest.mark.asyncio
async def test_busy_agent_queues_task_for_the_scheduler(db_session, telegram, agent_replies):
    outputs, _ = agent_replies
    agent = await make_agent(db_session)
    task = Task(text="Research competitors")
    async with db_session() as db:
        db.add(task)
        await db.commit()

    # Simulate the agent being busy with another run
    blocker = asyncio.get_running_loop().create_future()
    runner_mod._active_runs[agent.id] = blocker
    try:
        async with db_session() as db:
            started = await threads.assign_task(db, await db.get(Task, task.id), await db.get(AgentConfig, agent.id))
            assert started is False
            assert await threads.pending_assignments(db) == [(agent.id, task.id)]
    finally:
        runner_mod._active_runs.pop(agent.id)
        blocker.cancel()

    # Once the agent is free the scheduler starts it; afterwards nothing is pending
    outputs.append({"summary": "s", "reply": "Done.", "status": "done"})
    from app.orchestrator.scheduler import Scheduler
    await Scheduler()._check_schedules()
    await wait_for_runs()
    async with db_session() as db:
        assert await threads.pending_assignments(db) == []
        assert (await db.get(Task, task.id)).status == TaskStatus.DONE


@pytest.mark.asyncio
async def test_failed_task_run_blocks_task_without_retry_loop(db_session, telegram, monkeypatch):
    async def boom(self, prompt, agent):
        raise RuntimeError("budget exceeded")
    monkeypatch.setattr(AgentRunner, "execute_with_agent_sdk", boom)
    agent = await make_agent(db_session)

    await commands.cmd_ask("navigator do something", "telegram")
    await wait_for_runs()

    async with db_session() as db:
        task = (await db.execute(select(Task))).scalar_one()
        assert task.status == TaskStatus.BLOCKED
        assert await threads.pending_assignments(db) == []
        assert (await db.get(AgentConfig, agent.id)).status == AgentStatus.ERROR
    authors = [a for a, _ in await thread_of(db_session, task.id)]
    assert authors == ["user", "system"]
    assert "couldn't finish" in telegram[0]


@pytest.mark.asyncio
async def test_dashboard_comment_reaches_agent(client, db_session, telegram, agent_replies):
    outputs, prompts = agent_replies
    outputs.extend([
        {"summary": "s", "reply": "Draft v1", "status": "done"},
        {"summary": "s", "reply": "Draft v2, shorter", "status": "done"},
    ])
    agent = await make_agent(db_session)
    task_id = (await client.post("/api/tasks", json={"text": "Draft launch tweet"})).json()["id"]
    await client.post(f"/api/tasks/{task_id}/assign", json={"agent_id": str(agent.id)})
    await wait_for_runs()

    r = await client.post(f"/api/tasks/{task_id}/comments", json={"body": "Make it shorter"})
    assert r.json() == {"added": True, "agent": "navigator"}
    await wait_for_runs()

    assert "[user] Make it shorter" in prompts[1]
    detail = (await client.get(f"/api/tasks/{task_id}")).json()
    assert detail["comments"][-1]["body"] == "Draft v2, shorter"
