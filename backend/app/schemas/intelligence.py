import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict


class SymbolResponse(BaseModel):
    """Schema for a code symbol."""

    id: uuid.UUID
    repository_id: uuid.UUID
    file_id: uuid.UUID
    file_path: Optional[str] = None
    parent_symbol_id: Optional[uuid.UUID] = None
    name: str
    kind: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    docstring: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SymbolListResponse(BaseModel):
    """Paginated or filtered list of code symbols."""

    total: int
    limit: int
    offset: int
    symbols: List[SymbolResponse]


class ChunkResponse(BaseModel):
    """Schema for a code chunk."""

    id: uuid.UUID
    repository_id: uuid.UUID
    file_id: uuid.UUID
    file_path: Optional[str] = None
    symbol_id: Optional[uuid.UUID] = None
    symbol_name: Optional[str] = None
    content: str
    start_line: int
    end_line: int
    chunk_index: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChunkListResponse(BaseModel):
    """Paginated list of code chunks."""

    total: int
    limit: int
    offset: int
    chunks: List[ChunkResponse]


class DependencyNode(BaseModel):
    """A node in the dependency graph (either a file or a symbol)."""

    id: str
    label: str
    type: str  # "file" or "symbol"
    language: Optional[str] = None


class DependencyEdge(BaseModel):
    """A directed edge in the dependency graph."""

    source: str
    target: str
    type: str  # "import", "call", "inheritance"
    symbol_name: Optional[str] = None


class DependencyGraphResponse(BaseModel):
    """Full dependency graph with nodes and edges."""

    repository_id: uuid.UUID
    nodes: List[DependencyNode]
    edges: List[DependencyEdge]
    total_dependencies: int


class ImpactResponse(BaseModel):
    """Impact analysis report for a changed symbol or file."""

    target: str
    target_type: str
    direct_dependents: List[str]
    indirect_dependents: List[str]
    affected_files: List[str]
    impact_level: str
    summary: str


class SearchRequest(BaseModel):
    """Request for code search across repository."""

    query: str
    limit: int = 10


class SearchItemResponse(BaseModel):
    """A search result item."""

    chunk_id: str
    file_id: str
    file_path: str
    symbol_name: Optional[str] = None
    content: str
    start_line: int
    end_line: int
    score: float
    language: Optional[str] = None


class SearchResponse(BaseModel):
    """Search results response."""

    query: str
    total_results: int
    results: List[SearchItemResponse]


class QueryRequest(BaseModel):
    """Natural language question about repository."""

    question: str


class QueryCitationResponse(BaseModel):
    """Citation of code reference in an answer."""

    file_path: str
    start_line: int
    end_line: int
    symbol_name: Optional[str] = None
    snippet: str


class QueryResponse(BaseModel):
    """Structured AI answer to codebase question."""

    question: str
    answer: str
    citations: List[QueryCitationResponse]
    related_symbols: List[str]
    confidence: float


class FileContentResponse(BaseModel):
    """Content and metadata for a specific file."""

    id: uuid.UUID
    path: str
    language: Optional[str] = None
    size_bytes: Optional[int] = None
    content: str
