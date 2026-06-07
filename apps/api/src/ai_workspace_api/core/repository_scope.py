import uuid

from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.errors import ApiError
from ai_workspace_api.core.models import Repository


async def get_repository_for_organization(
    session: AsyncSession,
    organization_id: uuid.UUID,
    repository_id: uuid.UUID,
) -> Repository:
    repository = await session.get(Repository, repository_id)
    if repository is None or repository.organization_id != organization_id:
        raise ApiError("Repository not found", status.HTTP_404_NOT_FOUND)
    return repository
