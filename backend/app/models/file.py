import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import ForeignKey, Integer, String, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.symbol import CodeSymbol
    from app.models.chunk import CodeChunk
    from app.models.dependency import Dependency


class File(Base, TimestampMixin):
    """Represents a source code file within a repository."""

    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("repository_id", "path", name="uq_repo_file_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    path: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    language: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Relationships
    repository: Mapped["Repository"] = relationship(
        "Repository",
        back_populates="files",
    )
    symbols: Mapped[List["CodeSymbol"]] = relationship(
        "CodeSymbol",
        back_populates="file",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[List["CodeChunk"]] = relationship(
        "CodeChunk",
        back_populates="file",
        cascade="all, delete-orphan",
    )
    source_dependencies: Mapped[List["Dependency"]] = relationship(
        "Dependency",
        foreign_keys="Dependency.source_file_id",
        back_populates="source_file",
        cascade="all, delete-orphan",
    )
    target_dependencies: Mapped[List["Dependency"]] = relationship(
        "Dependency",
        foreign_keys="Dependency.target_file_id",
        back_populates="target_file",
    )
