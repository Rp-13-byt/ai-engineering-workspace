"""FastAPI REST router for ChangeLens risk assessments and test plans."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.database import get_session
from ai_workspace_api.core.dependencies import get_organization_id, require_permission
from ai_workspace_api.core.models import User
from ai_workspace_api.core.permissions import Permission
from ai_workspace_api.modules.changelens.schemas import (
    ChangeAnalysisListResponse,
    ChangeAnalysisRead,
    ChangeAnalysisRequest,
)
from ai_workspace_api.modules.changelens.service import ChangeLensService

router = APIRouter(prefix="/changelens", tags=["changelens"])


def get_changelens_service(
    session: AsyncSession = Depends(get_session),
) -> ChangeLensService:
    return ChangeLensService(session)


@router.post(
    "/analyze",
    response_model=ChangeAnalysisRead,
    status_code=status.HTTP_201_CREATED,
)
async def analyze_change(
    payload: ChangeAnalysisRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.index_repository)),
    service: ChangeLensService = Depends(get_changelens_service),
) -> ChangeAnalysisRead:
    return await service.analyze_change(payload, organization_id)


@router.get(
    "/analyses/{analysis_id}",
    response_model=ChangeAnalysisRead,
)
async def get_analysis(
    analysis_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.read_repository)),
    service: ChangeLensService = Depends(get_changelens_service),
) -> ChangeAnalysisRead:
    return await service.get_analysis(analysis_id, organization_id)


@router.get(
    "/repositories/{repository_id}/analyses",
    response_model=ChangeAnalysisListResponse,
)
async def list_repository_analyses(
    repository_id: uuid.UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.read_repository)),
    service: ChangeLensService = Depends(get_changelens_service),
) -> ChangeAnalysisListResponse:
    return await service.list_analyses(
        repository_id=repository_id,
        organization_id=organization_id,
        limit=limit,
        offset=offset,
    )


@router.delete(
    "/analyses/{analysis_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
async def delete_analysis(
    analysis_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.index_repository)),
    service: ChangeLensService = Depends(get_changelens_service),
) -> Response:
    await service.delete_analysis(analysis_id, organization_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
