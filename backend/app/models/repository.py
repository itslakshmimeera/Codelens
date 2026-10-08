import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.file import File
    from app.models.symbol import CodeSymbol
    from app.models.chunk import CodeChunk
    from app.models.dependency import Dependency
    from app.models.ingestion_job import IngestionJob


class Repository(Base, TimestampMixin):
    """Represents a code repository tracked by CodeLens."""

    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    default_branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)

    # Relationships
    files: Mapped[List["File"]] = relationship(
        "File",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    symbols: Mapped[List["CodeSymbol"]] = relationship(
        "CodeSymbol",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[List["CodeChunk"]] = relationship(
        "CodeChunk",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    dependencies: Mapped[List["Dependency"]] = relationship(
        "Dependency",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
    ingestion_jobs: Mapped[List["IngestionJob"]] = relationship(
        "IngestionJob",
        back_populates="repository",
        cascade="all, delete-orphan",
    )
