import pytest
from datetime import datetime, timezone
from app.rules.sha_engine import SHARulesEngine
from app.models import ScrubStatus, Severity, VitalSign

def test_engine_initialization():
    engine = SHARulesEngine(config_path="app/rules/sha_rules.yaml")
    assert engine.rules is not None
    assert "membership" in engine.rules

def test_membership_rule(mock_extraction_passed):
    engine = SHARulesEngine(config_path="app/rules/sha_rules.yaml")
    
    # Should block
    result = engine.scrub(
        extraction=mock_extraction_passed,
        patient_sha_status="DEFAULTED",
        patient_sha_package="SHIF",
        amount_billed=1000,
        encounter_date=datetime.now(timezone.utc)
    )
    
    assert result.status == ScrubStatus.BLOCKED
    assert not result.can_submit
    assert any(v.rule_id == "SHA-R1" for v in result.violations)

def test_clinical_evidence_rule_missing_bp(mock_extraction_hypertension):
    engine = SHARulesEngine(config_path="app/rules/sha_rules.yaml")
    
    # Missing vitals for BA00 (Hypertension)
    result = engine.scrub(
        extraction=mock_extraction_hypertension,
        patient_sha_status="ACTIVE",
        patient_sha_package="SHIF",
        amount_billed=1000,
        encounter_date=datetime.now(timezone.utc)
    )
    
    assert result.status == ScrubStatus.BLOCKED
    assert any(v.rule_id == "SHA-R3a" for v in result.violations)

def test_clinical_evidence_rule_has_bp(mock_extraction_hypertension):
    engine = SHARulesEngine(config_path="app/rules/sha_rules.yaml")
    
    # Add the required vital
    mock_extraction_hypertension.vitals.append(
        VitalSign(name="BP", value="140/90", loinc_code="85354-9", confidence=0.9)
    )
    
    result = engine.scrub(
        extraction=mock_extraction_hypertension,
        patient_sha_status="ACTIVE",
        patient_sha_package="SHIF",
        amount_billed=1000,
        encounter_date=datetime.now(timezone.utc)
    )
    
    assert result.status == ScrubStatus.PASSED
    assert not any(v.rule_id == "SHA-R3a" for v in result.violations)
