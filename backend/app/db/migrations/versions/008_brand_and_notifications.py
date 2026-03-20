"""Add brand_profile table and notification priority columns.

Revision ID: 008
Revises: 007
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision = "008"
down_revision = "007"


def upgrade() -> None:
    # Brand profile table
    op.create_table(
        "brand_profile",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False, server_default=""),
        sa.Column("bio", sa.Text, server_default=""),
        sa.Column("tone", sa.String(255), server_default=""),
        sa.Column("social_handles", JSON, server_default="{}"),
        sa.Column("topics", JSON, server_default="[]"),
        sa.Column("talking_points", JSON, server_default="{}"),
        sa.Column("avoid", JSON, server_default="[]"),
        sa.Column("example_posts", JSON, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Notification priority enum + columns
    op.execute("CREATE TYPE notificationpriority AS ENUM ('urgent', 'routine')")
    op.add_column("notifications", sa.Column(
        "priority",
        sa.Enum("urgent", "routine", name="notificationpriority", create_type=False),
        server_default="routine",
        nullable=False,
    ))
    op.add_column("notifications", sa.Column(
        "telegram_sent",
        sa.Boolean,
        server_default="false",
        nullable=False,
    ))
    op.create_index("idx_notifications_priority_sent", "notifications", ["priority", "telegram_sent"])


def downgrade() -> None:
    op.drop_index("idx_notifications_priority_sent", table_name="notifications")
    op.drop_column("notifications", "telegram_sent")
    op.drop_column("notifications", "priority")
    op.execute("DROP TYPE notificationpriority")
    op.drop_table("brand_profile")
