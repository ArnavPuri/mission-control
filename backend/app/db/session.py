"""Database session and engine setup."""

from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.config import settings

db_url = settings.effective_database_url

# SQLite needs different engine config
if settings.is_sqlite:
    # Ensure the directory exists
    db_path = settings.sqlite_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(
        db_url,
        echo=False,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_async_engine(db_url, echo=False, pool_size=10, max_overflow=20)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """FastAPI dependency for DB sessions."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Run Alembic migrations so the database matches the models."""
    from app.db.migrate import run_migrations

    async with engine.begin() as conn:
        await conn.run_sync(run_migrations)
