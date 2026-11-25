"""Integration tests for ChangeLens repository persistence and Alembic migration 0004."""

import importlib.util
import pathlib
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ai_workspace_api.core.models import ChangeAnalysis, ChangeFinding, ChangeTestPlan
from ai_workspace_api.modules.changelens.repository import ChangeLensRepository
from ai_workspace_api.modules.changelens.risk_engine import (
    RiskAssessmentResult,
    RiskDimension,
    RiskLevel,
)
from ai_workspace_api.modules.changelens.test_selection import (
    ExecutionBudget,
    SelectionMode,
    TestCandidate,
    TestPlanResult,
    TestTier,
)


class FakeAsyncSession:
    """In-memory mock AsyncSession tracking added objects and executing queries."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flushed = False
        self.execute = AsyncMock()

    def add(self, item: Any) -> None:
        if hasattr(item, "id") and item.id is None:
            item.id = uuid.uuid4()
        self.added.append(item)

    async def flush(self) -> None:
        self.flushed = True

    async def delete(self, item: object) -> None:
        self.deleted.append(item)


def _sample_risk_result() -> RiskAssessmentResult:
    return RiskAssessmentResult(
        overall_risk_score=74.5,
        risk_level=RiskLevel.HIGH,
        confidence=0.92,
        dimensions=[
            RiskDimension(
                name="Blast Radius",
                score=20.0,
                max_score=25.0,
                explanation="High downstream impact",
                evidence=["api/routes/auth.py", "services/token.py"],
            )
        ],
        breaking_indicators=["Auth middleware signature modified"],
        assumptions_and_unknowns=[],
        requires_human_approval=True,
        summary_explanation="High-risk auth change impacting 12 symbols.",
    )


def _sample_test_plan() -> TestPlanResult:
    return TestPlanResult(
        mode=SelectionMode.FAST_FEEDBACK,
        budget=ExecutionBudget.for_mode(SelectionMode.FAST_FEEDBACK),
        selected_tests=[
            TestCandidate(
                test_id="tests/test_auth.py::test_login",
                target_file="api/routes/auth.py",
                estimated_duration_seconds=1.5,
                tier=TestTier.CRITICAL,
                covered_node_ids=["api/routes/auth.py:login"],
                priority_score=115.0,
                selection_reason="Critical auth path",
            )
        ],
        omitted_tests=[],
        total_estimated_duration_seconds=1.5,
        covered_symbol_count=1,
        total_symbol_count=1,
        coverage_ratio=1.0,
        fallback_triggered=False,
        fallback_reason=None,
    )


@pytest.mark.asyncio
async def test_save_analysis_persists_analysis_findings_and_test_plan() -> None:
    session = FakeAsyncSession()
    repo = ChangeLensRepository(session)  # type: ignore[arg-type]
    repo_id = uuid.uuid4()

    analysis = await repo.save_analysis(
        repository_id=repo_id,
        base_sha="abc111",
        head_sha="def222",
        risk_result=_sample_risk_result(),
        blast_radius=12,
        test_plan=_sample_test_plan(),
        pr_number=42,
    )

    assert session.flushed is True
    assert isinstance(analysis, ChangeAnalysis)
    assert analysis.repository_id == repo_id
    assert analysis.risk_score == 74.5
    assert analysis.risk_level == "HIGH"
    assert analysis.confidence_score == 0.92
    assert analysis.blast_radius == 12
    assert analysis.pr_number == 42
    assert len(analysis.dimensions_json) == 1
    assert analysis.dimensions_json[0]["name"] == "Blast Radius"
    assert analysis.metadata_json["requires_human_approval"] is True

    # Verify ChangeFinding and ChangeTestPlan were added
    findings = [obj for obj in session.added if isinstance(obj, ChangeFinding)]
    test_plans = [obj for obj in session.added if isinstance(obj, ChangeTestPlan)]
    assert len(findings) == 1
    assert findings[0].category == "breaking_change"
    assert findings[0].message == "Auth middleware signature modified"

    assert len(test_plans) == 1
    assert test_plans[0].selection_mode == "fast_feedback"
    assert test_plans[0].selected_tests_json[0]["tier"] == "critical"
    assert test_plans[0].coverage_ratio == 1.0


@pytest.mark.asyncio
async def test_save_analysis_with_explicit_findings() -> None:
    session = FakeAsyncSession()
    repo = ChangeLensRepository(session)  # type: ignore[arg-type]

    explicit_findings = [
        {
            "category": "missing_tests",
            "severity": "warning",
            "file_path": "core/billing.py",
            "symbol_name": "charge_card",
            "message": "No direct unit test covers charge_card",
            "evidence": {"coverage": 0.0},
        }
    ]

    await repo.save_analysis(
        repository_id=uuid.uuid4(),
        base_sha="111",
        head_sha="222",
        risk_result=_sample_risk_result(),
        findings=explicit_findings,
    )

    findings = [obj for obj in session.added if isinstance(obj, ChangeFinding)]
    assert len(findings) == 1
    assert findings[0].category == "missing_tests"
    assert findings[0].file_path == "core/billing.py"
    assert findings[0].symbol_name == "charge_card"


@pytest.mark.asyncio
async def test_query_and_delete_analysis_methods() -> None:
    session = FakeAsyncSession()
    repo = ChangeLensRepository(session)  # type: ignore[arg-type]

    sample = ChangeAnalysis(
        id=uuid.uuid4(),
        repository_id=uuid.uuid4(),
        base_sha="base",
        head_sha="head",
        risk_score=15.0,
        risk_level="LOW",
        confidence_score=0.85,
        blast_radius=1,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample
    mock_result.scalars.return_value.all.return_value = [sample]
    session.execute.return_value = mock_result

    fetched = await repo.get_analysis_by_id(sample.id)
    assert fetched is sample

    latest = await repo.get_latest_for_commits(sample.repository_id, "base", "head")
    assert latest is sample

    recent = await repo.list_recent_for_repository(sample.repository_id)
    assert len(recent) == 1

    deleted = await repo.delete_analysis(sample.id)
    assert deleted is True
    assert sample in session.deleted

    # Test delete when not found
    mock_result.scalar_one_or_none.return_value = None
    assert await repo.delete_analysis(uuid.uuid4()) is False


def test_alembic_migration_0004_structure() -> None:
    """Verify migration 0004 revision ID length and linkage to 0003."""
    mig_path = (
        pathlib.Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0004_changelens_schema.py"
    )
    assert mig_path.exists()

    spec = importlib.util.spec_from_file_location("mig_0004", mig_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.revision == "0004_changelens_schema"
    assert len(module.revision) <= 32
    assert module.down_revision == "0003_hybrid_retrieval"
    assert callable(module.upgrade)
    assert callable(module.downgrade)
