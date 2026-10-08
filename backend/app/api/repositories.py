import logging
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.chunk import CodeChunk
from app.models.dependency import Dependency
from app.models.file import File
from app.models.ingestion_job import IngestionJob
from app.models.repository import Repository
from app.models.symbol import CodeSymbol
from app.schemas.file import FileListResponse, FileResponse
from app.schemas.ingestion import IngestionJobResponse, IngestionTriggerResponse
from app.schemas.intelligence import (
    ChunkListResponse,
    ChunkResponse,
    DependencyEdge,
    DependencyGraphResponse,
    DependencyNode,
    FileContentResponse,
    ImpactResponse,
    QueryCitationResponse,
    QueryRequest,
    QueryResponse,
    SearchItemResponse,
    SearchRequest,
    SearchResponse,
    SymbolListResponse,
    SymbolResponse,
)
from app.schemas.repository import RepositoryCreate, RepositoryResponse
from app.services.cloner import CloneError
from app.services.dependency_analyzer import analyze_impact
from app.services.github_url import parse_github_url
from app.services.ingestion import ingest_repository
from app.services.search import (
    CodeSearchEngine,
    synthesize_codebase_answer,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_repository_with_file_count(
    repository_id: uuid.UUID,
    session: AsyncSession,
) -> Optional[RepositoryResponse]:
    """Helper to fetch a single repository along with its file count."""
    repo = await session.get(Repository, repository_id)
    if not repo:
        return None

    count_result = await session.execute(
        select(func.count(File.id)).where(File.repository_id == repository_id)
    )
    file_count = count_result.scalar() or 0

    return RepositoryResponse(
        id=repo.id,
        name=repo.name,
        owner=repo.owner,
        url=repo.url,
        default_branch=repo.default_branch,
        description=repo.description,
        language=repo.language,
        status=repo.status,
        created_at=repo.created_at,
        updated_at=repo.updated_at,
        file_count=file_count,
    )


@router.post(
    "",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or import a repository record",
)
async def create_repository(
    payload: RepositoryCreate,
    session: AsyncSession = Depends(get_db),
):
    """Validates the GitHub repository URL and creates a new repository entry
    in PostgreSQL / SQLite. If the repository already exists, returns existing record.
    """
    try:
        parsed = parse_github_url(payload.url)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # Check if repository already exists by URL
    result = await session.execute(
        select(Repository).where(Repository.url == parsed["normalized_url"])
    )
    existing_repo = result.scalars().first()
    if existing_repo:
        logger.info(
            "Repository '%s' already exists with ID %s",
            existing_repo.url,
            existing_repo.id,
        )
        count_res = await session.execute(
            select(func.count(File.id)).where(File.repository_id == existing_repo.id)
        )
        return RepositoryResponse(
            id=existing_repo.id,
            name=existing_repo.name,
            owner=existing_repo.owner,
            url=existing_repo.url,
            default_branch=existing_repo.default_branch,
            description=existing_repo.description,
            language=existing_repo.language,
            status=existing_repo.status,
            created_at=existing_repo.created_at,
            updated_at=existing_repo.updated_at,
            file_count=count_res.scalar() or 0,
        )

    # Create new repository record
    new_repo = Repository(
        name=parsed["name"],
        owner=parsed["owner"],
        url=parsed["normalized_url"],
        default_branch="main",
        status="pending",
    )
    session.add(new_repo)
    await session.commit()
    await session.refresh(new_repo)

    return RepositoryResponse(
        id=new_repo.id,
        name=new_repo.name,
        owner=new_repo.owner,
        url=new_repo.url,
        default_branch=new_repo.default_branch,
        description=new_repo.description,
        language=new_repo.language,
        status=new_repo.status,
        created_at=new_repo.created_at,
        updated_at=new_repo.updated_at,
        file_count=0,
    )


@router.get(
    "",
    response_model=List[RepositoryResponse],
    summary="List all tracked repositories",
)
async def list_repositories(
    session: AsyncSession = Depends(get_db),
):
    """Retrieves all tracked repositories with their file counts, ordered by creation date."""
    stmt = (
        select(
            Repository,
            func.count(File.id).label("file_count"),
        )
        .outerjoin(File, Repository.id == File.repository_id)
        .group_by(Repository.id)
        .order_by(Repository.created_at.desc())
    )
    result = await session.execute(stmt)
    rows = result.all()

    response_list: List[RepositoryResponse] = []
    for repo, count in rows:
        response_list.append(
            RepositoryResponse(
                id=repo.id,
                name=repo.name,
                owner=repo.owner,
                url=repo.url,
                default_branch=repo.default_branch,
                description=repo.description,
                language=repo.language,
                status=repo.status,
                created_at=repo.created_at,
                updated_at=repo.updated_at,
                file_count=count,
            )
        )
    return response_list


@router.get(
    "/{repository_id}",
    response_model=RepositoryResponse,
    summary="Get repository details by ID",
)
async def get_repository(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Fetches details for a single repository by UUID."""
    repo_response = await get_repository_with_file_count(repository_id, session)
    if not repo_response:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID '{repository_id}' not found.",
        )
    return repo_response


@router.post(
    "/{repository_id}/ingest",
    response_model=IngestionTriggerResponse,
    summary="Trigger repository ingestion",
)
async def trigger_ingestion(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Triggers the full ingestion pipeline: clone, scan, parse AST, extract symbols,
    create chunks, analyze dependencies, and store in database.
    """
    repo = await session.get(Repository, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID '{repository_id}' not found.",
        )

    try:
        result = await ingest_repository(repository_id, session)
        return IngestionTriggerResponse(
            repository_id=result.repository_id,
            job_id=result.job_id,
            status=result.status,
            files_indexed=result.files_indexed,
            symbols_indexed=result.symbols_indexed,
            chunks_indexed=result.chunks_indexed,
            dependencies_indexed=result.dependencies_indexed,
            primary_language=result.primary_language,
        )
    except CloneError as clone_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(clone_err),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ingestion failed: {exc}",
        )


@router.get(
    "/{repository_id}/files",
    response_model=FileListResponse,
    summary="List files scanned in a repository",
)
async def list_repository_files(
    repository_id: uuid.UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Optional path substring search"),
    session: AsyncSession = Depends(get_db),
):
    """Retrieves paginated list of scanned files for the repository."""
    repo = await session.get(Repository, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID '{repository_id}' not found.",
        )

    base_query = select(File).where(File.repository_id == repository_id)
    if search:
        base_query = base_query.where(File.path.ilike(f"%{search.strip()}%"))

    count_stmt = select(func.count()).select_from(base_query.subquery())
    total_count = (await session.execute(count_stmt)).scalar() or 0

    files_stmt = base_query.order_by(File.path.asc()).offset(offset).limit(limit)
    files_result = (await session.execute(files_stmt)).scalars().all()

    return FileListResponse(
        total=total_count,
        limit=limit,
        offset=offset,
        files=[FileResponse.model_validate(f) for f in files_result],
    )


@router.get(
    "/{repository_id}/files/{file_id}/content",
    response_model=FileContentResponse,
    summary="Get source code content of a specific file",
)
async def get_file_content(
    repository_id: uuid.UUID,
    file_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Retrieves the source content of a file reconstructed from indexed chunks."""
    file_rec = await session.get(File, file_id)
    if not file_rec or file_rec.repository_id != repository_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File with ID '{file_id}' not found.",
        )

    chunks_stmt = (
        select(CodeChunk)
        .where(CodeChunk.file_id == file_id)
        .order_by(CodeChunk.chunk_index.asc(), CodeChunk.start_line.asc())
    )
    chunks = (await session.execute(chunks_stmt)).scalars().all()

    # If chunks exist, combine their contents or use first full chunk
    if chunks:
        # Check if chunks are structural pieces or sequential
        content = "\n".join(c.content.rstrip("\r\n") for c in chunks)
    else:
        content = "// File content not indexed or empty."

    return FileContentResponse(
        id=file_rec.id,
        path=file_rec.path,
        language=file_rec.language,
        size_bytes=file_rec.size_bytes,
        content=content,
    )


@router.get(
    "/{repository_id}/symbols",
    response_model=SymbolListResponse,
    summary="List extracted code symbols (classes, functions, methods)",
)
async def list_repository_symbols(
    repository_id: uuid.UUID,
    file_id: Optional[uuid.UUID] = Query(None, description="Filter by file ID"),
    kind: Optional[str] = Query(None, description="Filter by kind: class, function, method, interface"),
    search: Optional[str] = Query(None, description="Search symbol name"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """Returns paginated extracted AST symbols for the repository."""
    repo = await session.get(Repository, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID '{repository_id}' not found.",
        )

    base_query = (
        select(CodeSymbol, File.path)
        .join(File, CodeSymbol.file_id == File.id)
        .where(CodeSymbol.repository_id == repository_id)
    )

    if file_id:
        base_query = base_query.where(CodeSymbol.file_id == file_id)
    if kind:
        base_query = base_query.where(CodeSymbol.kind == kind.lower().strip())
    if search:
        base_query = base_query.where(CodeSymbol.name.ilike(f"%{search.strip()}%"))

    count_stmt = select(func.count()).select_from(base_query.subquery())
    total_count = (await session.execute(count_stmt)).scalar() or 0

    results_stmt = base_query.order_by(File.path.asc(), CodeSymbol.line_start.asc()).offset(offset).limit(limit)
    rows = (await session.execute(results_stmt)).all()

    symbols_out = []
    for sym, f_path in rows:
        symbols_out.append(
            SymbolResponse(
                id=sym.id,
                repository_id=sym.repository_id,
                file_id=sym.file_id,
                file_path=f_path,
                parent_symbol_id=sym.parent_symbol_id,
                name=sym.name,
                kind=sym.kind,
                line_start=sym.line_start,
                line_end=sym.line_end,
                signature=sym.signature,
                docstring=sym.docstring,
                created_at=sym.created_at,
            )
        )

    return SymbolListResponse(
        total=total_count,
        limit=limit,
        offset=offset,
        symbols=symbols_out,
    )


@router.get(
    "/{repository_id}/chunks",
    response_model=ChunkListResponse,
    summary="List code chunks",
)
async def list_repository_chunks(
    repository_id: uuid.UUID,
    file_id: Optional[uuid.UUID] = Query(None, description="Filter by file ID"),
    search: Optional[str] = Query(None, description="Content search"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    """Retrieves paginated structural code chunks."""
    repo = await session.get(Repository, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID '{repository_id}' not found.",
        )

    base_query = (
        select(CodeChunk, File.path, CodeSymbol.name)
        .join(File, CodeChunk.file_id == File.id)
        .outerjoin(CodeSymbol, CodeChunk.symbol_id == CodeSymbol.id)
        .where(CodeChunk.repository_id == repository_id)
    )

    if file_id:
        base_query = base_query.where(CodeChunk.file_id == file_id)
    if search:
        base_query = base_query.where(CodeChunk.content.ilike(f"%{search.strip()}%"))

    count_stmt = select(func.count()).select_from(base_query.subquery())
    total_count = (await session.execute(count_stmt)).scalar() or 0

    stmt = base_query.order_by(File.path.asc(), CodeChunk.start_line.asc()).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).all()

    chunks_out = []
    for chunk, f_path, sym_name in rows:
        chunks_out.append(
            ChunkResponse(
                id=chunk.id,
                repository_id=chunk.repository_id,
                file_id=chunk.file_id,
                file_path=f_path,
                symbol_id=chunk.symbol_id,
                symbol_name=sym_name,
                content=chunk.content,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                chunk_index=chunk.chunk_index,
                created_at=chunk.created_at,
            )
        )

    return ChunkListResponse(
        total=total_count,
        limit=limit,
        offset=offset,
        chunks=chunks_out,
    )


@router.get(
    "/{repository_id}/dependencies",
    response_model=DependencyGraphResponse,
    summary="Get full dependency graph (nodes and edges)",
)
async def get_dependency_graph(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Builds and returns the dependency graph for visual explorer."""
    repo = await session.get(Repository, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID '{repository_id}' not found.",
        )

    # 1. Fetch files to construct nodes
    files_stmt = select(File).where(File.repository_id == repository_id)
    files = (await session.execute(files_stmt)).scalars().all()
    file_map = {f.id: f for f in files}

    nodes: List[DependencyNode] = []
    node_ids: set = set()
    for f in files:
        nodes.append(
            DependencyNode(
                id=f.path,
                label=f.path.split("/")[-1],
                type="file",
                language=f.language,
            )
        )
        node_ids.add(f.path)

    # 2. Fetch dependencies to construct edges
    deps_stmt = select(Dependency).where(Dependency.repository_id == repository_id)
    deps = (await session.execute(deps_stmt)).scalars().all()

    edges: List[DependencyEdge] = []
    for d in deps:
        src_file = file_map.get(d.source_file_id)
        if not src_file:
            continue
        tgt_file = file_map.get(d.target_file_id) if d.target_file_id else None

        target_node_id = tgt_file.path if tgt_file else (d.target_symbol_name or "external")
        if target_node_id not in node_ids:
            nodes.append(
                DependencyNode(
                    id=target_node_id,
                    label=target_node_id,
                    type="symbol" if tgt_file is None else "file",
                )
            )
            node_ids.add(target_node_id)

        edges.append(
            DependencyEdge(
                source=src_file.path,
                target=target_node_id,
                type=d.dependency_type,
                symbol_name=d.target_symbol_name,
            )
        )

    return DependencyGraphResponse(
        repository_id=repository_id,
        nodes=nodes,
        edges=edges,
        total_dependencies=len(edges),
    )


@router.get(
    "/{repository_id}/impact",
    response_model=ImpactResponse,
    summary="Analyze impact of modifying a symbol or file",
)
async def get_impact_analysis(
    repository_id: uuid.UUID,
    target: str = Query(..., description="File path (e.g. app/main.py) or symbol name (e.g. Repository)"),
    session: AsyncSession = Depends(get_db),
):
    """Analyzes the cascading impact across the dependency graph if a file or symbol is changed."""
    repo = await session.get(Repository, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID '{repository_id}' not found.",
        )

    # Fetch all dependencies and files
    files_stmt = select(File).where(File.repository_id == repository_id)
    files = (await session.execute(files_stmt)).scalars().all()
    file_map = {f.id: f.path for f in files}

    deps_stmt = select(Dependency).where(Dependency.repository_id == repository_id)
    deps = (await session.execute(deps_stmt)).scalars().all()

    dep_dicts = []
    for d in deps:
        dep_dicts.append(
            {
                "source_file": file_map.get(d.source_file_id, ""),
                "target_file": file_map.get(d.target_file_id, "") if d.target_file_id else None,
                "target_symbol": d.target_symbol_name,
                "type": d.dependency_type,
            }
        )

    report = analyze_impact(target, dep_dicts)

    return ImpactResponse(
        target=report.target,
        target_type=report.target_type,
        direct_dependents=report.direct_dependents,
        indirect_dependents=report.indirect_dependents,
        affected_files=report.affected_files,
        impact_level=report.impact_level,
        summary=report.summary,
    )


@router.post(
    "/{repository_id}/search",
    response_model=SearchResponse,
    summary="Search codebase using hybrid semantic ranking",
)
async def search_codebase(
    repository_id: uuid.UUID,
    payload: SearchRequest,
    session: AsyncSession = Depends(get_db),
):
    """Performs hybrid lexical and symbol search across all indexed chunks."""
    repo = await session.get(Repository, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID '{repository_id}' not found.",
        )

    chunks_stmt = (
        select(CodeChunk, File.path, File.language, CodeSymbol.name)
        .join(File, CodeChunk.file_id == File.id)
        .outerjoin(CodeSymbol, CodeChunk.symbol_id == CodeSymbol.id)
        .where(CodeChunk.repository_id == repository_id)
    )
    rows = (await session.execute(chunks_stmt)).all()

    chunks_data = [
        {
            "id": c.id,
            "file_id": c.file_id,
            "file_path": f_path,
            "language": lang,
            "symbol_name": sym_name,
            "content": c.content,
            "start_line": c.start_line,
            "end_line": c.end_line,
        }
        for c, f_path, lang, sym_name in rows
    ]

    engine = CodeSearchEngine(chunks_data)
    results = engine.search(payload.query, top_k=payload.limit)

    return SearchResponse(
        query=payload.query,
        total_results=len(results),
        results=[
            SearchItemResponse(
                chunk_id=r.chunk_id,
                file_id=r.file_id,
                file_path=r.file_path,
                symbol_name=r.symbol_name,
                content=r.content,
                start_line=r.start_line,
                end_line=r.end_line,
                score=r.score,
                language=r.language,
            )
            for r in results
        ],
    )


@router.post(
    "/{repository_id}/ask",
    response_model=QueryResponse,
    summary="Ask a question about the repository using AI Codebase Intelligence",
)
async def ask_codebase(
    repository_id: uuid.UUID,
    payload: QueryRequest,
    session: AsyncSession = Depends(get_db),
):
    """Answers a developer question about the repository using context retrieval
    across code chunks, symbols, and dependencies.
    """
    repo = await session.get(Repository, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID '{repository_id}' not found.",
        )

    # 1. Fetch chunks
    chunks_stmt = (
        select(CodeChunk, File.path, File.language, CodeSymbol.name)
        .join(File, CodeChunk.file_id == File.id)
        .outerjoin(CodeSymbol, CodeChunk.symbol_id == CodeSymbol.id)
        .where(CodeChunk.repository_id == repository_id)
    )
    rows = (await session.execute(chunks_stmt)).all()

    chunks_data = [
        {
            "id": c.id,
            "file_id": c.file_id,
            "file_path": f_path,
            "language": lang,
            "symbol_name": sym_name,
            "content": c.content,
            "start_line": c.start_line,
            "end_line": c.end_line,
        }
        for c, f_path, lang, sym_name in rows
    ]

    engine = CodeSearchEngine(chunks_data)
    search_results = engine.search(payload.question, top_k=6)

    # 2. Fetch files and dependencies
    files_stmt = select(File).where(File.repository_id == repository_id)
    files = (await session.execute(files_stmt)).scalars().all()
    file_map = {f.id: f.path for f in files}

    deps_stmt = select(Dependency).where(Dependency.repository_id == repository_id)
    deps = (await session.execute(deps_stmt)).scalars().all()

    dep_dicts = [
        {
            "source_file": file_map.get(d.source_file_id, ""),
            "target_file": file_map.get(d.target_file_id, "") if d.target_file_id else None,
            "target_symbol": d.target_symbol_name,
            "type": d.dependency_type,
        }
        for d in deps
    ]

    # 3. Synthesize answer
    answer = synthesize_codebase_answer(
        question=payload.question,
        search_results=search_results,
        all_symbols=[],
        dependencies=dep_dicts,
    )

    return QueryResponse(
        question=answer.question,
        answer=answer.answer,
        citations=[
            QueryCitationResponse(
                file_path=c.file_path,
                start_line=c.start_line,
                end_line=c.end_line,
                symbol_name=c.symbol_name,
                snippet=c.snippet,
            )
            for c in answer.citations
        ],
        related_symbols=answer.related_symbols,
        confidence=answer.confidence,
    )


@router.get(
    "/{repository_id}/jobs",
    response_model=List[IngestionJobResponse],
    summary="List ingestion job history for a repository",
)
async def list_ingestion_jobs(
    repository_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Returns the history of ingestion jobs for this repository."""
    repo = await session.get(Repository, repository_id)
    if not repo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repository with ID '{repository_id}' not found.",
        )

    stmt = (
        select(IngestionJob)
        .where(IngestionJob.repository_id == repository_id)
        .order_by(IngestionJob.created_at.desc())
    )
    jobs = (await session.execute(stmt)).scalars().all()
    return [IngestionJobResponse.model_validate(j) for j in jobs]
