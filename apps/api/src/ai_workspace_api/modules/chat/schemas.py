import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    repository_id: uuid.UUID
    message: str = Field(min_length=2, max_length=8000)
    conversation_id: uuid.UUID | None = None


class Citation(BaseModel):
    path: str
    start_line: int
    end_line: int
    score: float


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    answer: str
    citations: list[Citation]
    created_at: datetime
