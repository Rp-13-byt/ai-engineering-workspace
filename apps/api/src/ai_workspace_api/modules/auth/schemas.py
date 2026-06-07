import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, HttpUrl


class UserRead(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    avatar_url: str | None
    is_verified: bool

    model_config = {"from_attributes": True}


class OrganizationRead(BaseModel):
    id: uuid.UUID
    slug: str
    name: str

    model_config = {"from_attributes": True}


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    display_name: str = Field(min_length=2, max_length=160)
    organization_name: str = Field(min_length=2, max_length=160)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    token: str


class OAuthCallbackRequest(BaseModel):
    code: str
    state: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserRead
    organization: OrganizationRead


class OAuthUrlResponse(BaseModel):
    authorization_url: HttpUrl | str
    state: str
