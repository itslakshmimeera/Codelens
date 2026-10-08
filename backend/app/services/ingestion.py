import logging
import os
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chunk import CodeChunk
from app.models.dependency import Dependency
from app.models.file import File
from app.models.ingestion_job import IngestionJob
from app.models.repository import Repository
from app.models.symbol import CodeSymbol
from app.services.chunker import chunk_file_content
from app.services.cloner import CloneError, cleanup_directory, clone_repository
from app.services.dependency_analyzer import DependencyAnalyzer
from app.services.parser import ExtractedSymbol, ParseResult, parse_file
from app.services.scanner import ScanResult, scan_repository

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result summary of a repository ingestion run."""

    repository_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    files_indexed: int
    symbols_indexed: int = 0
    chunks_indexed: int = 0
    dependencies_indexed: int = 0
    primary_language: Optional[str] = None
    error_message: Optional[str] = None


async def ingest_repository(
    repository_id: uuid.UUID,
    session: AsyncSession,
) -> IngestionResult:
    """Coordinates the full repository ingestion and code intelligence pipeline:

    1. Checks repository record existence.
    2. Spawns an IngestionJob record in 'running' state.
    3. Clones the repository into an isolated temporary directory.
    4. Recursively scans the files, filtering ignored and binary artifacts.
    5. Cleans up previous files, symbols, chunks, and dependencies.
    6. Persists new File records into database.
    7. Parses AST and extracts CodeSymbols (classes, functions, methods, interfaces).
    8. Divides source code into structural CodeChunks for retrieval.
    9. Analyzes and resolves cross-file Dependencies.
    10. Updates repository and IngestionJob statuses.
    11. Guaranteed cleanup of disk workspace in finally block.
    """
    repo = await session.get(Repository, repository_id)
    if not repo:
        raise ValueError(f"Repository with ID '{repository_id}' does not exist.")

    # Create ingestion job record
    job = IngestionJob(
        repository_id=repo.id,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    session.add(job)
    repo.status = "ingesting"
    await session.commit()
    await session.refresh(job)
    await session.refresh(repo)

    temp_dir = tempfile.mkdtemp(prefix=f"codelens_repo_{repo.name}_")
    scan_result: Optional[ScanResult] = None

    try:
        logger.info(
            "Starting ingestion for repository '%s/%s' (%s)",
            repo.owner,
            repo.name,
            repo.url,
        )

        # Step 1: Clone repository
        clone_repository(
            repo_url=repo.url,
            target_dir=temp_dir,
            branch=repo.default_branch if repo.default_branch != "main" else None,
        )

        # Step 2: Scan repository source files
        scan_result = scan_repository(temp_dir)
        logger.info(
            "Repository '%s/%s' scanned: %d files discovered (%d ignored).",
            repo.owner,
            repo.name,
            scan_result.total_scanned,
            scan_result.total_ignored,
        )

        # Step 3: Handle duplicate/repeated ingestion safely by removing old file records
        # Note: cascade delete removes related symbols, chunks, and dependencies
        await session.execute(
            delete(File).where(File.repository_id == repo.id)
        )

        # Step 4: Persist discovered files in batch and flush to assign UUIDs
        file_map: Dict[str, File] = {}
        for scanned in scan_result.files:
            file_rec = File(
                repository_id=repo.id,
                path=scanned.path,
                language=scanned.language,
                size_bytes=scanned.size_bytes,
                content_hash=scanned.content_hash,
            )
            session.add(file_rec)
            file_map[scanned.path] = file_rec

        await session.flush()

        # Step 5: Parse source code files, extract symbols, create chunks
        all_symbols: List[CodeSymbol] = []
        all_chunks: List[CodeChunk] = []
        parsed_results: Dict[str, ParseResult] = {}
        symbol_name_to_id: Dict[str, uuid.UUID] = {}

        for scanned in scan_result.files:
            file_rec = file_map[scanned.path]
            disk_path = os.path.join(temp_dir, scanned.path.replace("/", os.sep))

            content = ""
            try:
                with open(disk_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception as e:
                logger.debug("Could not read file %s: %s", scanned.path, e)
                continue

            # Parse symbols and structure
            parse_res = parse_file(content, scanned.language)
            parsed_results[scanned.path] = parse_res

            file_symbols: List[CodeSymbol] = []
            for sym in parse_res.symbols:
                sym_rec = CodeSymbol(
                    repository_id=repo.id,
                    file_id=file_rec.id,
                    name=sym.name,
                    kind=sym.kind,
                    line_start=sym.line_start,
                    line_end=sym.line_end,
                    signature=sym.signature,
                    docstring=sym.docstring,
                )
                session.add(sym_rec)
                file_symbols.append(sym_rec)

            await session.flush()

            for sym_rec in file_symbols:
                symbol_name_to_id[f"{scanned.path}:{sym_rec.name}"] = sym_rec.id
                all_symbols.append(sym_rec)

            # Process child symbols (e.g. methods within classes)
            for sym in parse_res.symbols:
                parent_id = symbol_name_to_id.get(f"{scanned.path}:{sym.name}")
                if parent_id and sym.children:
                    for child in sym.children:
                        child_rec = CodeSymbol(
                            repository_id=repo.id,
                            file_id=file_rec.id,
                            parent_symbol_id=parent_id,
                            name=child.name,
                            kind=child.kind,
                            line_start=child.line_start,
                            line_end=child.line_end,
                            signature=child.signature,
                            docstring=child.docstring,
                        )
                        session.add(child_rec)
                        all_symbols.append(child_rec)

            await session.flush()

            # Create code chunks
            generated_chunks = chunk_file_content(content, parse_res.symbols)
            for chunk_data in generated_chunks:
                sym_id = None
                if chunk_data.symbol_name:
                    sym_id = symbol_name_to_id.get(f"{scanned.path}:{chunk_data.symbol_name}")

                chunk_rec = CodeChunk(
                    repository_id=repo.id,
                    file_id=file_rec.id,
                    symbol_id=sym_id,
                    content=chunk_data.content,
                    start_line=chunk_data.start_line,
                    end_line=chunk_data.end_line,
                    chunk_index=chunk_data.chunk_index,
                )
                session.add(chunk_rec)
                all_chunks.append(chunk_rec)

        await session.flush()

        # Step 6: Analyze cross-file and symbol dependencies
        analyzer = DependencyAnalyzer(list(file_map.keys()))
        all_deps: List[Dependency] = []

        for rel_path, parse_res in parsed_results.items():
            source_file = file_map[rel_path]
            resolved_deps = analyzer.resolve_file_dependencies(
                source_path=rel_path,
                parse_result=parse_res,
                language=source_file.language,
            )

            for dep_item in resolved_deps:
                target_file_rec = file_map.get(dep_item.target_file_path) if dep_item.target_file_path else None
                source_sym_id = None
                if dep_item.source_symbol_name:
                    source_sym_id = symbol_name_to_id.get(f"{rel_path}:{dep_item.source_symbol_name}")

                dep_rec = Dependency(
                    repository_id=repo.id,
                    source_file_id=source_file.id,
                    target_file_id=target_file_rec.id if target_file_rec else None,
                    source_symbol_id=source_sym_id,
                    target_symbol_name=dep_item.target_symbol_name,
                    dependency_type=dep_item.dependency_type,
                )
                session.add(dep_rec)
                all_deps.append(dep_rec)

        # Step 7: Update repository metadata
        repo.status = "completed"
        if scan_result.primary_language:
            repo.language = scan_result.primary_language

        # Step 8: Mark job completed
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.error_message = None

        await session.commit()
        await session.refresh(job)
        await session.refresh(repo)

        return IngestionResult(
            repository_id=repo.id,
            job_id=job.id,
            status="completed",
            files_indexed=scan_result.total_scanned,
            symbols_indexed=len(all_symbols),
            chunks_indexed=len(all_chunks),
            dependencies_indexed=len(all_deps),
            primary_language=scan_result.primary_language,
        )

    except Exception as exc:
        logger.error(
            "Ingestion failed for repository '%s/%s': %s",
            repo.owner,
            repo.name,
            exc,
            exc_info=True,
        )
        await session.rollback()

        # Update status to failed
        repo.status = "failed"
        job.status = "failed"
        job.error_message = str(exc)
        job.completed_at = datetime.now(timezone.utc)

        session.add(repo)
        session.add(job)
        await session.commit()

        raise exc

    finally:
        # Guaranteed cleanup of local workspace directory
        cleanup_directory(temp_dir)
