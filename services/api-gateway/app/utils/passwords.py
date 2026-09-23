"""Password hashing for internal (non-Keycloak) authentication.

PBKDF2-HMAC-SHA256 using only the standard library, so no extra dependency is
required. Encoded format: pbkdf2_sha256$<iterations>$<salt_hex>$<digest_hex>
"""
import hashlib
import hmac
import secrets

_ITERATIONS = 390_000


def hash_password(password: str) -> str:
    """Hash a plaintext password.

    @param password: Plaintext password
    @returns Encoded PBKDF2 hash string
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _ITERATIONS
    )
    return "pbkdf2_sha256" + "$" + str(_ITERATIONS) + "$" + salt.hex() + "$" + digest.hex()


def verify_password(password: str, encoded: str) -> bool:
    """Verify a plaintext password against an encoded hash.

    @param password: Plaintext candidate
    @param encoded: Stored hash produced by hash_password()
    @returns True when the password matches
    """
    try:
        scheme, iterations_str, salt_hex, digest_hex = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations
    )
    return hmac.compare_digest(candidate, expected)
