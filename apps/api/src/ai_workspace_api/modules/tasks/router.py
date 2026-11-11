import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.database import get_session
from ai_workspace_api.core.dependencies import get_organization_id, require_permission
from ai_workspace_api.core.models import TaskStatus, User
from ai_workspace_api.core.permissions import Permission
from ai_workspace_api.modules.tasks.schemas import (
    TaskCreateRequest,
    TaskListResponse,
    TaskRead,
    TaskUpdateRequest,
)
from ai_workspace_api.modules.tasks.service import TaskService

router = APIRouter(prefix="/tasks", tags=["tasks"])


def get_task_service(session: AsyncSession = Depends(get_session)) -> TaskService:
    return TaskService(session)


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreateRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.manage_tasks)),
    service: TaskService = Depends(get_task_service),
) -> TaskRead:
    return TaskRead.model_validate(await service.create(organization_id, payload))


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.read_repository)),
    service: TaskService = Depends(get_task_service),
    repository_id: uuid.UUID | None = Query(None),
    task_status: TaskStatus | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> TaskListResponse:
    items, total = await service.list(organization_id, repository_id, task_status, limit, offset)
    return TaskListResponse(
        items=[TaskRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.patch("/{task_id}", response_model=TaskRead)
async def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdateRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.manage_tasks)),
    service: TaskService = Depends(get_task_service),
) -> TaskRead:
    return TaskRead.model_validate(await service.update(organization_id, task_id, payload))
