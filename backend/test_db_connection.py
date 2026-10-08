import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings


async def main():
    print("Testing URL:")
    print(
        settings.async_database_url.replace(
            settings.POSTGRES_PASSWORD,
            "***"
        )
    )

    engine = create_async_engine(settings.async_database_url)

    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            print("SQLAlchemy connection successful:", result.scalar())
    finally:
        await engine.dispose()


asyncio.run(main())
