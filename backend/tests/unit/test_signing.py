import time

import pytest

from app.modules.delivery.signing import SignatureVerificationError, sign, verify


def test_sign_then_verify_succeeds():
    body = b'{"amount": 4200}'
    headers = sign(secret="whsec_test123", raw_body=body)
    verify(
        secret="whsec_test123",
        raw_body=body,
        signature=headers["X-RelayHub-Signature"],
        timestamp=headers["X-RelayHub-Timestamp"],
        nonce=headers["X-RelayHub-Nonce"],
    )  # should not raise


def test_verify_fails_with_wrong_secret():
    body = b'{"amount": 4200}'
    headers = sign(secret="whsec_test123", raw_body=body)
    with pytest.raises(SignatureVerificationError):
        verify(
            secret="whsec_WRONG",
            raw_body=body,
            signature=headers["X-RelayHub-Signature"],
            timestamp=headers["X-RelayHub-Timestamp"],
            nonce=headers["X-RelayHub-Nonce"],
        )


def test_verify_fails_if_body_tampered():
    body = b'{"amount": 4200}'
    headers = sign(secret="whsec_test123", raw_body=body)
    tampered_body = b'{"amount": 999999}'
    with pytest.raises(SignatureVerificationError):
        verify(
            secret="whsec_test123",
            raw_body=tampered_body,
            signature=headers["X-RelayHub-Signature"],
            timestamp=headers["X-RelayHub-Timestamp"],
            nonce=headers["X-RelayHub-Nonce"],
        )


def test_verify_fails_if_timestamp_outside_tolerance():
    body = b'{"amount": 4200}'
    old_timestamp = str(int(time.time()) - 600)  # 10 minutes ago, tolerance is 5 min
    headers = sign(secret="whsec_test123", raw_body=body, timestamp=old_timestamp)
    with pytest.raises(SignatureVerificationError, match="tolerance"):
        verify(
            secret="whsec_test123",
            raw_body=body,
            signature=headers["X-RelayHub-Signature"],
            timestamp=headers["X-RelayHub-Timestamp"],
            nonce=headers["X-RelayHub-Nonce"],
        )


def test_two_signings_of_same_body_produce_different_signatures_due_to_nonce():
    body = b'{"amount": 4200}'
    headers1 = sign(secret="whsec_test123", raw_body=body)
    headers2 = sign(secret="whsec_test123", raw_body=body)
    assert headers1["X-RelayHub-Signature"] != headers2["X-RelayHub-Signature"]
    assert headers1["X-RelayHub-Nonce"] != headers2["X-RelayHub-Nonce"]
