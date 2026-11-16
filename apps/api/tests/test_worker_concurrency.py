import json
import uuid

import pytest

from ai_workspace_api.core.models import JobRecord
from ai_workspace_api.infrastructure.distributed_lock import DistributedLock
from ai_workspace_api.workers import main as worker_main


class FakeProcessContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        return False


class FakeMessage:
    def __init__(self, body: dict) -> None:
        self.body = json.dumps(body).encode("utf-8")
        self.requeue: bool | None = None

    def process(self, requeue: bool) -> FakeProcessContext:
        self.requeue = requeue
        return FakeProcessContext()


class FakeSession:
    def __init__(self, job: JobRecord | None) -> None:
        self.job = job
        self.commits = 0
        self.added: list[JobRecord] = []

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        return False

    async def scalar(self, statement) -> JobRecord | None:
        return self.job

    def add(self, job: JobRecord) -> None:
        self.added.append(job)
        self.job = job

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_worker_skips_duplicate_delivery_if_succeeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_id = uuid.uuid4()
    idempotency_key = f"index:{repo_id}:main"
    job = JobRecord(
        job_type="repository.index",
        status="succeeded",
        idempotency_key=idempotency_key,
        payload={"repository_id": str(repo_id)},
        attempts=1,
    )
    session = FakeSession(job)
    indexed_called = False

    class FakeIndexingService:
        def __init__(self, session, settings) -> None:
            pass

        async def index_repository(self, indexed_repository_id: uuid.UUID) -> None:
            nonlocal indexed_called
            indexed_called = True

    monkeypatch.setattr(worker_main, "SessionLocal", lambda: session)
    monkeypatch.setattr(worker_main, "IndexingService", FakeIndexingService)

    message = FakeMessage(
        {
            "job_type": "repository.index",
            "payload": {"repository_id": str(repo_id)},
            "idempotency_key": idempotency_key,
        }
    )

    await worker_main.handle_message(message)  # type: ignore[arg-type]

    # Verification: already succeeded job must not be re-executed
    assert not indexed_called
    assert job.status == "succeeded"
    assert job.attempts == 1


@pytest.mark.asyncio
async def test_worker_retries_after_previous_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    repo_id = uuid.uuid4()
    idempotency_key = f"index:{repo_id}:main"
    job = JobRecord(
        job_type="repository.index",
        status="failed",
        idempotency_key=idempotency_key,
        payload={"repository_id": str(repo_id)},
        attempts=1,
        last_error="previous network error",
    )
    session = FakeSession(job)
    indexed_called = False

    class FakeIndexingService:
        def __init__(self, session, settings) -> None:
            pass

        async def index_repository(self, indexed_repository_id: uuid.UUID) -> None:
            nonlocal indexed_called
            indexed_called = True

    monkeypatch.setattr(worker_main, "SessionLocal", lambda: session)
    monkeypatch.setattr(worker_main, "IndexingService", FakeIndexingService)

    message = FakeMessage(
        {
            "job_type": "repository.index",
            "payload": {"repository_id": str(repo_id)},
            "idempotency_key": idempotency_key,
        }
    )

    await worker_main.handle_message(message)  # type: ignore[arg-type]

    assert indexed_called
    assert job.status == "succeeded"
    assert job.attempts == 2
    assert job.last_error is None


@pytest.mark.asyncio
async def test_distributed_lock_contention() -> None:
    # Test Redis lock behavior with mock Redis
    redis_store: dict[str, str] = {}

    class MockRedis:
        async def set(self, key: str, val: str, nx: bool = False, ex: int = 0) -> bool:
            if nx and key in redis_store:
                return False
            redis_store[key] = val
            return True

        async def get(self, key: str) -> str | None:
            return redis_store.get(key)

        async def eval(self, script: str, numkeys: int, key: str, token: str) -> int:
            if redis_store.get(key) == token:
                del redis_store[key]
                return 1
            return 0

    mock_redis = MockRedis()
    lock1 = DistributedLock(mock_redis, "lock:repo-1", ttl_seconds=60)  # type: ignore[arg-type]
    lock2 = DistributedLock(mock_redis, "lock:repo-1", ttl_seconds=60)  # type: ignore[arg-type]

    # First worker acquires lock
    assert await lock1.acquire() is True

    # Second worker attempts to acquire same lock simultaneously -> must be rejected
    assert await lock2.acquire() is False

    # First worker releases lock
    assert await lock1.release() is True

    # Now second worker can acquire
    assert await lock2.acquire() is True
    await lock2.release()
