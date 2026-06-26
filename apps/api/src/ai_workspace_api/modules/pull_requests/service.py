import uuid
from datetime import UTC, datetime

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.errors import ApiError
from ai_workspace_api.core.models import AuditLog, PullRequestDraft
from ai_workspace_api.core.repository_scope import get_repository_for_organization
from ai_workspace_api.infrastructure.github import GitHubClient
from ai_workspace_api.infrastructure.llm import LLMGateway
from ai_workspace_api.infrastructure.vector_store import VectorStore
from ai_workspace_api.modules.pull_requests.diff_parser import extract_changed_files
from ai_workspace_api.modules.pull_requests.explainability import build_governed_pr_body
from ai_workspace_api.modules.pull_requests.governance import (
    ApprovalStatus,
    PolicyAction,
    PolicyEngine,
)
from ai_workspace_api.modules.pull_requests.risk import RiskEngine
from ai_workspace_api.modules.pull_requests.schemas import (
    PullRequestApprovalRequest,
    PullRequestGenerateRequest,
)
from ai_workspace_api.modules.pull_requests.security_scanner import SecurityScanner


def _risk_label(level: str) -> str:
    return f"risk-{level}"


def _labels_for_decision(level: str, decision: PolicyAction, critical_findings: bool) -> list[str]:
    labels = ["ai-generated", _risk_label(level)]
    if decision in {PolicyAction.block, PolicyAction.require_approval} or critical_findings:
        labels.append("needs-review")
    return labels


class PullRequestService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.llm = LLMGateway(settings)
        self.vector_store = VectorStore(session)
        self.policy_engine = PolicyEngine.from_settings(settings)
        self.risk_engine = RiskEngine()
        self.security_scanner = SecurityScanner()

    async def generate(
        self,
        payload: PullRequestGenerateRequest,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> PullRequestDraft:
        repository = await get_repository_for_organization(
            self.session,
            organization_id,
            payload.repository_id,
        )
        embedding = (await self.llm.embed([payload.instructions]))[0]
        contexts = await self.vector_store.semantic_search(repository.id, embedding, limit=10)
        draft_payload = await self.llm.generate_pull_request(payload.instructions, contexts)
        changes = extract_changed_files(draft_payload["diff"])
        changed_paths = [change.path for change in changes]
        repository_name = f"{repository.owner}/{repository.name}"
        policy = self.policy_engine.evaluate(
            changed_paths,
            repository=repository_name,
            organization=str(repository.organization_id),
        )
        risk = self.risk_engine.assess(changes)
        security_scan = (
            self.security_scanner.scan(draft_payload["diff"], changed_paths)
            if self.settings.ai_governance_security_scans_enabled
            else self.security_scanner.scan("", [])
        )

        decision = self._decision_from_governance(policy, risk.overall_score, security_scan.has_critical_findings)
        labels = _labels_for_decision(risk.level, decision, security_scan.has_critical_findings)
        approval_status = self._approval_status_for_decision(decision)
        body = build_governed_pr_body(
            original_body=draft_payload["body"],
            changed_paths=changed_paths,
            risk=risk,
            policy=policy,
            security_scan=security_scan,
            decision=decision.value,
        )
        draft = PullRequestDraft(
            id=uuid.uuid4(),
            repository_id=repository.id,
            created_by_id=user_id,
            title=draft_payload["title"],
            body=body,
            branch_name=draft_payload["branch_name"],
            diff=draft_payload["diff"],
            status=self._status_for_decision(decision, payload.open_on_github),
            approval_status=approval_status.value,
            labels_json=labels,
            risk_assessment_json=risk.to_dict(),
            policy_evaluation_json=policy.to_dict(),
            security_scan_json=security_scan.to_dict(),
            approval_history_json=[],
            governance_metadata_json={
                "open_on_github_requested": payload.open_on_github,
                "repository": repository_name,
                "branch": draft_payload["branch_name"],
                "base_branch": repository.default_branch,
                "commit": repository.last_indexed_commit,
                "decision": decision.value,
            },
        )
        if payload.open_on_github and decision == PolicyAction.allow:
            await self._open_on_github(draft, repository.owner, repository.name, repository.default_branch)
        self.session.add(draft)
        self._audit(
            organization_id=organization_id,
            actor_id=user_id,
            action="pull_request.governance_evaluated",
            draft=draft,
            metadata={
                "policy": policy.to_dict(),
                "risk": risk.to_dict(),
                "security_scan": security_scan.to_dict(),
                "labels": labels,
                "decision": decision.value,
            },
        )
        if decision == PolicyAction.block:
            self._audit(
                organization_id=organization_id,
                actor_id=user_id,
                action="pull_request.blocked",
                draft=draft,
                metadata={
                    "reason": "Governance policy, risk threshold, or critical security finding blocked PR creation.",
                    "decision": decision.value,
                    "policy_action": policy.action.value,
                    "risk_score": risk.overall_score,
                    "critical_security_findings": security_scan.has_critical_findings,
                },
            )
        await self.session.commit()
        return draft

    async def review(
        self,
        pull_request_id: uuid.UUID,
        payload: PullRequestApprovalRequest,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> PullRequestDraft:
        draft = await self.session.get(PullRequestDraft, pull_request_id)
        if draft is None:
            raise ApiError("Pull request draft not found.", status.HTTP_404_NOT_FOUND)
        repository = await get_repository_for_organization(
            self.session,
            organization_id,
            draft.repository_id,
        )
        history_entry = {
            "decision": payload.decision,
            "actor_id": str(user_id),
            "timestamp": datetime.now(UTC).isoformat(),
            "reason": payload.reason,
        }
        draft.approval_history_json = [*draft.approval_history_json, history_entry]

        if payload.decision == "rejected":
            draft.approval_status = ApprovalStatus.rejected.value
            draft.status = "rejected"
            draft.labels_json = sorted(set([*draft.labels_json, "needs-review"]))
            self._audit(
                organization_id=organization_id,
                actor_id=user_id,
                action="pull_request.rejected",
                draft=draft,
                metadata=history_entry,
            )
            await self.session.commit()
            return draft

        if draft.policy_evaluation_json.get("action") == PolicyAction.block.value:
            raise ApiError("Blocked pull request drafts cannot be approved.", status.HTTP_409_CONFLICT)
        if any(finding.get("severity") == "critical" for finding in draft.security_scan_json.get("findings", [])):
            raise ApiError("Draft has critical security findings and cannot be approved.", status.HTTP_409_CONFLICT)

        draft.approval_status = ApprovalStatus.approved.value
        draft.status = "approved"
        draft.labels_json = sorted(set(label for label in draft.labels_json if label != "needs-review"))
        if payload.open_on_github:
            await self._open_on_github(draft, repository.owner, repository.name, repository.default_branch)
        self._audit(
            organization_id=organization_id,
            actor_id=user_id,
            action="pull_request.approved",
            draft=draft,
            metadata=history_entry,
        )
        await self.session.commit()
        return draft

    def _decision_from_governance(
        self,
        policy,
        risk_score: int,
        critical_findings: bool,
    ) -> PolicyAction:
        if critical_findings or policy.action == PolicyAction.block:
            return PolicyAction.block
        if risk_score >= self.settings.ai_governance_block_threshold:
            return PolicyAction.block
        if (
            policy.action == PolicyAction.require_approval
            or risk_score >= self.settings.ai_governance_require_approval_threshold
        ):
            return PolicyAction.require_approval
        return PolicyAction.allow

    def _approval_status_for_decision(self, decision: PolicyAction) -> ApprovalStatus:
        if decision == PolicyAction.require_approval:
            return ApprovalStatus.pending_review
        if decision == PolicyAction.block:
            return ApprovalStatus.rejected
        return ApprovalStatus.not_required

    def _status_for_decision(self, decision: PolicyAction, open_requested: bool) -> str:
        if decision == PolicyAction.block:
            return "blocked"
        if decision == PolicyAction.require_approval:
            return "pending_review"
        return "draft" if not open_requested else "opened"

    async def _open_on_github(
        self,
        draft: PullRequestDraft,
        owner: str,
        name: str,
        default_branch: str,
    ) -> None:
        async with GitHubClient() as github:
            pull_request = await github.create_pull_request(
                owner,
                name,
                draft.title,
                draft.body,
                draft.branch_name,
                default_branch,
            )
            await github.add_labels(owner, name, pull_request.number, draft.labels_json)
        draft.github_url = pull_request.html_url
        draft.status = "opened"

    def _audit(
        self,
        *,
        organization_id: uuid.UUID,
        actor_id: uuid.UUID,
        action: str,
        draft: PullRequestDraft,
        metadata: dict,
    ) -> None:
        self.session.add(
            AuditLog(
                organization_id=organization_id,
                actor_id=actor_id,
                action=action,
                resource_type="pull_request",
                resource_id=str(draft.id),
                metadata_json={
                    **metadata,
                    "repository_id": str(draft.repository_id),
                    "branch": draft.branch_name,
                    "commit": draft.governance_metadata_json.get("commit"),
                    "status": draft.status,
                },
            )
        )
