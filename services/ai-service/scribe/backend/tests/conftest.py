import pytest
from datetime import datetime
from app.models import ClinicalExtraction

@pytest.fixture
def mock_extraction_passed():
    return ClinicalExtraction(
        chief_complaint="Routine checkup",
        vitals=[],
        diagnoses=[],
        lab_orders=[],
        medications=[],
        procedures=[],
        warnings=[]
    )

@pytest.fixture
def mock_extraction_hypertension():
    from app.models import Diagnosis, VitalSign
    return ClinicalExtraction(
        chief_complaint="Headache",
        vitals=[], # Intentionally missing BP
        diagnoses=[
            Diagnosis(name="Hypertension", icd11_validated="BA00", is_primary=True, confidence=0.99)
        ],
        lab_orders=[],
        medications=[],
        procedures=[],
        warnings=[]
    )
