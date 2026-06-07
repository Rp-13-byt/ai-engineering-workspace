import uuid

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.errors import ApiError
from ai_workspace_api.core.models import Repository, TaskStatus, WorkspaceTask
from ai_workspace_api.modules.tasks.schemas import TaskCreateRequest, TaskUpdateRequest


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, organization_id: uuid.UUID, payload: TaskCreateRequest) -> WorkspaceTask:
        repository = await self._get_repository(organization_id, payload.repository_id)
        task = WorkspaceTask(
            repository_id=repository.id,
            assignee_id=payload.assignee_id,
            title=payload.title,
            description=payload.description,
            status=TaskStatus.todo,
            priority=payload.priority,
        )
        self.session.add(task)
        await self.session.commit()
        return task

    async def list(
        self,
        organization_id: uuid.UUID,
        repository_id: uuid.UUID | None,
        status_filter: TaskStatus | None,
        limit: int,
        offset: int,
    ) -> tuple[list[WorkspaceTask], int]:
        repository_ids = select(Repository.id).where(Repository.organization_id == organization_id)
        criteria = [WorkspaceTask.repository_id.in_(repository_ids)]
        if repository_id:
            criteria.append(WorkspaceTask.repository_id == repository_id)
        if status_filter:
            criteria.append(WorkspaceTask.status == status_filter)
        total = await self.session.scalar(select(func.count(WorkspaceTask.id)).where(*criteria))
        rows = await self.session.scalars(
            select(WorkspaceTask)
            .where(*criteria)
            .order_by(WorkspaceTask.priority.asc(), WorkspaceTask.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(rows), int(total or 0)

    async def update(
        self,
        organization_id: uuid.UUID,
        task_id: uuid.UUID,
        payload: TaskUpdateRequest,
    ) -> WorkspaceTask:
        task = await self.session.get(WorkspaceTask, task_id)
        if task is None:
            raise ApiError("Task not found", status.HTTP_404_NOT_FOUND)
        await self._get_repository(organization_id, task.repository_id)
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(task, key, value)
        await self.session.commit()
        return task

    async def _get_repository(self, organization_id: uuid.UUID, repository_id: uuid.UUID) -> Repository:
        repository = await self.session.get(Repository, repository_id)
        if repository is None or repository.organization_id != organization_id:
            raise ApiError("Repository not found", status.HTTP_404_NOT_FOUND)
        return repository
