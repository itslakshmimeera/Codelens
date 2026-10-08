import os
import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import File
from app.models.ingestion_job import IngestionJob
from app.models.repository import Repository
from app.services.cloner import CloneError


@pytest.mark.asyncio
async def test_create_repository_endpoint_success(async_client: AsyncClient):
    """Verifies importing a repository via valid GitHub URL."""
    payload = {"url": "https://github.com/encode/uvicorn"}
    response = await async_client.post("/repositories", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "uvicorn"
    assert data["owner"] == "encode"
    assert data["url"] == "https://github.com/encode/uvicorn"
    assert data["status"] == "pending"
    assert data["file_count"] == 0
    assert "id" in data


@pytest.mark.asyncio
async def test_create_repository_endpoint_invalid_url(async_client: AsyncClient):
    """Verifies that invalid repository URLs return HTTP 400."""
    invalid_urls = [
        {"url": "not-a-url"},
        {"url": "https://gitlab.com/owner/repo"},
        {"url": "https://github.com/onlyowner"},
    ]
    for payload in invalid_urls:
        response = await async_client.post("/repositories", json=payload)
        assert response.status_code == 400
        assert "detail" in response.json()


@pytest.mark.asyncio
async def test_create_duplicate_repository_returns_existing(async_client: AsyncClient):
    """Verifies that importing an already existing repository returns the existing record safely."""
    payload = {"url": "https://github.com/psf/black"}
    first_res = await async_client.post("/repositories", json=payload)
    assert first_res.status_code == 201
    first_id = first_res.json()["id"]

    second_res = await async_client.post("/repositories", json=payload)
    assert second_res.status_code in (200, 201)
    assert second_res.json()["id"] == first_id


@pytest.mark.asyncio
async def test_get_repositories_and_single_repo(async_client: AsyncClient):
    """Verifies listing repositories and retrieving by ID."""
    # Create two repositories
    await async_client.post("/repositories", json={"url": "https://github.com/pallets/click"})
    res2 = await async_client.post("/repositories", json={"url": "https://github.com/pallets/jinja"})
    repo2_id = res2.json()["id"]

    # List all
    list_res = await async_client.get("/repositories")
    assert list_res.status_code == 200
    repo_list = list_res.json()
    assert len(repo_list) >= 2

    # Get single repo
    get_res = await async_client.get(f"/repositories/{repo2_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == repo2_id
    assert get_res.json()["name"] == "jinja"

    # Get non-existent repo
    unknown_id = str(uuid.uuid4())
    not_found_res = await async_client.get(f"/repositories/{unknown_id}")
    assert not_found_res.status_code == 404


@pytest.mark.asyncio
async def test_repository_ingestion_success(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    """Verifies end-to-end repository ingestion with file discovery,

    metadata extraction, and database persistence.
    """
    # 1. Create repository
    create_res = await async_client.post(
        "/repositories", json={"url": "https://github.com/test-org/test-repo"}
    )
    repo_id = create_res.json()["id"]

    # 2. Mock clone_repository to populate files in target_dir
    def mock_clone(repo_url, target_dir, timeout_seconds=120, branch=None):
        # Create valid source files
        os.makedirs(os.path.join(target_dir, "src"), exist_ok=True)
        with open(os.path.join(target_dir, "main.py"), "w") as f:
            f.write("def run(): pass\n")
        with open(os.path.join(target_dir, "src", "app.py"), "w") as f:
            f.write("print('hello')\n")
        with open(os.path.join(target_dir, "README.md"), "w") as f:
            f.write("# Test Repo\n")
        # Ignored items
        os.makedirs(os.path.join(target_dir, "node_modules"), exist_ok=True)
        with open(os.path.join(target_dir, "node_modules", "skip.js"), "w") as f:
            f.write("skip\n")
        with open(os.path.join(target_dir, ".env"), "w") as f:
            f.write("SECRET=123\n")

    monkeypatch.setattr("app.services.ingestion.clone_repository", mock_clone)

    # 3. Trigger ingestion
    ingest_res = await async_client.post(f"/repositories/{repo_id}/ingest")
    assert ingest_res.status_code == 200
    ingest_data = ingest_res.json()
    assert ingest_data["status"] == "completed"
    assert ingest_data["files_indexed"] == 3
    assert ingest_data["primary_language"] == "Python"

    # 4. Verify database state
    repo_db = await db_session.get(Repository, uuid.UUID(repo_id))
    assert repo_db is not None
    assert repo_db.status == "completed"
    assert repo_db.language == "Python"

    # Verify File records
    files_result = await db_session.execute(
        select(File).where(File.repository_id == uuid.UUID(repo_id))
    )
    files = files_result.scalars().all()
    assert len(files) == 3
    file_paths = {f.path for f in files}
    assert file_paths == {"main.py", "src/app.py", "README.md"}

    # 5. Verify /files API endpoint
    files_res = await async_client.get(f"/repositories/{repo_id}/files")
    assert files_res.status_code == 200
    files_data = files_res.json()
    assert files_data["total"] == 3
    assert len(files_data["files"]) == 3

    # Verify search in files endpoint
    search_res = await async_client.get(f"/repositories/{repo_id}/files?search=src")
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total"] == 1
    assert search_data["files"][0]["path"] == "src/app.py"

    # 6. Verify repeated ingestion does not crash and cleans up old files
    repeat_res = await async_client.post(f"/repositories/{repo_id}/ingest")
    assert repeat_res.status_code == 200
    assert repeat_res.json()["files_indexed"] == 3

    # 7. Verify ingestion jobs endpoint
    jobs_res = await async_client.get(f"/repositories/{repo_id}/jobs")
    assert jobs_res.status_code == 200
    jobs = jobs_res.json()
    assert len(jobs) == 2
    assert jobs[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_repository_ingestion_failure(
    async_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch,
):
    """Verifies that clone failures mark the IngestionJob and Repository as failed cleanly."""
    create_res = await async_client.post(
        "/repositories", json={"url": "https://github.com/fail-org/fail-repo"}
    )
    repo_id = create_res.json()["id"]

    def mock_clone_fail(repo_url, target_dir, timeout_seconds=120, branch=None):
        raise CloneError("Repository not found or private repository")

    monkeypatch.setattr("app.services.ingestion.clone_repository", mock_clone_fail)

    ingest_res = await async_client.post(f"/repositories/{repo_id}/ingest")
    assert ingest_res.status_code == 400
    assert "private repository" in ingest_res.json()["detail"].lower()

    # Verify repository status is 'failed'
    repo_db = await db_session.get(Repository, uuid.UUID(repo_id))
    assert repo_db is not None
    assert repo_db.status == "failed"

    # Verify IngestionJob status is 'failed'
    jobs_res = await async_client.get(f"/repositories/{repo_id}/jobs")
    assert jobs_res.status_code == 200
    jobs = jobs_res.json()
    assert len(jobs) == 1
    assert jobs[0]["status"] == "failed"
    assert "private repository" in jobs[0]["error_message"].lower()
