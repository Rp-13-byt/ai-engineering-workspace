from ai_workspace_api.modules.pull_requests.governance import PolicyEvaluation
from ai_workspace_api.modules.pull_requests.risk import RiskAssessment
from ai_workspace_api.modules.pull_requests.security_scanner import SecurityScanResult


def build_governed_pr_body(
    *,
    original_body: str,
    changed_paths: list[str],
    risk: RiskAssessment,
    policy: PolicyEvaluation,
    security_scan: SecurityScanResult,
    decision: str,
) -> str:
    scan_summary = (
        "No critical findings detected."
        if not security_scan.findings
        else "\n".join(
            f"- {finding.severity.upper()} {finding.scanner}: {finding.message}"
            for finding in security_scan.findings
        )
    )
    policy_summary = "\n".join(
        f"- {file.path}: {file.action.value} ({', '.join(file.matched_rules)})"
        for file in policy.files
    ) or "- No changed files detected."
    file_summary = "\n".join(f"- {path}" for path in changed_paths) or "- No files detected."
    risk_summary = "\n".join(
        f"- {file.path}: {file.score}/100 ({', '.join(file.factors) or 'no elevated factors'})"
        for file in risk.files
    ) or "- No file-level risk factors detected."

    return "\n\n".join(
        [
            "## Summary\n" + (original_body.strip() or "AI-generated pull request draft."),
            "## Files Changed\n" + file_summary,
            (
                "## Risk Assessment\n"
                f"Overall risk: {risk.level} ({risk.overall_score}/100).\n\n"
                f"{risk.explanation}\n\n"
                f"{risk_summary}"
            ),
            "## Policy Evaluation\n" + f"Decision: {decision}.\n\n" + policy_summary,
            "## Reasoning\nThe draft was evaluated by deterministic policy, risk, and security scan gates before PR creation.",
            "## Rollback Strategy\nRevert the generated branch or close the pull request. For deployed changes, follow the repository release rollback process.",
            "## Testing Performed\nAutomated governance evaluation completed before PR creation.\n\n" + scan_summary,
        ]
    )
