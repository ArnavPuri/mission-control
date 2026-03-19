"""Make agent_memories.agent_id nullable for shared scratchpad support.

Shared scratchpad entries have agent_id=NULL and are visible to all agents,
enabling inter-agent collaboration without direct communication.

Revision ID: 004
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "agent_memories",
        "agent_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade():
    # Delete any shared entries (agent_id=NULL) before making column non-nullable
    op.execute("DELETE FROM agent_memories WHERE agent_id IS NULL")
    op.alter_column(
        "agent_memories",
        "agent_id",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )
