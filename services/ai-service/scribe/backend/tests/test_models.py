"""Tests for Pydantic model validation."""
import pytest
from datetime import datetime
from pydantic import ValidationError
from app.models import (
    ClinicalExtraction, Diagnosis, VitalSign, Medication, LabOrder, Procedure,
    ScrubResult, ScrubStatus, RuleViolation, Severity,
    UserCreate, LoginRequest, TranscriptInput, ScrubRequest, ClaimOverrideRequest,
    DischargeStatusUpdate, UserRole, EncounterType,
)


class TestClinicalExtraction:
    def test_valid_extraction(self):
        extraction = ClinicalExtraction(
            chief_complaint="Headache for 3 days",
            vitals=[VitalSign(name="BP", value="140/90", confidence=0.9)],
            diagnoses=[Diagnosis(name="HTN", icd11_validated="BA00", is_primary=True, confidence=0.95)],
            lab_orders=[],
            medications=[],
            procedures=[],
            warnings=[],
        )
        assert extraction.chief_complaint == "Headache for 3 days"
        assert len(extraction.vitals) == 1
        assert extraction.diagnoses[0].is_primary is True

    def test_empty_extraction(self):
        extraction = ClinicalExtraction()
        assert extraction.chief_complaint is None
        assert extraction.vitals == []
        assert extraction.diagnoses == []

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            VitalSign(name="BP", value="120/80", confidence=1.5)
        with pytest.raises(ValidationError):
            VitalSign(name="BP", value="120/80", confidence=-0.1)


class TestUserCreate:
    def test_valid_user(self):
        user = UserCreate(
            email="doctor@hospital.org",
            password="SecurePass1",
            full_name="Dr. Smith",
            role=UserRole.CLINICIAN,
        )
        assert user.email == "doctor@hospital.org"

    def test_email_normalized(self):
        user = UserCreate(
            email="  DOCTOR@Hospital.Org  ",
            password="SecurePass1",
            full_name="Dr. Smith",
            role=UserRole.CLINICIAN,
        )
        assert user.email == "doctor@hospital.org"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            UserCreate(email="not-an-email", password="SecurePass1", full_name="Test", role=UserRole.CLINICIAN)

    def test_weak_password_no_uppercase(self):
        with pytest.raises(ValidationError):
            UserCreate(email="test@test.com", password="lowercase1", full_name="Test", role=UserRole.CLINICIAN)

    def test_weak_password_no_digit(self):
        with pytest.raises(ValidationError):
            UserCreate(email="test@test.com", password="NoDigitHere", full_name="Test", role=UserRole.CLINICIAN)

    def test_short_password(self):
        with pytest.raises(ValidationError):
            UserCreate(email="test@test.com", password="Ab1", full_name="Test", role=UserRole.CLINICIAN)


class TestLoginRequest:
    def test_valid_login(self):
        req = LoginRequest(email="test@test.com", password="anything")
        assert req.email == "test@test.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            LoginRequest(email="bad", password="test")


class TestTranscriptInput:
    def test_valid_transcript(self):
        t = TranscriptInput(transcript="[CLINICIAN]: Hello patient, how are you today?")
        assert len(t.transcript) > 10

    def test_too_short(self):
        with pytest.raises(ValidationError):
            TranscriptInput(transcript="hi")


class TestScrubRequest:
    def test_valid_request(self):
        req = ScrubRequest(
            extraction=ClinicalExtraction(),
            sha_status="ACTIVE",
            sha_package="SHIF",
            amount=5000.0,
            encounter_date=datetime.utcnow(),
        )
        assert req.amount == 5000.0

    def test_negative_amount(self):
        with pytest.raises(ValidationError):
            ScrubRequest(
                extraction=ClinicalExtraction(),
                sha_status="ACTIVE",
                sha_package="SHIF",
                amount=-100.0,
                encounter_date=datetime.utcnow(),
            )


class TestClaimOverrideRequest:
    def test_valid_override(self):
        req = ClaimOverrideRequest(reason="Clinical review confirmed appropriate billing for this case.")
        assert len(req.reason) >= 10

    def test_reason_too_short(self):
        with pytest.raises(ValidationError):
            ClaimOverrideRequest(reason="short")


class TestDischargeStatusUpdate:
    def test_valid_status(self):
        update = DischargeStatusUpdate(new_status="reviewed")
        assert update.new_status == "reviewed"

    def test_invalid_status(self):
        with pytest.raises(ValidationError):
            DischargeStatusUpdate(new_status="deleted")


class TestScrubResult:
    def test_blocked_result(self):
        result = ScrubResult(
            status=ScrubStatus.BLOCKED,
            violations=[
                RuleViolation(
                    rule_id="SHA-R1",
                    rule_name="Member Status",
                    severity=Severity.BLOCK,
                    message="Patient SHA status must be active",
                    suggested_fix="Verify SHA card",
                )
            ],
            can_submit=False,
        )
        assert result.status == ScrubStatus.BLOCKED
        assert not result.can_submit
        assert len(result.violations) == 1

    def test_passed_result(self):
        result = ScrubResult(status=ScrubStatus.PASSED, violations=[], can_submit=True)
        assert result.can_submit
