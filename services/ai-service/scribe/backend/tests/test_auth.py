"""Tests for auth utilities."""
import pytest
from app.auth.auth import (
    get_password_hash, verify_password,
    create_access_token, create_refresh_token,
)
from app.models import UserRole
from jose import jwt
from app.config import get_settings

settings = get_settings()


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "SecureP@ssw0rd123!"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed)

    def test_wrong_password_fails(self):
        hashed = get_password_hash("correct_password")
        assert not verify_password("wrong_password", hashed)

    def test_different_hashes_same_password(self):
        password = "TestPassword1!"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)
        assert hash1 != hash2  # bcrypt salting
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)


class TestTokenCreation:
    def test_access_token_contains_claims(self):
        token = create_access_token(subject="user-123", role=UserRole.CLINICIAN)
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "user-123"
        assert payload["role"] == "clinician"
        assert "exp" in payload
        assert "iat" in payload

    def test_access_token_with_facility(self):
        token = create_access_token(subject="user-123", role=UserRole.BILLING_ADMIN, facility_id="fac-456")
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["facility_id"] == "fac-456"

    def test_refresh_token_has_sub(self):
        token = create_refresh_token(subject="user-123")
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == "user-123"
        assert "exp" in payload
