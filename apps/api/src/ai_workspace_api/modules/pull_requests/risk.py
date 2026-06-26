from dataclasses import dataclass
from typing import Any

from ai_workspace_api.modules.pull_requests.diff_parser import ProposedFileChange


@dataclass(frozen=True)
class RiskFactor:
    name: str
    weight: int
    patterns: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class FileRisk:
    path: str
    score: int
    factors: tuple[str, ...]
    explanation: str


@dataclass(frozen=True)
class RiskAssessment:
    overall_score: int
    level: str
    files: tuple[FileRisk, ...]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "level": self.level,
            "explanation": self.explanation,
            "files": [
                {
                    "path": file.path,
                    "score": file.score,
                    "factors": list(file.factors),
                    "explanation": file.explanation,
                }
                for file in self.files
            ],
        }


RISK_FACTORS: tuple[RiskFactor, ...] = (
    RiskFactor("authentication", 30, ("auth", "oauth", "jwt", "session", "permission", "rbac"), "Touches authentication or authorization."),
    RiskFactor("infrastructure", 35, ("infra/", "infrastructure/", "deploy/", "deployment"), "Touches infrastructure or deployment topology."),
    RiskFactor("workflows", 45, (".github/workflows/", ".gitlab-ci", "circleci", "jenkins"), "Touches CI/CD workflow automation."),
    RiskFactor("deployment", 30, ("production", "staging", "release", "rollback"), "Touches deployment environments or release flow."),
    RiskFactor("secrets", 50, (".env", "secret", "credential", "private_key", "token"), "Touches files or names associated with secrets."),
    RiskFactor("package_managers", 25, ("package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "pyproject.toml", "poetry.lock", "requirements.txt", "go.mod", "cargo.toml"), "Touches package manager configuration."),
    RiskFactor("dependency_files", 25, ("lock", "requirements", "dependencies", "deps"), "Touches dependency resolution files."),
    RiskFactor("docker", 25, ("dockerfile", "docker-compose", ".dockerignore"), "Touches container build or runtime configuration."),
    RiskFactor("kubernetes", 35, ("k8s/", "kubernetes/", "kustomization.yaml", "namespace.yaml", "ingress.yaml"), "Touches Kubernetes manifests."),
    RiskFactor("terraform", 40, (".tf", ".tfvars", "terraform/"), "Touches Terraform infrastructure as code."),
    RiskFactor("helm", 35, ("chart.yaml", "values.yaml", "helm/", "charts/"), "Touches Helm release configuration."),
)


class RiskEngine:
    def assess(self, changes: list[ProposedFileChange]) -> RiskAssessment:
        file_risks = tuple(self._assess_file(change.path) for change in changes)
        if not file_risks:
            return RiskAssessment(
                overall_score=0,
                level="low",
                files=(),
                explanation="No changed files were detected in the generated diff.",
            )

        max_file_score = max(file.score for file in file_risks)
        breadth_score = min(20, max(0, len([file for file in file_risks if file.score >= 25]) - 1) * 5)
        overall_score = min(100, max_file_score + breadth_score)
        level = "high" if overall_score >= 70 else "medium" if overall_score >= 35 else "low"
        explanations = [file.explanation for file in file_risks if file.factors]
        explanation = " ".join(explanations) if explanations else "Changed files do not match elevated risk factors."
        return RiskAssessment(
            overall_score=overall_score,
            level=level,
            files=file_risks,
            explanation=explanation,
        )

    def _assess_file(self, path: str) -> FileRisk:
        normalized = path.replace("\\", "/").lower()
        matched: list[RiskFactor] = []
        for factor in RISK_FACTORS:
            if any(pattern in normalized for pattern in factor.patterns):
                matched.append(factor)
        score = min(100, sum(factor.weight for factor in matched))
        factor_names = tuple(factor.name for factor in matched)
        explanation = (
            f"{path} matched risk factors: {', '.join(factor_names)}."
            if factor_names
            else f"{path} did not match elevated risk factors."
        )
        return FileRisk(path=path, score=score, factors=factor_names, explanation=explanation)
