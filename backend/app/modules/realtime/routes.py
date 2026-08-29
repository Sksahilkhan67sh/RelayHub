"""
Server-Sent Events endpoint for live delivery status. See
PHASE_REALTIME_DELIVERY_AUDIT.md section 4 for why SSE (not WebSocket) was chosen.

Tenant isolation (spec Step 5) is enforced here, not by the frontend: the org a
connection subscribes to comes ONLY from the decoded, signature-verified JWT
(`organization_id`), never from a client-supplied parameter -- identical to every
other tenant-scoped route in this codebase (see `AuthContext` in
auth/dependencies.py). A connection has no way to name a different organization's
channel.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.common.realtime_publisher import RealtimePublisher, get_realtime_publisher
from app.core.metrics import REALTIME_CONNECTIONS, realtime_reconnects_total
from app.core.security import TokenError, decode_token
from app.modules.auth.models import ROLE_HIERARCHY, Role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/realtime", tags=["realtime"])

KEEPALIVE_COMMENT = ": keepalive\n\n"


def _authenticate_stream(request: Request, token: str | None) -> tuple[uuid.UUID, uuid.UUID, Role]:
    """
    Browser `EventSource` cannot set an `Authorization` header, so the same
    short-lived access token the REST API already issues is accepted as a query
    parameter here -- falling back to a normal `Authorization: Bearer` header for
    non-browser callers (tests, CLI, curl, `web_fetch`-style tooling). This is the
    SAME `decode_token` verification and the SAME JWT claims
    (`sub`/`org_id`/`role`) `get_current_auth` uses for every other route -- no
    separate authentication system, per spec Step 6. An unauthenticated or
    malformed-token connection is rejected before any subscription is created.
    """
    raw_token = token
    if raw_token is None:
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            raw_token = auth_header[7:]

    if not raw_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token")

    try:
        payload = decode_token(raw_token, expected_type="access")
        return uuid.UUID(payload["sub"]), uuid.UUID(payload["org_id"]), Role(payload["role"])
    except (TokenError, KeyError, ValueError) as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from e


@router.get("/deliveries/stream")
async def stream_delivery_updates(
    request: Request,
    token: str | None = Query(default=None, description="Access token -- EventSource cannot set an Authorization header"),
    publisher: RealtimePublisher = Depends(get_realtime_publisher),
) -> StreamingResponse:
    # Same minimum role as GET /v1/deliveries/{id} (Role.VIEWER) -- anyone who can
    # read delivery state over REST can also watch it live; nobody else.
    _user_id, organization_id, role = _authenticate_stream(request, token)
    if ROLE_HIERARCHY[role] < ROLE_HIERARCHY[Role.VIEWER]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Requires role 'viewer' or higher")

    subscription = publisher.subscribe(organization_id)
    realtime_reconnects_total.inc()
    REALTIME_CONNECTIONS.inc()

    async def event_stream():
        try:
            # Hints the browser's built-in EventSource reconnect delay (spec Step
            # 7: "use exponential backoff or another safe reconnect strategy, do
            # not create aggressive reconnect loops") -- 3s is a reasonable floor;
            # the browser backs off further on repeated failures on its own.
            yield "retry: 3000\n\n"
            async for message in subscription.messages():
                if await request.is_disconnected():
                    break
                if message.get("type") == "keepalive":
                    yield KEEPALIVE_COMMENT
                    continue
                yield f"event: delivery.updated\ndata: {json.dumps(message)}\n\n"
        except Exception:  # noqa: BLE001 - a stream-teardown error must never surface as a 500 mid-stream
            logger.exception("realtime: SSE stream for org=%s ended with an error", organization_id)
        finally:
            await subscription.close()
            REALTIME_CONNECTIONS.dec()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            # Fallback API-refresh strategy (spec Step 17) lives entirely on the
            # frontend (apps/web/lib/realtime.ts) -- this endpoint has no
            # responsibility beyond "stream what's published, isolated by org".
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable reverse-proxy buffering so events aren't held back
            "Connection": "keep-alive",
        },
    )
