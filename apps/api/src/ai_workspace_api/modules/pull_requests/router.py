import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings, get_settings
from ai_workspace_api.core.database import get_session
from ai_workspace_api.core.dependencies import (
    get_current_user,
    get_organization_id,
    require_permission,
)
from ai_workspace_api.core.models import User
from ai_workspace_api.core.permissions import Permission
from ai_workspace_api.modules.pull_requests.schemas import (
    PullRequestApprovalRequest,
    PullRequestDraftRead,
    PullRequestGenerateRequest,
)
from ai_workspace_api.modules.pull_requests.service import PullRequestService

router = APIRouter(prefix="/pull-requests", tags=["pull requests"])


def get_pull_request_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PullRequestService:
    return PullRequestService(session, settings)


@router.post("/generate", response_model=PullRequestDraftRead, status_code=status.HTTP_201_CREATED)
async def generate_pull_request(
    payload: PullRequestGenerateRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    user: User = Depends(get_current_user),
    _: User = Depends(require_permission(Permission.generate_pull_request)),
    service: PullRequestService = Depends(get_pull_request_service),
) -> PullRequestDraftRead:
    draft = await service.generate(payload, user.id, organization_id)
    return PullRequestDraftRead.model_validate(draft)


@router.post("/{pull_request_id}/approval", response_model=PullRequestDraftRead)
async def review_pull_request(
    pull_request_id: uuid.UUID,
    payload: PullRequestApprovalRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    user: User = Depends(get_current_user),
    _: User = Depends(require_permission(Permission.approve_pull_request)),
    service: PullRequestService = Depends(get_pull_request_service),
) -> PullRequestDraftRead:
    draft = await service.review(pull_request_id, payload, user.id, organization_id)
    return PullRequestDraftRead.model_validate(draft)
