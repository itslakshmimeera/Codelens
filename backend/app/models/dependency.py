import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.file import File
    from app.models.symbol import CodeSymbol


class Dependency(Base):
    """Represents a directional relationship between files and/or symbols in the codebase."""

    __tablename__ = "dependencies"

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
    source_file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_file_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("files.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_symbol_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("code_symbols.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    target_symbol_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
    )
    dependency_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship(
        "Repository",
        back_populates="dependencies",
    )
    source_file: Mapped["File"] = relationship(
        "File",
        foreign_keys=[source_file_id],
        back_populates="source_dependencies",
    )
    target_file: Mapped[Optional["File"]] = relationship(
        "File",
        foreign_keys=[target_file_id],
        back_populates="target_dependencies",
    )
    source_symbol: Mapped[Optional["CodeSymbol"]] = relationship(
        "CodeSymbol",
        foreign_keys=[source_symbol_id],
        back_populates="source_dependencies",
    )
