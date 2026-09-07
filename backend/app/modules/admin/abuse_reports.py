from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.models import AbuseReport, AbuseReportStatus
from app.modules.audit import service as audit_service
from app.modules.audit.models import AuditAction
from app.modules.notifications import service as notifications_service


async def create_abuse_report(db: AsyncSession, *, organization_id: uuid.UUID, reason: str, reported_by_user_id: uuid.UUID | None) -> AbuseReport:
    report = AbuseReport(organization_id=organization_id, reason=reason, reported_by_user_id=reported_by_user_id)
    db.add(report)
    await notifications_service.notify_org_admins(
        db, organization_id=organization_id,
        type="abuse_report.created", title="Your organization was flagged for review",
        body=f"A report was filed against your organization: {reason}",
        resource_type="abuse_report", resource_id=str(report.id),
    )
    await db.commit()
    await db.refresh(report)
    return report


async def list_abuse_reports(db: AsyncSession, *, status_filter: str | None = None) -> list[AbuseReport]:
    query = select(AbuseReport).order_by(AbuseReport.created_at.desc())  # tenant-scope: safe - platform admin only, route requires require_platform_admin
    if status_filter:
        query = query.where(AbuseReport.status == status_filter)
    return list((await db.execute(query)).scalars().all())


async def list_abuse_reports_for_org(db: AsyncSession, *, organization_id: uuid.UUID) -> list[AbuseReport]:
    """
    Org-facing counterpart to list_abuse_reports above. That function is
    deliberately unscoped (global, platform-admin only); this one is the opposite
    -- always filtered to a single org -- so an org's own OWNER/ADMIN members can
    see reports filed against *their* organization (they're notified via
    notify_org_admins when one is created/updated, but previously had nowhere to
    actually go read it). Route enforces the org scope via AuthContext.
    """
    query = (
        select(AbuseReport)
        .where(AbuseReport.organization_id == organization_id)
        .order_by(AbuseReport.created_at.desc())
    )
    return list((await db.execute(query)).scalars().all())


async def create_org_self_report(
    db: AsyncSession, *, organization_id: uuid.UUID, reason: str, reported_by_user_id: uuid.UUID
) -> AbuseReport:
    """
    Lets a member file a report about their *own* organization (e.g. flagging
    something for platform review), as opposed to create_abuse_report above,
    which is a platform admin flagging an arbitrary org from the outside. The
    row lands in the exact same abuse_reports table, so it shows up in the
    platform admin's /admin/abuse-reports queue like any other report -- the
    two creation paths are just different front doors onto the same review
    workflow. exclude_user_id skips notifying the person who just filed it;
    other OWNER/ADMIN members of the org still hear about it.
    """
    report = AbuseReport(organization_id=organization_id, reason=reason, reported_by_user_id=reported_by_user_id)
    db.add(report)
    await notifications_service.notify_org_admins(
        db, organization_id=organization_id,
        type="abuse_report.created", title="Abuse report submitted",
        body=f"A report was submitted for your organization: {reason}",
        resource_type="abuse_report", resource_id=str(report.id),
        exclude_user_id=reported_by_user_id,
    )
    await db.commit()
    await db.refresh(report)
    return report


async def resolve_abuse_report(
    db: AsyncSession, *, report_id: uuid.UUID, new_status: str, resolution_notes: str | None,
    actor_user_id: uuid.UUID, ip_address: str | None,
) -> AbuseReport:
    # tenant-scope: safe - platform admin only, route requires require_platform_admin
    report = (await db.execute(select(AbuseReport).where(AbuseReport.id == report_id))).scalar_one_or_none()
    if not report:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Abuse report not found")

    report.status = new_status
    report.resolution_notes = resolution_notes
    if new_status in (AbuseReportStatus.RESOLVED.value, AbuseReportStatus.DISMISSED.value):
        report.resolved_at = datetime.now(timezone.utc)

    await audit_service.record(
        db, organization_id=report.organization_id, actor_user_id=actor_user_id, action=AuditAction.ADMIN_ABUSE_REPORT_RESOLVED,
        resource_type="abuse_report", resource_id=str(report.id), metadata={"status": new_status}, ip_address=ip_address,
    )
    await notifications_service.notify_org_admins(
        db, organization_id=report.organization_id,
        type="abuse_report.status_changed", title="Abuse report update",
        body=f"The report filed against your organization is now {new_status}.",
        resource_type="abuse_report", resource_id=str(report.id),
    )
    await db.commit()
    await db.refresh(report)
    return report
