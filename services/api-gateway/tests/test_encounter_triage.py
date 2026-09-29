"""Provenance for the nurse's triage step.

Recording vitals used to leave the encounter itself untouched: vital_signs
knew who measured what, but the visit could not say it had been triaged, so
the OPD board could not tell a triaged patient from an untriaged one. These
tests pin the two places the stamp has to exist for that to hold - the mapped
column and the API response - because losing either quietly puts the board
back where it started.
"""

import uuid
from datetime import UTC, datetime

from app.models.encounter import Encounter
from app.schemas.encounter import EncounterResponse


def _encounter(**overrides) -> Encounter:
    """Build an unsaved encounter with the fields the response requires.

    @param overrides: Fields to replace
    @returns Stand-in for a persisted Encounter
    """
    now = datetime.now(UTC)
    fields = {
        "id": uuid.uuid4(),
        "facility_id": uuid.uuid4(),
        "patient_id": uuid.uuid4(),
        "encounter_type": "opd",
        "encounter_date": now,
        "priority": 0,
        "status": "waiting",
        "billing_status": "pending",
        "created_at": now,
        "updated_at": now,
    }
    fields.update(overrides)
    return Encounter(**fields)


def test_encounter_maps_the_triage_timestamp():
    """The visit itself carries the moment it was triaged."""
    assert "triaged_at" in Encounter.__table__.columns


def test_triage_index_serves_the_opd_board():
    """The board asks "who is still waiting untriaged?" once per facility."""
    names = {index.name for index in Encounter.__table__.indexes}
    assert "ix_encounters_facility_triaged" in names


def test_encounter_response_carries_the_triage_timestamp():
    """A triaged visit reports when, without a second request."""
    triaged_at = datetime.now(UTC)
    response = EncounterResponse.model_validate(
        _encounter(triaged_at=triaged_at)
    )

    assert response.triaged_at == triaged_at


def test_encounter_response_leaves_an_untriaged_visit_null():
    """An untriaged visit says so instead of inventing a time."""
    response = EncounterResponse.model_validate(_encounter())

    assert response.triaged_at is None