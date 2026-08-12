"""
The SECOND SSRF check, promised in endpoints/security.py's docstring: re-resolve the
destination hostname and validate the IP RelayHub is actually about to connect to,
immediately before connecting. This is what actually stops DNS rebinding -- a
hostname that resolved to a public IP at endpoint-registration time can be
repointed at 169.254.169.254 an hour later, and only a check performed at connection
time (using the same resolution the HTTP client will use) catches that.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import settings
from app.modules.endpoints.security import is_blocked_ip


class DeliveryBlockedError(Exception):
    pass


async def resolve_and_validate(url: str) -> str:
    """
    Resolves the URL's hostname and returns the IP address that will be connected to,
    raising DeliveryBlockedError if that IP is in a blocked range. Literal-IP URLs are
    checked directly without a DNS lookup.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise DeliveryBlockedError("URL has no hostname")

    try:
        ip = ipaddress.ip_address(hostname)
        resolved_ip = str(ip)
    except ValueError:
        loop = asyncio.get_event_loop()
        try:
            infos = await loop.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        except socket.gaierror as e:
            raise DeliveryBlockedError(f"DNS resolution failed for '{hostname}': {e}") from e

        if not infos:
            raise DeliveryBlockedError(f"DNS resolution returned no results for '{hostname}'") from None

        resolved_ip = str(infos[0][4][0])
        ip = ipaddress.ip_address(resolved_ip)

    if settings.BLOCK_PRIVATE_IP_TARGETS and is_blocked_ip(ip):
        raise DeliveryBlockedError(f"Resolved IP '{resolved_ip}' for host '{hostname}' is in a blocked range")

    return resolved_ip
