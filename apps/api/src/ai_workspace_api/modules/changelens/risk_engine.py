import enum
from dataclasses import dataclass, field

from ai_workspace_api.modules.changelens.history_analysis import HistoryAnalysisResult
from ai_workspace_api.modules.changelens.models import DiffAnalysisResult
from ai_workspace_api.modules.changelens.reachability import ReachabilityAssessment


class RiskLevel(str, enum.Enum):
    LOW = "LOW"            # 0.0 - 29.9
    MEDIUM = "MEDIUM"      # 30.0 - 59.9
    HIGH = "HIGH"          # 60.0 - 79.9
    CRITICAL = "CRITICAL"  # 80.0 - 100.0


@dataclass(frozen=True)
class RiskDimension:
    name: str
    score: float
    max_score: float
    explanation: str
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RiskAssessmentResult:
    overall_risk_score: float
    risk_level: RiskLevel
    confidence: float
    dimensions: list[RiskDimension]
    breaking_indicators: list[str]
    assumptions_and_unknowns: list[str]
    requires_human_approval: bool
    summary_explanation: str


class ChangeRiskEngine:
    """Calculates deterministic, multi-dimensional risk scores with explicit evidence."""

    def evaluate_risk(
        self,
        diff_result: DiffAnalysisResult,
        reachability: ReachabilityAssessment | None = None,
        history: HistoryAnalysisResult | None = None,
        mapped_tests_count: int | None = None,
    ) -> RiskAssessmentResult:
        dimensions: list[RiskDimension] = []
        breaking_indicators: list[str] = []
        unknowns: list[str] = []

        # 1. Blast Radius Dimension (Max 25 pts)
        dim_blast = self._eval_blast_radius(reachability)
        dimensions.append(dim_blast)

        # 2. Critical Boundaries Dimension (Max 20 pts)
        dim_critical = self._eval_critical_boundaries(diff_result, reachability)
        dimensions.append(dim_critical)

        # 3. Test Gaps Dimension (Max 20 pts)
        dim_test_gaps = self._eval_test_gaps(reachability, mapped_tests_count)
        dimensions.append(dim_test_gaps)

        # 4. Complexity & Diff Size Dimension (Max 10 pts)
        dim_complexity = self._eval_complexity(diff_result)
        dimensions.append(dim_complexity)

        # 5. History & Churn Dimension (Max 15 pts)
        dim_history = self._eval_history(history, unknowns)
        dimensions.append(dim_history)

        # 6. Breaking Changes Dimension (Max 10 pts)
        dim_breaking = self._eval_breaking_changes(diff_result, breaking_indicators)
        dimensions.append(dim_breaking)

        # Calculate Overall Score (sum of all dimensions, capped at 100)
        total_score = sum(d.score for d in dimensions)
        overall_score = min(100.0, max(0.0, round(total_score, 1)))

        # Determine Risk Level
        if overall_score >= 80.0:
            risk_level = RiskLevel.CRITICAL
        elif overall_score >= 60.0:
            risk_level = RiskLevel.HIGH
        elif overall_score >= 30.0:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        # Confidence Calculation: independent from risk score
        confidence = self._compute_confidence(reachability, history, unknowns)

        # Human Approval Required if Critical, or touched database migrations / security
        has_migration = any(f.is_migration for f in diff_result.files)
        has_security = any(f.is_security_sensitive for f in diff_result.files)
        requires_approval = (
            risk_level == RiskLevel.CRITICAL
            or has_migration
            or has_security
            or len(breaking_indicators) > 0
        )

        summary = (
            f"Evaluated change risk as {risk_level.value} ({overall_score}/100) with "
            f"{int(confidence * 100)}% analysis confidence across 6 deterministic dimensions."
        )

        return RiskAssessmentResult(
            overall_risk_score=overall_score,
            risk_level=risk_level,
            confidence=confidence,
            dimensions=dimensions,
            breaking_indicators=breaking_indicators,
            assumptions_and_unknowns=unknowns,
            requires_human_approval=requires_approval,
            summary_explanation=summary,
        )

    def _eval_blast_radius(
        self,
        reachability: ReachabilityAssessment | None,
    ) -> RiskDimension:
        if not reachability:
            return RiskDimension(
                name="Blast Radius",
                score=10.0,
                max_score=25.0,
                explanation="No reachability assessment provided; using baseline estimate.",
                evidence=["Reachability traversal unperformed"],
            )

        score = min(25.0, round(reachability.blast_radius_score, 1))
        evidence = [
            f"Total downstream affected nodes: {reachability.total_affected_count}",
            f"Direct dependents: {reachability.direct_dependents_count}",
            f"Max reach depth: {reachability.max_reach_depth}",
        ]
        return RiskDimension(
            name="Blast Radius",
            score=score,
            max_score=25.0,
            explanation=f"Downstream blast radius calculated as {score}/25 based on dependency traversal.",
            evidence=evidence,
        )

    def _eval_critical_boundaries(
        self,
        diff_result: DiffAnalysisResult,
        reachability: ReachabilityAssessment | None,
    ) -> RiskDimension:
        score = 0.0
        evidence: list[str] = []

        # Database migrations (+10 pts)
        migrations = [f.path for f in diff_result.files if f.is_migration]
        if migrations:
            score += 10.0
            evidence.append(f"Database schema migrations touched: {', '.join(migrations)}")

        # Security/Auth (+7 pts)
        security_files = [f.path for f in diff_result.files if f.is_security_sensitive]
        if security_files:
            score += 7.0
            evidence.append(f"Security or auth boundaries touched: {', '.join(security_files)}")

        # Traversal touched security boundaries (+3 pts)
        if reachability and reachability.security_critical_paths:
            score += 3.0
            evidence.append(
                f"{len(reachability.security_critical_paths)} downstream paths reach security boundaries"
            )

        score = min(20.0, round(score, 1))
        return RiskDimension(
            name="Critical Boundaries",
            score=score,
            max_score=20.0,
            explanation=f"Critical system boundary risk scored at {score}/20.",
            evidence=evidence if evidence else ["No critical architectural boundaries modified"],
        )

    def _eval_test_gaps(
        self,
        reachability: ReachabilityAssessment | None,
        mapped_tests_count: int | None,
    ) -> RiskDimension:
        evidence: list[str] = []
        if reachability is None or reachability.total_affected_count == 0:
            return RiskDimension(
                name="Test Gaps",
                score=0.0,
                max_score=20.0,
                explanation="No affected code symbols identified.",
                evidence=["Zero affected code symbols"],
            )

        tests_found = (
            mapped_tests_count
            if mapped_tests_count is not None
            else len(reachability.affected_tests)
        )

        # Ratio of affected nodes that have tests
        if tests_found == 0:
            score = 20.0
            evidence.append("Critical test gap: 0 regression tests found covering affected code")
        elif tests_found < reachability.direct_dependents_count:
            # Under-tested relative to direct impact
            gap = reachability.direct_dependents_count - tests_found
            score = min(16.0, round(gap * 3.0 + 5.0, 1))
            evidence.append(f"{tests_found} tests cover {reachability.direct_dependents_count} direct dependents")
        else:
            score = 2.0
            evidence.append(f"{tests_found} regression tests map to affected symbols")

        return RiskDimension(
            name="Test Gaps",
            score=score,
            max_score=20.0,
            explanation=f"Test coverage and verification gap scored at {score}/20.",
            evidence=evidence,
        )

    def _eval_complexity(self, diff_result: DiffAnalysisResult) -> RiskDimension:
        total_lines = diff_result.total_added_lines + diff_result.total_deleted_lines
        symbols_count = len(diff_result.changed_symbols)
        evidence: list[str] = [
            f"{total_lines} lines changed (+{diff_result.total_added_lines}, -{diff_result.total_deleted_lines})",
            f"{symbols_count} AST symbols modified",
        ]

        score = 0.0
        if total_lines > 500:
            score += 5.0
        elif total_lines > 150:
            score += 3.0
        elif total_lines > 50:
            score += 1.5

        if symbols_count > 10:
            score += 5.0
        elif symbols_count > 4:
            score += 3.0
        elif symbols_count > 0:
            score += 1.0

        score = min(10.0, round(score, 1))
        return RiskDimension(
            name="Complexity & Size",
            score=score,
            max_score=10.0,
            explanation=f"Change size and AST symbol complexity scored at {score}/10.",
            evidence=evidence,
        )

    def _eval_history(
        self,
        history: HistoryAnalysisResult | None,
        unknowns: list[str],
    ) -> RiskDimension:
        if not history:
            unknowns.append("No historical commit analysis available; neutral baseline assigned.")
            return RiskDimension(
                name="History & Churn",
                score=5.0,
                max_score=15.0,
                explanation="Historical churn unavailable; default conservative score assigned.",
                evidence=["Commit history not provided"],
            )

        if history.is_shallow_history:
            unknowns.extend(history.assumptions_and_unknowns)

        score = min(15.0, round(history.history_risk_score, 1))
        evidence = [
            f"Examined {history.historical_commits_examined} commits",
            f"History confidence: {int(history.history_confidence * 100)}%",
            f"Frequently co-changed files: {len(history.frequently_co_changed_files)}",
        ]
        return RiskDimension(
            name="History & Churn",
            score=score,
            max_score=15.0,
            explanation=f"Historical code churn and coupled co-modifications scored at {score}/15.",
            evidence=evidence,
        )

    def _eval_breaking_changes(
        self,
        diff_result: DiffAnalysisResult,
        breaking_indicators: list[str],
    ) -> RiskDimension:
        score = 0.0
        evidence: list[str] = []

        # Detect deleted public symbols
        for sym in diff_result.changed_symbols:
            if sym.change_nature == "deleted" and not sym.name.startswith("_"):
                score += 4.0
                msg = f"Public {sym.symbol_type} '{sym.name}' deleted in {sym.file_path}"
                evidence.append(msg)
                breaking_indicators.append(msg)

        # Detect deleted files
        for f in diff_result.files:
            if f.change_type.value == "deleted":
                score += 3.0
                msg = f"File deleted: {f.path}"
                evidence.append(msg)
                breaking_indicators.append(msg)

        score = min(10.0, round(score, 1))
        return RiskDimension(
            name="Breaking Changes",
            score=score,
            max_score=10.0,
            explanation=f"API and symbol breaking change risk scored at {score}/10.",
            evidence=evidence if evidence else ["No removed public symbols or breaking removals detected"],
        )

    def _compute_confidence(
        self,
        reachability: ReachabilityAssessment | None,
        history: HistoryAnalysisResult | None,
        unknowns: list[str],
    ) -> float:
        # Baseline confidence is 0.95 when all analysis modules supply data
        conf = 0.95

        if reachability is None:
            conf -= 0.35
            unknowns.append("Downstream dependency reachability unperformed; impact graph unknown.")

        if history is None:
            conf -= 0.20
        elif history.is_shallow_history:
            conf = min(conf, history.history_confidence)

        return max(0.1, min(1.0, round(conf, 2)))
