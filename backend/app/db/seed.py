"""
Seed data for new Mission Control installations.

Creates example projects, tasks, and notes so new users have something to explore.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import async_session
from app.db.models import Project, Task, Note, TaskStatus


SEED_TAG = "seed-data"


async def seed_data_if_empty(db: AsyncSession | None = None):
    """Seed the database with example data if no projects exist."""
    close_session = False
    if db is None:
        db = async_session()
        close_session = True

    try:
        count = await db.scalar(select(func.count(Project.id)))
        if count and count > 0:
            return

        # Create a sample project
        project = Project(
            name="Mission Control",
            description="The command center itself — meta!",
            status="active",
            color="#00ffc8",
        )
        db.add(project)
        await db.flush()

        # Sample tasks
        tasks = [
            Task(text="Set up Telegram bot token", priority="high", project_id=project.id, tags=[SEED_TAG]),
            Task(text="Configure brand profile", priority="medium", project_id=project.id, tags=[SEED_TAG]),
            Task(text="Create first agent skill YAML", priority="medium", project_id=project.id, tags=[SEED_TAG]),
            Task(text="Test morning briefing", priority="low", project_id=project.id, tags=[SEED_TAG]),
        ]
        for t in tasks:
            db.add(t)

        # Sample note
        note = Note(
            title="Getting Started",
            content="Welcome to Mission Control! Start by:\n\n1. Setting up your Telegram bot\n2. Configuring your brand profile\n3. Creating agent skills in `backend/skills/`\n4. Talking to your bot!",
            tags=[SEED_TAG],
            is_pinned=True,
        )
        db.add(note)

        await db.commit()
    finally:
        if close_session:
            await db.close()
