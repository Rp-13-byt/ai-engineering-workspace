"""Orchestration service for ChangeLens end-to-end change analysis."""

from __future__ import annotations

import uuid

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.errors import ApiError
from ai_workspace_api.core.models import ChangeAnalysis
from ai_workspace_api.core.repository_scope import get_repository_for_organization
from ai_workspace_api.modules.changelens.diff_analysis import DiffAnalyzer
from ai_workspace_api.modules.changelens.graph_models import ImpactGraph
from ai_workspace_api.modules.changelens.impact_graph import ImpactGraphBuilder
from ai_workspace_api.modules.changelens.reachability import ReachabilityAnalyzer
from ai_workspace_api.modules.changelens.repository import ChangeLensRepository
from ai_workspace_api.modules.changelens.risk_engine import ChangeRiskEngine
from ai_workspace_api.modules.changelens.schemas import (
    ChangeAnalysisListResponse,
    ChangeAnalysisRead,
    ChangeAnalysisRequest,
    ChangeFindingRead,
    ChangeTestPlanRead,
    RiskDimensionRead,
)
from ai_workspace_api.modules.changelens.test_selection import BudgetAwareTestPlanner


class ChangeLensService:
    """Orchestrates diff analysis, impact graph reachability, risk scoring, and test planning."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = ChangeLensRepository(session)
        self.diff_analyzer = DiffAnalyzer()
        self.graph_builder = ImpactGraphBuilder()
        self.reachability_analyzer = ReachabilityAnalyzer()
        self.risk_engine = ChangeRiskEngine()

    @staticmethod
    def _to_read_schema(record: ChangeAnalysis) -> ChangeAnalysisRead:
        dimensions = [RiskDimensionRead(**dim) for dim in (record.dimensions_json or [])]
        metadata = record.metadata_json or {}
        findings = [ChangeFindingRead.model_validate(f) for f in (record.findings or [])]
        test_plans = [ChangeTestPlanRead.model_validate(tp) for tp in (record.test_plans or [])]

        return ChangeAnalysisRead(
            id=record.id,
            repository_id=record.repository_id,
            base_sha=record.base_sha,
            head_sha=record.head_sha,
            pr_number=record.pr_number,
            risk_score=record.risk_score,
            risk_level=record.risk_level,
            confidence_score=record.confidence_score,
            blast_radius=record.blast_radius,
            summary=record.summary,
            dimensions=dimensions,
            breaking_indicators=list(metadata.get("breaking_indicators", [])),
            requires_human_approval=bool(metadata.get("requires_human_approval", False)),
            findings=findings,
            test_plans=test_plans,
            created_at=record.created_at,
        )

    async def analyze_change(
        self,
        payload: ChangeAnalysisRequest,
        organization_id: uuid.UUID,
    ) -> ChangeAnalysisRead:
        """Runs the full ChangeLens pipeline and persists the analysis."""
        await get_repository_for_organization(
            self.session, organization_id, payload.repository_id
        )

        diff_result = self.diff_analyzer.analyze(
            repository_id=payload.repository_id,
            base_sha=payload.base_sha,
            head_sha=payload.head_sha,
            diff_text=payload.diff_text,
            file_contents=payload.file_contents or None,
        )

        graph = (
            self.graph_builder.build_from_files(payload.file_contents)
            if payload.file_contents
            else ImpactGraph()
        )

        changed_node_ids = [f"{s.file_path}:{s.name}" for s in diff_result.changed_symbols]
        if not changed_node_ids:
            changed_node_ids = [f.path for f in diff_result.files]

        reachability = self.reachability_analyzer.analyze_reachability(
            graph=graph,
            changed_node_ids=changed_node_ids,
        )

        planner = BudgetAwareTestPlanner(test_index=payload.test_index)
        test_plan = planner.plan_tests(
            diff=diff_result,
            reachability=reachability,
            graph=graph,
            mode=payload.selection_mode,
        )

        risk_result = self.risk_engine.evaluate_risk(
            diff_result=diff_result,
            reachability=reachability,
            mapped_tests_count=len(test_plan.selected_tests),
        )

        record = await self.repository.save_analysis(
            repository_id=payload.repository_id,
            base_sha=payload.base_sha,
            head_sha=payload.head_sha,
            risk_result=risk_result,
            blast_radius=reachability.total_affected_count,
            test_plan=test_plan,
            pr_number=payload.pr_number,
        )
        await self.session.commit()

        loaded = await self.repository.get_analysis_by_id(record.id)
        return self._to_read_schema(loaded or record)

    async def get_analysis(
        self,
        analysis_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> ChangeAnalysisRead:
        """Retrieves an analysis by ID, verifying organization ownership."""
        record = await self.repository.get_analysis_by_id(analysis_id)
        if record is None:
            raise ApiError("Change analysis not found", status.HTTP_404_NOT_FOUND)

        await get_repository_for_organization(
            self.session, organization_id, record.repository_id
        )
        return self._to_read_schema(record)

    async def list_analyses(
        self,
        repository_id: uuid.UUID,
        organization_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> ChangeAnalysisListResponse:
        """Lists recent analyses for a repository within the caller's organization."""
        await get_repository_for_organization(
            self.session, organization_id, repository_id
        )
        records = await self.repository.list_recent_for_repository(
            repository_id=repository_id,
            limit=limit,
            offset=offset,
        )
        items = [self._to_read_schema(rec) for rec in records]
        return ChangeAnalysisListResponse(items=items, total=len(items))

    async def delete_analysis(
        self,
        analysis_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> None:
        """Deletes an analysis after verifying organization ownership."""
        record = await self.repository.get_analysis_by_id(analysis_id)
        if record is None:
            raise ApiError("Change analysis not found", status.HTTP_404_NOT_FOUND)

        await get_repository_for_organization(
            self.session, organization_id, record.repository_id
        )
        await self.repository.delete_analysis(analysis_id)
        await self.session.commit()
