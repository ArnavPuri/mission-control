"""
Mission Control - Database Models

Telegram-first personal AI assistant with agents, memory, and scheduling.

Column types are portable (sa.Uuid, JSON) so the same models work on
PostgreSQL and SQLite. Schema changes go through Alembic migrations.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    BigInteger, Column, String, Text, Boolean, Float, Integer, Uuid,
    DateTime, ForeignKey, Enum, JSON, Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


def _now():
    return datetime.now(timezone.utc)


# ---------- Enums ----------

class ProjectStatus(str, PyEnum):
    ACTIVE = "active"
    PLANNING = "planning"
    LAUNCHED = "launched"
    PAUSED = "paused"
    ARCHIVED = "archived"


class TaskPriority(str, PyEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TaskStatus(str, PyEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class AgentStatus(str, PyEnum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    DISABLED = "disabled"


class AgentRunStatus(str, PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class NotificationPriority(str, PyEnum):
    URGENT = "urgent"
    ROUTINE = "routine"


class ContentStatus(str, PyEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    POSTED = "posted"
    ARCHIVED = "archived"


# Tag that marks a task as a marketing lead found by an agent
LEAD_TAG = "lead"


# ---------- Models ----------

class Project(Base):
    __tablename__ = "projects"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    status = Column(Enum(ProjectStatus), default=ProjectStatus.PLANNING, nullable=False)
    color = Column(String(7), default="#00ffc8")
    url = Column(String(512))
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    tasks = relationship("Task", back_populates="project", lazy="selectin")
    agents = relationship("AgentConfig", back_populates="project", lazy="selectin")


class Task(Base):
    """A unit of work. Leads found by marketing agents are tasks tagged "lead"."""
    __tablename__ = "tasks"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    text = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    url = Column(String(2048), nullable=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.TODO, nullable=False)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False)
    project_id = Column(Uuid, ForeignKey("projects.id"), nullable=True)
    assigned_agent_id = Column(Uuid, ForeignKey("agent_configs.id"), nullable=True)
    source = Column(String(50), default="manual")
    tags = Column(JSON, default=list)
    due_date = Column(DateTime(timezone=True), nullable=True)
    sort_order = Column(Integer, default=0)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    project = relationship("Project", back_populates="tasks", lazy="selectin")
    assigned_agent = relationship("AgentConfig", foreign_keys=[assigned_agent_id], lazy="selectin")

    __table_args__ = (
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_priority", "priority"),
        Index("idx_tasks_project", "project_id"),
    )


class TaskComment(Base):
    """The thread on a task: messages between you and the agent working on it.

    author is "user", "agent:<slug>" or "system". When a comment was sent to
    Telegram, telegram_message_id lets a Telegram reply continue the thread.
    """
    __tablename__ = "task_comments"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id = Column(Uuid, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    author = Column(String(100), nullable=False)
    body = Column(Text, nullable=False)
    run_id = Column(Uuid, ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True)
    telegram_message_id = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("idx_task_comments_task", "task_id", "created_at"),
        Index("idx_task_comments_telegram", "telegram_message_id"),
    )


class Note(Base):
    """Markdown notes for knowledge, ideas, reading notes, reflections."""
    __tablename__ = "notes"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False, default="")
    tags = Column(JSON, default=list)
    is_pinned = Column(Boolean, default=False)
    project_id = Column(Uuid, ForeignKey("projects.id"), nullable=True)
    source = Column(String(50), default="manual")
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        Index("idx_notes_project", "project_id"),
    )


class AgentConfig(Base):
    """Agent definition - loaded from skill YAML files and stored in DB."""
    __tablename__ = "agent_configs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    slug = Column(String(255), nullable=False, unique=True)
    description = Column(Text, default="")
    agent_type = Column(String(50), nullable=False)
    status = Column(Enum(AgentStatus), default=AgentStatus.IDLE, nullable=False)
    model = Column(String(100), default="claude-haiku-4-5")
    max_budget_usd = Column(Float, default=0.10)
    prompt_template = Column(Text, nullable=False)
    tools = Column(JSON, default=list)
    schedule_type = Column(String(20), nullable=True)  # interval, cron, manual
    schedule_value = Column(String(100), nullable=True)  # "4h", "0 9 * * *"
    data_reads = Column(JSON, default=list)
    data_writes = Column(JSON, default=list)
    project_id = Column(Uuid, ForeignKey("projects.id"), nullable=True)
    config = Column(JSON, default=dict)
    skill_file = Column(String(255), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    project = relationship("Project", back_populates="agents")
    runs = relationship("AgentRun", back_populates="agent", lazy="selectin", order_by="AgentRun.started_at.desc()")


class AgentRun(Base):
    """Log of every agent execution."""
    __tablename__ = "agent_runs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_id = Column(Uuid, ForeignKey("agent_configs.id"), nullable=False)
    status = Column(Enum(AgentRunStatus), default=AgentRunStatus.PENDING, nullable=False)
    trigger = Column(String(50), default="manual")
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    transcript = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=True), default=_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("AgentConfig", back_populates="runs")

    __table_args__ = (
        Index("idx_agent_runs_agent", "agent_id"),
        Index("idx_agent_runs_status", "status"),
    )


class EventLog(Base):
    """Central event log for audit trail."""
    __tablename__ = "event_log"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Uuid, nullable=True)
    source = Column(String(50), default="system")
    data = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("idx_events_type", "event_type"),
        Index("idx_events_created", "created_at"),
    )


class AgentApproval(Base):
    """Pending agent actions that require human approval."""
    __tablename__ = "agent_approvals"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id = Column(Uuid, ForeignKey("agent_runs.id"), nullable=False)
    agent_id = Column(Uuid, ForeignKey("agent_configs.id"), nullable=False)
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False)
    actions = Column(JSON, nullable=False)
    summary = Column(Text, default="")
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    agent = relationship("AgentConfig", foreign_keys=[agent_id], lazy="selectin")
    run = relationship("AgentRun", foreign_keys=[run_id])

    __table_args__ = (
        Index("idx_approvals_status", "status"),
        Index("idx_approvals_agent", "agent_id"),
    )


class AgentMemory(Base):
    """Persistent key/value memory for an agent, kept across runs."""
    __tablename__ = "agent_memories"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    agent_id = Column(Uuid, ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)
    memory_type = Column(String(50), default="general")
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    agent = relationship("AgentConfig", foreign_keys=[agent_id])

    __table_args__ = (
        Index("idx_agent_memory_agent", "agent_id"),
        Index("idx_agent_memory_key", "agent_id", "key", unique=True),
    )


class BrandProfile(Base):
    """Personal brand profile for content generation."""
    __tablename__ = "brand_profile"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, default="")
    bio = Column(Text, default="")
    tone = Column(String(255), default="")
    social_handles = Column(JSON, default=dict)  # {"x": "@handle", "linkedin": "url", ...}
    topics = Column(JSON, default=list)
    talking_points = Column(JSON, default=dict)
    avoid = Column(JSON, default=list)
    example_posts = Column(JSON, default=list)
    notification_prefs = Column(JSON, default=lambda: {
        "agent_completions": True,
        "agent_failures": True,
        "signal_summary": True,
        "content_drafts": True,
    })
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class Notification(Base):
    """Notifications sent via Telegram."""
    __tablename__ = "notifications"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    body = Column(Text, default="")
    category = Column(String(50), default="info")
    source = Column(String(100), default="system")
    is_read = Column(Boolean, default=False)
    action_url = Column(String(500), nullable=True)
    data = Column(JSON, default=dict)
    priority = Column(Enum(NotificationPriority, values_callable=lambda x: [e.value for e in x]), default=NotificationPriority.ROUTINE, nullable=False)
    telegram_sent = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("idx_notifications_read", "is_read"),
        Index("idx_notifications_created", "created_at"),
    )


class MarketingContent(Base):
    """Content drafts for X, LinkedIn, Instagram, YouTube, etc."""
    __tablename__ = "marketing_content"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    channel = Column(String(50), nullable=False)  # x, linkedin, instagram, youtube, blog
    status = Column(Enum(ContentStatus), default=ContentStatus.DRAFT, nullable=False)
    source = Column(String(50), default="manual")
    task_id = Column(Uuid, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    project_id = Column(Uuid, ForeignKey("projects.id"), nullable=True)
    agent_id = Column(Uuid, ForeignKey("agent_configs.id"), nullable=True)
    posted_url = Column(String(2048), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    task = relationship("Task", foreign_keys=[task_id])
    project = relationship("Project", foreign_keys=[project_id])
    agent = relationship("AgentConfig", foreign_keys=[agent_id])

    __table_args__ = (
        Index("idx_mkt_content_status", "status"),
        Index("idx_mkt_content_channel", "channel"),
        Index("idx_mkt_content_project", "project_id"),
        Index("idx_mkt_content_created", "created_at"),
    )


class ChatSession(Base):
    """Persistent chat session for Telegram conversations."""
    __tablename__ = "chat_sessions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(String(100), nullable=False)
    platform = Column(String(50), nullable=False, default="telegram")
    messages = Column(JSON, default=list)
    last_active = Column(DateTime(timezone=True), default=_now)
    created_at = Column(DateTime(timezone=True), default=_now)

    __table_args__ = (
        Index("idx_chat_sessions_user", "user_id", "platform", unique=True),
        Index("idx_chat_sessions_active", "last_active"),
    )
