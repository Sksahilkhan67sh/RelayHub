from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

# 2 MiB is generous for every real RelayHub payload (event bodies, invitation/org
# forms, etc.) while still bounding worst-case memory use per request. Webhook
# *delivery* (RelayHub -> customer endpoint) is unaffected -- this only guards
# inbound requests to RelayHub's own API.
MAX_BODY_BYTES = 2 * 1024 * 1024


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > MAX_BODY_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"error": {"code": "payload_too_large", "message": "Request body too large"}},
                    )
            except ValueError:
                pass
        return await call_next(request)
