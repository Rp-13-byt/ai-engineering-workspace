"""GitHub Check Run & PR summary reporting for ChangeLens."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ai_workspace_api.modules.changelens.reachability import ReachabilityAssessment
    from ai_workspace_api.modules.changelens.risk_engine import RiskAssessmentResult
    from ai_workspace_api.modules.changelens.test_selection import TestPlanResult


class CheckConclusion(str, enum.Enum):
    SUCCESS = "success"
    NEUTRAL = "neutral"
    ACTION_REQUIRED = "action_required"
    FAILURE = "failure"


class AnnotationLevel(str, enum.Enum):
    NOTICE = "notice"
    WARNING = "warning"
    FAILURE = "failure"


@dataclass(frozen=True)
class CheckAnnotation:
    path: str
    start_line: int
    end_line: int
    annotation_level: AnnotationLevel
    message: str
    title: str | None = None

    def to_github_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "start_line": max(1, self.start_line),
            "end_line": max(1, self.end_line),
            "annotation_level": self.annotation_level.value,
            "message": self.message,
        }
        if self.title:
            payload["title"] = self.title
        return payload


@dataclass(frozen=True)
class CheckRunPayload:
    name: str
    head_sha: str
    conclusion: CheckConclusion
    output_title: str
    output_summary: str
    output_text: str = ""
    status: str = "completed"
    annotations: list[CheckAnnotation] = field(default_factory=list)

    def to_github_dict(self) -> dict[str, Any]:
        # GitHub Check Runs API accepts at most 50 annotations per request
        output: dict[str, Any] = {
            "title": self.output_title,
            "summary": self.output_summary,
        }
        if self.output_text:
            output["text"] = self.output_text
        if self.annotations:
            output["annotations"] = [a.to_github_dict() for a in self.annotations[:50]]

        return {
            "name": self.name,
            "head_sha": self.head_sha,
            "status": self.status,
            "conclusion": self.conclusion.value,
            "output": output,
        }


class MarkdownReportBuilder:
    """Generates deterministic GitHub-Flavored Markdown PR summaries from ChangeLens results."""

    LEVEL_BADGES: dict[str, str] = {
        "LOW": "🟢 LOW",
        "MEDIUM": "🟡 MEDIUM",
        "HIGH": "🟠 HIGH",
        "CRITICAL": "🔴 CRITICAL",
    }

    def render_pr_summary(
        self,
        risk_result: RiskAssessmentResult,
        test_plan: TestPlanResult | None = None,
        reachability: ReachabilityAssessment | None = None,
    ) -> str:
        level_str = risk_result.risk_level.value
        badge = self.LEVEL_BADGES.get(level_str, level_str)
        conf_pct = round(risk_result.confidence * 100)

        lines: list[str] = [
            "## ChangeLens Risk Assessment",
            "",
            f"**Risk Level:** {badge} (`{risk_result.overall_risk_score:.1f}/100`) | **Confidence:** `{conf_pct}%`",
            "",
            risk_result.summary_explanation,
            "",
        ]

        if risk_result.requires_human_approval:
            lines.extend(
                [
                    "> **Human Review Required:** Deterministic policy requires explicit reviewer sign-off before merging.",
                    "",
                ]
            )

        if reachability is not None:
            lines.extend(
                [
                    f"- **Blast Radius:** {reachability.total_affected_count} affected symbols "
                    f"({reachability.direct_dependents_count} direct, {reachability.indirect_dependents_count} indirect)",
                    f"- **Max Reach Depth:** {reachability.max_reach_depth}",
                    "",
                ]
            )

        if risk_result.breaking_indicators:
            lines.append("### Breaking Change Indicators")
            for indicator in risk_result.breaking_indicators:
                lines.append(f"- {indicator}")
            lines.append("")

        if risk_result.dimensions:
            lines.extend(
                [
                    "### Risk Dimensions",
                    "",
                    "| Dimension | Score | Max | Explanation |",
                    "|---|---:|---:|---|",
                ]
            )
            for dim in risk_result.dimensions:
                lines.append(
                    f"| {dim.name} | {dim.score:.1f} | {dim.max_score:.1f} | {dim.explanation} |"
                )
            lines.append("")

        if test_plan is not None:
            cov_pct = round(test_plan.coverage_ratio * 100)
            lines.extend(
                [
                    "### Recommended Regression Test Plan",
                    "",
                    f"- **Selection Mode:** `{test_plan.mode.value}`",
                    f"- **Selected Tests:** {len(test_plan.selected_tests)} "
                    f"(Estimated Duration: `{test_plan.total_estimated_duration_seconds:.1f}s`)",
                    f"- **Symbol Coverage:** `{cov_pct}%`",
                ]
            )
            if test_plan.fallback_triggered and test_plan.fallback_reason:
                lines.append(f"- **Fallback Notice:** {test_plan.fallback_reason}")
            if test_plan.selected_tests:
                lines.append("")
                for cand in test_plan.selected_tests[:10]:
                    lines.append(
                        f"  - `{cand.test_id}` (`{cand.tier.value}`, {cand.estimated_duration_seconds:.1f}s)"
                    )
            lines.append("")

        if risk_result.assumptions_and_unknowns:
            lines.append("### Assumptions & Unknowns")
            for item in risk_result.assumptions_and_unknowns:
                lines.append(f"- {item}")
            lines.append("")

        return "\n".join(lines).strip() + "\n"
