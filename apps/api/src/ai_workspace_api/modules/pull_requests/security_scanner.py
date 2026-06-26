import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SecurityFinding:
    scanner: str
    severity: str
    path: str
    message: str


@dataclass(frozen=True)
class SecurityScanResult:
    findings: tuple[SecurityFinding, ...]

    @property
    def has_critical_findings(self) -> bool:
        return any(finding.severity == "critical" for finding in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "findings": [
                {
                    "scanner": finding.scanner,
                    "severity": finding.severity,
                    "path": finding.path,
                    "message": finding.message,
                }
                for finding in self.findings
            ]
        }


_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
)

_CRITICAL_DEPENDENCIES = (
    "event-stream@3.3.6",
    "log4j-core:2.14.1",
    "django==1.2",
)

_STATIC_ANALYSIS_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\beval\s*\("), "Use of eval introduces code execution risk."),
    (re.compile(r"\bexec\s*\("), "Use of exec introduces code execution risk."),
    (re.compile(r"subprocess\.(Popen|run|call)\(.*shell\s*=\s*True"), "Shell execution with shell=True is unsafe."),
)


class SecurityScanner:
    def scan(self, diff: str, changed_paths: list[str]) -> SecurityScanResult:
        findings: list[SecurityFinding] = []
        findings.extend(self._scan_secrets(diff))
        findings.extend(self._scan_dependency_audit(diff, changed_paths))
        findings.extend(self._scan_static_analysis(diff))
        return SecurityScanResult(findings=tuple(findings))

    def _scan_secrets(self, diff: str) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        for line in self._added_lines(diff):
            if any(pattern.search(line) for pattern in _SECRET_PATTERNS):
                findings.append(
                    SecurityFinding(
                        scanner="secret-scanning",
                        severity="critical",
                        path="generated-diff",
                        message="Generated diff appears to add credential-like material.",
                    )
                )
                break
        return findings

    def _scan_dependency_audit(self, diff: str, changed_paths: list[str]) -> list[SecurityFinding]:
        dependency_file_changed = any(
            path.endswith(
                (
                    "package.json",
                    "package-lock.json",
                    "requirements.txt",
                    "pyproject.toml",
                    "poetry.lock",
                    "go.mod",
                    "go.sum",
                    "Cargo.toml",
                    "Cargo.lock",
                )
            )
            for path in changed_paths
        )
        if not dependency_file_changed:
            return []

        normalized_diff = diff.lower()
        for dependency in _CRITICAL_DEPENDENCIES:
            if dependency.lower() in normalized_diff:
                return [
                    SecurityFinding(
                        scanner="dependency-audit",
                        severity="critical",
                        path="generated-diff",
                        message=f"Generated diff references known critical dependency {dependency}.",
                    )
                ]
        return [
            SecurityFinding(
                scanner="dependency-audit",
                severity="low",
                path="generated-diff",
                message="Dependency manifest changed; no known critical fixture matched in deterministic audit.",
            )
        ]

    def _scan_static_analysis(self, diff: str) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        for line in self._added_lines(diff):
            for pattern, message in _STATIC_ANALYSIS_PATTERNS:
                if pattern.search(line):
                    findings.append(
                        SecurityFinding(
                            scanner="static-analysis",
                            severity="high",
                            path="generated-diff",
                            message=message,
                        )
                    )
        return findings

    def _added_lines(self, diff: str) -> list[str]:
        return [
            line[1:]
            for line in diff.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        ]
