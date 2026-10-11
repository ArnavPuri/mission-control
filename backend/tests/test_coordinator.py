"""The coordinator: takes a request, runs the team, answers once."""

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models import AgentConfig, Task, TaskStatus
from app.integrations import commands
from app.orchestrator import coordinator, handoffs, runner as runner_mod
from app.orchestrator.runner import AgentRunner
from app.orchestrator.threads import pending_assignments

from tests.test_threads import make_agent, telegram, thread_of, wait_for_runs  # noqa: F401


@pytest.fixture
def team_replies(monkeypatch):
    """Per-agent queues of outputs; records each agent's prompts."""
    outputs: dict[str, list[dict]] = {}
    prompts: dict[str, list[str]] = {}

    async def fake(self, prompt, agent):
        prompts.setdefault(agent.slug, []).append(prompt)
        return outputs[agent.slug].pop(0)

    monkeypatch.setattr(AgentRunner, "execute_with_agent_sdk", fake)
    return outputs, prompts


async def make_team(db_session) -> tuple[AgentConfig, AgentConfig, AgentConfig]:
    ace = await make_agent(db_session, name="Ace (Assistant)", slug="ace", config={"role": "coordinator"},
                           description="Your coordinator")
    nav = await make_agent(db_session, name="Navigator (Web Researcher)", slug="navigator")
    echo = await make_agent(db_session, name="Echo (Content Drafts)", slug="echo")
    return ace, nav, echo


@pytest.mark.asyncio
async def test_coordinator_runs_the_team_and_answers_once(db_session, telegram, team_replies):  # noqa: F811
    outputs, prompts = team_replies
    await make_team(db_session)
    outputs["ace"] = [
        {"summary": "split", "status": "waiting",
         "reply": "On it: Navigator compares the tools, Echo drafts the post.",
         "actions": [
             {"type": "handoff", "agent": "navigator", "request": "Compare Plausible and Fathom pricing"},
             {"type": "handoff", "agent": "echo", "request": "Draft a LinkedIn post on why we switched analytics"},
         ]},
        # Round 2: Echo asked something Ace can answer itself
        {"summary": "answered echo", "status": "waiting", "reply": "Told Echo to keep it casual.",
         "actions": [{"type": "follow_up", "task_id": "ECHO_TASK", "request": "Casual, first person."}]},
        # Round 3: everything is in
        {"summary": "done", "status": "done",
         "reply": "Plausible is $9/mo vs Fathom $15/mo. Here's your post: We switched to Plausible…"},
    ]
    outputs["navigator"] = [{"summary": "compared", "status": "done", "reply": "Plausible $9/mo, Fathom $15/mo."}]
    outputs["echo"] = [
        {"summary": "question", "status": "needs_input", "reply": "Formal or casual tone?"},
        {"summary": "drafted", "status": "done", "reply": "We switched to Plausible…"},
    ]

    # Fill in Echo's task id for Ace's follow_up once it exists
    original = AgentRunner.execute_with_agent_sdk

    async def with_task_ids(self, prompt, agent):
        if agent.slug == "ace" and len(prompts.get("ace", [])) == 1:
            async with db_session() as db:
                echo_task = (await db.execute(select(Task).where(Task.text.like("Draft a LinkedIn%")))).scalar_one()
            outputs["ace"][0]["actions"][0]["task_id"] = str(echo_task.id)
        return await original(self, prompt, agent)

    import app.orchestrator.runner  # noqa: F401
    AgentRunner.execute_with_agent_sdk = with_task_ids
    try:
        result = await commands.cmd_do("compare analytics tools and draft a LinkedIn post about it", "telegram")
        assert result.text.startswith("Ace (Assistant) is on it")
        await wait_for_runs()
    finally:
        AgentRunner.execute_with_agent_sdk = original

    async with db_session() as db:
        request = (await db.execute(select(Task).where(Task.parent_task_id.is_(None)))).scalar_one()
        children = (await db.execute(select(Task).where(Task.parent_task_id == request.id))).scalars().all()
        assert request.status == TaskStatus.DONE
        assert sorted(c.status for c in children) == [TaskStatus.DONE, TaskStatus.DONE]

    # Ace ran three times; round 2 saw both teammates' replies and the team status
    assert len(prompts["ace"]) == 3
    assert "Plausible $9/mo, Fathom $15/mo." in prompts["ace"][1] and "Formal or casual tone?" in prompts["ace"][1]
    assert "WORK YOU HANDED OUT" in prompts["ace"][1]
    assert "[waiting for an answer] echo" in prompts["ace"][1]
    # Echo got Ace's answer
    assert "Casual, first person." in prompts["echo"][1]

    # One voice: only Ace talked to the user
    assert len(telegram) == 2
    assert all("Ace (Assistant)" in t for t in telegram)
    assert "On it" in telegram[0] and "Here's your post" in telegram[1]

    authors = [a for a, _ in await thread_of(db_session, request.id)]
    assert authors[0] == "user" and authors[-1] == "agent:ace"
    assert "agent:navigator" in authors and "agent:echo" in authors


@pytest.mark.asyncio
async def test_coordinator_waits_for_all_handoffs(db_session):
    ace, nav, echo = await make_team(db_session)
    async with db_session() as db:
        request = Task(text="Big request", assigned_agent_id=ace.id, status=TaskStatus.IN_PROGRESS)
        db.add(request)
        await db.flush()
        runner_mod._active_runs[nav.id] = runner_mod._active_runs[echo.id] = None  # don't start them
        try:
            a = await handoffs.hand_off(db, ace, {"agent": "navigator", "request": "research", "task_id": str(request.id)})
            b = await handoffs.hand_off(db, ace, {"agent": "echo", "request": "draft", "task_id": str(request.id)})
            await db.commit()
        finally:
            runner_mod._active_runs.pop(nav.id, None)
            runner_mod._active_runs.pop(echo.id, None)

        a.status = TaskStatus.DONE
        await handoffs.report_to_parent(db, a, nav, needs_input=False, reply="findings")
        runner_mod._active_runs[ace.id] = None  # keep the start-after-commit hook from running Ace
        try:
            await db.commit()
            # Navigator's reply is in, but Echo is still working: not Ace's turn yet
            assert (ace.id, request.id) not in await pending_assignments(db)
            b.status = TaskStatus.DONE
            await handoffs.report_to_parent(db, b, echo, needs_input=False, reply="draft")
            await db.commit()
            assert (ace.id, request.id) in await pending_assignments(db)
        finally:
            runner_mod._active_runs.pop(ace.id, None)


@pytest.mark.asyncio
async def test_teammate_failure_goes_to_the_coordinator(db_session, telegram, team_replies):  # noqa: F811
    outputs, prompts = team_replies
    await make_team(db_session)
    outputs["ace"] = [
        {"summary": "split", "status": "waiting", "reply": "Navigator is on it.",
         "actions": [{"type": "handoff", "agent": "navigator", "request": "research"}]},
        {"summary": "gave up", "status": "done", "reply": "Research failed; here's what I know."},
    ]

    async def boom(self, prompt, agent):
        if agent.slug == "navigator":
            raise RuntimeError("search is down")
        prompts.setdefault(agent.slug, []).append(prompt)
        return outputs[agent.slug].pop(0)

    AgentRunner.execute_with_agent_sdk = boom
    await commands.cmd_do("research something", "telegram")
    await wait_for_runs()

    assert "search is down" in prompts["ace"][1]
    assert len(telegram) == 2 and not any("couldn't finish" in t for t in telegram)


@pytest.mark.asyncio
async def test_relay_setting_also_sends_teammate_replies(db_session, telegram, team_replies, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "coordinator_relay_teammates", True)
    outputs, _ = team_replies
    await make_team(db_session)
    outputs["ace"] = [
        {"summary": "s", "status": "waiting", "reply": "plan",
         "actions": [{"type": "handoff", "agent": "navigator", "request": "research"}]},
        {"summary": "d", "status": "done", "reply": "final"},
    ]
    outputs["navigator"] = [{"summary": "r", "status": "done", "reply": "findings"}]
    await commands.cmd_do("research", "telegram")
    await wait_for_runs()
    assert any("Navigator" in t and "findings" in t for t in telegram)


@pytest.mark.asyncio
async def test_rounds_and_handoffs_are_capped(db_session):
    ace, _, _ = await make_team(db_session)
    many = [{"type": "handoff", "agent": "echo", "request": f"r{i}"} for i in range(coordinator.MAX_HANDOFFS_PER_ROUND + 1)]
    kept, warnings = runner_mod._limit_handoffs(many, None, ace, rounds=0)
    assert len(kept) == coordinator.MAX_HANDOFFS_PER_ROUND and len(warnings) == 1
    kept, warnings = runner_mod._limit_handoffs(many, None, ace, rounds=coordinator.MAX_ROUNDS - 1)
    assert kept == [] and "last round" in warnings[0]


@pytest.mark.asyncio
async def test_follow_up_only_on_your_own_handoffs(db_session):
    ace, nav, echo = await make_team(db_session)
    async with db_session() as db:
        other = Task(text="not Ace's", assigned_agent_id=nav.id)
        db.add(other)
        await db.flush()
        with pytest.raises(ValueError, match="work you handed out"):
            await handoffs.follow_up(db, ace, {"task_id": str(other.id), "request": "hi"})
        with pytest.raises(ValueError, match="needs a request"):
            await handoffs.follow_up(db, ace, {"task_id": str(other.id)})


@pytest.mark.asyncio
async def test_do_without_a_coordinator(db_session):
    await make_agent(db_session)
    result = await commands.cmd_do("research something", "telegram")
    assert "No coordinator" in result.text


@pytest.mark.asyncio
async def test_chat_routes_work_to_the_coordinator(db_session, telegram, team_replies):  # noqa: F811
    from app.integrations.chat import build_system_prompt, execute_tool_call

    outputs, _ = team_replies
    await make_team(db_session)
    outputs["ace"] = [{"summary": "done", "status": "done", "reply": "Here you go."}]
    assert "coordinate" in build_system_prompt({"coordinator": "Ace (Assistant)"})
    assert "coordinate:" not in build_system_prompt({}).split("Available action types:")[0]

    async with db_session() as db:
        out = await execute_tool_call("coordinate", {"request": "write me a launch tweet"}, db)
        await db.commit()
    assert out.startswith("Ace (Assistant)")
    await wait_for_runs()
    assert telegram and "Here you go." in telegram[-1]


@pytest.mark.asyncio
async def test_activity_feed_hides_team_chatter(client, db_session):
    from app.db.models import TaskComment
    ace, nav, _ = await make_team(db_session)
    async with db_session() as db:
        request = Task(text="Big request", assigned_agent_id=ace.id)
        db.add(request)
        await db.flush()
        child = Task(text="research", assigned_agent_id=nav.id, parent_task_id=request.id)
        db.add(child)
        await db.flush()
        db.add_all([
            TaskComment(task_id=request.id, author="system", body="↪ Ace handed “research” to Navigator"),
            TaskComment(task_id=child.id, author="agent:ace", body="please research"),
            TaskComment(task_id=child.id, author="agent:navigator", body="findings"),
            TaskComment(task_id=request.id, author="agent:navigator", body="**Navigator** finished: findings"),
            TaskComment(task_id=request.id, author="agent:ace", body="final answer"),
        ])
        await db.commit()
    feed = (await client.get("/api/activity")).json()
    assert sorted(e["body"] for e in feed) == ["final answer", "findings"]
