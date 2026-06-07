import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from ai_workspace_api.core.models import TaskStatus


class TaskCreateRequest(BaseModel):
    repository_id: uuid.UUID
    title: str = Field(min_length=2, max_length=240)
    description: str = Field(default="", max_length=8000)
    assignee_id: uuid.UUID | None = None
    priority: int = Field(default=3, ge=1, le=5)


class TaskUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=8000)
    status: TaskStatus | None = None
    assignee_id: uuid.UUID | None = None
    priority: int | None = Field(default=None, ge=1, le=5)


class TaskRead(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    assignee_id: uuid.UUID | None
    title: str
    description: str
    status: TaskStatus
    priority: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    items: list[TaskRead]
    total: int
    limit: int
    offset: int
