import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.auth.schemas import InviteUserRequest

# InviteUserRequest ({email, role}) already existed in auth/schemas.py and matched
# this endpoint's request shape exactly -- reused rather than duplicated.
CreateInvitationRequest = InviteUserRequest


class InvitationOut(BaseModel):
    """Authenticated, org-scoped view -- returned to the admin who created/lists it."""

    id: uuid.UUID
    organization_id: uuid.UUID
    email: str
    role: str
    invited_by_user_id: uuid.UUID
    status: str
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvitationPublicOut(BaseModel):
    """
    Unauthenticated view returned by GET /invitations/{token} -- deliberately minimal
    (no invitation id, no inviter identity) since this endpoint is reachable by
    anyone holding the link, before any login has happened.
    """

    organization_name: str
    email: str
    role: str
    status: str
    expires_at: datetime


class AcceptInvitationRequest(BaseModel):
    token: str = Field(min_length=1)
    # Only required when the invitee has no existing RelayHub account yet -- in that
    # case accepting also creates the account (validated in invitation_service).
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str | None) -> str | None:
        if v is None:
            return v
        # Same bar as RegisterRequest.password -- accepting an invite shouldn't be a
        # way to land on a weaker password than registering directly would allow.
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v
