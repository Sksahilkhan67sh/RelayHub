from __future__ import annotations

import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"

# Bounded and restricted to characters that are safe to echo into a header, a
# JSON log field, and a trace attribute without any further escaping --
# generous enough for a UUID, a ULID, or most clients' own correlation-ID
# conventions, but rejects anything that could carry a newline (log-line
# injection), control characters, or an unbounded length (a client could
# otherwise hand us an arbitrarily large string that we'd then store in every
# log line for the request). A caller-supplied ID that doesn't match this is
# treated the same as no ID supplied at all -- we still generate one, we just
# don't trust theirs.
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Ensures every request has a request ID: reuses one supplied by the caller
    if it looks safe to (useful for clients that want to correlate their own
    logs with ours), or generates a new one otherwise. Stored on
    request.state.request_id so route handlers and the error-envelope
    exception handlers can attach it to responses/logs, and in a contextvar
    (app.core.logging_config.request_id_var) for the duration of the request
    so every log line emitted while handling it -- including from code that
    has no access to the Request object -- gets it attached automatically.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming if incoming and _VALID_REQUEST_ID.match(incoming) else str(uuid.uuid4())
        request.state.request_id = request_id

        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
