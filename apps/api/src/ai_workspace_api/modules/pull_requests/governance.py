import fnmatch
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from ai_workspace_api.core.config import Settings


class PolicyAction(StrEnum):
    block = "block"
    require_approval = "require_approval"
    allow = "allow"


class ApprovalStatus(StrEnum):
    not_required = "Not Required"
    pending_review = "Pending Review"
    approved = "Approved"
    rejected = "Rejected"


@dataclass(frozen=True)
class PolicyRule:
    name: str
    action: PolicyAction
    paths: tuple[str, ...] = ()
    repositories: tuple[str, ...] = ()
    organizations: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class FilePolicyDecision:
    path: str
    action: PolicyAction
    matched_rules: tuple[str, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PolicyEvaluation:
    action: PolicyAction
    files: tuple[FilePolicyDecision, ...]
    explanations: tuple[str, ...]

    @property
    def blocked(self) -> bool:
        return self.action == PolicyAction.block

    @property
    def requires_approval(self) -> bool:
        return self.action == PolicyAction.require_approval

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action.value,
            "explanations": list(self.explanations),
            "files": [
                {
                    "path": file.path,
                    "action": file.action.value,
                    "matched_rules": list(file.matched_rules),
                    "reasons": list(file.reasons),
                }
                for file in self.files
            ],
        }


DEFAULT_POLICY_RULES: tuple[PolicyRule, ...] = (
    PolicyRule(
        name="block-github-workflows",
        action=PolicyAction.block,
        paths=(".github/workflows/**",),
        reason="GitHub workflow changes can alter CI/CD execution and require a separate trusted path.",
    ),
    PolicyRule(
        name="block-env-files",
        action=PolicyAction.block,
        paths=(".env*", "**/.env*"),
        reason="Environment files can contain credentials or production configuration.",
    ),
    PolicyRule(
        name="block-secrets",
        action=PolicyAction.block,
        paths=("secrets/**", "**/secrets/**", "*secret*", "*secrets*"),
        reason="Secret material must never be changed automatically.",
    ),
    PolicyRule(
        name="protect-infrastructure",
        action=PolicyAction.require_approval,
        paths=("infra/**", "infrastructure/**"),
        reason="Infrastructure changes need human approval.",
    ),
    PolicyRule(
        name="protect-production-deployments",
        action=PolicyAction.require_approval,
        paths=("deploy/**/production/**", "deployments/**/production/**", "**/production/**"),
        reason="Production deployment changes need human approval.",
    ),
    PolicyRule(
        name="protect-terraform",
        action=PolicyAction.require_approval,
        paths=("**/*.tf", "**/*.tfvars", "**/terraform/**"),
        reason="Terraform changes can modify cloud resources.",
    ),
    PolicyRule(
        name="protect-helm",
        action=PolicyAction.require_approval,
        paths=("charts/**", "**/helm/**", "**/Chart.yaml", "**/values*.yaml"),
        reason="Helm changes can alter deployed workloads.",
    ),
    PolicyRule(
        name="protect-kubernetes",
        action=PolicyAction.require_approval,
        paths=("k8s/**", "kubernetes/**", "**/k8s/**", "**/kubernetes/**", "**/kustomization.yaml"),
        reason="Kubernetes manifests can change runtime permissions, secrets, and deployments.",
    ),
    PolicyRule(
        name="allow-docs",
        action=PolicyAction.allow,
        paths=("docs/**", "*.md", "**/*.md"),
        reason="Documentation-only changes are low governance risk by default.",
    ),
    PolicyRule(
        name="allow-source",
        action=PolicyAction.allow,
        paths=("src/**", "apps/**"),
        reason="Application source changes are allowed unless another rule raises risk.",
    ),
)


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("/")


def _matches_any(value: str, patterns: tuple[str, ...]) -> bool:
    normalized = _normalize_path(value).lower()
    return any(fnmatch.fnmatchcase(normalized, _normalize_path(pattern).lower()) for pattern in patterns)


def _most_restrictive(actions: list[PolicyAction]) -> PolicyAction:
    if PolicyAction.block in actions:
        return PolicyAction.block
    if PolicyAction.require_approval in actions:
        return PolicyAction.require_approval
    return PolicyAction.allow


@dataclass
class PolicyEngine:
    rules: tuple[PolicyRule, ...] = field(default_factory=lambda: DEFAULT_POLICY_RULES)

    @classmethod
    def from_settings(cls, settings: Settings) -> "PolicyEngine":
        if not settings.ai_governance_policy_path:
            return cls()
        policy_path = Path(settings.ai_governance_policy_path)
        if not policy_path.exists():
            return cls()
        payload = json.loads(policy_path.read_text(encoding="utf-8"))
        rules = tuple(
            PolicyRule(
                name=str(item["name"]),
                action=PolicyAction(str(item["action"])),
                paths=tuple(item.get("paths", ())),
                repositories=tuple(item.get("repositories", ())),
                organizations=tuple(item.get("organizations", ())),
                reason=str(item.get("reason", "")),
            )
            for item in payload.get("rules", [])
        )
        return cls(rules=rules or DEFAULT_POLICY_RULES)

    def evaluate(
        self,
        paths: list[str],
        repository: str,
        organization: str,
    ) -> PolicyEvaluation:
        if not paths:
            return PolicyEvaluation(
                action=PolicyAction.block,
                files=(),
                explanations=("No changed files were detected; empty or unparsable diffs are blocked.",),
            )

        file_decisions = tuple(
            self._evaluate_file(path, repository=repository, organization=organization) for path in paths
        )
        overall = _most_restrictive([decision.action for decision in file_decisions])
        explanations = tuple(
            explanation
            for decision in file_decisions
            for explanation in decision.reasons
        )
        return PolicyEvaluation(action=overall, files=file_decisions, explanations=explanations)

    def _evaluate_file(
        self,
        path: str,
        *,
        repository: str,
        organization: str,
    ) -> FilePolicyDecision:
        matched_rules: list[str] = []
        reasons: list[str] = []
        actions: list[PolicyAction] = []

        for rule in self.rules:
            path_match = not rule.paths or _matches_any(path, rule.paths)
            repo_match = not rule.repositories or _matches_any(repository, rule.repositories)
            org_match = not rule.organizations or _matches_any(organization, rule.organizations)
            if path_match and repo_match and org_match:
                matched_rules.append(rule.name)
                reasons.append(rule.reason or f"{path} matched {rule.name}.")
                actions.append(rule.action)

        if not actions:
            matched_rules.append("default-require-approval")
            reasons.append("No explicit allow policy matched this file.")
            actions.append(PolicyAction.require_approval)

        return FilePolicyDecision(
            path=path,
            action=_most_restrictive(actions),
            matched_rules=tuple(matched_rules),
            reasons=tuple(reasons),
        )
