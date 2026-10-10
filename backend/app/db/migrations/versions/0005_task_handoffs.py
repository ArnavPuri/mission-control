"""Tasks handed from one agent to another link back to where they came from.

Revision ID: 0005_task_handoffs
Revises: 0004_task_reminders
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_task_handoffs"
down_revision = "0004_task_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.add_column(sa.Column("parent_task_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key("fk_tasks_parent_task_id", "tasks", ["parent_task_id"], ["id"], ondelete="SET NULL")
        batch.create_index("idx_tasks_parent", ["parent_task_id"])


def downgrade() -> None:
    with op.batch_alter_table("tasks") as batch:
        batch.drop_index("idx_tasks_parent")
        batch.drop_constraint("fk_tasks_parent_task_id", type_="foreignkey")
        batch.drop_column("parent_task_id")
