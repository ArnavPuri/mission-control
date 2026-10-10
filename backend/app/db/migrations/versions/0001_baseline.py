"""Baseline schema.

Replaces the old 001-010 chain, whose enum values (lowercase) never matched
what the app writes (enum names, uppercase). Databases created by the app's
old create_all() startup are converted to this schema by app.db.migrate and
then stamped at this revision.

Revision ID: 0001_baseline
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def _ts(name: str, **kw) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.Enum("ACTIVE", "PLANNING", "LAUNCHED", "PAUSED", "ARCHIVED", name="projectstatus"), nullable=False),
        sa.Column("color", sa.String(7)),
        sa.Column("url", sa.String(512)),
        sa.Column("metadata", sa.JSON),
        _ts("created_at"),
        _ts("updated_at"),
    )

    op.create_table(
        "agent_configs",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("status", sa.Enum("IDLE", "RUNNING", "ERROR", "DISABLED", name="agentstatus"), nullable=False),
        sa.Column("model", sa.String(100)),
        sa.Column("max_budget_usd", sa.Float),
        sa.Column("prompt_template", sa.Text, nullable=False),
        sa.Column("tools", sa.JSON),
        sa.Column("schedule_type", sa.String(20)),
        sa.Column("schedule_value", sa.String(100)),
        sa.Column("data_reads", sa.JSON),
        sa.Column("data_writes", sa.JSON),
        sa.Column("project_id", sa.Uuid, sa.ForeignKey("projects.id")),
        sa.Column("config", sa.JSON),
        sa.Column("skill_file", sa.String(255)),
        _ts("last_run_at"),
        _ts("created_at"),
        _ts("updated_at"),
    )

    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("url", sa.String(2048)),
        sa.Column("status", sa.Enum("TODO", "IN_PROGRESS", "BLOCKED", "DONE", name="taskstatus"), nullable=False),
        sa.Column("priority", sa.Enum("CRITICAL", "HIGH", "MEDIUM", "LOW", name="taskpriority"), nullable=False),
        sa.Column("project_id", sa.Uuid, sa.ForeignKey("projects.id")),
        sa.Column("assigned_agent_id", sa.Uuid, sa.ForeignKey("agent_configs.id")),
        sa.Column("source", sa.String(50)),
        sa.Column("tags", sa.JSON),
        _ts("due_date"),
        sa.Column("sort_order", sa.Integer),
        _ts("completed_at"),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("idx_tasks_status", "tasks", ["status"])
    op.create_index("idx_tasks_priority", "tasks", ["priority"])
    op.create_index("idx_tasks_project", "tasks", ["project_id"])

    op.create_table(
        "notes",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tags", sa.JSON),
        sa.Column("is_pinned", sa.Boolean),
        sa.Column("project_id", sa.Uuid, sa.ForeignKey("projects.id")),
        sa.Column("source", sa.String(50)),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("idx_notes_project", "notes", ["project_id"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("agent_id", sa.Uuid, sa.ForeignKey("agent_configs.id"), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", name="agentrunstatus"), nullable=False),
        sa.Column("trigger", sa.String(50)),
        sa.Column("input_data", sa.JSON),
        sa.Column("output_data", sa.JSON),
        sa.Column("error", sa.Text),
        sa.Column("tokens_used", sa.Integer),
        sa.Column("cost_usd", sa.Float),
        sa.Column("transcript", sa.JSON),
        _ts("started_at"),
        _ts("completed_at"),
    )
    op.create_index("idx_agent_runs_agent", "agent_runs", ["agent_id"])
    op.create_index("idx_agent_runs_status", "agent_runs", ["status"])

    op.create_table(
        "event_log",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Uuid),
        sa.Column("source", sa.String(50)),
        sa.Column("data", sa.JSON),
        _ts("created_at"),
    )
    op.create_index("idx_events_type", "event_log", ["event_type"])
    op.create_index("idx_events_created", "event_log", ["created_at"])

    op.create_table(
        "agent_approvals",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("run_id", sa.Uuid, sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("agent_id", sa.Uuid, sa.ForeignKey("agent_configs.id"), nullable=False),
        sa.Column("status", sa.Enum("PENDING", "APPROVED", "REJECTED", "EXPIRED", name="approvalstatus"), nullable=False),
        sa.Column("actions", sa.JSON, nullable=False),
        sa.Column("summary", sa.Text),
        _ts("reviewed_at"),
        _ts("expires_at"),
        _ts("created_at"),
    )
    op.create_index("idx_approvals_status", "agent_approvals", ["status"])
    op.create_index("idx_approvals_agent", "agent_approvals", ["agent_id"])

    op.create_table(
        "agent_memories",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("agent_id", sa.Uuid, sa.ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("memory_type", sa.String(50)),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("idx_agent_memory_agent", "agent_memories", ["agent_id"])
    op.create_index("idx_agent_memory_key", "agent_memories", ["agent_id", "key"], unique=True)

    op.create_table(
        "brand_profile",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("bio", sa.Text),
        sa.Column("tone", sa.String(255)),
        sa.Column("social_handles", sa.JSON),
        sa.Column("topics", sa.JSON),
        sa.Column("talking_points", sa.JSON),
        sa.Column("avoid", sa.JSON),
        sa.Column("example_posts", sa.JSON),
        sa.Column("notification_prefs", sa.JSON),
        _ts("created_at"),
        _ts("updated_at"),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text),
        sa.Column("category", sa.String(50)),
        sa.Column("source", sa.String(100)),
        sa.Column("is_read", sa.Boolean),
        sa.Column("action_url", sa.String(500)),
        sa.Column("data", sa.JSON),
        sa.Column("priority", sa.Enum("urgent", "routine", name="notificationpriority"), nullable=False),
        sa.Column("telegram_sent", sa.Boolean),
        _ts("created_at"),
    )
    op.create_index("idx_notifications_read", "notifications", ["is_read"])
    op.create_index("idx_notifications_created", "notifications", ["created_at"])

    op.create_table(
        "marketing_content",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("status", sa.Enum("DRAFT", "APPROVED", "POSTED", "ARCHIVED", name="contentstatus"), nullable=False),
        sa.Column("source", sa.String(50)),
        sa.Column("task_id", sa.Uuid, sa.ForeignKey("tasks.id", ondelete="SET NULL")),
        sa.Column("project_id", sa.Uuid, sa.ForeignKey("projects.id")),
        sa.Column("agent_id", sa.Uuid, sa.ForeignKey("agent_configs.id")),
        sa.Column("posted_url", sa.String(2048)),
        _ts("posted_at"),
        sa.Column("notes", sa.Text),
        sa.Column("tags", sa.JSON),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("idx_mkt_content_status", "marketing_content", ["status"])
    op.create_index("idx_mkt_content_channel", "marketing_content", ["channel"])
    op.create_index("idx_mkt_content_project", "marketing_content", ["project_id"])
    op.create_index("idx_mkt_content_created", "marketing_content", ["created_at"])

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("messages", sa.JSON),
        _ts("last_active"),
        _ts("created_at"),
    )
    op.create_index("idx_chat_sessions_user", "chat_sessions", ["user_id", "platform"], unique=True)
    op.create_index("idx_chat_sessions_active", "chat_sessions", ["last_active"])


def downgrade() -> None:
    for table in (
        "chat_sessions", "marketing_content", "notifications", "brand_profile",
        "agent_memories", "agent_approvals", "event_log", "agent_runs",
        "notes", "tasks", "agent_configs", "projects",
    ):
        op.drop_table(table)
    for enum in (
        "projectstatus", "agentstatus", "taskstatus", "taskpriority", "agentrunstatus",
        "approvalstatus", "notificationpriority", "contentstatus",
    ):
        sa.Enum(name=enum).drop(op.get_bind(), checkfirst=True)
