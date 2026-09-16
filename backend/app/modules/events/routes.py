import uuid

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.queue_client import QueueClient, get_queue_client
from app.common.realtime_publisher import RealtimePublisher, get_realtime_publisher
from app.common.route_rate_limit import org_rate_limit
from app.db.session import get_db
from app.modules.api_keys.dependencies import enforce_api_key_rate_limit, require_scope
from app.modules.api_keys.models import ApiKey, ApiKeyScope
from app.modules.auth.dependencies import AuthContext, require_role
from app.modules.auth.models import Role
from app.modules.billing.dependencies import enforce_event_publishing_limit
from app.modules.events import service
from app.modules.events.schemas import EventOut, PublishEventRequest

router = APIRouter(prefix="/events", tags=["events"])

# Dashboard-originated test events. Deliberately tighter than the API-key
# ingestion limit: this exists for a developer clicking "send test event" in
# the UI, not for programmatic traffic (which should use a real API key and
# POST /v1/events). Per-organization, using the same limiter as everything
# else -- see app/common/route_rate_limit.py.
TEST_EVENT_LIMIT = 30
TEST_EVENT_WINDOW_SECONDS = 60


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
    realtime_publisher: RealtimePublisher = Depends(get_realtime_publisher),
):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    event = await service.publish_event(
        db,
        organization_id=api_key.organization_id,
        api_key_id=api_key.id,
        data=payload,
        request_id=request_id,
        queue_client=queue_client,
        realtime_publisher=realtime_publisher,
    )
    return event


@router.post("/test", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def publish_test_event(
    payload: PublishEventRequest,
    request: Request,
    auth: AuthContext = Depends(require_role(Role.MEMBER)),
    db: AsyncSession = Depends(get_db),
    queue_client: QueueClient = Depends(get_queue_client),
    realtime_publisher: RealtimePublisher = Depends(get_realtime_publisher),
    _rate_limit: None = Depends(
        org_rate_limit("test-event", limit=TEST_EVENT_LIMIT, window_seconds=TEST_EVENT_WINDOW_SECONDS)
    ),
):
    """
    Publish an event from the dashboard (session/JWT auth) rather than with an
    API key, so a developer can send a test event from the UI without first
    minting a key and pasting it somewhere.

    This is NOT a separate or simulated delivery path: it calls exactly the same
    `service.publish_event` as `POST /v1/events` above, so the event goes through
    real fan-out, real signing, the real delivery queue, real retries, and the
    real DLQ. The only differences are how the caller is authenticated and that
    `api_key_id` is left null (the column is nullable), which is what makes
    dashboard-originated events distinguishable from API-key traffic afterwards.

    Note on quota: `enforce_event_publishing_limit` is an API-key-scoped
    dependency and therefore isn't applied here; the per-organization rate limit
    above is what bounds this endpoint. Volume is intentionally low enough that
    it isn't a meaningful quota-evasion path -- see docs/DEVELOPER_EXPERIENCE.md.
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return await service.publish_event(
        db,
        organization_id=auth.organization_id,
        api_key_id=None,
        data=payload,
        request_id=request_id,
        queue_client=queue_client,
        realtime_publisher=realtime_publisher,
    )


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
