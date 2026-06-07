import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class PullRequestGenerateRequest(BaseModel):
    repository_id: uuid.UUID
    instructions: str = Field(min_length=5, max_length=6000)
    open_on_github: bool = False


class PullRequestDraftRead(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    title: str
    body: str
    branch_name: str
    diff: str
    status: str
    github_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
