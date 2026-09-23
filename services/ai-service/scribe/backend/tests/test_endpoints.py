"""Tests for API endpoints using FastAPI TestClient with mocked dependencies."""
import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from jose import jwt
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.models import UserRole

settings = get_settings()


def create_test_token(role: str = "clinician", user_id: str = None) -> str:
    """Create a valid JWT token for testing."""
    user_id = user_id or str(uuid.uuid4())
    payload = {
        "sub": user_id,
        "role": role,
        "facility_id": "test-facility",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def auth_header(role: str = "clinician") -> dict:
    """Create authorization header with a valid test token."""
    token = create_test_token(role)
    return {"Authorization": f"Bearer {token}"}


# ============================
# Fixtures
# ============================

@pytest.fixture
def mock_adapter():
    """Mock the QAfyaAdapter to prevent real DB calls."""
    with patch("app.main.qafya_adapter") as mock:
        mock.pool = True  # Simulate connected pool
        mock.breaker = MagicMock()
        mock.breaker.is_open = False
        mock.breaker.failures = 0
        mock.last_success_timestamp = datetime.now(timezone.utc)
        mock.current_latency_ms = 12.5

        # Default async mocks
        mock.connect = AsyncMock()
        mock.close = AsyncMock()
        mock.validate_schema_on_startup = AsyncMock()
        mock._execute_read = AsyncMock(return_value=[{"?column?": 1}])
        mock.log_audit = AsyncMock()
        mock.get_user_by_email = AsyncMock(return_value=None)
        mock.get_user_by_id = AsyncMock(return_value=None)
        mock.create_user = AsyncMock(return_value=True)
        mock.get_patient = AsyncMock(return_value=None)
        mock.get_patient_encounters = AsyncMock(return_value=[])
        mock.get_claims = AsyncMock(return_value=[])
        mock.get_claims_count = AsyncMock(return_value=0)
        mock.get_claim_by_id = AsyncMock(return_value=None)
        mock.get_claims_stats = AsyncMock(return_value={
            "total": 100, "blocked": 10, "passed": 70, "warnings_only": 15,
            "overridden": 5, "today_count": 12, "total_billed": 500000, "total_approved": 420000,
        })
        mock.override_claim = AsyncMock(return_value=True)
        mock.submit_claim = AsyncMock(return_value=True)
        mock.get_all_users = AsyncMock(return_value=[])
        mock.get_audit_logs = AsyncMock(return_value=[])
        mock.get_discharge_by_id = AsyncMock(return_value=None)
        mock.save_discharge_summary = AsyncMock()
        mock.update_discharge_status = AsyncMock(return_value=True)
        mock.write_clinical_note = AsyncMock(return_value=True)
        mock.write_discharge_summary = AsyncMock(return_value=True)
        mock.append_addendum = AsyncMock(return_value=True)

        yield mock


@pytest.fixture
def mock_nlp():
    """Mock the NLP engine."""
    with patch("app.main.nlp_engine") as mock:
        mock.process_transcript = AsyncMock(return_value={
            "chief_complaint": "Headache",
            "vitals": [],
            "diagnoses": [{"name": "Tension headache", "icd11_validated": "MG30.0", "is_primary": True, "confidence": 0.9}],
            "lab_orders": [],
            "medications": [],
            "procedures": [],
            "warnings": [],
        })
        yield mock


@pytest.fixture
def mock_discharge():
    """Mock the discharge engine."""
    with patch("app.main.discharge_engine") as mock:
        mock.generate = AsyncMock(return_value={
            "id": str(uuid.uuid4()),
            "patient_name": "Test Patient",
            "admission_diagnosis": "Pneumonia",
            "final_diagnosis": "Community-acquired pneumonia",
            "clinical_narrative": "Patient presented with...",
            "length_of_stay_days": 5,
            "status": "draft",
        })
        mock.generate_pdf = MagicMock(return_value=b"%PDF-1.4 mock")
        yield mock


@pytest.fixture
def client(mock_adapter):
    """Create a TestClient with mocked dependencies."""
    from app.main import app
    return TestClient(app)


# ============================
# Health Check Tests
# ============================
class TestHealthCheck:
    def test_health_returns_ok(self, client, mock_adapter):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "components" in data
        assert "api" in data["components"]

    def test_health_shows_db_connected(self, client, mock_adapter):
        mock_adapter._execute_read = AsyncMock(return_value=[{"?column?": 1}])
        response = client.get("/health")
        data = response.json()
        assert data["components"]["qafya_db"] == "connected"


# ============================
# Auth Endpoint Tests
# ============================
class TestAuthEndpoints:
    def test_register_success(self, client, mock_adapter):
        mock_adapter.get_user_by_email = AsyncMock(return_value=None)
        response = client.post(
            f"{settings.api_v1_str}/auth/register",
            json={
                "email": "newdoc@hospital.org",
                "password": "SecurePass1",
                "full_name": "Dr. Test",
                "role": "clinician",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newdoc@hospital.org"
        assert data["full_name"] == "Dr. Test"

    def test_register_duplicate_email(self, client, mock_adapter):
        mock_adapter.get_user_by_email = AsyncMock(return_value={"id": "existing"})
        response = client.post(
            f"{settings.api_v1_str}/auth/register",
            json={
                "email": "existing@hospital.org",
                "password": "SecurePass1",
                "full_name": "Dr. Duplicate",
                "role": "clinician",
            },
        )
        assert response.status_code == 409

    def test_register_invalid_email(self, client, mock_adapter):
        response = client.post(
            f"{settings.api_v1_str}/auth/register",
            json={
                "email": "not-an-email",
                "password": "SecurePass1",
                "full_name": "Test",
                "role": "clinician",
            },
        )
        assert response.status_code == 422

    def test_register_weak_password(self, client, mock_adapter):
        response = client.post(
            f"{settings.api_v1_str}/auth/register",
            json={
                "email": "test@hospital.org",
                "password": "weak",
                "full_name": "Test",
                "role": "clinician",
            },
        )
        assert response.status_code == 422

    def test_login_success(self, client, mock_adapter):
        from app.auth.auth import get_password_hash
        mock_adapter.get_user_by_email = AsyncMock(return_value={
            "id": "user-123",
            "password_hash": get_password_hash("ValidPass1"),
            "role": "clinician",
            "full_name": "Dr. Login",
            "is_active": True,
            "facility_id": "fac-1",
        })
        response = client.post(
            f"{settings.api_v1_str}/auth/login",
            json={"email": "doc@hospital.org", "password": "ValidPass1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["full_name"] == "Dr. Login"

    def test_login_wrong_password(self, client, mock_adapter):
        from app.auth.auth import get_password_hash
        mock_adapter.get_user_by_email = AsyncMock(return_value={
            "id": "user-123",
            "password_hash": get_password_hash("CorrectPass1"),
            "role": "clinician",
            "full_name": "Dr. Test",
            "is_active": True,
        })
        response = client.post(
            f"{settings.api_v1_str}/auth/login",
            json={"email": "doc@hospital.org", "password": "WrongPass1"},
        )
        assert response.status_code == 401

    def test_login_inactive_user(self, client, mock_adapter):
        from app.auth.auth import get_password_hash
        mock_adapter.get_user_by_email = AsyncMock(return_value={
            "id": "user-123",
            "password_hash": get_password_hash("ValidPass1"),
            "role": "clinician",
            "full_name": "Disabled Doc",
            "is_active": False,
        })
        response = client.post(
            f"{settings.api_v1_str}/auth/login",
            json={"email": "disabled@hospital.org", "password": "ValidPass1"},
        )
        assert response.status_code == 403

    def test_logout(self, client, mock_adapter):
        response = client.post(
            f"{settings.api_v1_str}/auth/logout",
            headers=auth_header(),
        )
        assert response.status_code == 200


# ============================
# Patient Endpoint Tests
# ============================
class TestPatientEndpoints:
    def test_get_patient_found(self, client, mock_adapter):
        mock_adapter.get_patient = AsyncMock(return_value={
            "national_id": "12345678",
            "full_name": "John Doe",
            "insurance_no": "SHA-001",
            "insurance_status": "ACTIVE",
        })
        response = client.get(
            f"{settings.api_v1_str}/patients/12345678",
            headers=auth_header(),
        )
        assert response.status_code == 200
        assert response.json()["full_name"] == "John Doe"

    def test_get_patient_not_found(self, client, mock_adapter):
        mock_adapter.get_patient = AsyncMock(return_value=None)
        response = client.get(
            f"{settings.api_v1_str}/patients/nonexistent",
            headers=auth_header(),
        )
        assert response.status_code == 404

    def test_get_patient_unauthorized(self, client, mock_adapter):
        response = client.get(f"{settings.api_v1_str}/patients/12345678")
        assert response.status_code in (401, 403)

    def test_get_encounters(self, client, mock_adapter):
        mock_adapter.get_patient_encounters = AsyncMock(return_value=[
            {"id": "enc-1", "date": "2026-01-01"},
        ])
        response = client.get(
            f"{settings.api_v1_str}/patients/patient-1/encounters",
            headers=auth_header(),
        )
        assert response.status_code == 200


# ============================
# Scribe Endpoint Tests
# ============================
class TestScribeEndpoints:
    def test_extract_success(self, client, mock_adapter, mock_nlp):
        response = client.post(
            f"{settings.api_v1_str}/scribe/extract",
            json={"transcript": "[CLINICIAN]: Patient presents with severe headache for 3 days."},
            headers=auth_header(),
        )
        assert response.status_code == 200
        data = response.json()
        assert "chief_complaint" in data

    def test_extract_too_short(self, client, mock_adapter):
        response = client.post(
            f"{settings.api_v1_str}/scribe/extract",
            json={"transcript": "hi"},
            headers=auth_header(),
        )
        assert response.status_code == 422

    def test_extract_requires_clinician_role(self, client, mock_adapter):
        response = client.post(
            f"{settings.api_v1_str}/scribe/extract",
            json={"transcript": "A sufficiently long transcript for testing purposes here"},
            headers=auth_header(role="billing_admin"),
        )
        assert response.status_code == 403

    def test_process_full_pipeline(self, client, mock_adapter, mock_nlp):
        response = client.post(
            f"{settings.api_v1_str}/scribe/process",
            json={"transcript": "[CLINICIAN]: Full pipeline test with enough text."},
            headers=auth_header(),
        )
        assert response.status_code == 200
        data = response.json()
        assert "extraction" in data

    def test_addendum_success(self, client, mock_adapter):
        response = client.post(
            f"{settings.api_v1_str}/scribe/addendum",
            json={"encounter_id": "enc-1", "addendum_text": "Patient called back with improvement."},
            headers=auth_header(),
        )
        assert response.status_code == 200


# ============================
# Claims Endpoint Tests
# ============================
class TestClaimsEndpoints:
    def test_list_claims(self, client, mock_adapter):
        mock_adapter.get_claims = AsyncMock(return_value=[
            {"id": "claim-1", "amount_billed": 5000, "scrub_status": "passed"},
        ])
        mock_adapter.get_claims_count = AsyncMock(return_value=1)
        response = client.get(
            f"{settings.api_v1_str}/claims",
            headers=auth_header(role="billing_admin"),
        )
        assert response.status_code == 200
        data = response.json()
        assert "claims" in data
        assert "total" in data

    def test_list_claims_with_filter(self, client, mock_adapter):
        response = client.get(
            f"{settings.api_v1_str}/claims?status=blocked",
            headers=auth_header(role="billing_admin"),
        )
        assert response.status_code == 200

    def test_list_claims_requires_billing_role(self, client, mock_adapter):
        response = client.get(
            f"{settings.api_v1_str}/claims",
            headers=auth_header(role="clinician"),
        )
        assert response.status_code == 403

    def test_get_claim_found(self, client, mock_adapter):
        mock_adapter.get_claim_by_id = AsyncMock(return_value={
            "id": "claim-1", "amount_billed": 5000,
        })
        response = client.get(
            f"{settings.api_v1_str}/claims/claim-1",
            headers=auth_header(role="billing_admin"),
        )
        assert response.status_code == 200

    def test_get_claim_not_found(self, client, mock_adapter):
        response = client.get(
            f"{settings.api_v1_str}/claims/nonexistent",
            headers=auth_header(role="billing_admin"),
        )
        assert response.status_code == 404

    def test_override_claim_success(self, client, mock_adapter):
        mock_adapter.get_claim_by_id = AsyncMock(return_value={
            "id": "claim-1", "scrub_status": "blocked",
        })
        response = client.post(
            f"{settings.api_v1_str}/claims/claim-1/override",
            json={"reason": "Clinical review confirms appropriate billing for this encounter."},
            headers=auth_header(role="billing_admin"),
        )
        assert response.status_code == 200

    def test_override_wrong_status(self, client, mock_adapter):
        mock_adapter.get_claim_by_id = AsyncMock(return_value={
            "id": "claim-1", "scrub_status": "passed",
        })
        response = client.post(
            f"{settings.api_v1_str}/claims/claim-1/override",
            json={"reason": "This should fail because claim already passed scrub."},
            headers=auth_header(role="billing_admin"),
        )
        assert response.status_code == 400

    def test_submit_claim_success(self, client, mock_adapter):
        mock_adapter.get_claim_by_id = AsyncMock(return_value={
            "id": "claim-1", "scrub_status": "passed",
        })
        response = client.post(
            f"{settings.api_v1_str}/claims/claim-1/submit",
            headers=auth_header(role="billing_admin"),
        )
        assert response.status_code == 200
        assert "sha_submission_ref" in response.json()

    def test_submit_blocked_claim_fails(self, client, mock_adapter):
        mock_adapter.get_claim_by_id = AsyncMock(return_value={
            "id": "claim-1", "scrub_status": "blocked",
        })
        response = client.post(
            f"{settings.api_v1_str}/claims/claim-1/submit",
            headers=auth_header(role="billing_admin"),
        )
        assert response.status_code == 400

    def test_claims_stats(self, client, mock_adapter):
        response = client.get(
            f"{settings.api_v1_str}/claims/stats",
            headers=auth_header(role="billing_admin"),
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "total_billed" in data


# ============================
# Admin Endpoint Tests
# ============================
class TestAdminEndpoints:
    def test_list_users(self, client, mock_adapter):
        mock_adapter.get_all_users = AsyncMock(return_value=[
            {"id": "u1", "full_name": "Admin", "role": "superadmin"},
        ])
        response = client.get(
            f"{settings.api_v1_str}/admin/users",
            headers=auth_header(role="superadmin"),
        )
        assert response.status_code == 200
        assert "users" in response.json()

    def test_list_users_forbidden_for_clinician(self, client, mock_adapter):
        response = client.get(
            f"{settings.api_v1_str}/admin/users",
            headers=auth_header(role="clinician"),
        )
        assert response.status_code == 403

    def test_create_user_admin(self, client, mock_adapter):
        response = client.post(
            f"{settings.api_v1_str}/admin/users",
            json={
                "email": "newuser@hospital.org",
                "password": "SecurePass1",
                "full_name": "New User",
                "role": "clinician",
            },
            headers=auth_header(role="superadmin"),
        )
        assert response.status_code == 200

    def test_audit_log(self, client, mock_adapter):
        mock_adapter.get_audit_logs = AsyncMock(return_value=[
            {"id": "log-1", "action": "USER_LOGIN_SUCCESS", "created_at": "2026-03-18T10:00:00"},
        ])
        response = client.get(
            f"{settings.api_v1_str}/admin/audit-log",
            headers=auth_header(role="superadmin"),
        )
        assert response.status_code == 200
        assert "logs" in response.json()

    def test_audit_log_with_filter(self, client, mock_adapter):
        response = client.get(
            f"{settings.api_v1_str}/admin/audit-log?action=USER_LOGIN_SUCCESS",
            headers=auth_header(role="superadmin"),
        )
        assert response.status_code == 200

    def test_sync_status(self, client, mock_adapter):
        response = client.get(
            f"{settings.api_v1_str}/admin/sync-status",
            headers=auth_header(role="facility_admin"),
        )
        assert response.status_code == 200
        data = response.json()
        assert "qafya_connection" in data
        assert "circuit_breaker_state" in data


# ============================
# Discharge Endpoint Tests
# ============================
class TestDischargeEndpoints:
    def test_generate_discharge(self, client, mock_adapter, mock_discharge):
        response = client.post(
            f"{settings.api_v1_str}/discharge/generate",
            json={"admission_id": "adm-1", "patient_id": "pat-1"},
            headers=auth_header(),
        )
        assert response.status_code == 200
        data = response.json()
        assert "patient_name" in data

    def test_get_discharge_not_found(self, client, mock_adapter):
        response = client.get(
            f"{settings.api_v1_str}/discharge/nonexistent",
            headers=auth_header(),
        )
        assert response.status_code == 404

    def test_update_discharge_status(self, client, mock_adapter):
        mock_adapter.get_discharge_by_id = AsyncMock(return_value={
            "id": "dc-1", "status": "draft",
        })
        response = client.put(
            f"{settings.api_v1_str}/discharge/dc-1/status",
            json={"new_status": "reviewed"},
            headers=auth_header(),
        )
        assert response.status_code == 200

    def test_invalid_status_transition(self, client, mock_adapter):
        mock_adapter.get_discharge_by_id = AsyncMock(return_value={
            "id": "dc-1", "status": "draft",
        })
        response = client.put(
            f"{settings.api_v1_str}/discharge/dc-1/status",
            json={"new_status": "approved"},  # Can't go from draft to approved
            headers=auth_header(),
        )
        assert response.status_code == 400

    def test_download_pdf(self, client, mock_adapter, mock_discharge):
        mock_adapter.get_discharge_by_id = AsyncMock(return_value={
            "id": "dc-1", "status": "approved", "patient_name": "Test",
        })
        response = client.get(
            f"{settings.api_v1_str}/discharge/dc-1/pdf",
            headers=auth_header(),
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"


# ============================
# Sync Endpoint Tests
# ============================
class TestSyncEndpoints:
    def test_sync_clinical_note(self, client, mock_adapter):
        response = client.post(
            f"{settings.api_v1_str}/sync/clinical-note",
            json={
                "qafya_encounter_id": "enc-1",
                "soap_json": {"subjective": "Headache", "objective": {}, "assessment": {}, "plan": {}},
            },
            headers=auth_header(),
        )
        assert response.status_code == 200
        assert response.json()["synced"] is True

    def test_sync_discharge_not_approved(self, client, mock_adapter):
        mock_adapter.get_discharge_by_id = AsyncMock(return_value={
            "id": "dc-1", "status": "draft", "admission_id": "adm-1",
        })
        response = client.post(
            f"{settings.api_v1_str}/sync/discharge-summary",
            json={"discharge_id": "dc-1"},
            headers=auth_header(),
        )
        assert response.status_code == 400

    def test_sync_discharge_approved(self, client, mock_adapter):
        mock_adapter.get_discharge_by_id = AsyncMock(return_value={
            "id": "dc-1", "status": "approved", "admission_id": "adm-1",
        })
        response = client.post(
            f"{settings.api_v1_str}/sync/discharge-summary",
            json={"discharge_id": "dc-1"},
            headers=auth_header(),
        )
        assert response.status_code == 200
        assert response.json()["synced"] is True
