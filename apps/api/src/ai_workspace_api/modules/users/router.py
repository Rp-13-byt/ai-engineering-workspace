from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.database import get_session
from ai_workspace_api.core.dependencies import get_current_user
from ai_workspace_api.core.models import Membership, User
from ai_workspace_api.modules.users.schemas import CurrentUserResponse, MembershipRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> CurrentUserResponse:
    memberships = await session.scalars(select(Membership).where(Membership.user_id == user.id))
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_verified=user.is_verified,
        memberships=[
            MembershipRead(organization_id=membership.organization_id, role=membership.role.value)
            for membership in memberships
        ],
    )
