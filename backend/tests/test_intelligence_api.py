import uuid
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import CodeChunk
from app.models.dependency import Dependency
from app.models.file import File
from app.models.repository import Repository
from app.models.symbol import CodeSymbol


@pytest.mark.asyncio
async def test_intelligence_endpoints(async_client: AsyncClient, db_session: AsyncSession):
    # 1. Setup repository, file, symbols, chunk, dependency
    repo = Repository(
        name="test-repo",
        owner="test-owner",
        url="https://github.com/test-owner/test-repo",
        status="completed",
        language="Python",
    )
    db_session.add(repo)
    await db_session.flush()

    file_rec = File(
        repository_id=repo.id,
        path="app/auth.py",
        language="Python",
        size_bytes=500,
    )
    file_user = File(
        repository_id=repo.id,
        path="app/user.py",
        language="Python",
        size_bytes=600,
    )
    db_session.add_all([file_rec, file_user])
    await db_session.flush()

    sym = CodeSymbol(
        repository_id=repo.id,
        file_id=file_rec.id,
        name="authenticate_user",
        kind="function",
        line_start=10,
        line_end=25,
        signature="def authenticate_user(token: str) -> bool:",
        docstring="Verifies authentication token.",
    )
    db_session.add(sym)
    await db_session.flush()

    chunk = CodeChunk(
        repository_id=repo.id,
        file_id=file_rec.id,
        symbol_id=sym.id,
        content="def authenticate_user(token: str) -> bool:\n    return len(token) > 0\n",
        start_line=10,
        end_line=25,
        chunk_index=0,
    )
    dep = Dependency(
        repository_id=repo.id,
        source_file_id=file_user.id,
        target_file_id=file_rec.id,
        target_symbol_name="authenticate_user",
        dependency_type="import",
    )
    db_session.add_all([chunk, dep])
    await db_session.commit()

    repo_id_str = str(repo.id)
    file_id_str = str(file_rec.id)

    # 2. Test GET /symbols
    sym_res = await async_client.get(f"/repositories/{repo_id_str}/symbols")
    assert sym_res.status_code == 200
    sym_data = sym_res.json()
    assert sym_data["total"] >= 1
    assert sym_data["symbols"][0]["name"] == "authenticate_user"
    assert sym_data["symbols"][0]["kind"] == "function"

    # 3. Test GET /chunks
    chunk_res = await async_client.get(f"/repositories/{repo_id_str}/chunks")
    assert chunk_res.status_code == 200
    chunk_data = chunk_res.json()
    assert chunk_data["total"] >= 1
    assert "authenticate_user" in chunk_data["chunks"][0]["content"]

    # 4. Test GET /files/{id}/content
    content_res = await async_client.get(f"/repositories/{repo_id_str}/files/{file_id_str}/content")
    assert content_res.status_code == 200
    content_data = content_res.json()
    assert "def authenticate_user" in content_data["content"]

    # 5. Test GET /dependencies (graph)
    dep_res = await async_client.get(f"/repositories/{repo_id_str}/dependencies")
    assert dep_res.status_code == 200
    graph_data = dep_res.json()
    assert len(graph_data["nodes"]) >= 2
    assert len(graph_data["edges"]) >= 1

    # 6. Test GET /impact
    impact_res = await async_client.get(f"/repositories/{repo_id_str}/impact?target=app/auth.py")
    assert impact_res.status_code == 200
    impact_data = impact_res.json()
    assert "app/user.py" in impact_data["direct_dependents"]

    # 7. Test POST /search
    search_res = await async_client.post(
        f"/repositories/{repo_id_str}/search",
        json={"query": "authenticate_user token"},
    )
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert search_data["total_results"] >= 1
    assert search_data["results"][0]["symbol_name"] == "authenticate_user"

    # 8. Test POST /ask
    ask_res = await async_client.post(
        f"/repositories/{repo_id_str}/ask",
        json={"question": "Where is user authentication implemented?"},
    )
    assert ask_res.status_code == 200
    ask_data = ask_res.json()
    assert len(ask_data["citations"]) >= 1
    assert ask_data["citations"][0]["file_path"] == "app/auth.py"
    assert "authenticate_user" in ask_data["answer"]
