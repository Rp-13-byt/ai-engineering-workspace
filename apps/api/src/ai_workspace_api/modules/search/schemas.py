import uuid

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    repository_id: uuid.UUID
    query: str = Field(min_length=1, max_length=2000)
    limit: int = Field(default=8, ge=1, le=20)
    exact_symbol: str | None = None


class SearchResult(BaseModel):
    path: str
    start_line: int
    end_line: int
    content: str
    score: float
    symbol: str | None = None
    symbol_type: str | None = None
    parent_scope: str | None = None


class SearchResponse(BaseModel):
    results: list[SearchResult]
    cached: bool = False
