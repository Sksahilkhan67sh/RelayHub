"""
SSRF protection for customer-registered destination URLs.

Two layers, deliberately separated:

1. `validate_endpoint_url_at_registration()` -- cheap, synchronous checks run when a
   customer creates/updates an endpoint: scheme (https-only outside dev), obviously
   forbidden literal IPs/hostnames (localhost, 127.0.0.1, 169.254.169.254 cloud
   metadata, private ranges written as literal IPs).

2. A second check at ACTUAL DELIVERY TIME (implemented in the delivery worker,
   Phase 3e) that re-resolves the hostname and re-validates the resolved IP
   immediately before connecting. This second layer is the one that actually matters
   for security: registration-time validation alone is defeated by DNS rebinding
   (customer points evil.com at a public IP during review, then repoints it at
   169.254.169.254 later). We still validate at registration time because it gives
   customers immediate feedback and blocks the laziest attacks, but it is NOT a
   substitute for re-validating at connection time.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from app.core.config import settings

BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain", "metadata.google.internal"}


class UnsafeEndpointURLError(ValueError):
    pass


def is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local  # covers 169.254.0.0/16 (AWS/GCP/Azure metadata service range)
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_endpoint_url_at_registration(url: str) -> None:
    parsed = urlparse(url)

    if parsed.scheme not in ("https", "http"):
        raise UnsafeEndpointURLError(f"Unsupported URL scheme '{parsed.scheme}'; only http/https are allowed")

    if parsed.scheme == "http" and not (settings.ALLOW_HTTP_ENDPOINTS_IN_DEV and settings.ENV != "production"):
        raise UnsafeEndpointURLError(
            "Insecure http:// endpoints are rejected. RelayHub requires https:// destinations in production."
        )

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise UnsafeEndpointURLError("URL must include a hostname")

    if hostname in BLOCKED_HOSTNAMES or hostname.endswith(".local"):
        raise UnsafeEndpointURLError(f"Hostname '{hostname}' is not allowed as a webhook destination")

    # If the hostname is a literal IP address, validate it directly. If it's a DNS
    # name, we deliberately do NOT resolve it here -- see module docstring on why
    # that check belongs at delivery time instead.
    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        return  # it's a DNS hostname, not a literal IP -- allowed at registration time

    if settings.BLOCK_PRIVATE_IP_TARGETS and is_blocked_ip(ip):
        raise UnsafeEndpointURLError(f"IP address '{hostname}' is in a blocked range (private/loopback/link-local)")
