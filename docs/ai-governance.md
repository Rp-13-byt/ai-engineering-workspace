# AI Pull Request Governance

The pull request generator is guarded by a deterministic governance pipeline before any AI-authored change can be opened on GitHub. The pipeline evaluates the generated diff, records the decision, labels the draft, and writes an audit record.

## Governance Flow

1. The model produces a pull request title, body, branch name, and unified diff.
2. The diff parser extracts every changed file path.
3. The policy engine evaluates repository, organization, path, and glob rules.
4. The risk engine assigns per-file and overall risk scores.
5. Security scanning runs against the generated diff.
6. The service decides one of `allow`, `require_approval`, or `block`.
7. Allowed drafts may open on GitHub immediately. Approval-required drafts remain in `Pending Review`. Blocked drafts are persisted but never opened automatically.
8. The draft body is rewritten with explainability sections: summary, files changed, risk assessment, policy evaluation, reasoning, rollback strategy, and testing performed.

Empty or unparsable diffs are blocked. The system fails closed when it cannot identify the changed files.

## Policy Engine

Policies are ordered by restrictiveness, not by file order. If any matching rule blocks a path, the whole draft is blocked. If no block rule matches but any matched rule requires approval, the draft requires approval. Otherwise it is allowed.

Supported actions:

- `block`
- `require_approval`
- `allow`

Supported selectors:

- File paths and glob patterns
- Repository names, for example `acme/platform`
- Organization identifiers or slugs

Default rules:

| Pattern | Action | Reason |
| --- | --- | --- |
| `.github/workflows/**` | `block` | CI/CD workflow changes can alter automation. |
| `.env*`, `**/.env*` | `block` | Environment files may contain credentials. |
| `secrets/**`, `**/secrets/**`, `*secret*` | `block` | Secret material must not be changed automatically. |
| `infra/**`, `infrastructure/**` | `require_approval` | Infrastructure changes need human review. |
| `**/production/**` | `require_approval` | Production deployment changes need human review. |
| `**/*.tf`, `**/*.tfvars`, `**/terraform/**` | `require_approval` | Terraform can modify cloud resources. |
| `charts/**`, `**/helm/**`, `**/Chart.yaml`, `**/values*.yaml` | `require_approval` | Helm changes can alter releases. |
| `k8s/**`, `**/k8s/**`, `**/kustomization.yaml` | `require_approval` | Kubernetes manifests can affect runtime workloads. |
| `docs/**`, `*.md`, `**/*.md` | `allow` | Documentation is low risk by default. |
| `src/**`, `apps/**` | `allow` | Application source is allowed unless another rule raises risk. |

Set `AI_GOVERNANCE_POLICY_PATH` to a JSON file to replace the default policy set:

```json
{
  "rules": [
    {
      "name": "block-workflows",
      "action": "block",
      "paths": [".github/workflows/**"],
      "repositories": ["acme/*"],
      "organizations": ["acme"],
      "reason": "Workflow changes require a release engineer."
    },
    {
      "name": "allow-docs",
      "action": "allow",
      "paths": ["docs/**"]
    }
  ]
}
```

## Risk Scoring

Risk scoring is deterministic and based only on changed paths. Each matched factor contributes a weighted score to the file, capped at 100. Overall risk is the highest file score plus a small breadth score for multiple risky files.

Risk factors include authentication, infrastructure, workflows, deployment, secrets, package managers, dependency files, Docker, Kubernetes, Terraform, and Helm.

Default thresholds:

- `AI_GOVERNANCE_REQUIRE_APPROVAL_THRESHOLD=45`
- `AI_GOVERNANCE_BLOCK_THRESHOLD=85`

Risk labels:

- `risk-low` for scores below 35
- `risk-medium` for scores from 35 to 69
- `risk-high` for scores 70 and above

## Protected Paths

Protected paths are immutable for automatic PR opening. The AI cannot automatically open changes touching GitHub workflows, environment files, secrets, production deployment paths, infrastructure, Terraform, Helm, or Kubernetes. Depending on the path, the draft is either blocked outright or held for explicit approval.

## Approval Workflow

Approval states:

- `Pending Review`
- `Approved`
- `Rejected`
- `Not Required`

Reviewers call the approval endpoint with a decision and reason. The system records:

- Approver user ID
- Timestamp
- Decision
- Reason

Approved drafts can be opened on GitHub and have the `needs-review` label removed. Rejected drafts stay closed and retain review context.

## Labels

Every governed draft gets:

- `ai-generated`
- One risk label: `risk-low`, `risk-medium`, or `risk-high`
- `needs-review` when the draft requires approval or contains blocking scan findings

When GitHub PR creation is allowed, the same labels are applied to the GitHub pull request.

## Audit Logging

The system writes audit log entries for:

- Policy decisions
- Risk scores
- Security scan results
- Blocked actions
- Approval and rejection history

Audit metadata includes actor, organization, repository, branch, commit, status, labels, and the full governance decision payload.

## Security Scanning

Before automatic PR creation, the service runs:

- Secret scanning over added diff lines
- Dependency audit checks for dependency manifest changes
- Static analysis for obvious unsafe code execution patterns

Critical findings block PR creation. High findings are recorded and surfaced in the generated PR body.

## Security Model

The governance system treats AI output as untrusted. It stores generated drafts, but automatic repository mutation is only allowed after deterministic checks pass. Protected path changes cannot bypass policy by changing labels or prompt text because enforcement uses the generated diff, not model-provided explanations.

Organization administrators should keep blocking rules for workflows, environment files, and secrets, and route infrastructure approvals to users with the `pull_request:approve` permission.
