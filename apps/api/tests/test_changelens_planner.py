"""Unit tests for ChangeLens Budget-Aware Regression Test Planner."""

import uuid

from ai_workspace_api.modules.changelens.models import (
    ChangedFile,
    ChangedSymbol,
    DiffAnalysisResult,
    FileChangeType,
)
from ai_workspace_api.modules.changelens.reachability import ReachabilityAssessment
from ai_workspace_api.modules.changelens.test_selection import (
    BudgetAwareTestPlanner,
    ExecutionBudget,
    SelectionMode,
    TestCandidate,
    TestTier,
)


def _make_dummy_diff(
    files: list[ChangedFile] | None = None,
    symbols: list[ChangedSymbol] | None = None,
    added: int = 50,
    deleted: int = 10,
) -> DiffAnalysisResult:
    if files is None:
        file_paths = {s.file_path for s in (symbols or [])}
        files = [ChangedFile(path=fp, change_type=FileChangeType.MODIFIED) for fp in file_paths]
    return DiffAnalysisResult(
        repository_id=uuid.uuid4(),
        base_sha="base_123",
        head_sha="head_456",
        files=files,
        changed_symbols=symbols or [],
        total_added_lines=added,
        total_deleted_lines=deleted,
    )


def test_models_and_budget_instantiation():
    """Verify execution budget defaults and model properties across selection modes."""
    fast_budget = ExecutionBudget.for_mode(SelectionMode.FAST_FEEDBACK)
    assert fast_budget.max_duration_seconds == 300.0
    assert fast_budget.max_tests == 10

    balanced_budget = ExecutionBudget.for_mode(SelectionMode.BALANCED)
    assert balanced_budget.max_duration_seconds == 900.0
    assert balanced_budget.max_tests == 25

    full_budget = ExecutionBudget.for_mode(SelectionMode.FULL_REGRESSION)
    assert full_budget.max_duration_seconds == float("inf")
    assert full_budget.max_tests >= 99999

    candidate = TestCandidate(
        test_id="tests/test_demo.py::test_case",
        target_file="demo.py",
        estimated_duration_seconds=1.5,
        tier=TestTier.CRITICAL,
        covered_node_ids=["demo.py:process"],
        priority_score=95.0,
        selection_reason="Direct critical target",
    )
    assert candidate.tier == TestTier.CRITICAL
    assert candidate.estimated_duration_seconds == 1.5


def test_greedy_test_prioritization_and_blast_radius():
    """Verify prioritization weighting awards higher score to critical targets and blast radius."""
    planner = BudgetAwareTestPlanner(
        test_index={
            "core.py:critical_func": ["tests/test_core.py::test_critical"],
            "core.py:normal_func": ["tests/test_core.py::test_normal"],
        },
        test_durations={
            "tests/test_core.py::test_critical": 1.0,
            "tests/test_core.py::test_normal": 1.0,
        },
    )

    crit_file = ChangedFile(
        path="core.py",
        change_type=FileChangeType.MODIFIED,
        is_security_sensitive=True,
    )
    norm_file = ChangedFile(
        path="utils.py",
        change_type=FileChangeType.MODIFIED,
    )

    crit_sym = ChangedSymbol(
        name="critical_func",
        symbol_type="function",
        file_path="core.py",
        start_line=10,
        end_line=20,
    )
    norm_sym = ChangedSymbol(
        name="normal_func",
        symbol_type="function",
        file_path="utils.py",
        start_line=30,
        end_line=40,
    )
    diff = _make_dummy_diff(files=[crit_file, norm_file], symbols=[crit_sym, norm_sym])

    reachability = ReachabilityAssessment(
        changed_node_ids=["core.py:critical_func"],
        total_affected_count=5,
        direct_dependents_count=2,
        indirect_dependents_count=3,
        max_reach_depth=2,
        blast_radius_score=15.0,
    )

    result = planner.plan_tests(diff=diff, reachability=reachability, mode=SelectionMode.BALANCED)
    assert len(result.selected_tests) >= 1
    # Critical test should be ranked first
    assert result.selected_tests[0].test_id == "tests/test_core.py::test_critical"
    assert result.selected_tests[0].tier == TestTier.CRITICAL


def test_fast_feedback_mode_enforces_budget_limit():
    """Verify FAST_FEEDBACK mode enforces max_tests constraint and partitions omitted tests."""
    test_index = {}
    test_durations = {}
    symbols = []
    files = []
    for i in range(15):
        sname = f"func_{i}"
        fpath = f"mod_{i}.py"
        tid = f"tests/test_mod_{i}.py::test_run"
        test_index[f"{fpath}:{sname}"] = [tid]
        test_durations[tid] = 1.0
        files.append(
            ChangedFile(
                path=fpath,
                change_type=FileChangeType.MODIFIED,
                is_api_route=(i == 0),
            )
        )
        symbols.append(
            ChangedSymbol(
                name=sname,
                symbol_type="function",
                file_path=fpath,
                start_line=10,
                end_line=20,
            )
        )

    planner = BudgetAwareTestPlanner(test_index=test_index, test_durations=test_durations)
    diff = _make_dummy_diff(files=files, symbols=symbols)

    result = planner.plan_tests(diff=diff, mode=SelectionMode.FAST_FEEDBACK)
    assert len(result.selected_tests) == 10  # Capped at 10
    assert len(result.omitted_tests) == 5
    assert result.total_estimated_duration_seconds == 10.0
    # First selected test must be the critical path symbol
    assert result.selected_tests[0].test_id == "tests/test_mod_0.py::test_run"
    assert result.selected_tests[0].tier == TestTier.CRITICAL


def test_balanced_and_full_regression_modes():
    """Verify balanced mode accepts up to 25 tests, while full regression has zero omissions."""
    test_index = {}
    test_durations = {}
    symbols = []
    for i in range(20):
        sname = f"sym_{i}"
        tid = f"tests/test_all.py::test_{i}"
        test_index[f"all.py:{sname}"] = [tid]
        test_durations[tid] = 2.0
        symbols.append(
            ChangedSymbol(
                name=sname,
                symbol_type="function",
                file_path="all.py",
                start_line=i * 5,
                end_line=(i * 5) + 3,
            )
        )

    planner = BudgetAwareTestPlanner(test_index=test_index, test_durations=test_durations)
    diff = _make_dummy_diff(symbols=symbols)

    # Balanced mode
    balanced_res = planner.plan_tests(diff=diff, mode=SelectionMode.BALANCED)
    assert len(balanced_res.selected_tests) == 20
    assert len(balanced_res.omitted_tests) == 0

    # Full regression mode
    full_res = planner.plan_tests(diff=diff, mode=SelectionMode.FULL_REGRESSION)
    assert len(full_res.selected_tests) == 20
    assert len(full_res.omitted_tests) == 0
    assert full_res.coverage_ratio == 1.0


def test_fallback_to_smoke_suite_when_unmapped():
    """Verify fallback mechanism activates smoke tests when changes have no mapped unit tests."""
    unmapped_file = ChangedFile(
        path="hidden/internal.py",
        change_type=FileChangeType.MODIFIED,
    )
    unmapped_sym = ChangedSymbol(
        name="internal_helper",
        symbol_type="function",
        file_path="hidden/internal.py",
        start_line=1,
        end_line=10,
    )
    diff = _make_dummy_diff(files=[unmapped_file], symbols=[unmapped_sym])

    smoke_suite = [
        "tests/test_smoke.py::test_api_healthcheck",
        "tests/test_smoke.py::test_db_ping",
    ]
    planner = BudgetAwareTestPlanner(
        test_index={},  # No tests mapped
        smoke_tests=smoke_suite,
    )

    result = planner.plan_tests(diff=diff, mode=SelectionMode.FAST_FEEDBACK)
    assert result.fallback_triggered is True
    assert result.fallback_reason is not None
    assert "falling back to smoke suite" in result.fallback_reason
    assert len(result.selected_tests) == 2
    assert result.selected_tests[0].test_id == smoke_suite[0]
    assert result.selected_tests[0].tier == TestTier.SMOKE
