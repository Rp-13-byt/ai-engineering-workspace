import uuid

import pytest

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.models import (
    CodeChunk,
    CodeDocument,
    Repository,
    RepositoryStatus,
)
from ai_workspace_api.modules.indexing.service import IndexingService


class FakeScalarResult:
    def __init__(self, items: list) -> None:
        self._items = items

    def all(self) -> list:
        return self._items


class MockIncrementalSession:
    def __init__(self, repo: Repository, existing_docs: list[CodeDocument]) -> None:
        self.repo = repo
        self.docs = {doc.path: doc for doc in existing_docs}
        self.chunks: list[CodeChunk] = []
        self.deleted_docs: list[CodeDocument] = []
        self.added_docs: list[CodeDocument] = []
        self.flushed = False
        self.commits = 0
        self.rollbacks = 0

    async def get(self, model: type, item_id: uuid.UUID) -> object | None:
        if model is Repository and item_id == self.repo.id:
            return self.repo
        return None

    async def scalars(self, stmt) -> FakeScalarResult:
        return FakeScalarResult(list(self.docs.values()))

    def add(self, item: object) -> None:
        if isinstance(item, CodeDocument):
            self.added_docs.append(item)
            self.docs[item.path] = item
        elif isinstance(item, CodeChunk):
            self.chunks.append(item)

    async def delete(self, item: object) -> None:
        if isinstance(item, CodeDocument):
            self.deleted_docs.append(item)
            self.docs.pop(item.path, None)

    async def execute(self, stmt) -> None:
        pass

    async def flush(self) -> None:
        self.flushed = True

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_incremental_indexing_detects_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    repo_id = uuid.uuid4()
    repo = Repository(
        id=repo_id,
        organization_id=uuid.uuid4(),
        owner="test-owner",
        name="test-repo",
        default_branch="main",
        remote_url="https://github.com/test-owner/test-repo.git",
        indexing_status=RepositoryStatus.indexed,
        last_indexed_commit="commit-1",
        embedding_model="text-embedding-3-small",
    )

    # Pre-existing documents
    doc_unchanged = CodeDocument(
        id=uuid.uuid4(),
        repository_id=repo_id,
        path="src/unchanged.py",
        language="python",
        commit_sha="commit-1",
        content_hash="hash_unchanged",
        size_bytes=50,
    )
    doc_modified = CodeDocument(
        id=uuid.uuid4(),
        repository_id=repo_id,
        path="src/modified.py",
        language="python",
        commit_sha="commit-1",
        content_hash="old_hash_modified",
        size_bytes=60,
    )
    doc_deleted = CodeDocument(
        id=uuid.uuid4(),
        repository_id=repo_id,
        path="src/deleted.py",
        language="python",
        commit_sha="commit-1",
        content_hash="hash_deleted",
        size_bytes=40,
    )

    session = MockIncrementalSession(
        repo=repo,
        existing_docs=[doc_unchanged, doc_modified, doc_deleted],
    )

    # Mock GitHubClient
    class FakeGitHubClient:
        async def get_tree(self, owner: str, name: str, ref: str) -> list[dict]:
            return [
                {"path": "src/unchanged.py", "type": "blob", "size": 50},
                {"path": "src/modified.py", "type": "blob", "size": 80},
                {"path": "src/added.py", "type": "blob", "size": 90},
            ]

        async def get_file_content(self, owner: str, name: str, path: str, ref: str) -> str:
            if path == "src/unchanged.py":
                return "UNCHANGED_CONTENT"
            if path == "src/modified.py":
                return "MODIFIED_CONTENT_V2"
            if path == "src/added.py":
                return "def new_function(): return True"
            return ""

    from ai_workspace_api.modules.indexing import service as indexing_service_module
    monkeypatch.setattr(indexing_service_module, "GitHubClient", FakeGitHubClient)

    service = IndexingService(
        session=session,  # type: ignore[arg-type]
        settings=Settings(embedding_provider="mock", embedding_model="text-embedding-3-small"),
    )

    # Align hash for unchanged file
    doc_unchanged.content_hash = service._sha256("UNCHANGED_CONTENT")

    stats = await service.index_repository(repo_id, target_commit="commit-2")

    # Verify change detection
    assert stats.unchanged_files == 1
    assert stats.modified_files == 1
    assert stats.added_files == 1
    assert stats.deleted_files == 1

    # Verify deleted file was removed from session
    assert any(d.path == "src/deleted.py" for d in session.deleted_docs)

    # Verify added file was created
    assert any(d.path == "src/added.py" for d in session.added_docs)

    # Verify repository status
    assert repo.indexing_status == RepositoryStatus.indexed
    assert repo.last_indexed_commit == "commit-2"


@pytest.mark.asyncio
async def test_indexing_failure_triggers_rollback(monkeypatch: pytest.MonkeyPatch) -> None:
    repo_id = uuid.uuid4()
    repo = Repository(
        id=repo_id,
        organization_id=uuid.uuid4(),
        owner="test-owner",
        name="test-repo",
        default_branch="main",
        remote_url="https://github.com/test-owner/test-repo.git",
        indexing_status=RepositoryStatus.indexed,
    )
    session = MockIncrementalSession(repo=repo, existing_docs=[])

    class FailingGitHubClient:
        async def get_tree(self, owner: str, name: str, ref: str) -> list[dict]:
            raise ConnectionError("GitHub network timeout")

    from ai_workspace_api.modules.indexing import service as indexing_service_module
    monkeypatch.setattr(indexing_service_module, "GitHubClient", FailingGitHubClient)

    service = IndexingService(
        session=session,  # type: ignore[arg-type]
        settings=Settings(embedding_provider="mock"),
    )

    with pytest.raises(ConnectionError):
        await service.index_repository(repo_id)

    # Verify rollback was triggered to preserve existing database state
    assert session.rollbacks >= 1
    assert repo.indexing_status == RepositoryStatus.failed
