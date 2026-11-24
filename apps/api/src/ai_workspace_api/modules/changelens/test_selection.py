"""ChangeLens Budget-Aware Regression Test Selection & Planning Engine."""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ai_workspace_api.modules.changelens.graph_models import ImpactGraph
    from ai_workspace_api.modules.changelens.models import DiffAnalysisResult
    from ai_workspace_api.modules.changelens.reachability import ReachabilityAssessment


class SelectionMode(str, enum.Enum):
    FAST_FEEDBACK = "fast_feedback"      # Max 5 min / 10 tests, top blast radius only
    BALANCED = "balanced"                # Max 15 min / 25 tests, direct + reachability
    FULL_REGRESSION = "full_regression"  # Unlimited budget, all reachable tests


class TestTier(str, enum.Enum):
    __test__ = False
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
    __test__ = False
    test_id: str
    target_file: str
    estimated_duration_seconds: float = 1.0
    tier: TestTier = TestTier.DIRECT
    covered_node_ids: list[str] = field(default_factory=list)
    priority_score: float = 0.0
    selection_reason: str = ""


@dataclass(frozen=True)
class TestPlanResult:
    __test__ = False
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


class BudgetAwareTestPlanner:
    """Calculates prioritized regression test plans constrained by execution budget and blast radius."""

    def __init__(
        self,
        test_index: dict[str, list[str]] | None = None,
        test_durations: dict[str, float] | None = None,
        smoke_tests: list[str] | None = None,
    ) -> None:
        self.test_index = test_index or {}
        self.test_durations = test_durations or {}
        self.smoke_tests = smoke_tests or [
            "tests/test_smoke.py::test_api_healthcheck",
            "tests/test_smoke.py::test_database_ping",
        ]

    def _compute_candidate_priority(
        self,
        test_id: str,
        target_file: str,
        tier: TestTier,
        covered_nodes: list[str],
        duration: float,
        blast_radius: int = 0,
        is_critical: bool = False,
    ) -> float:
        """Determines deterministic priority score normalized by time efficiency and impact."""
        tier_weights = {
            TestTier.CRITICAL: 100.0,
            TestTier.DIRECT: 60.0,
            TestTier.TRANSITIVE: 30.0,
            TestTier.HISTORICAL_FLAKY: 20.0,
            TestTier.SMOKE: 10.0,
        }
        base = tier_weights.get(tier, 20.0)
        if is_critical:
            base += 40.0

        # Blast radius bonus: scaled up to 30.0 points
        blast_bonus = min(blast_radius, 15) * 2.0

        # Coverage breadth bonus: up to 25.0 points
        breadth_bonus = min(len(covered_nodes) * 5.0, 25.0)

        raw_score = base + blast_bonus + breadth_bonus

        # Time-efficiency normalization: prefer tests delivering higher coverage per unit time
        efficiency = raw_score / math.sqrt(max(duration, 0.5))
        return round(efficiency, 2)

    def _find_tests_for_symbol_or_file(self, file_path: str, symbol_name: str | None = None) -> list[str]:
        """Resolves test candidates mapped to the given file path or symbol."""
        tests: list[str] = []
        if symbol_name:
            qualified = f"{file_path}:{symbol_name}"
            if qualified in self.test_index:
                tests.extend(self.test_index[qualified])
            if symbol_name in self.test_index:
                tests.extend(self.test_index[symbol_name])
        if file_path in self.test_index:
            tests.extend(self.test_index[file_path])

        # Convention fallback if unindexed
        if not tests:
            base_name = file_path.split("/")[-1].replace(".py", "")
            for cand in [f"tests/test_{base_name}.py", f"tests/test_changelens_{base_name}.py"]:
                if cand in self.test_index:
                    tests.extend(self.test_index[cand])

        seen: set[str] = set()
        unique: list[str] = []
        for t in tests:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        return unique

    def plan_tests(
        self,
        diff: DiffAnalysisResult,
        reachability: ReachabilityAssessment | None = None,
        graph: ImpactGraph | None = None,
        mode: SelectionMode = SelectionMode.BALANCED,
        custom_budget: ExecutionBudget | None = None,
    ) -> TestPlanResult:
        """Plans and ranks tests against the provided change diff and reachability blast radius."""
        budget = custom_budget or ExecutionBudget.for_mode(mode)

        all_changed_symbols = diff.changed_symbols
        file_map = {f.path: f for f in diff.files}

        blast_radius = 0
        reachability_nodes: list[str] = []
        if reachability:
            blast_radius = reachability.total_affected_count
            reachability_nodes = [node.id for node in reachability.affected_nodes]
            if not reachability_nodes and reachability.changed_node_ids:
                reachability_nodes = list(reachability.changed_node_ids)

        candidate_map: dict[str, TestCandidate] = {}
        all_target_nodes: set[str] = set()

        # 1. Directly changed symbols
        for sym in all_changed_symbols:
            node_id = f"{sym.file_path}:{sym.name}"
            all_target_nodes.add(node_id)
            f_info = file_map.get(sym.file_path)
            is_critical = False
            if f_info and (
                f_info.is_migration
                or f_info.is_config
                or f_info.is_api_route
                or f_info.is_security_sensitive
            ):
                is_critical = True

            tier = TestTier.CRITICAL if is_critical else TestTier.DIRECT

            mapped_tests = self._find_tests_for_symbol_or_file(sym.file_path, sym.name)
            for test_id in mapped_tests:
                dur = self.test_durations.get(test_id, 1.0)
                if test_id in candidate_map:
                    existing = candidate_map[test_id]
                    updated_nodes = list(set(existing.covered_node_ids + [node_id]))
                    is_crit = existing.tier == TestTier.CRITICAL or is_critical
                    new_score = self._compute_candidate_priority(
                        test_id=test_id,
                        target_file=sym.file_path,
                        tier=TestTier.CRITICAL if is_crit else existing.tier,
                        covered_nodes=updated_nodes,
                        duration=dur,
                        blast_radius=blast_radius,
                        is_critical=is_crit,
                    )
                    candidate_map[test_id] = TestCandidate(
                        test_id=test_id,
                        target_file=sym.file_path,
                        estimated_duration_seconds=dur,
                        tier=TestTier.CRITICAL if is_crit else existing.tier,
                        covered_node_ids=updated_nodes,
                        priority_score=new_score,
                        selection_reason=f"Covers {len(updated_nodes)} changed/affected symbols",
                    )
                else:
                    score = self._compute_candidate_priority(
                        test_id=test_id,
                        target_file=sym.file_path,
                        tier=tier,
                        covered_nodes=[node_id],
                        duration=dur,
                        blast_radius=blast_radius,
                        is_critical=is_critical,
                    )
                    candidate_map[test_id] = TestCandidate(
                        test_id=test_id,
                        target_file=sym.file_path,
                        estimated_duration_seconds=dur,
                        tier=tier,
                        covered_node_ids=[node_id],
                        priority_score=score,
                        selection_reason=f"Direct test for {node_id} (critical={is_critical})",
                    )

        # 2. Files changed with no symbols (e.g. migration, configs)
        for fpath, f_info in file_map.items():
            mapped_tests = self._find_tests_for_symbol_or_file(fpath)
            is_critical = (
                f_info.is_migration
                or f_info.is_config
                or f_info.is_api_route
                or f_info.is_security_sensitive
            )
            tier = TestTier.CRITICAL if is_critical else TestTier.DIRECT
            for test_id in mapped_tests:
                if test_id not in candidate_map:
                    dur = self.test_durations.get(test_id, 1.0)
                    score = self._compute_candidate_priority(
                        test_id=test_id,
                        target_file=fpath,
                        tier=tier,
                        covered_nodes=[fpath],
                        duration=dur,
                        blast_radius=blast_radius,
                        is_critical=is_critical,
                    )
                    candidate_map[test_id] = TestCandidate(
                        test_id=test_id,
                        target_file=fpath,
                        estimated_duration_seconds=dur,
                        tier=tier,
                        covered_node_ids=[fpath],
                        priority_score=score,
                        selection_reason=f"File-level test for {fpath} (critical={is_critical})",
                    )

        # 3. Transitive reachability nodes
        if reachability_nodes:
            for r_node in reachability_nodes:
                all_target_nodes.add(r_node)
                r_file = r_node.split(":")[0] if ":" in r_node else r_node
                r_symbol = r_node.split(":")[1] if ":" in r_node else None
                mapped_tests = self._find_tests_for_symbol_or_file(r_file, r_symbol)
                for test_id in mapped_tests:
                    dur = self.test_durations.get(test_id, 1.0)
                    if test_id in candidate_map:
                        existing = candidate_map[test_id]
                        if r_node not in existing.covered_node_ids:
                            updated_nodes = existing.covered_node_ids + [r_node]
                            is_crit = existing.tier == TestTier.CRITICAL
                            new_score = self._compute_candidate_priority(
                                test_id=test_id,
                                target_file=existing.target_file,
                                tier=existing.tier,
                                covered_nodes=updated_nodes,
                                duration=dur,
                                blast_radius=blast_radius,
                                is_critical=is_crit,
                            )
                            candidate_map[test_id] = TestCandidate(
                                test_id=test_id,
                                target_file=existing.target_file,
                                estimated_duration_seconds=dur,
                                tier=existing.tier,
                                covered_node_ids=updated_nodes,
                                priority_score=new_score,
                                selection_reason=existing.selection_reason,
                            )
                    else:
                        score = self._compute_candidate_priority(
                            test_id=test_id,
                            target_file=r_file,
                            tier=TestTier.TRANSITIVE,
                            covered_nodes=[r_node],
                            duration=dur,
                            blast_radius=blast_radius,
                            is_critical=False,
                        )
                        candidate_map[test_id] = TestCandidate(
                            test_id=test_id,
                            target_file=r_file,
                            estimated_duration_seconds=dur,
                            tier=TestTier.TRANSITIVE,
                            covered_node_ids=[r_node],
                            priority_score=score,
                            selection_reason=f"Transitive reachable test for {r_node}",
                        )

        # 4. Check for Fallback condition
        fallback_triggered = False
        fallback_reason = None

        candidates = list(candidate_map.values())
        if not candidates:
            fallback_triggered = True
            fallback_reason = (
                "No direct or transitive test mapped to modified symbols; falling back to smoke suite"
            )
            for idx, smoke_id in enumerate(self.smoke_tests):
                dur = self.test_durations.get(smoke_id, 0.5)
                candidates.append(
                    TestCandidate(
                        test_id=smoke_id,
                        target_file="smoke",
                        estimated_duration_seconds=dur,
                        tier=TestTier.SMOKE,
                        covered_node_ids=[],
                        priority_score=round(10.0 / (idx + 1), 2),
                        selection_reason="Fallback smoke test verification",
                    )
                )

        # 5. Greedy Selection under ExecutionBudget
        def sort_key(c: TestCandidate) -> tuple[int, float]:
            crit_rank = 1 if c.tier == TestTier.CRITICAL else 0
            return (crit_rank, c.priority_score)

        candidates.sort(key=sort_key, reverse=True)

        selected: list[TestCandidate] = []
        omitted: list[TestCandidate] = []
        total_time = 0.0
        covered_symbols: set[str] = set()

        for cand in candidates:
            will_exceed_time = (
                (total_time + cand.estimated_duration_seconds) > budget.max_duration_seconds
            )
            will_exceed_count = len(selected) >= budget.max_tests

            if mode == SelectionMode.FULL_REGRESSION or (
                not will_exceed_time and not will_exceed_count
            ):
                selected.append(cand)
                total_time += cand.estimated_duration_seconds
                covered_symbols.update(cand.covered_node_ids)
            else:
                omitted.append(cand)

        total_target_count = len(all_target_nodes)
        covered_count = (
            len(covered_symbols.intersection(all_target_nodes))
            if all_target_nodes
            else (len(selected) if fallback_triggered else 0)
        )
        coverage_ratio = (
            round(covered_count / total_target_count, 3)
            if total_target_count > 0
            else (1.0 if selected else 0.0)
        )

        return TestPlanResult(
            mode=mode,
            budget=budget,
            selected_tests=selected,
            omitted_tests=omitted,
            total_estimated_duration_seconds=round(total_time, 2),
            covered_symbol_count=covered_count,
            total_symbol_count=total_target_count,
            coverage_ratio=coverage_ratio,
            fallback_triggered=fallback_triggered,
            fallback_reason=fallback_reason,
        )
