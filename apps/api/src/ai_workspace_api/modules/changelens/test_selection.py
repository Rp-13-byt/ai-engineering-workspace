"""ChangeLens Budget-Aware Regression Test Selection & Planning Engine."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class SelectionMode(str, enum.Enum):
    FAST_FEEDBACK = "fast_feedback"      # Max 5 min / 10 tests, top blast radius only
    BALANCED = "balanced"                # Max 15 min / 25 tests, direct + reachability
    FULL_REGRESSION = "full_regression"  # Unlimited budget, all reachable tests


class TestTier(str, enum.Enum):
    CRITICAL = "critical"
    DIRECT = "direct"
    TRANSITIVE = "transitive"
    HISTORICAL_FLAKY = "historical_flaky"
    SMOKE = "smoke"


@dataclass(frozen=True)
class ExecutionBudget:
    max_duration_seconds: float = 300.0
    max_tests: int = 15
    min_critical_coverage: float = 1.0
    fail_on_missing_coverage: bool = False

    @classmethod
    def for_mode(cls, mode: SelectionMode) -> ExecutionBudget:
        if mode == SelectionMode.FAST_FEEDBACK:
            return cls(max_duration_seconds=300.0, max_tests=10, min_critical_coverage=1.0)
        elif mode == SelectionMode.BALANCED:
            return cls(max_duration_seconds=900.0, max_tests=25, min_critical_coverage=1.0)
        else:
            return cls(max_duration_seconds=float("inf"), max_tests=999999, min_critical_coverage=1.0)


@dataclass(frozen=True)
class TestCandidate:
    test_id: str
    target_file: str
    estimated_duration_seconds: float = 1.0
    tier: TestTier = TestTier.DIRECT
    covered_node_ids: list[str] = field(default_factory=list)
    priority_score: float = 0.0
    selection_reason: str = ""


@dataclass(frozen=True)
class TestPlanResult:
    mode: SelectionMode
    budget: ExecutionBudget
    selected_tests: list[TestCandidate] = field(default_factory=list)
    omitted_tests: list[TestCandidate] = field(default_factory=list)
    total_estimated_duration_seconds: float = 0.0
    covered_symbol_count: int = 0
    total_symbol_count: int = 0
    coverage_ratio: float = 0.0
    fallback_triggered: bool = False
    fallback_reason: str | None = None
