import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.repositories import router as repositories_router
from app.core.config import settings
from app.db.session import check_db_connection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("codelens")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context for startup and shutdown tasks."""
    logger.info("Initializing CodeLens backend v%s...", settings.VERSION)
    db_connected = await check_db_connection()
    if db_connected:
        logger.info("Database connection established successfully.")
        try:
            from app.db.base import Base
            from app.db.session import async_engine
            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database schema initialized.")
        except Exception as exc:
            logger.warning("Auto schema creation skipped: %s", exc)
    else:
        logger.warning(
            "Database connectivity check failed on startup. Will verify on incoming requests."
        )
    yield
    logger.info("Shutting down CodeLens backend.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="CodeLens Backend API",
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repositories_router, prefix="/repositories", tags=["Repositories"])


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint returning application and database status.
    Maintains full compatibility with frontend expectations: {"status": "ok"}.
    """
    db_ok = await check_db_connection()
    return {
        "status": "ok",
        "database": "connected" if db_ok else "disconnected",
        "version": settings.VERSION,
    }
