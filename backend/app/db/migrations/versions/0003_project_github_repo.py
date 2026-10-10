"""GitHub repo per project, for dev tasks.

Revision ID: 0003_project_github_repo
Revises: 0002_task_comments
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_project_github_repo"
down_revision = "0002_task_comments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("github_repo", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "github_repo")
