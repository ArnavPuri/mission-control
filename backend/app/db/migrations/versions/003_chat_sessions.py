"""Add chat_sessions table for persistent bot conversations.

Revision ID: 003_chat_sessions
Revises: 002_marketing_os
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "003_chat_sessions"
down_revision: Union[str, None] = "002_marketing_os"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False, server_default="telegram"),
        sa.Column("messages", sa.JSON, nullable=True),
        sa.Column("last_active", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_chat_sessions_user", "chat_sessions", ["user_id", "platform"], unique=True)
    op.create_index("idx_chat_sessions_active", "chat_sessions", ["last_active"])


def downgrade() -> None:
    op.drop_index("idx_chat_sessions_active")
    op.drop_index("idx_chat_sessions_user")
    op.drop_table("chat_sessions")
