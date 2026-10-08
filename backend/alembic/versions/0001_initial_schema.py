"""Initial database schema for CodeLens

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-08-21 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. repositories table
    op.create_table(
        "repositories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("default_branch", sa.String(length=100), server_default="main", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("language", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", name="uq_repositories_url"),
    )
    op.create_index(op.f("ix_repositories_name"), "repositories", ["name"], unique=False)
    op.create_index(op.f("ix_repositories_owner"), "repositories", ["owner"], unique=False)

    # 2. files table
    op.create_table(
        "files",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("language", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("repository_id", "path", name="uq_repo_file_path"),
    )
    op.create_index(op.f("ix_files_path"), "files", ["path"], unique=False)
    op.create_index(op.f("ix_files_repository_id"), "files", ["repository_id"], unique=False)

    # 3. code_symbols table
    op.create_table(
        "code_symbols",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("parent_symbol_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("docstring", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_symbol_id"], ["code_symbols.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_code_symbols_file_id"), "code_symbols", ["file_id"], unique=False)
    op.create_index(op.f("ix_code_symbols_kind"), "code_symbols", ["kind"], unique=False)
    op.create_index(op.f("ix_code_symbols_name"), "code_symbols", ["name"], unique=False)
    op.create_index(op.f("ix_code_symbols_parent_symbol_id"), "code_symbols", ["parent_symbol_id"], unique=False)
    op.create_index(op.f("ix_code_symbols_repository_id"), "code_symbols", ["repository_id"], unique=False)

    # 4. code_chunks table
    op.create_table(
        "code_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("file_id", sa.Uuid(), nullable=False),
        sa.Column("symbol_id", sa.Uuid(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=False),
        sa.Column("end_line", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["symbol_id"], ["code_symbols.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_code_chunks_file_id"), "code_chunks", ["file_id"], unique=False)
    op.create_index(op.f("ix_code_chunks_repository_id"), "code_chunks", ["repository_id"], unique=False)
    op.create_index(op.f("ix_code_chunks_symbol_id"), "code_chunks", ["symbol_id"], unique=False)

    # 5. dependencies table
    op.create_table(
        "dependencies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("source_file_id", sa.Uuid(), nullable=False),
        sa.Column("target_file_id", sa.Uuid(), nullable=True),
        sa.Column("source_symbol_id", sa.Uuid(), nullable=True),
        sa.Column("target_symbol_name", sa.String(length=255), nullable=True),
        sa.Column("dependency_type", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_file_id"], ["files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_symbol_id"], ["code_symbols.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_file_id"], ["files.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dependencies_dependency_type"), "dependencies", ["dependency_type"], unique=False)
    op.create_index(op.f("ix_dependencies_repository_id"), "dependencies", ["repository_id"], unique=False)
    op.create_index(op.f("ix_dependencies_source_file_id"), "dependencies", ["source_file_id"], unique=False)
    op.create_index(op.f("ix_dependencies_source_symbol_id"), "dependencies", ["source_symbol_id"], unique=False)
    op.create_index(op.f("ix_dependencies_target_file_id"), "dependencies", ["target_file_id"], unique=False)
    op.create_index(op.f("ix_dependencies_target_symbol_name"), "dependencies", ["target_symbol_name"], unique=False)

    # 6. ingestion_jobs table
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("repository_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="queued", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["repository_id"], ["repositories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ingestion_jobs_repository_id"), "ingestion_jobs", ["repository_id"], unique=False)
    op.create_index(op.f("ix_ingestion_jobs_status"), "ingestion_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("ingestion_jobs")
    op.drop_table("dependencies")
    op.drop_table("code_chunks")
    op.drop_table("code_symbols")
    op.drop_table("files")
    op.drop_table("repositories")
