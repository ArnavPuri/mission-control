"""The Alembic migrations must produce exactly the schema the models describe."""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db.migrate import run_migrations
from app.db.models import Base


def test_migrations_match_models(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mc.db'}")
    with engine.begin() as conn:
        run_migrations(conn)
    with engine.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        assert diffs == []
        assert "alembic_version" in inspect(conn).get_table_names()


def test_migrations_are_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mc.db'}")
    for _ in range(2):
        with engine.begin() as conn:
            run_migrations(conn)
