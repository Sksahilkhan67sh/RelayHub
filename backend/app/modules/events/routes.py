import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.queue_client import QueueClient, get_queue_client
from app.db.session import get_db
from app.modules.api_keys.dependencies import enforce_api_key_rate_limit, require_scope
from app.modules.api_keys.models import ApiKey, ApiKeyScope
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Role
from app.modules.billing.dependencies import enforce_event_publishing_limit
from app.modules.events import service
from app.modules.events.schemas import EventOut, PublishEventRequest

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def publish_event(
    payload: PublishEventRequest,
    request: Request,
    response: Response,
    api_key: ApiKey = Depends(require_scope(ApiKeyScope.EVENTS_WRITE.value)),
    _billing_check: ApiKey = Depends(enforce_event_publishing_limit),
    _rate_limit_check: ApiKey = Depends(enforce_api_key_rate_limit),
    db: AsyncSession = Depends(get_db),
    queue_client: QueueClient = Depends(get_queue_client),
):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    event = await service.publish_event(
        db,
        organization_id=api_key.organization_id,
        api_key_id=api_key.id,
        data=payload,
        request_id=request_id,
        queue_client=queue_client,
    )
    return event


@router.get("/{event_id}", response_model=EventOut)
async def get_event(
    event_id: uuid.UUID,
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    return await service.get_event(db, organization_id=auth.organization_id, event_id=event_id)


@router.get("", response_model=list[EventOut])
async def list_events(
    auth: AuthContext = Depends(require_role(Role.VIEWER)),
    db: AsyncSession = Depends(get_db),
):
    return await service.list_events(db, organization_id=auth.organization_id)
