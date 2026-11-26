"""API and service integration tests for ChangeLens REST endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from ai_workspace_api.core.database import get_session
from ai_workspace_api.core.dependencies import get_current_user, get_organization_id
from ai_workspace_api.core.errors import ApiError
from ai_workspace_api.core.models import ChangeAnalysis, Membership, Repository, Role, User
from ai_workspace_api.main import app
from ai_workspace_api.modules.changelens.router import get_changelens_service
from ai_workspace_api.modules.changelens.schemas import (
    ChangeAnalysisListResponse,
    ChangeAnalysisRead,
    ChangeAnalysisRequest,
)
from ai_workspace_api.modules.changelens.service import ChangeLensService
from ai_workspace_api.modules.changelens.test_selection import SelectionMode

SAMPLE_DIFF = """\
diff --git a/apps/api/auth.py b/apps/api/auth.py
--- a/apps/api/auth.py
+++ b/apps/api/auth.py
@@ -1,3 +1,5 @@
 def verify_token(token: str) -> bool:
+    if not token:
+        return False
     return token.startswith("valid_")
"""

SAMPLE_FILE = """\
def verify_token(token: str) -> bool:
    if not token:
        return False
    return token.startswith("valid_")
"""


class FakeSession:
    """In-memory AsyncSession stub for service-level tests."""

    def __init__(self, repo: Repository) -> None:
        self.repo = repo
        self.saved_records: dict[uuid.UUID, ChangeAnalysis] = {}
        self.committed = False

    async def get(self, model: type, item_id: uuid.UUID) -> object | None:
        if model is Repository and item_id == self.repo.id:
            return self.repo
        return None

    def add(self, item: Any) -> None:
        if getattr(item, "id", None) is None:
            item.id = uuid.uuid4()
        if getattr(item, "created_at", None) is None and hasattr(item, "created_at"):
            item.created_at = datetime.now(UTC)
        if isinstance(item, ChangeAnalysis):
            if item.findings is None:
                item.findings = []
            if item.test_plans is None:
                item.test_plans = []
            self.saved_records[item.id] = item

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        self.committed = True

    async def execute(self, stmt: Any) -> MagicMock:
        result = MagicMock()
        records = list(self.saved_records.values())
        result.scalar_one_or_none.return_value = records[0] if records else None
        result.scalars.return_value.all.return_value = records
        return result

    async def delete(self, item: Any) -> None:
        if isinstance(item, ChangeAnalysis):
            self.saved_records.pop(item.id, None)


@pytest.mark.asyncio
async def test_analyze_change_service_end_to_end() -> None:
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    repo = Repository(
        id=repo_id,
        organization_id=org_id,
        owner="acme",
        name="backend",
        remote_url="https://github.com/acme/backend.git",
    )
    session = FakeSession(repo)
    service = ChangeLensService(session)  # type: ignore[arg-type]

    payload = ChangeAnalysisRequest(
        repository_id=repo_id,
        base_sha="base111",
        head_sha="head222",
        diff_text=SAMPLE_DIFF,
        selection_mode=SelectionMode.FAST_FEEDBACK,
        pr_number=17,
        file_contents={"apps/api/auth.py": SAMPLE_FILE},
        test_index={"apps/api/auth.py:verify_token": ["tests/test_auth.py::test_verify_token"]},
    )

    result = await service.analyze_change(payload, org_id)

    assert session.committed is True
    assert result.repository_id == repo_id
    assert result.base_sha == "base111"
    assert result.head_sha == "head222"
    assert result.pr_number == 17
    assert result.risk_score >= 0.0
    assert result.risk_level in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert len(result.dimensions) == 6


@pytest.mark.asyncio
async def test_service_rejects_cross_organization_repository() -> None:
    org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()
    repo = Repository(
        id=uuid.uuid4(),
        organization_id=other_org_id,
        owner="acme",
        name="private-repo",
        remote_url="https://github.com/acme/private-repo.git",
    )
    session = FakeSession(repo)
    service = ChangeLensService(session)  # type: ignore[arg-type]

    payload = ChangeAnalysisRequest(
        repository_id=repo.id,
        base_sha="aaa",
        head_sha="bbb",
        diff_text=SAMPLE_DIFF,
    )

    with pytest.raises(ApiError) as exc_info:
        await service.analyze_change(payload, org_id)

    assert exc_info.value.status_code == 404


def test_changelens_router_endpoints() -> None:
    org_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    analysis_id = uuid.uuid4()

    sample_read = ChangeAnalysisRead(
        id=analysis_id,
        repository_id=repo_id,
        base_sha="abc",
        head_sha="def",
        pr_number=9,
        risk_score=45.0,
        risk_level="MEDIUM",
        confidence_score=0.9,
        blast_radius=3,
        summary="Medium risk change",
        dimensions=[],
        breaking_indicators=[],
        requires_human_approval=False,
        findings=[],
        test_plans=[],
        created_at=datetime.now(UTC),
    )

    mock_service = MagicMock(spec=ChangeLensService)
    mock_service.analyze_change = AsyncMock(return_value=sample_read)
    mock_service.get_analysis = AsyncMock(return_value=sample_read)
    mock_service.list_analyses = AsyncMock(
        return_value=ChangeAnalysisListResponse(items=[sample_read], total=1)
    )
    mock_service.delete_analysis = AsyncMock(return_value=None)

    fake_user = User(
        id=uuid.uuid4(),
        email="eng@acme.dev",
        display_name="Engineer",
        is_verified=True,
        is_active=True,
    )
    fake_membership = Membership(
        id=uuid.uuid4(),
        user_id=fake_user.id,
        organization_id=org_id,
        role=Role.owner,
    )
    fake_db_result = MagicMock()
    fake_db_result.scalar_one_or_none.return_value = fake_membership
    fake_db_session = MagicMock()
    fake_db_session.execute = AsyncMock(return_value=fake_db_result)

    app.dependency_overrides[get_organization_id] = lambda: org_id
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_session] = lambda: fake_db_session
    app.dependency_overrides[get_changelens_service] = lambda: mock_service

    try:
        client = TestClient(app)

        # POST /api/v1/changelens/analyze
        resp_post = client.post(
            "/api/v1/changelens/analyze",
            json={
                "repository_id": str(repo_id),
                "base_sha": "abc",
                "head_sha": "def",
                "diff_text": SAMPLE_DIFF,
            },
        )
        assert resp_post.status_code == 201
        assert resp_post.json()["id"] == str(analysis_id)
        assert resp_post.json()["risk_level"] == "MEDIUM"

        # GET /api/v1/changelens/analyses/{id}
        resp_get = client.get(f"/api/v1/changelens/analyses/{analysis_id}")
        assert resp_get.status_code == 200
        assert resp_get.json()["risk_score"] == 45.0

        # GET /api/v1/changelens/repositories/{repo_id}/analyses
        resp_list = client.get(f"/api/v1/changelens/repositories/{repo_id}/analyses")
        assert resp_list.status_code == 200
        assert resp_list.json()["total"] == 1

        # DELETE /api/v1/changelens/analyses/{id}
        resp_del = client.delete(f"/api/v1/changelens/analyses/{analysis_id}")
        assert resp_del.status_code == 204
    finally:
        app.dependency_overrides.clear()
