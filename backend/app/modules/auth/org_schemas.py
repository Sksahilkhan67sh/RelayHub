import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.modules.auth.models import Role


class MemberOut(BaseModel):
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    invited_by_user_id: uuid.UUID | None
    accepted_at: datetime | None
    joined_at: datetime


class InviteMemberRequest(BaseModel):
    email: EmailStr
    role: Role = Role.MEMBER


class UpdateMemberRoleRequest(BaseModel):
    role: Role


class UpdateOrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
