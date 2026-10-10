"""Reminders, due dates and recurring tasks."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.config import settings
from app.db.models import Task, TaskComment, TaskStatus
from app.integrations import commands
from app.orchestrator import reminders, review
from app.timeutil import aware, describe, end_of_day, next_occurrence, parse_when, split_reminder

NY = ZoneInfo("America/New_York")
# Saturday afternoon
NOW = datetime(2026, 10, 10, 14, 30, tzinfo=NY)


@pytest.fixture(autouse=True)
def new_york(monkeypatch):
    monkeypatch.setattr(settings, "notification_timezone", "America/New_York")


@pytest.fixture
def telegram(monkeypatch):
    sent = []

    async def fake_send(text, reply_markup=None):
        sent.append((text, reply_markup))
        return 500 + len(sent)

    monkeypatch.setattr(settings, "telegram_bot_token", "t")
    monkeypatch.setattr(settings, "telegram_notification_chat_id", "1")
    monkeypatch.setattr(reminders, "send_telegram", fake_send)
    return sent


def at(day: int, hour: int, minute: int = 0, month: int = 10) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=NY)


# --- Reading times ----------------------------------------------------------

@pytest.mark.parametrize("text, when, what, recurrence", [
    ("tomorrow at 9 call Sam", at(11, 9), "Call Sam", None),
    ("me tomorrow to call Sam", at(11, 9), "Call Sam", None),
    ("call Sam at 5", at(10, 17), "Call Sam", None),
    ("in 2h check the deploy", at(10, 16, 30), "Check the deploy", None),
    ("30m stretch", at(10, 15), "Stretch", None),
    ("friday 10am ship the release", at(16, 10), "Ship the release", None),
    ("9am monday standup", at(12, 9), "Standup", None),
    ("tonight at 9 take out the trash", at(10, 21), "Take out the trash", None),
    ("oct 12 dentist", at(12, 9), "Dentist", None),
    ("2026-12-01 file taxes", at(1, 9, month=12), "File taxes", None),
    ("at noon lunch with Ana", at(11, 12), "Lunch with Ana", None),
    ("call mom every sunday at 6", at(11, 18), "Call mom", "weekly"),
    ("every weekday 9:30 standup", at(12, 9, 30), "Standup", "weekdays"),
    ("daily drink water", at(11, 9), "Drink water", "daily"),
    ("pay rent monthly on nov 1", at(1, 9, month=11), "Pay rent", "monthly"),
])
def test_split_reminder(text, when, what, recurrence):
    assert split_reminder(text, NOW) == (when, what, recurrence)


@pytest.mark.parametrize("text", ["buy 2 apples", "call Sam", ""])
def test_no_time_no_reminder(text):
    assert split_reminder(text, NOW)[0] is None


def test_a_time_already_past_today_means_tomorrow():
    assert parse_when("9am", NOW) == at(11, 9)
    assert parse_when("6pm", NOW) == at(10, 18)


def test_this_weekday_already_past_means_next_week():
    assert parse_when("saturday 9am", NOW) == at(17, 9)


# --- Recurrence -------------------------------------------------------------

def test_next_occurrence_keeps_local_time_across_dst():
    # Clocks go back on Nov 1 in New York: 9am stays 9am
    assert next_occurrence(at(31, 9), "daily") == datetime(2026, 11, 1, 9, tzinfo=NY)
    assert next_occurrence(at(31, 9), "daily").utcoffset() == timedelta(hours=-5)


def test_next_occurrence_weekdays_skips_weekend():
    assert next_occurrence(at(9, 9), "weekdays") == at(12, 9)  # Fri → Mon


def test_next_occurrence_monthly_clamps_short_months():
    assert next_occurrence(datetime(2026, 1, 31, 9, tzinfo=NY), "monthly") == datetime(2026, 2, 28, 9, tzinfo=NY)


def test_describe():
    assert describe(at(10, 9), NOW) == "today 9:00"
    assert describe(at(11, 18, 30), NOW) == "tomorrow 18:30"
    assert describe(end_of_day(at(12, 9)), NOW) == "Mon Oct 12"


@pytest.mark.asyncio
async def test_completing_a_recurring_task_creates_the_next_one(db_session):
    due = end_of_day(datetime.now(timezone.utc))
    async with db_session() as db:
        task = Task(text="Weekly review", recurrence="weekly", due_date=due, remind_at=due - timedelta(hours=8))
        db.add(task)
        await db.flush()
        nxt = await reminders.complete_task(db, task)
        await db.commit()

        assert task.status == TaskStatus.DONE and task.recurrence is None
        assert nxt.recurrence == "weekly" and nxt.status == TaskStatus.TODO
        assert nxt.due_date == next_occurrence(due, "weekly")
        # The reminder keeps its offset from the due date
        assert nxt.due_date - nxt.remind_at == timedelta(hours=8)

        # Completing the old one again doesn't fork the series
        task.status = TaskStatus.TODO
        assert await reminders.complete_task(db, task) is None


@pytest.mark.asyncio
async def test_a_late_completion_skips_missed_occurrences(db_session):
    async with db_session() as db:
        task = Task(text="Water plants", recurrence="daily", due_date=datetime.now(timezone.utc) - timedelta(days=5))
        db.add(task)
        await db.flush()
        nxt = await reminders.complete_task(db, task)
        assert nxt.due_date > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_local_times_are_stored_as_utc(db_session):
    async with db_session() as db:
        task = Task(text="Call Sam", remind_at=at(11, 9))
        db.add(task)
        await db.commit()
        task_id = task.id
    async with db_session() as db:
        stored = (await db.execute(select(Task.remind_at).where(Task.id == task_id))).scalar_one()
        assert aware(stored) == at(11, 9)


# --- Sending reminders --------------------------------------------------------

@pytest.mark.asyncio
async def test_due_reminders_are_sent_once_with_buttons(db_session, telegram):
    now = datetime.now(timezone.utc)
    async with db_session() as db:
        db.add_all([
            Task(text="Call Sam", remind_at=now - timedelta(minutes=1)),
            Task(text="Later", remind_at=now + timedelta(hours=1)),
            Task(text="Finished", remind_at=now - timedelta(minutes=1), status=TaskStatus.DONE),
        ])
        await db.commit()
        assert await reminders.send_due_reminders(db) == 1
        await db.commit()
        assert await reminders.send_due_reminders(db) == 0

    assert len(telegram) == 1
    text, markup = telegram[0]
    assert "Call Sam" in text
    verbs = [b["callback_data"].split(":")[1] for b in markup["inline_keyboard"][0]]
    assert verbs == ["done", "1h", "tmr"]
    # Replying to the reminder on Telegram lands in the task's thread
    async with db_session() as db:
        comment = (await db.execute(select(TaskComment))).scalar_one()
        assert comment.telegram_message_id == 501


@pytest.mark.asyncio
async def test_reminders_wait_when_telegram_is_not_configured(db_session):
    async with db_session() as db:
        db.add(Task(text="Call Sam", remind_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
        await db.commit()
        assert await reminders.send_due_reminders(db) == 0
        assert len(await reminders.due_reminders(db, datetime.now(timezone.utc))) == 1


@pytest.mark.asyncio
async def test_snooze_and_done_buttons(db_session, telegram):
    async with db_session() as db:
        task = Task(text="Call Sam", remind_at=datetime.now(timezone.utc) - timedelta(minutes=1))
        db.add(task)
        await db.commit()
        await reminders.send_due_reminders(db)
        await db.commit()

        outcome = await review.handle_callback(db, f"rem:1h:{task.id}")
        assert outcome.startswith("⏰ Snoozed until")
        await db.commit()
        # Not due yet, but due again in an hour
        assert await reminders.due_reminders(db, datetime.now(timezone.utc)) == []
        assert len(await reminders.due_reminders(db, datetime.now(timezone.utc) + timedelta(hours=1, minutes=1))) == 1

        assert await review.handle_callback(db, f"rem:done:{task.id}") == "✅ Done"
        assert task.status == TaskStatus.DONE
        assert await review.handle_callback(db, f"rem:done:{task.id}") == "Already done."


@pytest.mark.asyncio
async def test_done_button_on_a_recurring_task_says_when_next(db_session):
    async with db_session() as db:
        now = datetime.now(timezone.utc)
        task = Task(text="Standup", recurrence="daily", remind_at=now - timedelta(minutes=1))
        db.add(task)
        await db.commit()
        outcome = await review.handle_callback(db, f"rem:done:{task.id}")
        assert outcome.startswith("✅ Done. Next: ")
        nxt = (await db.execute(select(Task).where(Task.status == TaskStatus.TODO))).scalar_one()
        assert aware(nxt.remind_at) > now


# --- Commands -----------------------------------------------------------------

@pytest.mark.asyncio
async def test_remind_command_creates_a_task_with_a_reminder(db_session):
    result = await commands.cmd_remind("tomorrow at 9 call Sam", "telegram")
    assert result.text.startswith("⏰ I'll remind you tomorrow 9:00: Call Sam")
    async with db_session() as db:
        task = (await db.execute(select(Task))).scalar_one()
        assert task.text == "Call Sam"
        assert task.remind_at is not None and task.due_date is not None

    listing = await commands.cmd_remind("", "telegram")
    assert "Call Sam" in listing.text


@pytest.mark.asyncio
async def test_remind_command_without_a_time_explains_usage():
    result = await commands.cmd_remind("call Sam", "telegram")
    assert result.text.startswith("Usage: /remind")


@pytest.mark.asyncio
async def test_today_lists_overdue_and_due_today(db_session):
    now = datetime.now(timezone.utc)
    async with db_session() as db:
        db.add_all([
            Task(text="Overdue thing", due_date=now - timedelta(days=2)),
            Task(text="Due today thing", due_date=end_of_day(now)),
            Task(text="Next week thing", due_date=now + timedelta(days=7)),
        ])
        await db.commit()
    text = (await commands.cmd_today("telegram")).text
    assert "Overdue thing" in text and "Due today thing" in text
    assert "Next week thing" not in text


# --- API ----------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_sets_reminders_and_completes_recurring_tasks(client):
    due = end_of_day(datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    created = (await client.post("/api/tasks", json={"text": "Invoice", "due_date": due, "recurrence": "monthly"})).json()
    task = (await client.get(f"/api/tasks/{created['id']}")).json()
    assert task["recurrence"] == "monthly" and task["due_date"]

    bad = await client.patch(f"/api/tasks/{created['id']}", json={"recurrence": "hourly"})
    assert bad.status_code == 422

    remind = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    await client.patch(f"/api/tasks/{created['id']}", json={"remind_at": remind})
    assert (await client.get(f"/api/tasks/{created['id']}")).json()["remind_at"]

    done = (await client.patch(f"/api/tasks/{created['id']}", json={"status": "done"})).json()
    assert done["next_id"]
    nxt = (await client.get(f"/api/tasks/{done['next_id']}")).json()
    assert nxt["recurrence"] == "monthly" and nxt["status"] == "todo"

    # Reopening clears completed_at; completing again doesn't create another
    await client.patch(f"/api/tasks/{created['id']}", json={"status": "todo"})
    again = (await client.patch(f"/api/tasks/{created['id']}", json={"status": "done"})).json()
    assert again["next_id"] is None


# --- Chat ---------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chat_actions_set_reminders_and_complete_tasks(db_session):
    from app.integrations.chat import execute_tool_call

    async with db_session() as db:
        out = await execute_tool_call("create_task", {
            "text": "Call Sam", "priority": "high", "remind_at": "2026-12-01T09:00", "recurrence": "weekly",
        }, db)
        assert "reminder" in out
        task = (await db.execute(select(Task))).scalar_one()
        assert aware(task.remind_at) == datetime(2026, 12, 1, 9, tzinfo=NY)
        assert task.due_date is not None and task.recurrence == "weekly"

        out = await execute_tool_call("update_task", {"task_text": "call sam", "due": "2026-12-02"}, db)
        assert "due→" in out
        assert aware(task.due_date) == datetime(2026, 12, 2, 23, 59, tzinfo=NY)

        out = await execute_tool_call("update_task", {"task_text": "call sam", "status": "done"}, db)
        assert "status→done" in out
        open_tasks = (await db.execute(select(Task).where(Task.status != TaskStatus.DONE))).scalars().all()
        assert [t.text for t in open_tasks] == ["Call Sam"]  # the next one in the series
