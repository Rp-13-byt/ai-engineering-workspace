import uuid

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    repository_id: uuid.UUID
    query: str = Field(min_length=2, max_length=2000)
    limit: int = Field(default=8, ge=1, le=20)


class SearchResult(BaseModel):
    path: str
    start_line: int
    end_line: int
    content: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchResult]
    cached: bool = False
