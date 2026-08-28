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


class CreateOrgAbuseReportRequest(BaseModel):
    """Self-service report a member files about their own organization -- distinct
    from admin.schemas.CreateAbuseReportRequest, which lets a *platform admin*
    target an arbitrary org_id. Here organization_id and reported_by_user_id are
    always taken from the caller's own AuthContext, never client-supplied."""

    reason: str = Field(min_length=1, max_length=2000)
