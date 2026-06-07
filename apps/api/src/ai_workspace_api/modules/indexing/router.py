import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings, get_settings
from ai_workspace_api.core.database import get_session
from ai_workspace_api.core.dependencies import get_organization_id, require_permission
from ai_workspace_api.core.models import User
from ai_workspace_api.core.permissions import Permission
from ai_workspace_api.modules.indexing.schemas import IndexingStatusResponse
from ai_workspace_api.modules.indexing.service import IndexingService

router = APIRouter(prefix="/indexing", tags=["indexing"])


def get_indexing_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> IndexingService:
    return IndexingService(session, settings)


@router.get("/{repository_id}", response_model=IndexingStatusResponse)
async def indexing_status(
    repository_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.read_repository)),
    service: IndexingService = Depends(get_indexing_service),
) -> IndexingStatusResponse:
    repository = await service.get_status(repository_id, organization_id)
    return IndexingStatusResponse(
        repository_id=repository.id,
        status=repository.indexing_status,
        last_indexed_commit=repository.last_indexed_commit,
        updated_at=repository.updated_at,
    )
