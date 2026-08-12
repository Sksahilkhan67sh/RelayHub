"""
Standalone signature verification -- no server required.
Run directly for a self-test: python verify.py
"""

import hashlib
import hmac


def verify_relayhub_signature(raw_body: bytes, signature_header: str | None, secret: str) -> bool:
    if not signature_header:
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


if __name__ == "__main__":
    secret = "test_secret_123"
    body = b'{"event": "payment.success", "payload": {"order_id": "ord_123"}}'
    valid_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    print("Valid signature accepted:", verify_relayhub_signature(body, valid_sig, secret) is True)
    print("Tampered body rejected:", verify_relayhub_signature(body + b"x", valid_sig, secret) is False)
    print("Wrong secret rejected:", verify_relayhub_signature(body, valid_sig, "wrong_secret") is False)
