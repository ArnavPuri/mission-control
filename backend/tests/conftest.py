"""Test configuration: an in-memory SQLite database shared by all tests.

Nothing here talks to Claude or Telegram; tests that run agents replace
AgentRunner.execute_with_agent_sdk with a stub.
"""

import sys

import sqlalchemy as sa
from sqlalchemy import event


@event.listens_for(sa.engine.Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign key enforcement for SQLite (tests only use SQLite)."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# --- Shared database fixtures -------------------------------------------------

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.models import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402

engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db(monkeypatch):
    # Tests must not pick up a developer's real .env (login, tokens)
    from app.config import settings
    for name in ("dashboard_password", "api_token", "telegram_bot_token", "github_token", "claude_code_oauth_token",
                 "x_api_key", "x_api_secret", "x_access_token", "x_access_token_secret",
                 "linkedin_access_token", "linkedin_author_urn"):
        monkeypatch.setattr(settings, name, None)
    # Code outside request handlers opens its own sessions; point them at the test DB
    for name, module in list(sys.modules.items()):
        if name.startswith("app.") and getattr(module, "async_session", None) is not None:
            monkeypatch.setattr(module, "async_session", TestSession)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def db_session():
    return TestSession
