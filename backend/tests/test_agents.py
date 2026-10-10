"""Agent runtime: skill loading, runs, approvals, scheduling, cancellation."""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.agents.skill_loader import sync_skills_to_db
from app.db.models import (
    AgentApproval, AgentConfig, AgentRun, AgentRunStatus, AgentStatus,
    Notification, Task, TaskPriority, TaskStatus,
)
from app.integrations import commands
from app.integrations.telegram import is_allowed
from app.orchestrator import runner as runner_mod
from app.orchestrator.runner import (
    AgentRunner, cancel_run, recover_interrupted_runs, start_background_run,
)
from app.orchestrator.scheduler import is_due


def make_agent(**overrides) -> AgentConfig:
    fields = dict(
        name="Tester", slug="tester", agent_type="ops", prompt_template="{{tasks}}",
        data_reads=["tasks"], data_writes=["tasks"], config={},
    )
    fields.update(overrides)
    return AgentConfig(**fields)


def stub_sdk(monkeypatch, output: dict | None = None, delay: float = 0, error: Exception | None = None):
    async def fake(self, prompt, agent):
        if delay:
            await asyncio.sleep(delay)
        if error:
            raise error
        self._last_cost_usd = 0.0123
        return output or {"summary": "done", "actions": []}
    monkeypatch.setattr(AgentRunner, "execute_with_agent_sdk", fake)


async def add(db_session, *objs):
    async with db_session() as db:
        db.add_all(objs)
        await db.commit()


# --- Skill loader -----------------------------------------------------------

@pytest.mark.asyncio
async def test_skill_loader_keeps_approval_flag_and_disables_orphans(tmp_path, db_session):
    (tmp_path / "careful.yaml").write_text(
        "name: Careful\nprompt_template: hi\nrequires_approval: true\nmax_actions_per_run: 3\n"
    )
    await add(db_session, make_agent(name="Gone", slug="gone", skill_file="skills/gone.yaml"))

    await sync_skills_to_db(str(tmp_path))

    async with db_session() as db:
        careful = (await db.execute(select(AgentConfig).where(AgentConfig.slug == "careful"))).scalar_one()
        gone = (await db.execute(select(AgentConfig).where(AgentConfig.slug == "gone"))).scalar_one()
    assert careful.config["requires_approval"] is True
    assert careful.config["max_actions_per_run"] == 3
    assert gone.status == AgentStatus.DISABLED


# --- Runs ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_records_cost_and_applies_actions(monkeypatch, db_session):
    stub_sdk(monkeypatch, {"summary": "made a task", "actions": [
        {"type": "create_task", "text": "Follow up", "priority": "high"},
    ]})
    agent = make_agent()
    await add(db_session, agent)

    async with db_session() as db:
        agent = await db.get(AgentConfig, agent.id)
        run = await AgentRunner().start_run(agent, trigger="manual", db=db)

    async with db_session() as db:
        run = await db.get(AgentRun, run.id)
        tasks = (await db.execute(select(Task))).scalars().all()
        agent = await db.get(AgentConfig, agent.id)
    assert run.status == AgentRunStatus.COMPLETED
    assert run.cost_usd == pytest.approx(0.0123)
    assert [(t.text, t.priority) for t in tasks] == [("Follow up", TaskPriority.HIGH)]
    assert agent.status == AgentStatus.IDLE


@pytest.mark.asyncio
async def test_requires_approval_queues_actions_and_notifies(monkeypatch, db_session):
    stub_sdk(monkeypatch, {"summary": "proposal", "actions": [{"type": "create_task", "text": "X"}]})
    agent = make_agent(config={"requires_approval": True})
    await add(db_session, agent)

    async with db_session() as db:
        await AgentRunner().start_run(await db.get(AgentConfig, agent.id), trigger="manual", db=db)

    async with db_session() as db:
        assert (await db.execute(select(Task))).scalars().all() == []
        approval = (await db.execute(select(AgentApproval))).scalar_one()
        notes = (await db.execute(select(Notification))).scalars().all()
    assert approval.actions[0]["text"] == "X"
    assert any(n.category == "approval" and n.priority.value == "urgent" for n in notes)


@pytest.mark.asyncio
async def test_bad_actions_are_skipped_and_limit_enforced(monkeypatch, db_session):
    stub_sdk(monkeypatch, {"summary": "s", "actions": [
        {"type": "update_task", "task_id": "not-a-uuid", "status": "done"},
        {"type": "create_task", "text": "one", "priority": "urgent!!"},
        {"type": "create_task", "text": "two"},
        {"type": "create_task", "text": "three"},
    ]})
    agent = make_agent(config={"max_actions_per_run": 3})
    await add(db_session, agent)

    async with db_session() as db:
        run = await AgentRunner().start_run(await db.get(AgentConfig, agent.id), trigger="manual", db=db)

    async with db_session() as db:
        run = await db.get(AgentRun, run.id)
        texts = sorted(t.text for t in (await db.execute(select(Task))).scalars().all())
    assert run.status == AgentRunStatus.COMPLETED
    # 4th action dropped by the limit; 1st and 2nd are malformed and skipped
    assert texts == ["two"]


@pytest.mark.asyncio
async def test_update_task_done_sets_completed_at(monkeypatch, db_session):
    task = Task(text="Ship")
    await add(db_session, task)
    stub_sdk(monkeypatch, {"summary": "s", "actions": [
        {"type": "update_task", "task_id": str(task.id), "status": "done"},
    ]})
    agent = make_agent()
    await add(db_session, agent)

    async with db_session() as db:
        await AgentRunner().start_run(await db.get(AgentConfig, agent.id), trigger="manual", db=db)

    async with db_session() as db:
        task = await db.get(Task, task.id)
    assert task.status == TaskStatus.DONE and task.completed_at is not None


@pytest.mark.asyncio
async def test_legacy_signal_action_becomes_lead(monkeypatch, db_session):
    stub_sdk(monkeypatch, {"summary": "s", "actions": [{
        "type": "create_signal", "title": "Reddit thread", "source_type": "reddit",
        "source_url": "https://reddit.com/x", "relevance_score": 0.9, "signal_type": "opportunity",
    }]})
    agent = make_agent(data_writes=["tasks"])
    await add(db_session, agent)

    async with db_session() as db:
        await AgentRunner().start_run(await db.get(AgentConfig, agent.id), trigger="manual", db=db)

    async with db_session() as db:
        lead = (await db.execute(select(Task))).scalar_one()
    assert lead.tags[:2] == ["lead", "reddit"]
    assert lead.url == "https://reddit.com/x"
    assert lead.priority == TaskPriority.HIGH


@pytest.mark.asyncio
async def test_failed_run_marks_error_and_stays_scheduled(monkeypatch, db_session):
    stub_sdk(monkeypatch, error=RuntimeError("boom"))
    agent = make_agent(schedule_type="interval", schedule_value="4h")
    await add(db_session, agent)

    async with db_session() as db:
        run = await AgentRunner().start_run(await db.get(AgentConfig, agent.id), trigger="schedule", db=db)

    async with db_session() as db:
        run = await db.get(AgentRun, run.id)
        agent = await db.get(AgentConfig, agent.id)
    assert run.status == AgentRunStatus.FAILED and "boom" in run.error
    assert agent.status == AgentStatus.ERROR
    now = datetime.now(timezone.utc)
    # Not retried in a tight loop: waits for the next interval, then runs again
    assert not is_due(agent, now)
    assert is_due(agent, now + timedelta(hours=4, minutes=1))


@pytest.mark.asyncio
async def test_background_run_can_be_cancelled(monkeypatch, db_session):
    stub_sdk(monkeypatch, delay=30)
    agent = make_agent()
    await add(db_session, agent)

    assert start_background_run(agent.id, trigger="manual")
    assert not start_background_run(agent.id, trigger="manual")  # no duplicate runs
    await asyncio.sleep(0.1)
    assert await cancel_run(agent.id)

    async with db_session() as db:
        run = (await db.execute(select(AgentRun))).scalar_one()
        agent = await db.get(AgentConfig, agent.id)
    assert run.status == AgentRunStatus.CANCELLED
    assert agent.status == AgentStatus.IDLE
    assert not runner_mod.is_running(agent.id)


@pytest.mark.asyncio
async def test_recover_interrupted_runs(db_session):
    agent = make_agent(status=AgentStatus.RUNNING)
    await add(db_session, agent)
    await add(db_session, AgentRun(agent_id=agent.id, status=AgentRunStatus.RUNNING))

    await recover_interrupted_runs()

    async with db_session() as db:
        run = (await db.execute(select(AgentRun))).scalar_one()
        agent = await db.get(AgentConfig, agent.id)
    assert run.status == AgentRunStatus.FAILED
    assert agent.status == AgentStatus.IDLE


# --- Commands, Telegram, scheduling ----------------------------------------------------

@pytest.mark.asyncio
async def test_run_command_handles_ambiguous_names(monkeypatch, db_session):
    await add(db_session,
              make_agent(name="Scout (Ideas)", slug="scout-ideas"),
              make_agent(name="Scout (Gigs)", slug="scout-gigs"))
    started = []
    monkeypatch.setattr(commands, "start_background_run", lambda *a, **k: started.append(a) or True)

    result = await commands.cmd_run("scout", "telegram")
    assert "Several agents match" in result.text and started == []

    result = await commands.cmd_run("scout-gigs", "telegram")
    assert result.text.startswith("Started Scout (Gigs)") and len(started) == 1


def test_telegram_denies_everyone_without_allowlist(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "telegram_allowed_users", "")
    assert not is_allowed(12345)
    monkeypatch.setattr(settings, "telegram_allowed_users", "12345, 678")
    assert is_allowed(12345) and not is_allowed(999)


def test_cron_uses_configured_timezone(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "notification_timezone", "Asia/Kolkata")
    agent = make_agent(schedule_type="cron", schedule_value="0 9 * * *")
    # 09:00 in Kolkata is 03:30 UTC
    assert is_due(agent, datetime(2026, 10, 12, 3, 30, tzinfo=timezone.utc))
    assert not is_due(agent, datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc))


def test_update_task_accepts_id_alias():
    from app.orchestrator.schemas import validate_agent_output
    output, warnings = validate_agent_output({"summary": "s", "actions": [
        {"type": "update_task", "id": "abc", "status": "done"},
    ]})
    assert warnings == [] and output.actions[0].task_id == "abc"


@pytest.mark.asyncio
async def test_skill_loader_skips_templates(tmp_path, db_session):
    (tmp_path / "_template.yaml").write_text("name: my-agent\nprompt_template: x\n")
    (tmp_path / "real.yaml").write_text("name: Real\nprompt_template: x\n")
    await sync_skills_to_db(str(tmp_path))
    async with db_session() as db:
        slugs = [a.slug for a in (await db.execute(select(AgentConfig))).scalars().all()]
    assert slugs == ["real"]


def test_memory_and_recent_runs_reach_templates_that_dont_name_them():
    runner = AgentRunner()
    context = {"tasks": [], "memory": {"tone": "casual"}, "past_runs": [{"summary": "found 3 leads"}]}
    prompt = runner.render_prompt("Tasks: {{tasks}}\nPast: {{past_runs}}", context)
    assert prompt.count("found 3 leads") == 1  # named once in the template, not repeated
    assert "YOUR MEMORY" in prompt and "casual" in prompt
