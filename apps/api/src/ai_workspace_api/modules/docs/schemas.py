import uuid

from pydantic import BaseModel, Field


class GenerationRequest(BaseModel):
    repository_id: uuid.UUID
    target: str = Field(min_length=2, max_length=500)


class DocumentationResponse(BaseModel):
    markdown: str


class TestGenerationResponse(BaseModel):
    test_plan: str


class BugFinding(BaseModel):
    path: str
    severity: str
    message: str


class BugDetectionResponse(BaseModel):
    findings: list[BugFinding]
