"""Task comment threads.

Revision ID: 0002_task_comments
Revises: 0001_baseline
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_task_comments"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_comments",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("task_id", sa.Uuid, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author", sa.String(100), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("run_id", sa.Uuid, sa.ForeignKey("agent_runs.id", ondelete="SET NULL")),
        sa.Column("telegram_message_id", sa.BigInteger),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_task_comments_task", "task_comments", ["task_id", "created_at"])
    op.create_index("idx_task_comments_telegram", "task_comments", ["telegram_message_id"])


def downgrade() -> None:
    op.drop_table("task_comments")
