import uuid

import pytest

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.errors import ApiError
from ai_workspace_api.core.models import Repository
from ai_workspace_api.infrastructure.llm import RetrievedContext
from ai_workspace_api.infrastructure.vector_store import reciprocal_rank_fusion
from ai_workspace_api.modules.search.schemas import SearchRequest
from ai_workspace_api.modules.search.service import SearchService


def test_reciprocal_rank_fusion_combines_and_deduplicates() -> None:
    semantic_results = [
        RetrievedContext(
            path="src/auth.py",
            start_line=10,
            end_line=25,
            content="def authenticate(): pass",
            score=0.92,
            symbol="authenticate",
        ),
        RetrievedContext(
            path="src/user.py",
            start_line=1,
            end_line=20,
            content="class User: pass",
            score=0.85,
            symbol="User",
        ),
    ]

    lexical_results = [
        RetrievedContext(
            path="src/auth.py",
            start_line=10,
            end_line=25,
            content="def authenticate(): pass",
            score=1.5,
            symbol="authenticate",
        ),
        RetrievedContext(
            path="src/config.py",
            start_line=5,
            end_line=15,
            content="AUTH_TOKEN = 'secret'",
            score=0.9,
            symbol="AUTH_TOKEN",
        ),
    ]

    symbol_results = [
        RetrievedContext(
            path="src/auth.py",
            start_line=10,
            end_line=25,
            content="def authenticate(): pass",
            score=1.0,
            symbol="authenticate",
        ),
    ]

    # Combine rankings with weights: semantic=1.0, lexical=0.8, symbol=1.2
    fused = reciprocal_rank_fusion(
        [
            (semantic_results, 1.0),
            (lexical_results, 0.8),
            (symbol_results, 1.2),
        ],
        k=60,
        limit=5,
    )

    # Deduplication: auth.py appeared in all 3 sets, appears once in fused
    auth_occurrences = [c for c in fused if c.path == "src/auth.py"]
    assert len(auth_occurrences) == 1

    # auth.py should have top fused score
    assert fused[0].path == "src/auth.py"
    assert fused[0].symbol == "authenticate"
    assert fused[0].score > fused[1].score


class FakeSession:
    def __init__(self, values: dict) -> None:
        self.values = values

    async def get(self, model: type, item_id: uuid.UUID) -> object | None:
        return self.values.get((model, item_id))


@pytest.mark.asyncio
async def test_search_isolation_rejects_unauthorized_org() -> None:
    repo_id = uuid.uuid4()
    owner_org_id = uuid.uuid4()
    other_org_id = uuid.uuid4()

    repo = Repository(
        id=repo_id,
        organization_id=owner_org_id,
        owner="owner",
        name="repo",
        remote_url="https://github.com/owner/repo.git",
        default_branch="main",
    )
    session = FakeSession({(Repository, repo_id): repo})

    service = SearchService(
        session=session,  # type: ignore[arg-type]
        redis=None,
        settings=Settings(embedding_provider="mock"),
    )

    payload = SearchRequest(repository_id=repo_id, query="authenticate")

    # Request from unauthorized organization must be rejected with 404
    with pytest.raises(ApiError) as exc_info:
        await service.hybrid_search(payload, organization_id=other_org_id)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_search_service_semantic_and_hybrid(monkeypatch: pytest.MonkeyPatch) -> None:
    repo_id = uuid.uuid4()
    org_id = uuid.uuid4()
    repo = Repository(
        id=repo_id,
        organization_id=org_id,
        owner="owner",
        name="repo",
        remote_url="https://github.com/owner/repo.git",
        default_branch="main",
        last_indexed_commit="c1",
        embedding_model="mock-model",
    )
    session = FakeSession({(Repository, repo_id): repo})

    class MockVectorStore:
        def __init__(self, session) -> None:
            pass

        async def semantic_search(self, repository_id, embedding, limit, embedding_model=None):
            return [
                RetrievedContext(
                    path="main.py",
                    start_line=1,
                    end_line=10,
                    content="def main(): pass",
                    score=0.95,
                    symbol="main",
                )
            ]

        async def lexical_search(self, repository_id, query, limit):
            return [
                RetrievedContext(
                    path="main.py",
                    start_line=1,
                    end_line=10,
                    content="def main(): pass",
                    score=1.2,
                    symbol="main",
                )
            ]

        async def symbol_search(self, repository_id, symbol_name, limit):
            return [
                RetrievedContext(
                    path="main.py",
                    start_line=1,
                    end_line=10,
                    content="def main(): pass",
                    score=1.0,
                    symbol="main",
                )
            ]

    from ai_workspace_api.modules.search import service as search_service_module
    monkeypatch.setattr(search_service_module, "VectorStore", MockVectorStore)

    service = SearchService(
        session=session,  # type: ignore[arg-type]
        redis=None,
        settings=Settings(embedding_provider="mock"),
    )

    req = SearchRequest(repository_id=repo_id, query="main", exact_symbol="main")

    # Semantic search call
    semantic_resp = await service.semantic_search(req, organization_id=org_id)
    assert len(semantic_resp.results) == 1
    assert semantic_resp.results[0].symbol == "main"
    assert semantic_resp.results[0].path == "main.py"

    # Hybrid search call with fusion
    hybrid_resp = await service.hybrid_search(req, organization_id=org_id)
    assert len(hybrid_resp.results) == 1
    assert hybrid_resp.results[0].symbol == "main"
    assert hybrid_resp.results[0].score > 0
