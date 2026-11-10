from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ai_workspace_api.core.config import Settings, get_settings
from ai_workspace_api.core.database import get_session
from ai_workspace_api.infrastructure.rate_limit import limiter
from ai_workspace_api.modules.auth.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    OAuthCallbackRequest,
    OAuthUrlResponse,
    RefreshRequest,
    SignupRequest,
    TokenPair,
    VerifyEmailRequest,
)
from ai_workspace_api.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AuthService:
    return AuthService(session=session, settings=settings)


@router.post("/signup", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def signup(
    payload: SignupRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return await service.signup(
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
        organization_name=payload.organization_name,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/login", response_model=TokenPair)
@limiter.limit("8/minute")
async def login(
    payload: LoginRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return await service.login(
        email=payload.email,
        password=payload.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/refresh", response_model=TokenPair)
@limiter.limit("30/minute")
async def refresh(
    payload: RefreshRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> TokenPair:
    return await service.refresh(
        refresh_token=payload.refresh_token,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, service: AuthService = Depends(get_auth_service)) -> Response:
    await service.logout(payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/github/url", response_model=OAuthUrlResponse)
async def github_oauth_url(service: AuthService = Depends(get_auth_service)) -> OAuthUrlResponse:
    url, state = await service.github_oauth_url()
    return OAuthUrlResponse(authorization_url=url, state=state)


@router.post("/github/callback", status_code=status.HTTP_202_ACCEPTED)
async def github_callback(payload: OAuthCallbackRequest) -> dict[str, str]:
    return {
        "status": "accepted",
        "message": "Exchange code for GitHub tokens in the auth service boundary.",
        "state": payload.state,
    }


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("5/minute")
async def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    await service.request_password_reset(payload.email)
    return {"status": "accepted"}


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
async def verify_email(payload: VerifyEmailRequest, service: AuthService = Depends(get_auth_service)) -> Response:
    await service.verify_email(payload.token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
