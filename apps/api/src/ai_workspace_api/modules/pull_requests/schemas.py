import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class PullRequestGenerateRequest(BaseModel):
    repository_id: uuid.UUID
    instructions: str = Field(min_length=5, max_length=6000)
    open_on_github: bool = False


class PullRequestApprovalRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str = Field(min_length=3, max_length=2000)
    open_on_github: bool = True


class PullRequestDraftRead(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    title: str
    body: str
    branch_name: str
    diff: str
    status: str
    github_url: str | None
    approval_status: str
    labels_json: list[str]
    risk_assessment_json: dict
    policy_evaluation_json: dict
    security_scan_json: dict
    approval_history_json: list[dict]
    governance_metadata_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}
