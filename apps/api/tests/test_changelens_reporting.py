"""Unit tests for ChangeLens GitHub Check Run & PR summary reporting."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ai_workspace_api.modules.changelens.reachability import ReachabilityAssessment
from ai_workspace_api.modules.changelens.reporting import (
    AnnotationLevel,
    CheckConclusion,
    GitHubCheckReporter,
    MarkdownReportBuilder,
)
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


def _sample_risk(
    level: RiskLevel = RiskLevel.HIGH,
    score: float = 68.5,
    requires_approval: bool = True,
) -> RiskAssessmentResult:
    return RiskAssessmentResult(
        overall_risk_score=score,
        risk_level=level,
        confidence=0.89,
        dimensions=[
            RiskDimension(
                name="Blast Radius",
                score=18.0,
                max_score=25.0,
                explanation="Impacts 9 downstream symbols.",
                evidence=["api/auth.py"],
            )
        ],
        breaking_indicators=["Auth token verification signature changed"] if level in {RiskLevel.HIGH, RiskLevel.CRITICAL} else [],
        assumptions_and_unknowns=["Runtime dynamic dispatch not traced"],
        requires_human_approval=requires_approval,
        summary_explanation="Evaluated deterministic risk across 6 dimensions.",
    )


def test_determine_conclusion_thresholds() -> None:
    assert (
        GitHubCheckReporter.determine_conclusion(_sample_risk(RiskLevel.LOW, 15.0, False))
        == CheckConclusion.SUCCESS
    )
    assert (
        GitHubCheckReporter.determine_conclusion(_sample_risk(RiskLevel.MEDIUM, 40.0, False))
        == CheckConclusion.SUCCESS
    )
    assert (
        GitHubCheckReporter.determine_conclusion(_sample_risk(RiskLevel.HIGH, 65.0, False))
        == CheckConclusion.NEUTRAL
    )
    assert (
        GitHubCheckReporter.determine_conclusion(_sample_risk(RiskLevel.CRITICAL, 85.0, True))
        == CheckConclusion.ACTION_REQUIRED
    )
    assert (
        GitHubCheckReporter.determine_conclusion(_sample_risk(RiskLevel.MEDIUM, 45.0, True))
        == CheckConclusion.ACTION_REQUIRED
    )


def test_markdown_report_builder_renders_complete_summary() -> None:
    builder = MarkdownReportBuilder()
    risk = _sample_risk(RiskLevel.CRITICAL, 86.0, True)
    reach = ReachabilityAssessment(
        changed_node_ids=["api/auth.py:verify"],
        total_affected_count=9,
        direct_dependents_count=4,
        indirect_dependents_count=5,
        max_reach_depth=3,
    )
    plan = TestPlanResult(
        mode=SelectionMode.FAST_FEEDBACK,
        budget=ExecutionBudget.for_mode(SelectionMode.FAST_FEEDBACK),
        selected_tests=[
            TestCandidate(
                test_id="tests/test_auth.py::test_verify",
                target_file="api/auth.py",
                estimated_duration_seconds=1.2,
                tier=TestTier.CRITICAL,
                covered_node_ids=["api/auth.py:verify"],
                priority_score=110.0,
            )
        ],
        total_estimated_duration_seconds=1.2,
        coverage_ratio=1.0,
    )

    md = builder.render_pr_summary(risk_result=risk, test_plan=plan, reachability=reach)

    assert "## ChangeLens Risk Assessment" in md
    assert "🔴 CRITICAL" in md
    assert "`86.0/100`" in md
    assert "`89%`" in md
    assert "Human Review Required" in md
    assert "9 affected symbols (4 direct, 5 indirect)" in md
    assert "Auth token verification signature changed" in md
    assert "| Blast Radius | 18.0 | 25.0 |" in md
    assert "`tests/test_auth.py::test_verify`" in md
    assert "Runtime dynamic dispatch not traced" in md


def test_build_check_run_payload_and_annotation_cap() -> None:
    reporter = GitHubCheckReporter(access_token="ghp_test")
    risk = _sample_risk(RiskLevel.HIGH, 68.5, False)

    # Provide 60 findings to verify GitHub's 50-annotation cap
    findings = [
        {
            "file_path": f"src/mod_{i}.py",
            "start_line": i + 1,
            "end_line": i + 2,
            "severity": "warning" if i % 2 == 0 else "critical",
            "category": "risk_finding",
            "message": f"Finding {i}",
        }
        for i in range(60)
    ]

    payload = reporter.build_check_run_payload(
        head_sha="deadbeef1234",
        risk_result=risk,
        findings=findings,
    )
    gh_dict = payload.to_github_dict()

    assert gh_dict["name"] == "ChangeLens Risk Gate"
    assert gh_dict["head_sha"] == "deadbeef1234"
    assert gh_dict["conclusion"] == "neutral"
    assert len(gh_dict["output"]["annotations"]) == 50
    assert gh_dict["output"]["annotations"][0]["annotation_level"] == AnnotationLevel.WARNING.value
    assert gh_dict["output"]["annotations"][1]["annotation_level"] == AnnotationLevel.FAILURE.value


@pytest.mark.asyncio
async def test_publish_check_run_and_pr_comment() -> None:
    reporter = GitHubCheckReporter(access_token="ghp_token")
    payload = reporter.build_check_run_payload(
        head_sha="abc999",
        risk_result=_sample_risk(RiskLevel.LOW, 12.0, False),
    )

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"id": 999, "status": "completed"}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        res_check = await reporter.publish_check_run("acme", "repo", payload)
        assert res_check["id"] == 999

        res_comment = await reporter.publish_pr_comment("acme", "repo", 42, "## Summary")
        assert res_comment["id"] == 999

    assert mock_client.post.call_count == 2
