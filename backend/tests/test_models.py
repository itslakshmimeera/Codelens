import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.repository import Repository
from app.models.file import File
from app.models.symbol import CodeSymbol
from app.models.chunk import CodeChunk
from app.models.dependency import Dependency
from app.models.ingestion_job import IngestionJob


@pytest.mark.asyncio
async def test_create_repository(db_session: AsyncSession):
    """Verifies creating a Repository entity with UUID primary key and default values."""
    repo = Repository(
        name="fastapi",
        owner="tiangolo",
        url="https://github.com/tiangolo/fastapi",
        description="FastAPI framework, high performance, easy to learn.",
        language="Python",
    )
    db_session.add(repo)
    await db_session.commit()
    await db_session.refresh(repo)

    assert repo.id is not None
    assert isinstance(repo.id, uuid.UUID)
    assert repo.name == "fastapi"
    assert repo.owner == "tiangolo"
    assert repo.default_branch == "main"
    assert repo.status == "pending"
    assert repo.created_at is not None
    assert repo.updated_at is not None


@pytest.mark.asyncio
async def test_repository_and_file_relationship(db_session: AsyncSession):
    """Verifies creating a File associated with a Repository."""
    repo = Repository(
        name="requests",
        owner="psf",
        url="https://github.com/psf/requests",
    )
    db_session.add(repo)
    await db_session.commit()
    await db_session.refresh(repo)

    file_record = File(
        repository_id=repo.id,
        path="src/requests/api.py",
        language="Python",
        size_bytes=10240,
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    db_session.add(file_record)
    await db_session.commit()
    await db_session.refresh(file_record)

    assert file_record.id is not None
    assert file_record.repository_id == repo.id
    assert file_record.path == "src/requests/api.py"


@pytest.mark.asyncio
async def test_symbol_hierarchy(db_session: AsyncSession):
    """Verifies creating CodeSymbol entities including parent-child hierarchy."""
    repo = Repository(
        name="flask",
        owner="pallets",
        url="https://github.com/pallets/flask",
    )
    db_session.add(repo)
    await db_session.flush()

    file_record = File(
        repository_id=repo.id,
        path="src/flask/app.py",
        language="Python",
    )
    db_session.add(file_record)
    await db_session.flush()

    parent_class = CodeSymbol(
        repository_id=repo.id,
        file_id=file_record.id,
        name="Flask",
        kind="class",
        line_start=50,
        line_end=500,
        signature="class Flask(App):",
        docstring="The flask object implements a WSGI application.",
    )
    db_session.add(parent_class)
    await db_session.flush()

    child_method = CodeSymbol(
        repository_id=repo.id,
        file_id=file_record.id,
        parent_symbol_id=parent_class.id,
        name="route",
        kind="method",
        line_start=120,
        line_end=150,
        signature="def route(self, rule: str, **options: Any):",
    )
    db_session.add(child_method)
    await db_session.commit()
    await db_session.refresh(child_method)

    assert child_method.parent_symbol_id == parent_class.id
    assert child_method.name == "route"
    assert child_method.kind == "method"


@pytest.mark.asyncio
async def test_code_chunk_and_dependency(db_session: AsyncSession):
    """Verifies creating CodeChunk and Dependency entities."""
    repo = Repository(
        name="uvicorn",
        owner="encode",
        url="https://github.com/encode/uvicorn",
    )
    db_session.add(repo)
    await db_session.flush()

    file_record = File(
        repository_id=repo.id,
        path="uvicorn/main.py",
        language="Python",
    )
    db_session.add(file_record)
    await db_session.flush()

    chunk = CodeChunk(
        repository_id=repo.id,
        file_id=file_record.id,
        content="async def run():\n    pass",
        start_line=1,
        end_line=2,
        chunk_index=0,
    )
    dep = Dependency(
        repository_id=repo.id,
        source_file_id=file_record.id,
        target_symbol_name="Config",
        dependency_type="import",
    )
    job = IngestionJob(
        repository_id=repo.id,
        status="in_progress",
    )

    db_session.add_all([chunk, dep, job])
    await db_session.commit()

    assert chunk.id is not None
    assert dep.id is not None
    assert job.id is not None
    assert job.status == "in_progress"


@pytest.mark.asyncio
async def test_cascade_delete(db_session: AsyncSession):
    """Verifies that deleting a Repository cascades to all associated files, symbols, chunks, dependencies, and jobs."""
    repo = Repository(
        name="django",
        owner="django",
        url="https://github.com/django/django",
    )
    db_session.add(repo)
    await db_session.flush()

    file_record = File(
        repository_id=repo.id,
        path="django/core/handlers/wsgi.py",
    )
    db_session.add(file_record)
    await db_session.flush()

    sym = CodeSymbol(
        repository_id=repo.id,
        file_id=file_record.id,
        name="WSGIHandler",
        kind="class",
        line_start=1,
        line_end=100,
    )
    chunk = CodeChunk(
        repository_id=repo.id,
        file_id=file_record.id,
        content="class WSGIHandler: pass",
        start_line=1,
        end_line=100,
    )
    dep = Dependency(
        repository_id=repo.id,
        source_file_id=file_record.id,
        target_symbol_name="base",
        dependency_type="import",
    )
    job = IngestionJob(
        repository_id=repo.id,
        status="completed",
    )
    db_session.add_all([sym, chunk, dep, job])
    await db_session.commit()

    # Delete the repository
    await db_session.delete(repo)
    await db_session.commit()

    # Assert that all related records are removed
    files_result = await db_session.execute(select(File).where(File.repository_id == repo.id))
    assert files_result.scalars().all() == []

    symbols_result = await db_session.execute(select(CodeSymbol).where(CodeSymbol.repository_id == repo.id))
    assert symbols_result.scalars().all() == []

    chunks_result = await db_session.execute(select(CodeChunk).where(CodeChunk.repository_id == repo.id))
    assert chunks_result.scalars().all() == []

    deps_result = await db_session.execute(select(Dependency).where(Dependency.repository_id == repo.id))
    assert deps_result.scalars().all() == []

    jobs_result = await db_session.execute(select(IngestionJob).where(IngestionJob.repository_id == repo.id))
    assert jobs_result.scalars().all() == []
