"""Marketing OS tables - signals and content.

Revision ID: 002_marketing_os
Revises: 001_initial
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision: str = "002_marketing_os"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Marketing Signals ---
    op.create_table(
        "marketing_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("relevance_score", sa.Float, nullable=True),
        sa.Column("signal_type", sa.String(50), nullable=True),
        sa.Column("status", sa.Enum("new", "reviewed", "acted_on", "dismissed", name="signalstatus"), nullable=False, server_default="new"),
        sa.Column("channel_metadata", sa.JSON, server_default="{}"),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agent_configs.id"), nullable=True),
        sa.Column("tags", ARRAY(sa.String), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_mkt_signals_status", "marketing_signals", ["status"])
    op.create_index("idx_mkt_signals_source_type", "marketing_signals", ["source_type"])
    op.create_index("idx_mkt_signals_signal_type", "marketing_signals", ["signal_type"])
    op.create_index("idx_mkt_signals_project", "marketing_signals", ["project_id"])
    op.create_index("idx_mkt_signals_created", "marketing_signals", ["created_at"])

    # --- Marketing Content ---
    op.create_table(
        "marketing_content",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("status", sa.Enum("draft", "approved", "posted", "archived", name="contentstatus"), nullable=False, server_default="draft"),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column("signal_id", UUID(as_uuid=True), sa.ForeignKey("marketing_signals.id"), nullable=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agent_configs.id"), nullable=True),
        sa.Column("posted_url", sa.String(2048), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("tags", ARRAY(sa.String), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_mkt_content_status", "marketing_content", ["status"])
    op.create_index("idx_mkt_content_channel", "marketing_content", ["channel"])
    op.create_index("idx_mkt_content_project", "marketing_content", ["project_id"])
    op.create_index("idx_mkt_content_signal", "marketing_content", ["signal_id"])
    op.create_index("idx_mkt_content_created", "marketing_content", ["created_at"])


def downgrade() -> None:
    op.drop_table("marketing_content")
    op.drop_table("marketing_signals")

    # Drop enums
    for enum_name in ["contentstatus", "signalstatus"]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
