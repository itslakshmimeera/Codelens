import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.file import File
    from app.models.chunk import CodeChunk
    from app.models.dependency import Dependency


class CodeSymbol(Base):
    """Represents an extracted code entity (function, class, method, interface, variable)."""

    __tablename__ = "code_symbols"

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
    file_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_symbol_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("code_symbols.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    line_start: Mapped[int] = mapped_column(Integer, nullable=False)
    line_end: Mapped[int] = mapped_column(Integer, nullable=False)
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    docstring: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    repository: Mapped["Repository"] = relationship(
        "Repository",
        back_populates="symbols",
    )
    file: Mapped["File"] = relationship(
        "File",
        back_populates="symbols",
    )
    parent_symbol: Mapped[Optional["CodeSymbol"]] = relationship(
        "CodeSymbol",
        remote_side=[id],
        back_populates="child_symbols",
    )
    child_symbols: Mapped[List["CodeSymbol"]] = relationship(
        "CodeSymbol",
        back_populates="parent_symbol",
        cascade="all, delete-orphan",
    )
    chunks: Mapped[List["CodeChunk"]] = relationship(
        "CodeChunk",
        back_populates="symbol",
    )
    source_dependencies: Mapped[List["Dependency"]] = relationship(
        "Dependency",
        foreign_keys="Dependency.source_symbol_id",
        back_populates="source_symbol",
    )
