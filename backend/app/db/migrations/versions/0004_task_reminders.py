"""Reminders and recurrence on tasks.

Revision ID: 0004_task_reminders
Revises: 0003_project_github_repo
"""

from alembic import op
import sqlalchemy as sa

revision = "0004_task_reminders"
down_revision = "0003_project_github_repo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("remind_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("reminded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tasks", sa.Column("recurrence", sa.String(20), nullable=True))
    op.create_index("idx_tasks_remind_at", "tasks", ["remind_at"])


def downgrade() -> None:
    op.drop_index("idx_tasks_remind_at", table_name="tasks")
    op.drop_column("tasks", "recurrence")
    op.drop_column("tasks", "reminded_at")
    op.drop_column("tasks", "remind_at")
