"""
Webhook signing, matching spec section 8.

Headers sent with every delivery:
  X-RelayHub-Signature   hex HMAC-SHA256 of "<timestamp>.<nonce>.<raw_body>"
  X-RelayHub-Timestamp   unix seconds, integer, as a string
  X-RelayHub-Nonce       random per-delivery value (also prevents identical retries
                         of the same body from ever producing the same signature,
                         which matters once a customer's replay-cache keys on signature)
  X-RelayHub-Event       event type, e.g. "payment.success"
  X-RelayHub-Delivery-ID the delivery_job UUID, for customer-side dedup

Signing the concatenation of timestamp + nonce + raw body (not just the body) is what
makes the timestamp/nonce tamper-evident -- if we only signed the body, an attacker
who captured one valid request could replay it indefinitely with a fresh timestamp and
the signature would still check out.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time


class SignatureVerificationError(Exception):
    pass


def generate_nonce() -> str:
    return secrets.token_hex(16)


def build_signed_string(*, timestamp: str, nonce: str, raw_body: bytes) -> bytes:
    return f"{timestamp}.{nonce}.".encode() + raw_body


def sign(*, secret: str, raw_body: bytes, timestamp: str | None = None, nonce: str | None = None) -> dict[str, str]:
    """Returns the four signing-related headers RelayHub attaches to a delivery."""
    ts = timestamp or str(int(time.time()))
    nc = nonce or generate_nonce()
    signed_string = build_signed_string(timestamp=ts, nonce=nc, raw_body=raw_body)
    signature = hmac.new(secret.encode(), signed_string, hashlib.sha256).hexdigest()
    return {
        "X-RelayHub-Signature": signature,
        "X-RelayHub-Timestamp": ts,
        "X-RelayHub-Nonce": nc,
    }


def verify(
    *, secret: str, raw_body: bytes, signature: str, timestamp: str, nonce: str, tolerance_seconds: int = 300
) -> None:
    """
    Reference verification (this is what the Node/Python/Go customer docs implement).
    Raises SignatureVerificationError on any failure. Never returns partial/boolean
    success -- webhook signature checks should fail loudly, not be silently ignored.
    """
    try:
        ts_int = int(timestamp)
    except ValueError as e:
        raise SignatureVerificationError("Timestamp is not a valid integer") from e

    now = int(time.time())
    if abs(now - ts_int) > tolerance_seconds:
        raise SignatureVerificationError(
            f"Timestamp outside tolerance window ({tolerance_seconds}s) -- possible replay attack"
        )

    expected_string = build_signed_string(timestamp=timestamp, nonce=nonce, raw_body=raw_body)
    expected_signature = hmac.new(secret.encode(), expected_string, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        raise SignatureVerificationError("Signature mismatch")
