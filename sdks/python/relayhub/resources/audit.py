from __future__ import annotations

from ..http import RequestOptions, Transport
from ..types import AuditLogOut


class AuditResource:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def list(self, *, limit: int = 50, offset: int = 0, options: RequestOptions | None = None) -> list[AuditLogOut]:
        """GET /v1/audit-logs"""
        opts = options or RequestOptions()
        opts.query = {**(opts.query or {}), "limit": limit, "offset": offset}
        return self._transport.request("GET", "/v1/audit-logs", None, opts)
