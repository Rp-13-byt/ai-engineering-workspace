import uuid
from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

from ai_workspace_api.core.models import RepositoryStatus


class RepositoryImportRequest(BaseModel):
    owner: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=160)
    provider: str = "github"


class RepositoryRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    provider: str
    owner: str
    name: str
    default_branch: str
    remote_url: HttpUrl | str
    indexing_status: RepositoryStatus
    last_indexed_commit: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RepositoryListResponse(BaseModel):
    items: list[RepositoryRead]
    total: int
    limit: int
    offset: int


class ReindexResponse(BaseModel):
    repository_id: uuid.UUID
    status: RepositoryStatus
    job_idempotency_key: str


class RepositorySnapshotRead(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    branch: str
    commit_sha: str
    documents_count: int
    chunks_count: int
    total_size_bytes: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    metadata_json: dict

    model_config = {"from_attributes": True}


class RepositoryBranchRead(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    name: str
    last_commit_sha: str
    is_default: bool
    last_indexed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
