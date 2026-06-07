import uuid

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings, get_settings
from ai_workspace_api.core.database import get_session
from ai_workspace_api.core.dependencies import get_organization_id, require_permission
from ai_workspace_api.core.models import RepositoryStatus, User
from ai_workspace_api.core.permissions import Permission
from ai_workspace_api.modules.repositories.schemas import (
    ReindexResponse,
    RepositoryImportRequest,
    RepositoryListResponse,
    RepositoryRead,
)
from ai_workspace_api.modules.repositories.service import RepositoryService

router = APIRouter(prefix="/repositories", tags=["repositories"])


def get_repository_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> RepositoryService:
    return RepositoryService(session, settings)


@router.post("/import", response_model=RepositoryRead, status_code=status.HTTP_202_ACCEPTED)
async def import_repository(
    payload: RepositoryImportRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.import_repository)),
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryRead:
    repository = await service.import_repository(
        organization_id=organization_id,
        owner=payload.owner,
        name=payload.name,
        provider=payload.provider,
    )
    return RepositoryRead.model_validate(repository)


@router.get("", response_model=RepositoryListResponse)
async def list_repositories(
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.read_repository)),
    service: RepositoryService = Depends(get_repository_service),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: str | None = Query(None, max_length=160),
    indexing_status: RepositoryStatus | None = Query(None),
) -> RepositoryListResponse:
    items, total = await service.list_repositories(
        organization_id=organization_id,
        limit=limit,
        offset=offset,
        search=search,
        status_filter=indexing_status,
    )
    return RepositoryListResponse(
        items=[RepositoryRead.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{repository_id}", response_model=RepositoryRead)
async def get_repository(
    repository_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.read_repository)),
    service: RepositoryService = Depends(get_repository_service),
) -> RepositoryRead:
    return RepositoryRead.model_validate(await service.get_repository(organization_id, repository_id))


@router.post("/{repository_id}/reindex", response_model=ReindexResponse, status_code=status.HTTP_202_ACCEPTED)
async def reindex_repository(
    repository_id: uuid.UUID,
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.index_repository)),
    service: RepositoryService = Depends(get_repository_service),
) -> ReindexResponse:
    repository = await service.get_repository(organization_id, repository_id)
    key = await service.enqueue_indexing(repository)
    await service.session.commit()
    return ReindexResponse(repository_id=repository.id, status=repository.indexing_status, job_idempotency_key=key)

from fastapi import Request
from sqlalchemy import select
from ai_workspace_api.core.models import Repository

@router.post("/github/webhook")
async def github_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
):
    """Receives GitHub push webhooks to trigger incremental indexing."""
    payload = await request.json()
    # In production, verify X-Hub-Signature-256 here
    
    if "repository" in payload and payload.get("ref", "").endswith("main"):
        owner = payload["repository"]["owner"]["login"]
        name = payload["repository"]["name"]
        
        repo_stmt = select(Repository).where(
            Repository.owner == owner,
            Repository.name == name
        )
        repo = (await session.execute(repo_stmt)).scalar_one_or_none()
        
        if repo:
            service = RepositoryService(session, settings)
            await service.enqueue_indexing(repo)
            await session.commit()
            return {"status": "accepted", "repository_id": str(repo.id)}
            
    return {"status": "ignored"}
