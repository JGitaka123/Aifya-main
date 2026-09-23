"""Application-level encryption for sensitive columns at rest (Kenya DPA).

Provides an ``EncryptedString`` SQLAlchemy type that transparently
encrypts values on write and decrypts on read using Fernet (AES-128-CBC +
HMAC). Ciphertext is stored with a versioned prefix so plaintext legacy
rows can be read back unchanged until they are re-written (lazy backfill).

The encryption key is taken from ``settings.field_encryption_key`` when
set, otherwise derived deterministically from ``SECRET_KEY`` so existing
deployments gain encryption without new required config. Rotating either
value makes previously encrypted values unreadable — document key custody
before enabling in production.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String, TypeDecorator

from app.config import settings

_ENC_PREFIX = "enc:v1:"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    """
    Build the Fernet cipher from configured/derived key material.

    @returns Cached Fernet instance
    """
    raw = settings.field_encryption_key or settings.secret_key
    # Fernet needs a 32-byte urlsafe-base64 key; derive one deterministically.
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_value(plaintext: str) -> str:
    """
    Encrypt a string for storage.

    @param plaintext: Cleartext value
    @returns Versioned ciphertext string
    """
    token = _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")
    return f"{_ENC_PREFIX}{token}"


def decrypt_value(stored: str) -> str:
    """
    Decrypt a stored value. Legacy plaintext (no prefix) is returned as-is
    so pre-encryption rows keep working until re-saved.

    @param stored: Value read from the database
    @returns Cleartext value
    """
    if not stored.startswith(_ENC_PREFIX):
        return stored
    token = stored[len(_ENC_PREFIX):]
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        # Wrong/rotated key — never leak ciphertext to callers.
        return ""


class EncryptedString(TypeDecorator):
    """
    SQLAlchemy column type that encrypts str values at rest.

    Stored as text (ciphertext is longer than plaintext); the ``length``
    argument bounds the *plaintext* and the underlying column is sized
    generously to hold the Fernet token.
    """

    impl = String
    cache_ok = True

    def __init__(self, length: int = 255, **kwargs: object) -> None:
        # Fernet output is ~1.4x + 100 bytes overhead; size the column safely.
        super().__init__(length=length * 3 + 128, **kwargs)

    def process_bind_param(self, value: str | None, dialect: object) -> str | None:
        """Encrypt on the way into the database."""
        if value is None:
            return None
        return encrypt_value(value)

    def process_result_value(self, value: str | None, dialect: object) -> str | None:
        """Decrypt on the way out of the database."""
        if value is None:
            return None
        return decrypt_value(value)
