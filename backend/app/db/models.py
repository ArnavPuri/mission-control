"""
Mission Control - Database Models (Simplified)

Telegram-first personal AI assistant with agents, memory, and scheduling.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Text, Boolean, Float, Integer,
    DateTime, ForeignKey, Enum, JSON, Index,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False
    Vector = None


class Base(DeclarativeBase):
    pass


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


class SignalStatus(str, PyEnum):
    NEW = "new"
    REVIEWED = "reviewed"
    ACTED_ON = "acted_on"
    DISMISSED = "dismissed"


# ---------- Models ----------

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    status = Column(Enum(ProjectStatus), default=ProjectStatus.PLANNING, nullable=False)
    color = Column(String(7), default="#00ffc8")
    url = Column(String(512))
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    tasks = relationship("Task", back_populates="project", lazy="selectin")
    agents = relationship("AgentConfig", back_populates="project", lazy="selectin")
    marketing_content = relationship("MarketingContent", foreign_keys="[MarketingContent.project_id]", back_populates="project", lazy="noload")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    text = Column(Text, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.TODO, nullable=False)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    assigned_agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id"), nullable=True)
    source = Column(String(50), default="manual")
    tags = Column(ARRAY(String), default=list)
    due_date = Column(DateTime(timezone=True), nullable=True)
    sort_order = Column(Integer, default=0)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", back_populates="tasks")
    assigned_agent = relationship("AgentConfig", foreign_keys=[assigned_agent_id])

    __table_args__ = (
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_priority", "priority"),
        Index("idx_tasks_project", "project_id"),
    )


class Note(Base):
    """Markdown notes for knowledge, ideas, reading notes, reflections."""
    __tablename__ = "notes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False, default="")
    tags = Column(ARRAY(String), default=list)
    is_pinned = Column(Boolean, default=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    source = Column(String(50), default="manual")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_notes_project", "project_id"),
    )


class AgentConfig(Base):
    """Agent definition - loaded from skill YAML files and stored in DB."""
    __tablename__ = "agent_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    slug = Column(String(255), nullable=False, unique=True)
    description = Column(Text, default="")
    agent_type = Column(String(50), nullable=False)
    status = Column(Enum(AgentStatus), default=AgentStatus.IDLE, nullable=False)
    model = Column(String(100), default="claude-haiku-4-5")
    max_budget_usd = Column(Float, default=0.10)
    prompt_template = Column(Text, nullable=False)
    tools = Column(ARRAY(String), default=list)
    schedule_type = Column(String(20), nullable=True)  # interval, cron, manual
    schedule_value = Column(String(100), nullable=True)  # "4h", "0 9 * * *"
    data_reads = Column(ARRAY(String), default=list)
    data_writes = Column(ARRAY(String), default=list)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    config = Column(JSON, default=dict)
    skill_file = Column(String(255), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Session persistence
    session_id = Column(String(255), nullable=True)
    last_message_uuid = Column(String(255), nullable=True)
    session_expires_at = Column(DateTime(timezone=True), nullable=True)
    session_window_days = Column(Integer, default=7)

    project = relationship("Project", back_populates="agents")
    runs = relationship("AgentRun", back_populates="agent", lazy="selectin", order_by="AgentRun.started_at.desc()")


class AgentRun(Base):
    """Log of every agent execution."""
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id"), nullable=False)
    status = Column(Enum(AgentRunStatus), default=AgentRunStatus.PENDING, nullable=False)
    trigger = Column(String(50), default="manual")
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    transcript = Column(JSON, nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    agent = relationship("AgentConfig", back_populates="runs")

    __table_args__ = (
        Index("idx_agent_runs_agent", "agent_id"),
        Index("idx_agent_runs_status", "status"),
    )


class EventLog(Base):
    """Central event log for audit trail."""
    __tablename__ = "event_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    source = Column(String(50), default="system")
    data = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_events_type", "event_type"),
        Index("idx_events_created", "created_at"),
    )


class AgentApproval(Base):
    """Pending agent actions that require human approval."""
    __tablename__ = "agent_approvals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id"), nullable=False)
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False)
    actions = Column(JSON, nullable=False)
    summary = Column(Text, default="")
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    agent = relationship("AgentConfig", foreign_keys=[agent_id])
    run = relationship("AgentRun", foreign_keys=[run_id])

    __table_args__ = (
        Index("idx_approvals_status", "status"),
        Index("idx_approvals_agent", "agent_id"),
    )


class AgentMemory(Base):
    """Persistent memory for agents. agent_id=NULL = shared scratchpad."""
    __tablename__ = "agent_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=True)
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)
    memory_type = Column(String(50), default="general")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    agent = relationship("AgentConfig", foreign_keys=[agent_id])

    __table_args__ = (
        Index("idx_agent_memory_agent", "agent_id"),
        Index("idx_agent_memory_key", "agent_id", "key", unique=True),
    )


class BrandProfile(Base):
    """Personal brand profile for content generation."""
    __tablename__ = "brand_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class Notification(Base):
    """Notifications sent via Telegram."""
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    body = Column(Text, default="")
    category = Column(String(50), default="info")
    source = Column(String(100), default="system")
    is_read = Column(Boolean, default=False)
    action_url = Column(String(500), nullable=True)
    data = Column(JSON, default=dict)
    priority = Column(Enum(NotificationPriority, values_callable=lambda x: [e.value for e in x]), default=NotificationPriority.ROUTINE, nullable=False)
    telegram_sent = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_notifications_read", "is_read"),
        Index("idx_notifications_created", "created_at"),
    )


class MarketingSignal(Base):
    """Market intelligence discovered by agents."""
    __tablename__ = "marketing_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    body = Column(Text, default="")
    source = Column(String(50), default="manual")
    source_type = Column(String(50), nullable=False)
    source_url = Column(String(2048), nullable=True)
    relevance_score = Column(Float, default=0.5)
    signal_type = Column(String(50), nullable=False)
    status = Column(Enum(SignalStatus), default=SignalStatus.NEW, nullable=False)
    channel_metadata = Column(JSON, default=dict)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id"), nullable=True)
    tags = Column(ARRAY(String), default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    project = relationship("Project", foreign_keys=[project_id])
    agent = relationship("AgentConfig", foreign_keys=[agent_id])

    __table_args__ = (
        Index("idx_mkt_signals_status", "status"),
        Index("idx_mkt_signals_project", "project_id"),
        Index("idx_mkt_signals_created", "created_at"),
    )


class MarketingContent(Base):
    """Content drafts for X, LinkedIn, Instagram, YouTube, etc."""
    __tablename__ = "marketing_content"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    channel = Column(String(50), nullable=False)  # x, linkedin, instagram, youtube, blog
    status = Column(Enum(ContentStatus), default=ContentStatus.DRAFT, nullable=False)
    source = Column(String(50), default="manual")
    signal_id = Column(UUID(as_uuid=True), ForeignKey("marketing_signals.id"), nullable=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id"), nullable=True)
    posted_url = Column(String(2048), nullable=True)
    posted_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    tags = Column(ARRAY(String), default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    signal = relationship("MarketingSignal", foreign_keys=[signal_id])
    project = relationship("Project", foreign_keys=[project_id], back_populates="marketing_content")
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

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(100), nullable=False)
    platform = Column(String(50), nullable=False, default="telegram")
    messages = Column(JSON, default=list)
    last_active = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_chat_sessions_user", "user_id", "platform", unique=True),
        Index("idx_chat_sessions_active", "last_active"),
    )


# Optional: pgvector embedding support
if HAS_PGVECTOR and Vector is not None:
    Task.embedding = Column(Vector(1536), nullable=True)
