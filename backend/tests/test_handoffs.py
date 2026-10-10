"""Agents handing work to each other, and live progress of agent runs."""

from uuid import UUID

import pytest
from claude_agent_sdk import AssistantMessage, TextBlock, ToolUseBlock
from sqlalchemy import select

from app.db.models import AgentConfig, Task, TaskStatus
from app.orchestrator import handoffs, runner as runner_mod
from app.orchestrator.runner import AgentRunner, current_progress, describe_tool_use
from app.orchestrator.threads import pending_assignments

from tests.test_threads import agent_replies, make_agent, telegram, thread_of, wait_for_runs  # noqa: F401


async def pulse_and_echo(db_session) -> tuple[AgentConfig, AgentConfig]:
    pulse = await make_agent(db_session, name="Pulse (Reddit Scout)", slug="pulse", data_writes=["tasks"])
    echo = await make_agent(db_session, name="Echo (Content Drafts)", slug="echo", description="Writes posts and replies")
    return pulse, echo


@pytest.mark.asyncio
async def test_agent_hands_off_to_a_teammate(client, db_session, telegram, agent_replies):  # noqa: F811
    outputs, prompts = agent_replies
    pulse, echo = await pulse_and_echo(db_session)
    outputs.append({"summary": "found a lead", "reply": "Found a good thread; Echo will draft a reply.", "status": "done",
                    "actions": [{"type": "handoff", "agent": "echo",
                                 "request": "Draft a reply to the r/SaaS thread about analytics\nKeep it helpful, mention our free tier."}]})
    outputs.append({"summary": "drafted", "reply": "Here's a draft: ...", "status": "done"})

    lead_id = (await client.post("/api/tasks", json={"text": "Lead: r/SaaS analytics thread"})).json()["id"]
    await client.post(f"/api/tasks/{lead_id}/assign", json={"agent_id": str(pulse.id)})
    await wait_for_runs()

    # Pulse's prompt listed its teammates
    assert '"slug": "echo"' in prompts[0]
    # Echo got the request, knew who it came from and what it's part of
    assert "Your teammate pulse handed you a task" in prompts[1]
    assert "PART OF: Lead: r/SaaS analytics thread" in prompts[1]
    assert "free tier" in prompts[1]

    async with db_session() as db:
        child = (await db.execute(select(Task).where(Task.parent_task_id.isnot(None)))).scalar_one()
        assert child.text == "Draft a reply to the r/SaaS thread about analytics"
        assert child.assigned_agent_id == echo.id and child.status == TaskStatus.DONE

    assert [a for a, _ in await thread_of(db_session, child.id)] == ["agent:pulse", "agent:echo"]
    parent_thread = [b for _, b in await thread_of(db_session, UUID(lead_id))]
    assert any("handed “Draft a reply" in b and "to Echo" in b for b in parent_thread)
    assert any("Echo (Content Drafts) finished" in b for b in parent_thread)
    assert any("Handed over by pulse" in t for t in telegram)

    detail = (await client.get(f"/api/tasks/{lead_id}")).json()
    assert detail["handoffs"] == [{
        "id": str(child.id), "text": child.text, "status": "done", "assigned_agent_name": "Echo (Content Drafts)",
    }]
    child_detail = (await client.get(f"/api/tasks/{child.id}")).json()
    assert child_detail["parent"] == {"id": lead_id, "text": "Lead: r/SaaS analytics thread"}


@pytest.mark.asyncio
async def test_handoffs_that_are_not_allowed_are_skipped(db_session):
    pulse, echo = await pulse_and_echo(db_session)
    async with db_session() as db:
        for action, error in [
            ({"type": "handoff", "agent": "pulse", "request": "x"}, "itself"),
            ({"type": "handoff", "agent": "nobody", "request": "x"}, "no agent"),
            ({"type": "handoff", "agent": "echo"}, "needs a request"),
        ]:
            with pytest.raises(ValueError, match=error):
                await handoffs.hand_off(db, pulse, action)

        warnings = await AgentRunner().process_actions([{"type": "handoff", "agent": "pulse", "request": "x"}], pulse, db)
        assert "itself" in warnings[0]
        assert (await db.execute(select(Task))).scalars().all() == []


@pytest.mark.asyncio
async def test_handoff_chains_are_bounded(db_session):
    pulse, echo = await pulse_and_echo(db_session)
    async with db_session() as db:
        task = Task(text="root")
        db.add(task)
        await db.flush()
        for _ in range(handoffs.MAX_DEPTH - 1):
            task = await handoffs.hand_off(db, pulse, {"agent": "echo", "request": "deeper", "task_id": str(task.id)})
        with pytest.raises(ValueError, match="deep"):
            await handoffs.hand_off(db, pulse, {"agent": "echo", "request": "too deep", "task_id": str(task.id)})
        await db.rollback()

    actions = [{"type": "handoff", "agent": "echo", "request": f"r{i}"} for i in range(handoffs.MAX_PER_RUN + 2)]
    kept, warnings = runner_mod._limit_handoffs(actions, None)
    assert len(kept) == handoffs.MAX_PER_RUN and len(warnings) == 2


@pytest.mark.asyncio
async def test_busy_teammate_picks_up_the_handoff_later(db_session):
    pulse, echo = await pulse_and_echo(db_session)
    async with db_session() as db:
        child = await handoffs.hand_off(db, pulse, {"agent": "echo", "request": "Draft a post"})
        # Not committed yet: the start-after-commit hook would launch Echo; stand in for a busy Echo
        runner_mod._active_runs[echo.id] = None
        try:
            await db.commit()
        finally:
            runner_mod._active_runs.pop(echo.id, None)
        assert (echo.id, child.id) in await pending_assignments(db)


@pytest.mark.asyncio
async def test_progress_is_published_while_an_agent_works(db_session, monkeypatch):
    events = []

    async def fake_broadcast(event_type, data):
        events.append((event_type, data))

    monkeypatch.setattr(runner_mod, "broadcast", fake_broadcast)
    agent = await make_agent(db_session)
    runner_mod._progress[agent.id] = {"task_id": "t1", "steps": []}
    try:
        message = AssistantMessage(content=[
            TextBlock(text="Let me look."),
            ToolUseBlock(id="1", name="WebSearch", input={"query": "plausible pricing"}),
            ToolUseBlock(id="2", name="WebFetch", input={"url": "https://plausible.io/pricing"}),
        ], model="m")
        await AgentRunner()._report_progress(agent, message)
        assert current_progress(agent.id, "t1") == [
            "Searching the web: plausible pricing", "Reading plausible.io/pricing",
        ]
        assert current_progress(agent.id, "other-task") == []
        assert events == [("run.progress", {"agent_id": str(agent.id), "task_id": "t1", "steps": current_progress(agent.id)})]
    finally:
        runner_mod._progress.pop(agent.id, None)


def test_describe_tool_use():
    assert describe_tool_use("Read", {"file_path": "/app/workdir/notes/plan.md"}) == "Reading plan.md"
    assert describe_tool_use("Bash", {"command": "ls -la"}) == "Running `ls -la`"
    assert describe_tool_use("Mystery", None) == "Using Mystery"


@pytest.mark.asyncio
async def test_task_is_not_shown_as_in_progress_while_its_agent_runs_another_job(db_session):
    agent = await make_agent(db_session)
    async with db_session() as db:
        task = Task(text="Compare pricing", assigned_agent_id=agent.id)
        db.add(task)
        await db.commit()
    runner_mod._active_runs[agent.id] = None
    try:
        runner_mod._progress[agent.id] = {"task_id": None, "steps": []}  # its scheduled job
        assert not runner_mod.is_working_on(agent.id, task.id)
        runner_mod._progress[agent.id] = {"task_id": str(task.id), "steps": []}
        assert runner_mod.is_working_on(agent.id, task.id)
    finally:
        runner_mod._active_runs.pop(agent.id, None)
        runner_mod._progress.pop(agent.id, None)
