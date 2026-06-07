import uuid

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.cache import get_redis
from ai_workspace_api.core.config import Settings, get_settings
from ai_workspace_api.core.database import get_session
from ai_workspace_api.core.dependencies import get_organization_id, require_permission
from ai_workspace_api.core.models import User
from ai_workspace_api.core.permissions import Permission
from ai_workspace_api.modules.search.schemas import SearchRequest, SearchResponse
from ai_workspace_api.modules.search.service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


def get_search_service(
    session: AsyncSession = Depends(get_session),
    redis: Redis = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> SearchService:
    return SearchService(session, redis, settings)


@router.post("/semantic", response_model=SearchResponse)
async def semantic_search(
    payload: SearchRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    _: User = Depends(require_permission(Permission.read_repository)),
    service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    return await service.semantic_search(payload, organization_id)
