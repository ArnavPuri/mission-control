"""Initial schema - all Mission Control tables.

Revision ID: 001_initial
Revises: None
Create Date: 2026-03-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Projects ---
    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("status", sa.Enum("active", "planning", "paused", "archived", name="projectstatus"), nullable=False, server_default="planning"),
        sa.Column("color", sa.String(7), server_default="#00ffc8"),
        sa.Column("url", sa.String(512), nullable=True),
        sa.Column("metadata", sa.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Agent Configs ---
    op.create_table(
        "agent_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("status", sa.Enum("idle", "running", "error", "disabled", name="agentstatus"), nullable=False, server_default="idle"),
        sa.Column("model", sa.String(100), server_default="claude-haiku-4-5"),
        sa.Column("max_budget_usd", sa.Float, server_default="0.1"),
        sa.Column("prompt_template", sa.Text, nullable=False),
        sa.Column("tools", ARRAY(sa.String), server_default="{}"),
        sa.Column("schedule_type", sa.String(20), nullable=True),
        sa.Column("schedule_value", sa.String(100), nullable=True),
        sa.Column("data_reads", ARRAY(sa.String), server_default="{}"),
        sa.Column("data_writes", ARRAY(sa.String), server_default="{}"),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("config", sa.JSON, server_default="{}"),
        sa.Column("skill_file", sa.String(255), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Tasks ---
    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("status", sa.Enum("todo", "in_progress", "blocked", "done", name="taskstatus"), nullable=False, server_default="todo"),
        sa.Column("priority", sa.Enum("critical", "high", "medium", "low", name="taskpriority"), nullable=False, server_default="medium"),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("assigned_agent_id", UUID(as_uuid=True), sa.ForeignKey("agent_configs.id"), nullable=True),
        sa.Column("source", sa.String(50), server_default="manual"),
        sa.Column("tags", ARRAY(sa.String), server_default="{}"),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_tasks_status", "tasks", ["status"])
    op.create_index("idx_tasks_priority", "tasks", ["priority"])
    op.create_index("idx_tasks_project", "tasks", ["project_id"])

    # --- Ideas ---
    op.create_table(
        "ideas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("tags", ARRAY(sa.String), server_default="{}"),
        sa.Column("source", sa.String(50), server_default="manual"),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("validation_notes", sa.Text, nullable=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Reading List ---
    op.create_table(
        "reading_list",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("source", sa.String(50), server_default="manual"),
        sa.Column("tags", ARRAY(sa.String), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )

    # --- Agent Runs ---
    op.create_table(
        "agent_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agent_configs.id"), nullable=False),
        sa.Column("status", sa.Enum("pending", "running", "completed", "failed", "cancelled", name="agentrunstatus"), nullable=False, server_default="pending"),
        sa.Column("trigger", sa.String(50), server_default="manual"),
        sa.Column("input_data", sa.JSON, server_default="{}"),
        sa.Column("output_data", sa.JSON, server_default="{}"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("tokens_used", sa.Integer, server_default="0"),
        sa.Column("cost_usd", sa.Float, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_agent_runs_agent", "agent_runs", ["agent_id"])
    op.create_index("idx_agent_runs_status", "agent_runs", ["status"])

    # --- Event Log ---
    op.create_table(
        "event_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(50), server_default="system"),
        sa.Column("data", sa.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_events_type", "event_log", ["event_type"])
    op.create_index("idx_events_created", "event_log", ["created_at"])

    # --- Habits ---
    op.create_table(
        "habits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("frequency", sa.Enum("daily", "weekly", "custom", name="habitfrequency"), nullable=False, server_default="daily"),
        sa.Column("target_days", ARRAY(sa.String), server_default="{}"),
        sa.Column("current_streak", sa.Integer, server_default="0"),
        sa.Column("best_streak", sa.Integer, server_default="0"),
        sa.Column("total_completions", sa.Integer, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("color", sa.String(7), server_default="#00ffc8"),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Habit Completions ---
    op.create_table(
        "habit_completions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("habit_id", UUID(as_uuid=True), sa.ForeignKey("habits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_index("idx_habit_completions_habit", "habit_completions", ["habit_id"])
    op.create_index("idx_habit_completions_date", "habit_completions", ["completed_at"])

    # --- Goals ---
    op.create_table(
        "goals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("status", sa.Enum("active", "completed", "abandoned", name="goalstatus"), nullable=False, server_default="active"),
        sa.Column("target_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress", sa.Float, server_default="0"),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("tags", ARRAY(sa.String), server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Key Results ---
    op.create_table(
        "key_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("goal_id", UUID(as_uuid=True), sa.ForeignKey("goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("target_value", sa.Float, nullable=False),
        sa.Column("current_value", sa.Float, server_default="0"),
        sa.Column("unit", sa.String(50), server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- Journal Entries ---
    op.create_table(
        "journal_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("mood", sa.Enum("great", "good", "okay", "low", "bad", name="moodlevel"), nullable=True),
        sa.Column("energy", sa.Integer, nullable=True),
        sa.Column("tags", ARRAY(sa.String), server_default="{}"),
        sa.Column("wins", ARRAY(sa.String), server_default="{}"),
        sa.Column("challenges", ARRAY(sa.String), server_default="{}"),
        sa.Column("gratitude", ARRAY(sa.String), server_default="{}"),
        sa.Column("source", sa.String(50), server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_journal_created", "journal_entries", ["created_at"])

    # --- Agent Approvals ---
    op.create_table(
        "agent_approvals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("agent_runs.id"), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agent_configs.id"), nullable=False),
        sa.Column("status", sa.Enum("pending", "approved", "rejected", "expired", name="approvalstatus"), nullable=False, server_default="pending"),
        sa.Column("actions", sa.JSON, nullable=False),
        sa.Column("summary", sa.Text, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_approvals_status", "agent_approvals", ["status"])
    op.create_index("idx_approvals_agent", "agent_approvals", ["agent_id"])

    # --- Agent Memories ---
    op.create_table(
        "agent_memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("memory_type", sa.String(50), server_default="general"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_agent_memory_agent", "agent_memories", ["agent_id"])
    op.create_index("idx_agent_memory_key", "agent_memories", ["agent_id", "key"], unique=True)

    # --- Agent Triggers ---
    op.create_table(
        "agent_triggers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("event", sa.String(50), nullable=False),
        sa.Column("condition", sa.JSON, nullable=True),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_agent_triggers_agent", "agent_triggers", ["agent_id"])
    op.create_index("idx_agent_triggers_active", "agent_triggers", ["is_active"])

    # --- Notes ---
    op.create_table(
        "notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("tags", ARRAY(sa.String), server_default="{}"),
        sa.Column("is_pinned", sa.Boolean, server_default="false"),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("source", sa.String(50), server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_notes_project", "notes", ["project_id"])

    # --- API Keys ---
    op.create_table(
        "api_keys",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("scopes", ARRAY(sa.String), server_default='{read}'),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- RSS Feeds ---
    op.create_table(
        "rss_feeds",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetch_interval_minutes", sa.Integer, server_default="60"),
        sa.Column("tags", ARRAY(sa.String), server_default="{}"),
        sa.Column("error_count", sa.Integer, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- GitHub Repos ---
    op.create_table(
        "github_repos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("owner", sa.String(255), nullable=False),
        sa.Column("repo", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("sync_issues", sa.Boolean, server_default="true"),
        sa.Column("sync_prs", sa.Boolean, server_default="true"),
        sa.Column("auto_create_tasks", sa.Boolean, server_default="false"),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("webhook_secret", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_github_repos_owner_repo", "github_repos", ["owner", "repo"], unique=True)

    # --- Webhook Configs ---
    op.create_table(
        "webhook_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("url", sa.String(2048), nullable=True),
        sa.Column("secret", sa.String(255), nullable=True),
        sa.Column("events", sa.JSON, server_default="[]"),
        sa.Column("headers", sa.JSON, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_webhooks_direction", "webhook_configs", ["direction"])
    op.create_index("idx_webhooks_active", "webhook_configs", ["is_active"])

    # --- Webhook Logs ---
    op.create_table(
        "webhook_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("webhook_id", UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON, server_default="{}"),
        sa.Column("status_code", sa.String(10), nullable=True),
        sa.Column("response_body", sa.Text, nullable=True),
        sa.Column("success", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_webhook_logs_webhook", "webhook_logs", ["webhook_id"])

    # --- Notifications ---
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text, server_default=""),
        sa.Column("category", sa.String(50), server_default="info"),
        sa.Column("source", sa.String(100), server_default="system"),
        sa.Column("is_read", sa.Boolean, server_default="false"),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("data", sa.JSON, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_notifications_read", "notifications", ["is_read"])
    op.create_index("idx_notifications_created", "notifications", ["created_at"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("webhook_logs")
    op.drop_table("webhook_configs")
    op.drop_table("github_repos")
    op.drop_table("rss_feeds")
    op.drop_table("api_keys")
    op.drop_table("notes")
    op.drop_table("agent_triggers")
    op.drop_table("agent_memories")
    op.drop_table("agent_approvals")
    op.drop_table("journal_entries")
    op.drop_table("key_results")
    op.drop_table("goals")
    op.drop_table("habit_completions")
    op.drop_table("habits")
    op.drop_table("event_log")
    op.drop_table("agent_runs")
    op.drop_table("reading_list")
    op.drop_table("ideas")
    op.drop_table("tasks")
    op.drop_table("agent_configs")
    op.drop_table("projects")

    # Drop enums
    for enum_name in ["projectstatus", "agentstatus", "taskstatus", "taskpriority",
                      "agentrunstatus", "habitfrequency", "goalstatus", "moodlevel", "approvalstatus"]:
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
