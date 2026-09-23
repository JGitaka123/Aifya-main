"""D5: ICD-10 diagnosis lookup + validation."""

import uuid

import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from app.schemas.diagnosis import DiagnosisCreate
from app.services.icd10_catalog import (
    is_valid_icd10,
    lookup_icd10,
    search_icd10,
)


def test_search_by_code_prefix_surfaces_exact_first() -> None:
    results = search_icd10("B54")
    assert results, "B54 (malaria) must be searchable"
    assert results[0]["code"] == "B54"
    assert results[0]["description"] == "Unspecified malaria"


def test_search_by_description() -> None:
    results = search_icd10("malaria")
    codes = {r["code"] for r in results}
    assert "B54" in codes


def test_lookup_and_validate() -> None:
    assert lookup_icd10("b54") == "Unspecified malaria"  # case-insensitive
    assert is_valid_icd10("I10") is True
    assert is_valid_icd10("ZZ999") is False
    assert lookup_icd10("ZZ999") is None


def test_diagnosis_create_rejects_unknown_code() -> None:
    with pytest.raises(ValidationError, match="Unknown ICD-10 code"):
        DiagnosisCreate(
            encounter_id=uuid.uuid4(),
            patient_id=uuid.uuid4(),
            icd10_code="NOTREAL",
            icd10_description="Something made up",
            diagnosis_type="primary",
        )


def test_diagnosis_create_canonicalizes_description() -> None:
    """A valid code overwrites a free-typed description with the canonical one."""
    dx = DiagnosisCreate(
        encounter_id=uuid.uuid4(),
        patient_id=uuid.uuid4(),
        icd10_code="b54",  # lowercase, should normalize
        icd10_description="malaria maybe?",  # wrong, should be replaced
        diagnosis_type="primary",
    )
    assert dx.icd10_code == "B54"
    assert dx.icd10_description == "Unspecified malaria"


@pytest.mark.asyncio
async def test_icd10_search_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/icd10/search", params={"q": "B54"})
    assert resp.status_code == 200
    body = resp.json()
    assert any(item["code"] == "B54" for item in body["items"])


@pytest.mark.asyncio
async def test_icd10_lookup_endpoint_404_on_unknown(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/icd10/ZZ999")
    assert resp.status_code == 404
