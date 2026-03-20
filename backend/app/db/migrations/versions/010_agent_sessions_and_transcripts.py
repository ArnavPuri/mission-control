"""Add session persistence to agent_configs and transcript to agent_runs.

Revision ID: 010
Revises: 009
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"


def upgrade() -> None:
    op.add_column("agent_configs", sa.Column("session_id", sa.String(255), nullable=True))
    op.add_column("agent_configs", sa.Column("last_message_uuid", sa.String(255), nullable=True))
    op.add_column("agent_configs", sa.Column("session_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agent_configs", sa.Column("session_window_days", sa.Integer, server_default="7", nullable=True))
    op.add_column("agent_runs", sa.Column("transcript", sa.JSON, nullable=True))


def downgrade() -> None:
    op.drop_column("agent_runs", "transcript")
    op.drop_column("agent_configs", "session_window_days")
    op.drop_column("agent_configs", "session_expires_at")
    op.drop_column("agent_configs", "last_message_uuid")
    op.drop_column("agent_configs", "session_id")
