"""Repository layer for persisting and querying ChangeLens risk analyses and test plans."""

from __future__ import annotations

import dataclasses
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import desc, select
from sqlalchemy.orm import selectinload

from ai_workspace_api.core.models import ChangeAnalysis, ChangeFinding, ChangeTestPlan

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from ai_workspace_api.modules.changelens.risk_engine import RiskAssessmentResult
    from ai_workspace_api.modules.changelens.test_selection import TestPlanResult


class ChangeLensRepository:
    """Async repository for persisting and querying ChangeLens analyses, findings, and test plans."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_analysis(
        self,
        repository_id: uuid.UUID,
        base_sha: str,
        head_sha: str,
        risk_result: RiskAssessmentResult,
        blast_radius: int = 0,
        test_plan: TestPlanResult | None = None,
        pr_number: int | None = None,
        findings: list[dict[str, Any]] | None = None,
    ) -> ChangeAnalysis:
        """Persists a complete ChangeAnalysis with optional findings and test plan."""
        dimensions_data = [
            {
                "name": d.name,
                "score": d.score,
                "max_score": d.max_score,
                "explanation": d.explanation,
                "evidence": list(d.evidence),
            }
            for d in risk_result.dimensions
        ]

        metadata_data = {
            "breaking_indicators": list(risk_result.breaking_indicators),
            "assumptions_and_unknowns": list(risk_result.assumptions_and_unknowns),
            "requires_human_approval": risk_result.requires_human_approval,
        }

        analysis = ChangeAnalysis(
            repository_id=repository_id,
            base_sha=base_sha,
            head_sha=head_sha,
            pr_number=pr_number,
            risk_score=risk_result.overall_risk_score,
            risk_level=risk_result.risk_level.value,
            confidence_score=risk_result.confidence,
            blast_radius=blast_radius,
            summary=risk_result.summary_explanation,
            dimensions_json=dimensions_data,
            metadata_json=metadata_data,
        )
        self.session.add(analysis)
        await self.session.flush()

        # Persist explicit findings
        if findings:
            for f_item in findings:
                finding = ChangeFinding(
                    analysis_id=analysis.id,
                    category=str(f_item.get("category", "general")),
                    severity=str(f_item.get("severity", "warning")),
                    file_path=str(f_item.get("file_path", "unknown")),
                    symbol_name=f_item.get("symbol_name"),
                    message=str(f_item.get("message", "")),
                    evidence_json=dict(f_item.get("evidence", {})),
                )
                self.session.add(finding)
        elif risk_result.breaking_indicators:
            for indicator in risk_result.breaking_indicators:
                finding = ChangeFinding(
                    analysis_id=analysis.id,
                    category="breaking_change",
                    severity="high",
                    file_path="repository",
                    symbol_name=None,
                    message=indicator,
                    evidence_json={"source": "risk_engine"},
                )
                self.session.add(finding)

        # Persist test plan if provided
        if test_plan is not None:
            selected_json = [dataclasses.asdict(t) for t in test_plan.selected_tests]
            omitted_json = [dataclasses.asdict(t) for t in test_plan.omitted_tests]
            # Convert enum tier values to strings for JSONB serialization
            for item in selected_json + omitted_json:
                if "tier" in item and hasattr(item["tier"], "value"):
                    item["tier"] = item["tier"].value

            plan_record = ChangeTestPlan(
                analysis_id=analysis.id,
                selection_mode=test_plan.mode.value,
                selected_tests_json=selected_json,
                omitted_tests_json=omitted_json,
                estimated_duration_seconds=test_plan.total_estimated_duration_seconds,
                coverage_ratio=test_plan.coverage_ratio,
                fallback_triggered=test_plan.fallback_triggered,
                fallback_reason=test_plan.fallback_reason,
            )
            self.session.add(plan_record)

        await self.session.flush()
        return analysis

    async def get_analysis_by_id(self, analysis_id: uuid.UUID) -> ChangeAnalysis | None:
        """Retrieves a ChangeAnalysis by its UUID with findings and test plans eager-loaded."""
        stmt = (
            select(ChangeAnalysis)
            .where(ChangeAnalysis.id == analysis_id)
            .options(
                selectinload(ChangeAnalysis.findings),
                selectinload(ChangeAnalysis.test_plans),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_for_commits(
        self,
        repository_id: uuid.UUID,
        base_sha: str,
        head_sha: str,
    ) -> ChangeAnalysis | None:
        """Fetches the most recent ChangeAnalysis for a specific commit pair in a repository."""
        stmt = (
            select(ChangeAnalysis)
            .where(
                ChangeAnalysis.repository_id == repository_id,
                ChangeAnalysis.base_sha == base_sha,
                ChangeAnalysis.head_sha == head_sha,
            )
            .order_by(desc(ChangeAnalysis.created_at))
            .limit(1)
            .options(
                selectinload(ChangeAnalysis.findings),
                selectinload(ChangeAnalysis.test_plans),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_recent_for_repository(
        self,
        repository_id: uuid.UUID,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ChangeAnalysis]:
        """Lists recent ChangeAnalysis records for a given repository."""
        stmt = (
            select(ChangeAnalysis)
            .where(ChangeAnalysis.repository_id == repository_id)
            .order_by(desc(ChangeAnalysis.created_at))
            .limit(limit)
            .offset(offset)
            .options(
                selectinload(ChangeAnalysis.findings),
                selectinload(ChangeAnalysis.test_plans),
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def delete_analysis(self, analysis_id: uuid.UUID) -> bool:
        """Deletes a ChangeAnalysis record by ID. Returns True if found and deleted."""
        analysis = await self.get_analysis_by_id(analysis_id)
        if analysis is None:
            return False
        await self.session.delete(analysis)
        await self.session.flush()
        return True
