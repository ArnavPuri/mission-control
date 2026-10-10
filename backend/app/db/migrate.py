"""
Schema migrations, run on app startup.

Alembic is the single source of truth for the schema. Before 0.8 the app
built tables with create_all() and never ran migrations, so most existing
databases have tables but no alembic_version. Those are converted in place
to the baseline schema once (see _convert_legacy_postgres), stamped, and
then upgraded like any other database.
"""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, inspect, text

from app.db.models import Base, LEAD_TAG

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
BASELINE_REVISION = "0001_baseline"

# Tables from features that have been removed
DEAD_TABLES = [
    "marketing_signals",
    "agent_triggers", "agent_workflows", "workflow_steps",
    "api_keys", "github_repos", "rss_feeds", "webhook_configs", "webhook_logs",
    "goals", "key_results", "habits", "habit_completions", "journal_entries",
    "ideas", "reading_list", "routines", "routine_items", "routine_completions",
]

# Columns that used to be PostgreSQL ARRAY and are now JSON
ARRAY_COLUMNS = [
    ("tasks", "tags"), ("notes", "tags"), ("marketing_content", "tags"),
    ("agent_configs", "tools"), ("agent_configs", "data_reads"), ("agent_configs", "data_writes"),
]

# Agent memory keys written by removed features
DEAD_MEMORY_KEYS = ["_run_count", "_last_run_summary", "_chain_input"]


def alembic_config(connection: Connection | None = None) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    if connection is not None:
        cfg.attributes["connection"] = connection
    return cfg


def run_migrations(connection: Connection) -> None:
    """Bring the database to the latest schema. Call via AsyncConnection.run_sync."""
    insp = inspect(connection)
    tables = set(insp.get_table_names())
    cfg = alembic_config(connection)

    current = None
    if "alembic_version" in tables:
        current = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()

    known = {rev.revision for rev in _script(cfg).walk_revisions()}
    legacy = "projects" in tables and (current is None or current not in known)

    if legacy:
        logger.warning("Converting a pre-0.8 database to the baseline schema (one-time)")
        if current is not None:
            # Revision from the removed 001-010 chain
            connection.execute(text("DELETE FROM alembic_version"))
        if connection.dialect.name == "postgresql":
            _convert_legacy_postgres(connection)
        Base.metadata.create_all(connection, checkfirst=True)
        command.stamp(cfg, BASELINE_REVISION)

    command.upgrade(cfg, "head")


def _script(cfg: Config):
    from alembic.script import ScriptDirectory
    return ScriptDirectory.from_config(cfg)


def _convert_legacy_postgres(conn: Connection) -> None:
    insp = inspect(conn)
    tables = set(insp.get_table_names())

    def columns(table: str) -> dict:
        return {c["name"]: c for c in inspect(conn).get_columns(table)}

    # 0. Enum labels: the old migration chain created lowercase labels
    _reconcile_enums(conn)

    # 1. Leads: marketing_signals rows become tasks tagged "lead" (same ids)
    for col, ddl in (("description", "TEXT"), ("url", "VARCHAR(2048)")):
        if col not in columns("tasks"):
            conn.execute(text(f"ALTER TABLE tasks ADD COLUMN {col} {ddl}"))
    if "marketing_content" in tables and "task_id" not in columns("marketing_content"):
        conn.execute(text("ALTER TABLE marketing_content ADD COLUMN task_id UUID"))

    if "marketing_signals" in tables:
        signals = conn.execute(text(
            "SELECT id, title, body, source, source_type, source_url, relevance_score, "
            "status::text AS status, project_id, tags, created_at, updated_at FROM marketing_signals"
        )).mappings().all()
        for s in signals:
            done = (s["status"] or "").upper() in ("ACTED_ON", "DISMISSED")
            tags = [LEAD_TAG] + ([s["source_type"]] if s["source_type"] else []) + list(s["tags"] or [])
            score = s["relevance_score"] or 0.5
            priority = "HIGH" if score >= 0.8 else "LOW" if score < 0.5 else "MEDIUM"
            conn.execute(
                text(
                    "INSERT INTO tasks (id, text, description, url, status, priority, project_id, "
                    "source, tags, sort_order, completed_at, created_at, updated_at) VALUES "
                    "(:id, :text, :description, :url, CAST(:status AS taskstatus), "
                    "CAST(:priority AS taskpriority), :project_id, :source, :tags, 0, "
                    ":completed_at, :created_at, :updated_at)"
                ),
                {
                    "id": s["id"], "text": s["title"], "description": s["body"],
                    "url": s["source_url"], "status": "DONE" if done else "TODO",
                    "priority": priority, "project_id": s["project_id"],
                    "source": s["source"], "tags": list(dict.fromkeys(tags)),
                    "completed_at": s["updated_at"] if done else None,
                    "created_at": s["created_at"], "updated_at": s["updated_at"],
                },
            )
        if "signal_id" in columns("marketing_content"):
            conn.execute(text("UPDATE marketing_content SET task_id = signal_id"))
        logger.info(f"Converted {len(signals)} marketing signals to lead tasks")

    # 2. Drop tables of removed features (CASCADE also drops FKs pointing at them)
    for table in DEAD_TABLES:
        conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))

    # 3. ARRAY -> JSON
    for table, col in ARRAY_COLUMNS:
        cols = columns(table) if table in tables else {}
        if col in cols and cols[col]["type"].__class__.__name__ == "ARRAY":
            conn.execute(text(f'ALTER TABLE {table} ALTER COLUMN {col} DROP DEFAULT'))
            conn.execute(text(f'ALTER TABLE {table} ALTER COLUMN {col} TYPE JSON USING to_json({col})'))

    # Agents that read/wrote signals now read leads / write tasks
    conn.execute(text(
        "UPDATE agent_configs SET "
        "data_reads = REPLACE(data_reads::text, '\"marketing_signals\"', '\"leads\"')::json, "
        "data_writes = REPLACE(data_writes::text, '\"marketing_signals\"', '\"tasks\"')::json"
    ))

    # 4. Memory: drop the shared scratchpad and bookkeeping keys of removed features
    conn.execute(text("DELETE FROM agent_memories WHERE agent_id IS NULL"))
    conn.execute(
        text("DELETE FROM agent_memories WHERE key = ANY(:keys)"),
        {"keys": DEAD_MEMORY_KEYS},
    )

    # 5. Columns: add what the models expect, drop what they no longer define
    for table in Base.metadata.sorted_tables:
        if table.name not in inspect(conn).get_table_names():
            continue
        existing = columns(table.name)
        for col in table.columns:
            if col.name not in existing:
                ddl = col.type.compile(dialect=conn.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN "{col.name}" {ddl}'))
        for name in existing:
            if name not in table.columns:
                conn.execute(text(f'ALTER TABLE {table.name} DROP COLUMN "{name}" CASCADE'))
    conn.execute(text("ALTER TABLE agent_memories ALTER COLUMN agent_id SET NOT NULL"))

    # marketing_content.task_id foreign key (signal_id's FK went with the column)
    fks = inspect(conn).get_foreign_keys("marketing_content")
    if not any(fk["constrained_columns"] == ["task_id"] for fk in fks):
        conn.execute(text(
            "ALTER TABLE marketing_content ADD CONSTRAINT marketing_content_task_id_fkey "
            "FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL"
        ))

    # 6. Enum types nothing uses any more
    used = {c.type.name for t in Base.metadata.tables.values() for c in t.columns
            if getattr(c.type, "name", None) and c.type.__class__.__name__ == "Enum"}
    for row in conn.execute(text("SELECT typname FROM pg_type WHERE typtype = 'e'")).all():
        if row.typname not in used:
            conn.execute(text(f'DROP TYPE IF EXISTS "{row.typname}" CASCADE'))


def _reconcile_enums(conn: Connection) -> None:
    for table in Base.metadata.tables.values():
        for col in table.columns:
            if col.type.__class__.__name__ != "Enum":
                continue
            name, expected = col.type.name, list(col.type.enums)
            labels = [r[0] for r in conn.execute(
                text("SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                     "WHERE t.typname = :n"), {"n": name}
            ).all()]
            if not labels:
                continue
            for label in labels:
                if label not in expected:
                    match = next((e for e in expected if e.lower() == label.lower()), None)
                    if match and match not in labels:
                        conn.execute(text(f"ALTER TYPE {name} RENAME VALUE '{label}' TO '{match}'"))
                        labels.append(match)
            for value in expected:
                if value not in labels:
                    conn.execute(text(f"ALTER TYPE {name} ADD VALUE IF NOT EXISTS '{value}'"))
