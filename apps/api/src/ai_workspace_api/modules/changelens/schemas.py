"""Pydantic schemas for ChangeLens API requests and responses."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ai_workspace_api.modules.changelens.test_selection import SelectionMode


class ChangeAnalysisRequest(BaseModel):
    repository_id: uuid.UUID
    base_sha: str = Field(min_length=1, max_length=64)
    head_sha: str = Field(min_length=1, max_length=64)
    diff_text: str = Field(min_length=1)
    selection_mode: SelectionMode = SelectionMode.BALANCED
    pr_number: int | None = None
    file_contents: dict[str, str] = Field(default_factory=dict)
    test_index: dict[str, list[str]] = Field(default_factory=dict)


class RiskDimensionRead(BaseModel):
    name: str
    score: float
    max_score: float
    explanation: str
    evidence: list[str] = Field(default_factory=list)


class ChangeFindingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    severity: str
    file_path: str
    symbol_name: str | None = None
    message: str
    evidence_json: dict[str, Any] = Field(default_factory=dict)


class ChangeTestPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    selection_mode: str
    selected_tests_json: list[dict[str, Any]] = Field(default_factory=list)
    omitted_tests_json: list[dict[str, Any]] = Field(default_factory=list)
    estimated_duration_seconds: float
    coverage_ratio: float
    fallback_triggered: bool
    fallback_reason: str | None = None


class ChangeAnalysisRead(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    base_sha: str
    head_sha: str
    pr_number: int | None = None
    risk_score: float
    risk_level: str
    confidence_score: float
    blast_radius: int
    summary: str
    dimensions: list[RiskDimensionRead] = Field(default_factory=list)
    breaking_indicators: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False
    findings: list[ChangeFindingRead] = Field(default_factory=list)
    test_plans: list[ChangeTestPlanRead] = Field(default_factory=list)
    created_at: datetime


class ChangeAnalysisListResponse(BaseModel):
    items: list[ChangeAnalysisRead]
    total: int
