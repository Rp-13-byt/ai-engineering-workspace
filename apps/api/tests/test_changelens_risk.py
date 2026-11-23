import uuid

from ai_workspace_api.modules.changelens.history_analysis import HistoryAnalysisResult
from ai_workspace_api.modules.changelens.models import (
    ChangedFile,
    ChangedSymbol,
    DiffAnalysisResult,
    FileChangeType,
)
from ai_workspace_api.modules.changelens.reachability import ReachabilityAssessment
from ai_workspace_api.modules.changelens.risk_engine import (
    ChangeRiskEngine,
    RiskLevel,
)


def _make_dummy_diff(
    files: list[ChangedFile],
    symbols: list[ChangedSymbol] | None = None,
    added: int = 10,
    deleted: int = 2,
) -> DiffAnalysisResult:
    return DiffAnalysisResult(
        repository_id=uuid.uuid4(),
        base_sha="base123",
        head_sha="head456",
        files=files,
        changed_symbols=symbols or [],
        total_added_lines=added,
        total_deleted_lines=deleted,
    )


def test_low_risk_evaluation_for_small_safe_change() -> None:
    file = ChangedFile(path="src/utils/math.py", change_type=FileChangeType.MODIFIED)
    diff = _make_dummy_diff([file], added=5, deleted=1)

    reach = ReachabilityAssessment(
        changed_node_ids=["src/utils/math.py"],
        total_affected_count=2,
        direct_dependents_count=1,
        indirect_dependents_count=1,
        max_reach_depth=1,
        blast_radius_score=4.0,
    )

    history = HistoryAnalysisResult(
        target_files=["src/utils/math.py"],
        file_churn={},
        frequently_co_changed_files=[],
        historical_commits_examined=20,
        is_shallow_history=False,
        history_confidence=0.95,
        history_risk_score=2.0,
    )

    engine = ChangeRiskEngine()
    result = engine.evaluate_risk(diff, reachability=reach, history=history, mapped_tests_count=2)

    assert result.risk_level == RiskLevel.LOW
    assert result.overall_risk_score < 30.0
    assert result.confidence >= 0.9
    assert result.requires_human_approval is False
    assert len(result.dimensions) == 6


def test_critical_risk_when_migrations_and_breaking_changes_present() -> None:
    f_mig = ChangedFile(
        path="alembic/versions/0005_audit.py",
        change_type=FileChangeType.ADDED,
        is_migration=True,
    )
    f_sec = ChangedFile(
        path="src/core/security.py",
        change_type=FileChangeType.MODIFIED,
        is_security_sensitive=True,
    )
    sym_deleted = ChangedSymbol(
        name="verify_jwt_token",
        symbol_type="function",
        file_path="src/core/security.py",
        start_line=10,
        end_line=25,
        change_nature="deleted",
    )

    diff = _make_dummy_diff([f_mig, f_sec], symbols=[sym_deleted], added=200, deleted=50)

    reach = ReachabilityAssessment(
        changed_node_ids=["src/core/security.py"],
        total_affected_count=15,
        direct_dependents_count=5,
        indirect_dependents_count=10,
        max_reach_depth=3,
        blast_radius_score=22.0,
    )

    engine = ChangeRiskEngine()
    result = engine.evaluate_risk(diff, reachability=reach, mapped_tests_count=0)

    assert result.requires_human_approval is True
    assert len(result.breaking_indicators) >= 1
    assert "verify_jwt_token" in result.breaking_indicators[0]
    assert result.overall_risk_score >= 60.0


def test_confidence_is_separated_from_risk_score() -> None:
    file = ChangedFile(path="src/calc.py", change_type=FileChangeType.MODIFIED)
    diff = _make_dummy_diff([file])

    # No reachability or history provided
    engine = ChangeRiskEngine()
    result = engine.evaluate_risk(diff, reachability=None, history=None)

    # Score should be a distinct deterministic value, while confidence is severely dampened
    assert result.confidence <= 0.5
    assert len(result.assumptions_and_unknowns) >= 2
    assert any("reachability unperformed" in u.lower() for u in result.assumptions_and_unknowns)


def test_risk_dimensions_sum_to_overall_score() -> None:
    file = ChangedFile(path="src/service.py", change_type=FileChangeType.MODIFIED)
    diff = _make_dummy_diff([file], added=20, deleted=5)

    engine = ChangeRiskEngine()
    result = engine.evaluate_risk(diff)

    assert len(result.dimensions) == 6
    calculated_sum = sum(d.score for d in result.dimensions)
    assert result.overall_risk_score == round(calculated_sum, 1)
