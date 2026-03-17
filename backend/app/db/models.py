"""
Mission Control - Database Models

The central database is the single source of truth.
Dashboard reads from it, agents read/write to it,
Telegram bot writes to it, orchestrator reads from it.
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


class Base(DeclarativeBase):
    pass


# ---------- Enums ----------

class ProjectStatus(str, PyEnum):
    ACTIVE = "active"
    PLANNING = "planning"
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


# ---------- Models ----------

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    status = Column(Enum(ProjectStatus), default=ProjectStatus.PLANNING, nullable=False)
    color = Column(String(7), default="#00ffc8")  # hex color
    url = Column(String(512))  # repo or site URL
    metadata_ = Column("metadata", JSON, default=dict)  # flexible extra data
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    tasks = relationship("Task", back_populates="project", lazy="selectin")
    agents = relationship("AgentConfig", back_populates="project", lazy="selectin")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    text = Column(Text, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.TODO, nullable=False)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    assigned_agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id"), nullable=True)
    source = Column(String(50), default="manual")  # manual, telegram, agent
    tags = Column(ARRAY(String), default=list)
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    project = relationship("Project", back_populates="tasks")
    assigned_agent = relationship("AgentConfig", foreign_keys=[assigned_agent_id])

    __table_args__ = (
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_priority", "priority"),
        Index("idx_tasks_project", "project_id"),
    )


class Idea(Base):
    __tablename__ = "ideas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    text = Column(Text, nullable=False)
    tags = Column(ARRAY(String), default=list)
    source = Column(String(50), default="manual")  # manual, telegram, agent
    score = Column(Float, nullable=True)  # validation score from AI
    validation_notes = Column(Text, nullable=True)  # AI analysis
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ReadingItem(Base):
    __tablename__ = "reading_list"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    url = Column(String(2048), nullable=True)
    notes = Column(Text, nullable=True)
    is_read = Column(Boolean, default=False)
    source = Column(String(50), default="manual")
    tags = Column(ARRAY(String), default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    read_at = Column(DateTime(timezone=True), nullable=True)


class AgentConfig(Base):
    """Agent definition - loaded from skill YAML files and stored in DB."""
    __tablename__ = "agent_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    slug = Column(String(255), nullable=False, unique=True)  # filesystem-safe name
    description = Column(Text, default="")
    agent_type = Column(String(50), nullable=False)  # marketing, research, content, ops
    status = Column(Enum(AgentStatus), default=AgentStatus.IDLE, nullable=False)
    model = Column(String(100), default="claude-haiku-4-5")
    max_budget_usd = Column(Float, default=0.10)
    prompt_template = Column(Text, nullable=False)
    tools = Column(ARRAY(String), default=list)  # tool names this agent can use
    schedule_type = Column(String(20), nullable=True)  # interval, cron, manual
    schedule_value = Column(String(100), nullable=True)  # "4h", "0 9 * * *", null
    data_reads = Column(ARRAY(String), default=list)  # which tables it reads
    data_writes = Column(ARRAY(String), default=list)  # which tables it writes
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    config = Column(JSON, default=dict)  # extra config from YAML
    skill_file = Column(String(255), nullable=True)  # path to source YAML
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    project = relationship("Project", back_populates="agents")
    runs = relationship("AgentRun", back_populates="agent", lazy="selectin", order_by="AgentRun.started_at.desc()")


class AgentRun(Base):
    """Log of every agent execution."""
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id"), nullable=False)
    status = Column(Enum(AgentRunStatus), default=AgentRunStatus.PENDING, nullable=False)
    trigger = Column(String(50), default="manual")  # manual, schedule, telegram
    input_data = Column(JSON, default=dict)
    output_data = Column(JSON, default=dict)
    error = Column(Text, nullable=True)
    tokens_used = Column(Integer, default=0)
    cost_usd = Column(Float, default=0.0)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    agent = relationship("AgentConfig", back_populates="runs")

    __table_args__ = (
        Index("idx_agent_runs_agent", "agent_id"),
        Index("idx_agent_runs_status", "status"),
    )


class EventLog(Base):
    """Central event log - everything that happens flows through here.
    Dashboard can subscribe to this via WebSocket for real-time updates."""
    __tablename__ = "event_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(100), nullable=False)  # task.created, agent.started, idea.added, etc.
    entity_type = Column(String(50), nullable=False)  # task, idea, agent, project, reading
    entity_id = Column(UUID(as_uuid=True), nullable=True)
    source = Column(String(50), default="system")  # system, telegram, agent:<name>, manual
    data = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_events_type", "event_type"),
        Index("idx_events_created", "created_at"),
    )
