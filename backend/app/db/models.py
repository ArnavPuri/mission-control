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


class HabitFrequency(str, PyEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    CUSTOM = "custom"


class GoalStatus(str, PyEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class MoodLevel(str, PyEnum):
    GREAT = "great"
    GOOD = "good"
    OKAY = "okay"
    LOW = "low"
    BAD = "bad"


class NotificationPriority(str, PyEnum):
    URGENT = "urgent"
    ROUTINE = "routine"


class SignalStatus(str, PyEnum):
    NEW = "new"
    REVIEWED = "reviewed"
    ACTED_ON = "acted_on"
    DISMISSED = "dismissed"


class ContentStatus(str, PyEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    POSTED = "posted"
    ARCHIVED = "archived"


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
    ideas = relationship("Idea", foreign_keys="[Idea.project_id]", back_populates="project", lazy="noload")
    marketing_signals = relationship("MarketingSignal", foreign_keys="[MarketingSignal.project_id]", back_populates="project", lazy="noload")
    marketing_content = relationship("MarketingContent", foreign_keys="[MarketingContent.project_id]", back_populates="project", lazy="noload")


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
    sort_order = Column(Integer, default=0)  # manual ordering for drag-and-drop
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

    project = relationship("Project", foreign_keys=[project_id], back_populates="ideas")


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


# ---------- Habits & Streaks ----------

class Habit(Base):
    """Recurring behavior to track with streaks."""
    __tablename__ = "habits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    frequency = Column(Enum(HabitFrequency), default=HabitFrequency.DAILY, nullable=False)
    target_days = Column(ARRAY(String), default=list)  # for custom: ["mon","wed","fri"]
    current_streak = Column(Integer, default=0)
    best_streak = Column(Integer, default=0)
    total_completions = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    color = Column(String(7), default="#00ffc8")
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    completions = relationship("HabitCompletion", back_populates="habit", lazy="selectin", order_by="HabitCompletion.completed_at.desc()")


class HabitCompletion(Base):
    """Individual completion log for a habit."""
    __tablename__ = "habit_completions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    habit_id = Column(UUID(as_uuid=True), ForeignKey("habits.id", ondelete="CASCADE"), nullable=False)
    completed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    notes = Column(Text, nullable=True)

    habit = relationship("Habit", back_populates="completions")

    __table_args__ = (
        Index("idx_habit_completions_habit", "habit_id"),
        Index("idx_habit_completions_date", "completed_at"),
    )


# ---------- Goals & Key Results ----------

class Goal(Base):
    """Long-term objective with measurable key results."""
    __tablename__ = "goals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    status = Column(Enum(GoalStatus), default=GoalStatus.ACTIVE, nullable=False)
    target_date = Column(DateTime(timezone=True), nullable=True)
    progress = Column(Float, default=0.0)  # 0.0 to 1.0
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    tags = Column(ARRAY(String), default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    key_results = relationship("KeyResult", back_populates="goal", lazy="selectin", order_by="KeyResult.created_at")


class KeyResult(Base):
    """Measurable outcome tied to a goal."""
    __tablename__ = "key_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal_id = Column(UUID(as_uuid=True), ForeignKey("goals.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    target_value = Column(Float, nullable=False)  # e.g., 100
    current_value = Column(Float, default=0.0)  # e.g., 45
    unit = Column(String(50), default="")  # e.g., "%", "users", "articles"
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    goal = relationship("Goal", back_populates="key_results")


# ---------- Journal ----------

class JournalEntry(Base):
    """Daily journal entry for reflection and tracking."""
    __tablename__ = "journal_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    content = Column(Text, nullable=False)
    mood = Column(Enum(MoodLevel), nullable=True)
    energy = Column(Integer, nullable=True)  # 1-5 scale
    tags = Column(ARRAY(String), default=list)
    wins = Column(ARRAY(String), default=list)  # things that went well
    challenges = Column(ARRAY(String), default=list)  # things that were hard
    gratitude = Column(ARRAY(String), default=list)  # gratitude items
    source = Column(String(50), default="manual")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_journal_created", "created_at"),
    )


# ---------- Agent Approval Queue ----------

class AgentApproval(Base):
    """Pending agent actions that require human approval before execution."""
    __tablename__ = "agent_approvals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), ForeignKey("agent_runs.id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id"), nullable=False)
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False)
    actions = Column(JSON, nullable=False)  # the proposed actions
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
    """Persistent memory entries for agents across runs.

    Shared scratchpad: entries with agent_id=NULL are visible to ALL agents,
    enabling inter-agent collaboration without direct communication.
    Use key prefixes like 'collab:' for shared context between agents.
    """
    __tablename__ = "agent_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=True)
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)
    memory_type = Column(String(50), default="general")  # general, preference, fact, decision, shared
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    agent = relationship("AgentConfig", foreign_keys=[agent_id])

    __table_args__ = (
        Index("idx_agent_memory_agent", "agent_id"),
        Index("idx_agent_memory_key", "agent_id", "key", unique=True),
    )


class AgentTrigger(Base):
    """Conditional triggers that run agents when DB conditions are met."""
    __tablename__ = "agent_triggers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    is_active = Column(Boolean, default=True)

    # Condition specification
    entity_type = Column(String(50), nullable=False)  # task, idea, goal, habit, journal
    event = Column(String(50), nullable=False)  # created, updated, status_changed, completed
    condition = Column(JSON, nullable=True)  # {"field": "priority", "op": "eq", "value": "critical"}

    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    trigger_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    agent = relationship("AgentConfig", foreign_keys=[agent_id])

    __table_args__ = (
        Index("idx_agent_triggers_agent", "agent_id"),
        Index("idx_agent_triggers_active", "is_active"),
    )


# ---------- Notes ----------

class Note(Base):
    """Long-form markdown note for knowledge management."""
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


# ---------- API Keys ----------

class ApiKey(Base):
    """API key for authenticated public access."""
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(128), nullable=False, unique=True)
    key_prefix = Column(String(8), nullable=False)  # first 8 chars for identification
    scopes = Column(ARRAY(String), default=lambda: ["read"])  # read, write, admin
    is_active = Column(Boolean, default=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ---------- RSS Feeds ----------

class RSSFeed(Base):
    """RSS feed subscription for auto-populating reading list."""
    __tablename__ = "rss_feeds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    url = Column(String(2048), nullable=False, unique=True)
    is_active = Column(Boolean, default=True)
    last_fetched_at = Column(DateTime(timezone=True), nullable=True)
    fetch_interval_minutes = Column(Integer, default=60)
    tags = Column(ARRAY(String), default=list)  # auto-applied to imported items
    error_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ---------- GitHub Integration ----------

class GitHubRepo(Base):
    """Linked GitHub repository for issue/PR sync."""
    __tablename__ = "github_repos"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner = Column(String(255), nullable=False)
    repo = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    sync_issues = Column(Boolean, default=True)
    sync_prs = Column(Boolean, default=True)
    auto_create_tasks = Column(Boolean, default=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    webhook_secret = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_github_repos_owner_repo", "owner", "repo", unique=True),
    )


# ---------- Webhooks ----------

class WebhookConfig(Base):
    """Webhook configuration for inbound and outbound hooks."""
    __tablename__ = "webhook_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    direction = Column(String(10), nullable=False)  # "inbound" or "outbound"
    url = Column(String(2048), nullable=True)  # target URL for outbound
    secret = Column(String(255), nullable=True)  # shared secret for verification
    events = Column(JSON, default=list)  # list of event types to trigger on
    headers = Column(JSON, default=dict)  # custom headers for outbound
    is_active = Column(Boolean, default=True)
    last_triggered_at = Column(DateTime(timezone=True), nullable=True)
    trigger_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_webhooks_direction", "direction"),
        Index("idx_webhooks_active", "is_active"),
    )


class WebhookLog(Base):
    """Log of webhook deliveries."""
    __tablename__ = "webhook_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    webhook_id = Column(UUID(as_uuid=True), nullable=False)
    direction = Column(String(10), nullable=False)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, default=dict)
    status_code = Column(String(10), nullable=True)
    response_body = Column(Text, nullable=True)
    success = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_webhook_logs_webhook", "webhook_id"),
    )


# ---------- Brand Profile ----------

class BrandProfile(Base):
    """Personal brand profile for agent content drafting."""
    __tablename__ = "brand_profile"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, default="")
    bio = Column(Text, default="")
    tone = Column(String(255), default="")
    social_handles = Column(JSON, default=dict)
    topics = Column(JSON, default=list)  # JSON list for SQLite compat
    talking_points = Column(JSON, default=dict)
    avoid = Column(JSON, default=list)  # JSON list for SQLite compat
    example_posts = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ---------- Notifications ----------

class Notification(Base):
    """In-app notification for the dashboard."""
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    body = Column(Text, default="")
    category = Column(String(50), default="info")  # info, success, warning, error, approval
    source = Column(String(100), default="system")  # agent:<name>, system, webhook:<name>
    is_read = Column(Boolean, default=False)
    action_url = Column(String(500), nullable=True)  # optional deep link
    data = Column(JSON, default=dict)
    priority = Column(Enum(NotificationPriority), default=NotificationPriority.ROUTINE, nullable=False)
    telegram_sent = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_notifications_read", "is_read"),
        Index("idx_notifications_created", "created_at"),
    )


# ---------- Marketing ----------

class MarketingSignal(Base):
    """Market intelligence discovered by agents or added manually."""
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

    project = relationship("Project", foreign_keys=[project_id], back_populates="marketing_signals")
    agent = relationship("AgentConfig", foreign_keys=[agent_id])

    __table_args__ = (
        Index("idx_mkt_signals_status", "status"),
        Index("idx_mkt_signals_source_type", "source_type"),
        Index("idx_mkt_signals_signal_type", "signal_type"),
        Index("idx_mkt_signals_project", "project_id"),
        Index("idx_mkt_signals_created", "created_at"),
    )


class MarketingContent(Base):
    """Content drafts for marketing channels."""
    __tablename__ = "marketing_content"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(500), nullable=False)
    body = Column(Text, nullable=False)
    channel = Column(String(50), nullable=False)
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
        Index("idx_mkt_content_signal", "signal_id"),
        Index("idx_mkt_content_created", "created_at"),
    )


# ---------- Agent Workflows (DAGs) ----------

class WorkflowStatus(str, PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class AgentWorkflow(Base):
    """Multi-step agent workflow with dependency resolution (DAG)."""
    __tablename__ = "agent_workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    status = Column(Enum(WorkflowStatus), default=WorkflowStatus.DRAFT, nullable=False)
    trigger_type = Column(String(50), default="manual")  # manual, schedule, event
    trigger_value = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    steps = relationship("WorkflowStep", back_populates="workflow", lazy="selectin", order_by="WorkflowStep.sort_order")

    __table_args__ = (
        Index("idx_workflows_status", "status"),
    )


class StepStatus(str, PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WorkflowStep(Base):
    """A single step in a workflow — references an agent and its dependencies."""
    __tablename__ = "workflow_steps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("agent_workflows.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id"), nullable=False)
    name = Column(String(255), nullable=False)
    sort_order = Column(Integer, default=0)
    depends_on = Column(ARRAY(String), default=list)  # list of step IDs this step depends on
    status = Column(Enum(StepStatus), default=StepStatus.PENDING, nullable=False)
    config = Column(JSON, default=dict)  # step-specific config overrides
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    run_id = Column(UUID(as_uuid=True), nullable=True)  # reference to the agent_run created
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    workflow = relationship("AgentWorkflow", back_populates="steps")
    agent = relationship("AgentConfig", foreign_keys=[agent_id])

    __table_args__ = (
        Index("idx_workflow_steps_workflow", "workflow_id"),
        Index("idx_workflow_steps_status", "status"),
    )


# ---------- Routines ----------

class RoutineType(str, PyEnum):
    MORNING = "morning"
    EVENING = "evening"
    CUSTOM = "custom"


class Routine(Base):
    """Repeatable routine (morning/evening) with ordered checklist items."""
    __tablename__ = "routines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    routine_type = Column(Enum(RoutineType), default=RoutineType.CUSTOM, nullable=False)
    is_active = Column(Boolean, default=True)
    days = Column(ARRAY(String), default=lambda: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    items = relationship("RoutineItem", back_populates="routine", lazy="selectin", order_by="RoutineItem.sort_order")

    __table_args__ = (
        Index("idx_routines_type", "routine_type"),
        Index("idx_routines_active", "is_active"),
    )


class RoutineItem(Base):
    """Individual step in a routine checklist."""
    __tablename__ = "routine_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    routine_id = Column(UUID(as_uuid=True), ForeignKey("routines.id", ondelete="CASCADE"), nullable=False)
    text = Column(String(500), nullable=False)
    sort_order = Column(Integer, default=0)
    duration_minutes = Column(Integer, nullable=True)  # estimated time
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    routine = relationship("Routine", back_populates="items")

    __table_args__ = (
        Index("idx_routine_items_routine", "routine_id"),
    )


class RoutineCompletion(Base):
    """Daily completion log for a routine — tracks which items were checked off."""
    __tablename__ = "routine_completions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    routine_id = Column(UUID(as_uuid=True), ForeignKey("routines.id", ondelete="CASCADE"), nullable=False)
    completed_items = Column(ARRAY(String), default=list)  # list of item IDs completed
    total_items = Column(Integer, default=0)
    completed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_routine_completions_routine", "routine_id"),
        Index("idx_routine_completions_date", "completed_at"),
    )


# ---------- Chat Sessions ----------

class ChatSession(Base):
    """Persistent chat session for bot conversations."""
    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(100), nullable=False)  # platform-specific user ID
    platform = Column(String(50), nullable=False, default="telegram")  # telegram, discord, etc.
    messages = Column(JSON, default=list)  # list of {role, content, timestamp}
    last_active = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_chat_sessions_user", "user_id", "platform", unique=True),
        Index("idx_chat_sessions_active", "last_active"),
    )


# Optional: Embedding column on existing models (only if pgvector is installed)
# These are added dynamically to avoid hard dependency on pgvector
if HAS_PGVECTOR and Vector is not None:
    Task.embedding = Column(Vector(1536), nullable=True)
    Idea.embedding = Column(Vector(1536), nullable=True)
    JournalEntry.embedding = Column(Vector(1536), nullable=True)
