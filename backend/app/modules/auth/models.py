import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPKMixin


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


ROLE_HIERARCHY = {Role.VIEWER: 0, Role.MEMBER: 1, Role.ADMIN: 2, Role.OWNER: 3}


def role_at_least(actual: Role, required: Role) -> bool:
    return ROLE_HIERARCHY[actual] >= ROLE_HIERARCHY[required]


class Organization(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id"), nullable=True
    )
    # Log retention in days for delivery_jobs/delivery_attempts, per spec's plan tiers
    # (Free=7, Starter=30, Pro=90, Enterprise=custom). Defaults to 30 until this phase's
    # billing enforcement wires it from the org's actual plan (see billing/service.py
    # sync_organization_plan_fields, called on every subscription change).
    log_retention_days: Mapped[int] = mapped_column(nullable=False, default=30)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suspension_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="organization")


class User(Base, UUIDPKMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # GitHub's numeric user id (stable even across username changes), set the first
    # time this account signs in via GitHub OAuth -- see auth/github_oauth.py. Null
    # for accounts that have never used GitHub sign-in.
    github_id: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True, index=True)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")


class Membership(Base, UUIDPKMixin, TimestampMixin):
    """A user's role within a specific organization. Users can belong to multiple orgs."""

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "organization_id", name="uq_user_org"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=Role.MEMBER.value)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="memberships")
    organization: Mapped["Organization"] = relationship(back_populates="memberships")


class PasswordResetToken(Base, UUIDPKMixin, TimestampMixin):
    """
    One-time-use password reset tokens. Only the sha256 hash of the raw token is ever
    stored (see core.security.generate_secure_token) -- the raw value exists only in
    the emailed link and the request/response cycle that issues it, never at rest.
    """

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hashed_token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def is_valid(self) -> bool:
        if self.used_at is not None:
            return False
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return expires > datetime.now(timezone.utc)


class Invitation(Base, UUIDPKMixin, TimestampMixin):
    """
    Email-based org invitation: unlike Membership (created directly by
    org_service.invite_member for users who already have an account), an Invitation
    can be sent to an email address with no RelayHub account yet -- accepting it is
    what creates the account (or attaches the membership, if the account already
    exists). Only the sha256 hash of the raw token is ever stored.
    """

    __tablename__ = "invitations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=Role.MEMBER.value)
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    hashed_token: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def status(self) -> str:
        if self.revoked_at is not None:
            return "revoked"
        if self.accepted_at is not None:
            return "accepted"
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
            return "expired"
        return "pending"


class RefreshTokenFamily(Base, UUIDPKMixin, TimestampMixin):
    """
    Tracks rotating refresh token families for reuse-detection.
    Each login creates a new family. Each refresh rotates `current_jti` and appends
    to `used_jtis`. If a `jti` outside the current one is presented, the whole
    family is revoked (`revoked_at` set) -- signals likely token theft.
    """

    __tablename__ = "refresh_token_families"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    current_jti: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)  # sha256 of current raw refresh token
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
