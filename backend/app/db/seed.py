"""
Seed data for new Mission Control installations.

Creates example projects, tasks, ideas, habits, goals, and an agent
so new users have something to explore immediately.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import async_session
from app.db.models import (
    Project, Task, Idea, ReadingItem, Habit, Goal, KeyResult,
    JournalEntry, Note, TaskStatus, GoalStatus, MoodLevel,
)


SEED_TAG = "seed-data"


async def seed_data_if_empty(db: AsyncSession | None = None):
    """Seed the database with example data if no projects exist."""
    close_session = False
    if db is None:
        db = async_session()
        close_session = True

    try:
        # Only seed if database is empty
        count = await db.scalar(select(func.count(Project.id)))
        if count and count > 0:
            return False

        now = datetime.now(timezone.utc)

        # ── Projects ──
        personal = Project(
            id=uuid.uuid4(), name="Personal Growth", description="Self-improvement goals and learning",
            status="active", color="#2563eb",
        )
        side_project = Project(
            id=uuid.uuid4(), name="Side Project", description="Weekend app idea — habit tracker",
            status="active", color="#059669",
        )
        learning = Project(
            id=uuid.uuid4(), name="Learning", description="Books, courses, and skill development",
            status="planning", color="#d97706",
        )
        db.add_all([personal, side_project, learning])

        # ── Tasks ──
        tasks = [
            Task(text="Set up Mission Control agents", status=TaskStatus.DONE, priority="high", project_id=side_project.id, tags=[SEED_TAG, "setup"]),
            Task(text="Review weekly goals every Sunday", status=TaskStatus.TODO, priority="medium", project_id=personal.id, tags=[SEED_TAG, "recurring"]),
            Task(text="Read 'Designing Data-Intensive Applications'", status=TaskStatus.IN_PROGRESS, priority="medium", project_id=learning.id, tags=[SEED_TAG, "reading"]),
            Task(text="Write project README", status=TaskStatus.TODO, priority="high", project_id=side_project.id, tags=[SEED_TAG, "docs"]),
            Task(text="Set up CI/CD pipeline", status=TaskStatus.TODO, priority="medium", project_id=side_project.id, tags=[SEED_TAG, "devops"]),
            Task(text="Plan Q2 objectives", status=TaskStatus.TODO, priority="critical", project_id=personal.id, tags=[SEED_TAG, "planning"]),
            Task(text="Research vector databases", status=TaskStatus.DONE, priority="low", project_id=learning.id, tags=[SEED_TAG, "research"]),
        ]
        db.add_all(tasks)

        # ── Ideas ──
        ideas = [
            Idea(text="Build a personal knowledge graph from journal entries", tags=[SEED_TAG, "ai", "knowledge"], source="manual"),
            Idea(text="Agent that summarizes Hacker News top stories daily", tags=[SEED_TAG, "agent", "news"], source="manual"),
            Idea(text="Voice memo transcription via Telegram voice messages", tags=[SEED_TAG, "telegram", "voice"], source="manual"),
            Idea(text="Weekly email digest of all agent activity", tags=[SEED_TAG, "email", "digest"], source="manual"),
        ]
        db.add_all(ideas)

        # ── Reading List ──
        reading = [
            ReadingItem(title="The Pragmatic Programmer", url="https://pragprog.com/titles/tpp20/", tags=[SEED_TAG, "book"], source="manual"),
            ReadingItem(title="Building AI Agents with Claude", url="https://docs.anthropic.com", tags=[SEED_TAG, "ai", "docs"], source="manual"),
            ReadingItem(title="PostgreSQL Performance Tips", tags=[SEED_TAG, "database"], source="manual"),
        ]
        db.add_all(reading)

        # ── Habits ──
        habits = [
            Habit(name="Morning exercise", description="30 min workout", frequency="daily", color="#059669", project_id=personal.id),
            Habit(name="Read 30 pages", description="Daily reading habit", frequency="daily", color="#2563eb", project_id=learning.id),
            Habit(name="Journal reflection", description="End-of-day review", frequency="daily", color="#d97706"),
            Habit(name="Code review", description="Review one PR or codebase", frequency="daily", color="#7c3aed", project_id=side_project.id),
        ]
        db.add_all(habits)

        # ── Goals ──
        fitness_goal = Goal(
            id=uuid.uuid4(), title="Run a half marathon", description="Train for and complete a half marathon",
            status=GoalStatus.ACTIVE, progress=0.3, project_id=personal.id, tags=[SEED_TAG, "fitness"],
            target_date=now + timedelta(days=120),
        )
        launch_goal = Goal(
            id=uuid.uuid4(), title="Launch side project MVP", description="Ship the first version to users",
            status=GoalStatus.ACTIVE, progress=0.5, project_id=side_project.id, tags=[SEED_TAG, "launch"],
            target_date=now + timedelta(days=60),
        )
        db.add_all([fitness_goal, launch_goal])

        # Key results
        db.add_all([
            KeyResult(goal_id=fitness_goal.id, title="Run 10K without stopping", target_value=10, current_value=6, unit="km"),
            KeyResult(goal_id=fitness_goal.id, title="Weekly training runs", target_value=4, current_value=3, unit="runs/week"),
            KeyResult(goal_id=launch_goal.id, title="Core features done", target_value=5, current_value=3, unit="features"),
            KeyResult(goal_id=launch_goal.id, title="Beta testers signed up", target_value=20, current_value=8, unit="users"),
        ])

        # ── Journal ──
        db.add(JournalEntry(
            content="Started using Mission Control today. Excited to see how AI agents can help organize my life. Set up the first few projects and configured some agents.",
            mood=MoodLevel.GREAT, energy=4,
            tags=[SEED_TAG], wins=["Set up Mission Control"], challenges=["Lots to configure"],
            gratitude=["Having tools that save time"],
        ))

        # ── Notes ──
        db.add_all([
            Note(title="Mission Control Quick Start", content="## Getting Started\n\n1. Add projects in the Projects page\n2. Create tasks and link them to projects\n3. Set up habits for daily tracking\n4. Configure agents to automate workflows\n5. Use keyboard shortcuts (press ? for help)\n\n## Keyboard Shortcuts\n\n- `g d` — Go to Dashboard\n- `g p` — Go to Projects\n- `n t` — New task\n- `Cmd+K` — Command palette", is_pinned=True, tags=[SEED_TAG, "guide"]),
            Note(title="Agent Ideas", content="Agents to build:\n\n- Daily standup summarizer\n- Reading list auto-tagger\n- Weekly review compiler\n- Deadline reminder", tags=[SEED_TAG, "agents"]),
        ])

        await db.commit()
        return True

    finally:
        if close_session:
            await db.close()


async def main():
    """Run seed data as standalone script."""
    from app.db.session import init_db
    await init_db()
    result = await seed_data_if_empty()
    if result:
        print("✓ Seed data created successfully")
    else:
        print("Database already has data, skipping seed")


if __name__ == "__main__":
    asyncio.run(main())
