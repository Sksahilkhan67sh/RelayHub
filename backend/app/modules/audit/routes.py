from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.audit import service
from app.modules.audit.schemas import AuditLogOut
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Role

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
async def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(require_role(Role.ADMIN)),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_audit_logs(db, organization_id=auth.organization_id, limit=limit, offset=offset)
