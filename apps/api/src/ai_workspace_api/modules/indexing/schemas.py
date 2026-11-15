import uuid
from datetime import datetime

from pydantic import BaseModel

from ai_workspace_api.core.models import RepositoryStatus


class IndexingStatusResponse(BaseModel):
    repository_id: uuid.UUID
    status: RepositoryStatus
    last_indexed_commit: str | None
    embedding_model: str | None = None
    updated_at: datetime


class IndexingStats(BaseModel):
    documents_indexed: int
    chunks_indexed: int
    skipped_files: int
    unchanged_files: int = 0
    modified_files: int = 0
    added_files: int = 0
    deleted_files: int = 0
