import uuid
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class FileResponse(BaseModel):
    """File metadata schema."""

    id: uuid.UUID
    repository_id: uuid.UUID
    path: str
    language: Optional[str] = None
    size_bytes: Optional[int] = None
    content_hash: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class FileListResponse(BaseModel):
    """Paginated list of files schema."""

    total: int
    limit: int
    offset: int
    files: List[FileResponse]
