"""Add routines, routine_items, and routine_completions tables.

Routine builder: morning/evening routines as checklists with daily completion tracking.

Revision ID: 005
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "routines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("routine_type", sa.Enum("morning", "evening", "custom", name="routinetype"), nullable=False, server_default="custom"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("days", ARRAY(sa.String), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_routines_type", "routines", ["routine_type"])
    op.create_index("idx_routines_active", "routines", ["is_active"])

    op.create_table(
        "routine_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("routine_id", UUID(as_uuid=True), sa.ForeignKey("routines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("duration_minutes", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_routine_items_routine", "routine_items", ["routine_id"])

    op.create_table(
        "routine_completions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("routine_id", UUID(as_uuid=True), sa.ForeignKey("routines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completed_items", ARRAY(sa.String), server_default="{}"),
        sa.Column("total_items", sa.Integer, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_routine_completions_routine", "routine_completions", ["routine_id"])
    op.create_index("idx_routine_completions_date", "routine_completions", ["completed_at"])


def downgrade():
    op.drop_table("routine_completions")
    op.drop_table("routine_items")
    op.drop_table("routines")
    op.execute("DROP TYPE IF EXISTS routinetype")
