import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class RepositoryCreate(BaseModel):
    """Payload for importing/creating a repository."""

    url: str = Field(
        ...,
        description="Public GitHub repository URL (e.g. https://github.com/owner/repo)",
        examples=["https://github.com/fastapi/fastapi"],
    )


class RepositoryResponse(BaseModel):
    """Repository metadata response schema."""

    id: uuid.UUID
    name: str
    owner: str
    url: str
    default_branch: str
    description: Optional[str] = None
    language: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    file_count: int = 0

    model_config = ConfigDict(from_attributes=True)
