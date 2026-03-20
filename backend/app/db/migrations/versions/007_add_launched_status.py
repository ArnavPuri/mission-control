"""Add launched status to project_status enum.

Revision ID: 007
Revises: 006
"""

from alembic import op


revision = "007"
down_revision = "006"


def upgrade() -> None:
    op.execute("ALTER TYPE projectstatus ADD VALUE IF NOT EXISTS 'launched'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; no-op
    pass
