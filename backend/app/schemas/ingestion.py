import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class IngestionJobResponse(BaseModel):
    """Schema for ingestion job status."""

    id: uuid.UUID
    repository_id: uuid.UUID
    status: str
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IngestionTriggerResponse(BaseModel):
    """Response returned when repository ingestion completes or starts."""

    repository_id: uuid.UUID
    job_id: uuid.UUID
    status: str
    files_indexed: int
    symbols_indexed: int = 0
    chunks_indexed: int = 0
    dependencies_indexed: int = 0
    primary_language: Optional[str] = None
    error_message: Optional[str] = None
