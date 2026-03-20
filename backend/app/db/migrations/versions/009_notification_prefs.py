"""Add notification_prefs to brand_profile.

Revision ID: 009
Revises: 008
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

revision = "009"
down_revision = "008"


def upgrade() -> None:
    op.add_column("brand_profile", sa.Column(
        "notification_prefs",
        JSON,
        server_default='{"agent_completions": true, "agent_failures": true, "signal_summary": true, "content_drafts": true}',
        nullable=True,
    ))


def downgrade() -> None:
    op.drop_column("brand_profile", "notification_prefs")
