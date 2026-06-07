import uuid

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.errors import ApiError
from ai_workspace_api.core.models import JobRecord, Repository, RepositoryStatus
from ai_workspace_api.infrastructure.github import GitHubClient
from ai_workspace_api.infrastructure.queue import JobMessage, QueuePublisher


class RepositoryService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.queue = QueuePublisher(settings)

    async def import_repository(
        self,
        organization_id: uuid.UUID,
        owner: str,
        name: str,
        provider: str,
    ) -> Repository:
        if provider != "github":
            raise ApiError("Only GitHub repositories are supported today", status.HTTP_400_BAD_REQUEST)
        existing = await self.session.scalar(
            select(Repository).where(
                Repository.organization_id == organization_id,
                Repository.provider == provider,
                Repository.owner == owner,
                Repository.name == name,
            )
        )
        if existing is not None:
            await self.enqueue_indexing(existing)
            return existing

        remote = await GitHubClient().get_repository(owner, name)
        repository = Repository(
            organization_id=organization_id,
            provider=provider,
            owner=remote.owner,
            name=remote.name,
            default_branch=remote.default_branch,
            remote_url=remote.clone_url,
            indexing_status=RepositoryStatus.queued,
            metadata_json={"private": remote.private},
        )
        self.session.add(repository)
        await self.session.flush()
        await self.enqueue_indexing(repository)
        await self.session.commit()
        return repository

    async def list_repositories(
        self,
        organization_id: uuid.UUID,
        limit: int,
        offset: int,
        search: str | None,
        status_filter: RepositoryStatus | None,
    ) -> tuple[list[Repository], int]:
        criteria = [Repository.organization_id == organization_id]
        if status_filter:
            criteria.append(Repository.indexing_status == status_filter)
        if search:
            pattern = f"%{search.lower()}%"
            criteria.append(func.lower(Repository.name).like(pattern))
        total = await self.session.scalar(select(func.count(Repository.id)).where(*criteria))
        rows = await self.session.scalars(
            select(Repository)
            .where(*criteria)
            .order_by(Repository.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(rows), int(total or 0)

    async def get_repository(self, organization_id: uuid.UUID, repository_id: uuid.UUID) -> Repository:
        repository = await self.session.get(Repository, repository_id)
        if repository is None or repository.organization_id != organization_id:
            raise ApiError("Repository not found", status.HTTP_404_NOT_FOUND)
        return repository

    async def enqueue_indexing(self, repository: Repository) -> str:
        idempotency_key = f"index:{repository.id}:{repository.default_branch}"
        existing_job = await self.session.scalar(
            select(JobRecord).where(JobRecord.idempotency_key == idempotency_key)
        )
        if existing_job is None:
            self.session.add(
                JobRecord(
                    job_type="repository.index",
                    status="queued",
                    idempotency_key=idempotency_key,
                    payload={"repository_id": str(repository.id)},
                )
            )
        repository.indexing_status = RepositoryStatus.queued
        await self.session.flush()
        await self.queue.publish(
            "repository.index",
            JobMessage(
                job_type="repository.index",
                payload={"repository_id": str(repository.id)},
                idempotency_key=idempotency_key,
            ),
        )
        return idempotency_key
