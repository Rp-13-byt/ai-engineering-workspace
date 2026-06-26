import uuid
from unittest.mock import AsyncMock

import pytest

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.errors import ApiError
from ai_workspace_api.core.models import AuditLog, PullRequestDraft, Repository
from ai_workspace_api.modules.pull_requests.diff_parser import extract_changed_files
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
from ai_workspace_api.modules.pull_requests.service import PullRequestService

DOCS_DIFF = """diff --git a/docs/guide.md b/docs/guide.md
--- a/docs/guide.md
+++ b/docs/guide.md
@@
+hello
"""

INFRA_DIFF = """diff --git a/infra/k8s/web.yaml b/infra/k8s/web.yaml
--- a/infra/k8s/web.yaml
+++ b/infra/k8s/web.yaml
@@
+kind: Deployment
"""

WORKFLOW_DIFF = """diff --git a/.github/workflows/deploy.yml b/.github/workflows/deploy.yml
--- a/.github/workflows/deploy.yml
+++ b/.github/workflows/deploy.yml
@@
+name: deploy
"""


class FakeSession:
    def __init__(self, values: dict[tuple[type, uuid.UUID], object] | None = None) -> None:
        self.values = values or {}
        self.added: list[object] = []
        self.commits = 0

    async def get(self, model: type, item_id: uuid.UUID) -> object | None:
        return self.values.get((model, item_id))

    def add(self, item: object) -> None:
        self.added.append(item)

    async def commit(self) -> None:
        self.commits += 1


class FakeLLM:
    def __init__(self, diff: str) -> None:
        self.diff = diff

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    async def generate_pull_request(self, instructions: str, contexts: list[object]) -> dict[str, str]:
        return {
            "title": "AI change",
            "body": "Implements the requested change.",
            "branch_name": "ai/test-change",
            "diff": self.diff,
        }


class FakeVectorStore:
    async def semantic_search(self, repository_id: uuid.UUID, embedding: list[float], limit: int) -> list[object]:
        return []


def test_policy_engine_blocks_workflows_and_allows_docs() -> None:
    engine = PolicyEngine()

    blocked = engine.evaluate([".github/workflows/deploy.yml"], "acme/app", "acme")
    allowed = engine.evaluate(["docs/guide.md"], "acme/app", "acme")

    assert blocked.action == PolicyAction.block
    assert allowed.action == PolicyAction.allow


def test_policy_engine_requires_approval_for_infrastructure() -> None:
    evaluation = PolicyEngine().evaluate(["infra/k8s/web.yaml"], "acme/app", "acme")

    assert evaluation.action == PolicyAction.require_approval
    assert "protect-infrastructure" in evaluation.files[0].matched_rules


def test_policy_engine_blocks_empty_or_unparsable_diffs() -> None:
    evaluation = PolicyEngine().evaluate([], "acme/app", "acme")

    assert evaluation.action == PolicyAction.block
    assert "empty or unparsable diffs are blocked" in evaluation.explanations[0]


def test_risk_engine_scores_protected_platform_files() -> None:
    changes = extract_changed_files(INFRA_DIFF)
    assessment = RiskEngine().assess(changes)

    assert assessment.level == "high"
    assert assessment.overall_score >= 70
    assert {"infrastructure", "kubernetes"}.issubset(set(assessment.files[0].factors))


def test_security_scanner_blocks_generated_secrets() -> None:
    diff = """diff --git a/src/settings.py b/src/settings.py
--- a/src/settings.py
+++ b/src/settings.py
@@
+API_KEY = "abcdefghijklmnop123456"
"""

    result = SecurityScanner().scan(diff, ["src/settings.py"])

    assert result.has_critical_findings
    assert result.findings[0].scanner == "secret-scanning"


@pytest.mark.asyncio
async def test_generate_blocks_workflow_pr_without_opening(monkeypatch: pytest.MonkeyPatch) -> None:
    repository_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    repository = Repository(
        id=repository_id,
        organization_id=organization_id,
        owner="acme",
        name="app",
        remote_url="https://github.com/acme/app.git",
        default_branch="main",
        last_indexed_commit="abc123",
    )

    async def fake_get_repository(session, org_id: uuid.UUID, repo_id: uuid.UUID) -> Repository:
        assert org_id == organization_id
        assert repo_id == repository_id
        return repository

    monkeypatch.setattr(
        "ai_workspace_api.modules.pull_requests.service.get_repository_for_organization",
        fake_get_repository,
    )
    session = FakeSession()
    service = PullRequestService(session=session, settings=Settings(embedding_cache_ttl_hours=0))  # type: ignore[arg-type]
    service.llm = FakeLLM(WORKFLOW_DIFF)  # type: ignore[assignment]
    service.vector_store = FakeVectorStore()  # type: ignore[assignment]
    service._open_on_github = AsyncMock()  # type: ignore[method-assign]

    draft = await service.generate(
        PullRequestGenerateRequest(
            repository_id=repository_id,
            instructions="Update deployment workflow",
            open_on_github=True,
        ),
        user_id=uuid.uuid4(),
        organization_id=organization_id,
    )

    assert draft.status == "blocked"
    assert draft.approval_status == ApprovalStatus.rejected.value
    assert "needs-review" in draft.labels_json
    assert draft.policy_evaluation_json["action"] == PolicyAction.block.value
    service._open_on_github.assert_not_called()
    assert any(isinstance(item, AuditLog) for item in session.added)


@pytest.mark.asyncio
async def test_generate_requires_review_for_infrastructure(monkeypatch: pytest.MonkeyPatch) -> None:
    repository_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    repository = Repository(
        id=repository_id,
        organization_id=organization_id,
        owner="acme",
        name="app",
        remote_url="https://github.com/acme/app.git",
        default_branch="main",
    )

    async def fake_get_repository(session, org_id: uuid.UUID, repo_id: uuid.UUID) -> Repository:
        return repository

    monkeypatch.setattr(
        "ai_workspace_api.modules.pull_requests.service.get_repository_for_organization",
        fake_get_repository,
    )
    service = PullRequestService(
        session=FakeSession(),
        settings=Settings(embedding_cache_ttl_hours=0, ai_governance_block_threshold=95),
    )  # type: ignore[arg-type]
    service.llm = FakeLLM(INFRA_DIFF)  # type: ignore[assignment]
    service.vector_store = FakeVectorStore()  # type: ignore[assignment]
    service._open_on_github = AsyncMock()  # type: ignore[method-assign]

    draft = await service.generate(
        PullRequestGenerateRequest(
            repository_id=repository_id,
            instructions="Update web deployment",
            open_on_github=True,
        ),
        user_id=uuid.uuid4(),
        organization_id=organization_id,
    )

    assert draft.status == "pending_review"
    assert draft.approval_status == ApprovalStatus.pending_review.value
    assert "needs-review" in draft.labels_json
    service._open_on_github.assert_not_called()


@pytest.mark.asyncio
async def test_review_approval_records_audit_trail_and_opens(monkeypatch: pytest.MonkeyPatch) -> None:
    pull_request_id = uuid.uuid4()
    repository_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    repository = Repository(
        id=repository_id,
        organization_id=organization_id,
        owner="acme",
        name="app",
        remote_url="https://github.com/acme/app.git",
        default_branch="main",
    )
    draft = PullRequestDraft(
        id=pull_request_id,
        repository_id=repository_id,
        created_by_id=uuid.uuid4(),
        title="AI change",
        body="body",
        branch_name="ai/change",
        diff=DOCS_DIFF,
        status="pending_review",
        approval_status=ApprovalStatus.pending_review.value,
        labels_json=["ai-generated", "risk-medium", "needs-review"],
        policy_evaluation_json={"action": PolicyAction.require_approval.value},
        security_scan_json={"findings": []},
        approval_history_json=[],
        governance_metadata_json={"commit": "abc123"},
    )

    async def fake_get_repository(session, org_id: uuid.UUID, repo_id: uuid.UUID) -> Repository:
        return repository

    monkeypatch.setattr(
        "ai_workspace_api.modules.pull_requests.service.get_repository_for_organization",
        fake_get_repository,
    )
    session = FakeSession({(PullRequestDraft, pull_request_id): draft})
    service = PullRequestService(session=session, settings=Settings(embedding_cache_ttl_hours=0))  # type: ignore[arg-type]
    service._open_on_github = AsyncMock()  # type: ignore[method-assign]

    reviewed = await service.review(
        pull_request_id,
        PullRequestApprovalRequest(
            decision="approved",
            reason="Reviewed deployment impact",
            open_on_github=True,
        ),
        user_id=uuid.uuid4(),
        organization_id=organization_id,
    )

    assert reviewed.approval_status == ApprovalStatus.approved.value
    assert reviewed.approval_history_json[0]["reason"] == "Reviewed deployment impact"
    assert "needs-review" not in reviewed.labels_json
    service._open_on_github.assert_awaited_once()
    assert any(isinstance(item, AuditLog) and item.action == "pull_request.approved" for item in session.added)


@pytest.mark.asyncio
async def test_review_cannot_approve_blocked_draft(monkeypatch: pytest.MonkeyPatch) -> None:
    pull_request_id = uuid.uuid4()
    repository_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    draft = PullRequestDraft(
        id=pull_request_id,
        repository_id=repository_id,
        created_by_id=uuid.uuid4(),
        title="AI change",
        body="body",
        branch_name="ai/change",
        diff=WORKFLOW_DIFF,
        status="blocked",
        approval_status=ApprovalStatus.rejected.value,
        labels_json=["ai-generated", "risk-high", "needs-review"],
        policy_evaluation_json={"action": PolicyAction.block.value},
        security_scan_json={"findings": []},
        approval_history_json=[],
        governance_metadata_json={"commit": "abc123"},
    )
    repository = Repository(
        id=repository_id,
        organization_id=organization_id,
        owner="acme",
        name="app",
        remote_url="https://github.com/acme/app.git",
    )

    async def fake_get_repository(session, org_id: uuid.UUID, repo_id: uuid.UUID) -> Repository:
        return repository

    monkeypatch.setattr(
        "ai_workspace_api.modules.pull_requests.service.get_repository_for_organization",
        fake_get_repository,
    )
    service = PullRequestService(
        session=FakeSession({(PullRequestDraft, pull_request_id): draft}),
        settings=Settings(embedding_cache_ttl_hours=0),
    )  # type: ignore[arg-type]

    with pytest.raises(ApiError):
        await service.review(
            pull_request_id,
            PullRequestApprovalRequest(
                decision="approved",
                reason="Trying to approve",
                open_on_github=False,
            ),
            user_id=uuid.uuid4(),
            organization_id=organization_id,
        )
