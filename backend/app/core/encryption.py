"""
Envelope-encryption-style helper for encrypting sensitive values at rest (endpoint
signing secrets today; extensible to OAuth tokens etc. later).

This uses Fernet (AES-128-CBC + HMAC) keyed off ENCRYPTION_MASTER_KEY as a simple,
correct starting point. In a real KMS-backed deployment, ENCRYPTION_MASTER_KEY would
itself be a data-encryption-key unwrapped via AWS KMS / GCP KMS / Vault at process
startup rather than a static env var -- the call sites here (`encrypt_secret` /
`decrypt_secret`) are written so that swap is a one-file change.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class DecryptionError(Exception):
    pass


def _fernet() -> Fernet:
    return Fernet(settings.ENCRYPTION_MASTER_KEY.encode() if isinstance(settings.ENCRYPTION_MASTER_KEY, str) else settings.ENCRYPTION_MASTER_KEY)


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as e:
        raise DecryptionError("Failed to decrypt secret -- wrong key or corrupted ciphertext") from e
