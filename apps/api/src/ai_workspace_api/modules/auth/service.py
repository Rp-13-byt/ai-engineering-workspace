import re
import uuid
from datetime import UTC, datetime, timedelta
from secrets import token_hex

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings
from ai_workspace_api.core.errors import ApiError
from ai_workspace_api.core.models import Membership, Organization, RefreshSession, Role, User
from ai_workspace_api.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_password,
)
from ai_workspace_api.modules.auth.schemas import OrganizationRead, TokenPair, UserRead


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self.session = session
        self.settings = settings

    async def signup(
        self,
        email: str,
        password: str,
        display_name: str,
        organization_name: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        normalized_email = email.lower()
        existing = await self.session.scalar(select(User).where(User.email == normalized_email))
        if existing is not None:
            raise ApiError("Email is already registered", status.HTTP_409_CONFLICT)

        user = User(
            email=normalized_email,
            password_hash=hash_password(password),
            display_name=display_name,
            is_verified=False,
        )
        organization = Organization(slug=self._slugify(organization_name), name=organization_name)
        self.session.add_all([user, organization])
        await self.session.flush()
        self.session.add(Membership(user_id=user.id, organization_id=organization.id, role=Role.owner))
        tokens = await self._issue_tokens(user, organization, ip_address, user_agent)
        await self.session.commit()
        return tokens

    async def login(
        self,
        email: str,
        password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        user = await self.session.scalar(select(User).where(User.email == email.lower(), User.is_active.is_(True)))
        if user is None or user.password_hash is None or not verify_password(password, user.password_hash):
            raise ApiError("Invalid credentials", status.HTTP_401_UNAUTHORIZED)

        membership = await self.session.scalar(select(Membership).where(Membership.user_id == user.id).limit(1))
        if membership is None:
            raise ApiError("User is not assigned to an organization", status.HTTP_403_FORBIDDEN)
        organization = await self.session.get(Organization, membership.organization_id)
        if organization is None:
            raise ApiError("Organization not found", status.HTTP_404_NOT_FOUND)
        tokens = await self._issue_tokens(user, organization, ip_address, user_agent)
        await self.session.commit()
        return tokens

    async def refresh(
        self,
        refresh_token: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        session = await self.session.scalar(
            select(RefreshSession).where(
                RefreshSession.token_hash == hash_token(refresh_token),
                RefreshSession.revoked_at.is_(None),
                RefreshSession.expires_at > datetime.now(UTC),
            )
        )
        if session is None:
            raise ApiError("Invalid refresh token", status.HTTP_401_UNAUTHORIZED)
        session.revoked_at = datetime.now(UTC)
        user = await self.session.get(User, session.user_id)
        if user is None or not user.is_active:
            raise ApiError("Invalid refresh token", status.HTTP_401_UNAUTHORIZED)
        membership = await self.session.scalar(select(Membership).where(Membership.user_id == user.id).limit(1))
        if membership is None:
            raise ApiError("User has no organization", status.HTTP_403_FORBIDDEN)
        organization = await self.session.get(Organization, membership.organization_id)
        if organization is None:
            raise ApiError("Organization not found", status.HTTP_404_NOT_FOUND)
        tokens = await self._issue_tokens(user, organization, ip_address, user_agent)
        await self.session.commit()
        return tokens

    async def logout(self, refresh_token: str) -> None:
        session = await self.session.scalar(
            select(RefreshSession).where(RefreshSession.token_hash == hash_token(refresh_token))
        )
        if session is not None:
            session.revoked_at = datetime.now(UTC)
            await self.session.commit()

    async def github_oauth_url(self) -> tuple[str, str]:
        if not self.settings.github_client_id:
            raise ApiError("GitHub OAuth is not configured", status.HTTP_503_SERVICE_UNAVAILABLE)
        state = token_hex(24)
        url = (
            "https://github.com/login/oauth/authorize"
            f"?client_id={self.settings.github_client_id}"
            "&scope=read:user%20user:email%20repo"
            f"&state={state}"
        )
        return url, state

    async def request_password_reset(self, email: str) -> None:
        await self.session.execute(select(User.id).where(User.email == email.lower()))

    async def verify_email(self, token: str) -> None:
        if len(token) < 20:
            raise ApiError("Invalid verification token", status.HTTP_400_BAD_REQUEST)

    async def _issue_tokens(
        self,
        user: User,
        organization: Organization,
        ip_address: str | None,
        user_agent: str | None,
    ) -> TokenPair:
        refresh_token = generate_opaque_token()
        expires_at = datetime.now(UTC) + timedelta(days=self.settings.refresh_token_ttl_days)
        self.session.add(
            RefreshSession(
                user_id=user.id,
                token_hash=hash_token(refresh_token),
                ip_address=ip_address,
                user_agent=user_agent,
                expires_at=expires_at,
            )
        )
        access_token = create_access_token(
            subject=str(user.id),
            organization_id=str(organization.id),
            settings=self.settings,
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            user=UserRead.model_validate(user),
            organization=OrganizationRead.model_validate(organization),
        )

    def _slugify(self, name: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return f"{normalized[:64]}-{token_hex(3)}"
