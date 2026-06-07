import json
import uuid

import pytest

from ai_workspace_api.core.models import JobRecord
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
    def __init__(self, job: JobRecord) -> None:
        self.job = job
        self.commits = 0
        self.added: list[JobRecord] = []

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> bool:
        return False

    async def scalar(self, statement) -> JobRecord:
        return self.job

    def add(self, job: JobRecord) -> None:
        self.added.append(job)

    async def commit(self) -> None:
        self.commits += 1


@pytest.mark.asyncio
async def test_worker_updates_job_by_idempotency_key(monkeypatch: pytest.MonkeyPatch) -> None:
    repository_id = uuid.uuid4()
    idempotency_key = f"index:{repository_id}:main"
    job = JobRecord(
        job_type="repository.index",
        status="queued",
        idempotency_key=idempotency_key,
        payload={"repository_id": str(repository_id)},
        attempts=2,
        last_error="previous failure",
    )
    session = FakeSession(job)

    class FakeIndexingService:
        def __init__(self, session, settings) -> None:
            self.session = session
            self.settings = settings

        async def index_repository(self, indexed_repository_id: uuid.UUID) -> None:
            assert indexed_repository_id == repository_id

    monkeypatch.setattr(worker_main, "SessionLocal", lambda: session)
    monkeypatch.setattr(worker_main, "IndexingService", FakeIndexingService)

    message = FakeMessage(
        {
            "job_type": "repository.index",
            "payload": {"repository_id": str(repository_id)},
            "idempotency_key": idempotency_key,
        }
    )

    await worker_main.handle_message(message)  # type: ignore[arg-type]

    assert message.requeue is False
    assert job.status == "succeeded"
    assert job.attempts == 3
    assert job.last_error is None
    assert session.commits == 1
