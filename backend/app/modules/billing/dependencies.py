from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.modules.api_keys.dependencies import get_api_key_context
from app.modules.api_keys.models import ApiKey
from app.modules.billing import service as billing_service


async def enforce_event_publishing_limit(
    key: ApiKey = Depends(get_api_key_context),
    db: AsyncSession = Depends(get_db),
) -> ApiKey:
    await billing_service.enforce_delivery_limit(db, organization_id=key.organization_id)
    return key
