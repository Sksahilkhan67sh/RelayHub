import uuid
from enum import Enum

from sqlalchemy import JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin


class AuditAction(str, Enum):
    # API keys
    API_KEY_CREATED = "api_key.created"
    API_KEY_ROTATED = "api_key.rotated"
    API_KEY_REVOKED = "api_key.revoked"
    # Endpoints (used by later phase, defined now for forward-compat)
    ENDPOINT_CREATED = "endpoint.created"
    ENDPOINT_UPDATED = "endpoint.updated"
    ENDPOINT_DELETED = "endpoint.deleted"
    # Auth
    USER_INVITED = "user.invited"
    SESSION_REVOKED_ALL = "session.revoked_all"
    PASSWORD_RESET_REQUESTED = "auth.password_reset_requested"
    PASSWORD_RESET_COMPLETED = "auth.password_reset_completed"
    # Invitations (email-based; distinct from USER_INVITED, which is the existing
    # direct-membership-creation flow in org_service.invite_member)
    INVITATION_CREATED = "invitation.created"
    INVITATION_ACCEPTED = "invitation.accepted"
    INVITATION_REVOKED = "invitation.revoked"
    INVITATION_RESENT = "invitation.resent"
    # Dead Letter Queue
    DLQ_JOB_RETRIED = "dlq.job_retried"
    DLQ_JOB_DELETED = "dlq.job_deleted"
    DLQ_BULK_RETRIED = "dlq.bulk_retried"
    # Admin panel
    ADMIN_IMPERSONATION_STARTED = "admin.impersonation_started"
    ADMIN_ORG_SUSPENDED = "admin.org_suspended"
    ADMIN_ORG_UNSUSPENDED = "admin.org_unsuspended"
    ADMIN_DELIVERY_JOB_FORCE_RETRIED = "admin.delivery_job_force_retried"
    ADMIN_DELIVERY_JOB_FORCE_CANCELED = "admin.delivery_job_force_canceled"
    ADMIN_FEATURE_FLAG_UPDATED = "admin.feature_flag_updated"
    ADMIN_ABUSE_REPORT_RESOLVED = "admin.abuse_report_resolved"


class AuditLog(Base, UUIDPKMixin, TimestampMixin):
    """
    Append-only audit trail. Never updated or soft-deleted -- audit logs must be
    immutable for compliance. Always tenant-scoped except for platform-admin actions
    (organization_id nullable to allow system/global entries).
    """

    __tablename__ = "audit_logs"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
