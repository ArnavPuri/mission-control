"""Add agent workflows (DAGs) and task sort_order for drag-and-drop.

Revision ID: 006
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade():
    # Agent workflows table
    op.create_table(
        "agent_workflows",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("status", sa.Enum("draft", "active", "running", "completed", "failed", "paused", name="workflowstatus"), nullable=False, server_default="draft"),
        sa.Column("trigger_type", sa.String(50), server_default="manual"),
        sa.Column("trigger_value", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_workflows_status", "agent_workflows", ["status"])

    # Workflow steps table
    op.create_table(
        "workflow_steps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("workflow_id", UUID(as_uuid=True), sa.ForeignKey("agent_workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agent_configs.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("depends_on", ARRAY(sa.String), server_default="{}"),
        sa.Column("status", sa.Enum("pending", "running", "completed", "failed", "skipped", name="stepstatus"), nullable=False, server_default="pending"),
        sa.Column("config", sa.JSON, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_workflow_steps_workflow", "workflow_steps", ["workflow_id"])
    op.create_index("idx_workflow_steps_status", "workflow_steps", ["status"])

    # Add sort_order to tasks for drag-and-drop reordering
    op.add_column("tasks", sa.Column("sort_order", sa.Integer, server_default="0"))


def downgrade():
    op.drop_column("tasks", "sort_order")
    op.drop_table("workflow_steps")
    op.drop_table("agent_workflows")
    op.execute("DROP TYPE IF EXISTS workflowstatus")
    op.execute("DROP TYPE IF EXISTS stepstatus")
