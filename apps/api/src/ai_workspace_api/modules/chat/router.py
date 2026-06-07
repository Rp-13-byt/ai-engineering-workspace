import uuid

from fastapi import APIRouter, Depends
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
from ai_workspace_api.modules.chat.schemas import ChatRequest, ChatResponse
from ai_workspace_api.modules.chat.service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


def get_chat_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ChatService:
    return ChatService(session, settings)


@router.post("", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    organization_id: uuid.UUID = Depends(get_organization_id),
    user: User = Depends(get_current_user),
    _: User = Depends(require_permission(Permission.use_ai)),
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return await service.answer(payload, user.id, organization_id)
