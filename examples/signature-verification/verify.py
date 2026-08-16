"""
Standalone signature verification -- no server required.
Run directly for a self-test: python verify.py

Matches backend/app/modules/delivery/signing.py exactly: the signed string is
"<timestamp>.<nonce>." concatenated with the raw body, not the body alone --
that's what makes the timestamp/nonce tamper-evident against replay.
"""

import hashlib
import hmac


def verify_relayhub_signature(
    raw_body: bytes,
    signature_header: str | None,
    timestamp_header: str | None,
    nonce_header: str | None,
    secret: str,
) -> bool:
    if not signature_header or not timestamp_header or not nonce_header:
        return False
    signed_string = f"{timestamp_header}.{nonce_header}.".encode() + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed_string, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


if __name__ == "__main__":
    secret = "test_secret_123"
    body = b'{"event": "payment.success", "payload": {"order_id": "ord_123"}}'
    timestamp = "1750000000"
    nonce = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
    signed_string = f"{timestamp}.{nonce}.".encode() + body
    valid_sig = hmac.new(secret.encode("utf-8"), signed_string, hashlib.sha256).hexdigest()

    print("Valid signature accepted:", verify_relayhub_signature(body, valid_sig, timestamp, nonce, secret) is True)
    print("Tampered body rejected:", verify_relayhub_signature(body + b"x", valid_sig, timestamp, nonce, secret) is False)
    print("Wrong secret rejected:", verify_relayhub_signature(body, valid_sig, timestamp, nonce, "wrong_secret") is False)
    print("Replayed timestamp/nonce mismatch rejected:", verify_relayhub_signature(body, valid_sig, "1750000001", nonce, secret) is False)
