import asyncio
import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

engine_kwargs = {"echo": settings.DB_ECHO}
if "sqlite" in settings.async_database_url:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_pre_ping": True,
        }
    )

# Async database engine
async_engine = create_async_engine(
    settings.async_database_url,
    **engine_kwargs,
)

# Async session factory
async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """Verifies that the PostgreSQL database is reachable and responsive."""
    try:
        async with asyncio.timeout(1.5):
            async with async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                return True
    except Exception as exc:
        logger.warning("Database connectivity check failed: %s", exc)
        return False

