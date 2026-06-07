import uuid

from pydantic import BaseModel, EmailStr


class MembershipRead(BaseModel):
    organization_id: uuid.UUID
    role: str


class CurrentUserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    avatar_url: str | None
    is_verified: bool
    memberships: list[MembershipRead]
