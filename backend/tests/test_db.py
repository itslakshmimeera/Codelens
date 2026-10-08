import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import Settings
from app.db.session import get_db


@pytest.mark.asyncio
async def test_db_session_query(db_session: AsyncSession):
    """Verifies that the async database session can execute SQL queries."""
    result = await db_session.execute(text("SELECT 1 AS num"))
    scalar_val = result.scalar()
    assert scalar_val == 1


@pytest.mark.asyncio
async def test_get_db_dependency(test_engine, monkeypatch):
    """Verifies that get_db yields an active session."""
    from sqlalchemy.ext.asyncio import async_sessionmaker
    test_session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    monkeypatch.setattr("app.db.session.async_session_factory", test_session_factory)
    async for session in get_db():
        assert isinstance(session, AsyncSession)
        break


def test_database_settings_url_generation():
    """Verifies that settings correctly generate async and sync database URLs."""
    custom_settings = Settings(
        DATABASE_URL=None,
        POSTGRES_USER="testuser",
        POSTGRES_PASSWORD="testpassword",
        POSTGRES_HOST="dbhost",
        POSTGRES_PORT=5432,
        POSTGRES_DB="testdb",
    )
    assert custom_settings.async_database_url == "postgresql+asyncpg://testuser:testpassword@dbhost:5432/testdb"
    assert custom_settings.sync_database_url == "postgresql://testuser:testpassword@dbhost:5432/testdb"
