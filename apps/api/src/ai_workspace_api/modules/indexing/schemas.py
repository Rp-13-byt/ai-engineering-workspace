import uuid
from datetime import datetime

from pydantic import BaseModel

from ai_workspace_api.core.models import RepositoryStatus


class IndexingStatusResponse(BaseModel):
    repository_id: uuid.UUID
    status: RepositoryStatus
    last_indexed_commit: str | None
    updated_at: datetime


class IndexingStats(BaseModel):
    documents_indexed: int
    chunks_indexed: int
    skipped_files: int
    deleted_files: int = 0
    is_incremental: bool = False
