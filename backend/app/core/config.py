from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings and environment configuration."""

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server Configuration
    PROJECT_NAME: str = "CodeLens"
    VERSION: str = "0.1.0"
    PORT: int = 8000
    HOST: str = "127.0.0.1"
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # PostgreSQL Database Configuration
    POSTGRES_USER: str = "codelens"
    POSTGRES_PASSWORD: str = "codelens_password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "codelens_db"
    DATABASE_URL: Optional[str] = None

    # Connection pool configuration
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False

    @property
    def async_database_url(self) -> str:
        """Returns the async PostgreSQL connection string."""
        if self.DATABASE_URL:
            url = self.DATABASE_URL
            if url.startswith("postgresql://"):
                return url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        """Returns the sync PostgreSQL connection string (useful for Alembic migrations)."""
        async_url = self.async_database_url
        if "postgresql+asyncpg://" in async_url:
            return async_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return async_url

    @property
    def cors_origins_list(self) -> List[str]:
        """Parsed list of allowed CORS origins."""
        return [
            origin.strip()
            for origin in self.CORS_ORIGINS.split(",")
            if origin.strip()
        ]


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
