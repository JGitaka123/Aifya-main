"""OPD prepares the patient; the consultation room decides what happens next.

One encounter passes two desks, and the order matters: a doctor must not call
in a patient whose observations have not been taken, because the notes they are
about to read do not exist yet. These tests pin the three things that keep the
two stages apart - the queue filter, the refusal in ``call_next``, and the
explicit hand-off a nurse can use when no measurements are needed.
"""

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models.base import EventBase
from app.models.encounter import Encounter
from app.services.clinical_workspace import ClinicalWorkspaceService
from app.services.encounter_service import EncounterService


class _StubResult:
    """Minimal stand-in for a SQLAlchemy result set.

    @param rows: Rows the result yields
    """

    def __init__(self, rows=()) -> None:
        self._rows = list(rows)

    def scalars(self) -> "_StubResult":
        """Return the result itself, as the scalar view does.

        @returns This result
        """
        return self

    def all(self) -> list:
        """Return every row.

        @returns Rows
        """
        return list(self._rows)

    def scalar_one_or_none(self):
        """Return the first row, or None.

        @returns First row or None
        """
        return self._rows[0] if self._rows else None

    def scalar(self):
        """Return the first column of the first row.

        @returns First value or None
        """
        return self._rows[0] if self._rows else None


class _ScriptedSession:
    """Async session that replays canned results and records the SQL it saw.

    @param results: Results handed out in call order
    """

    def __init__(self, results=()) -> None:
        self._results = list(results)
        self.statements: list = []
        self.added: list = []
        self.flush_count = 0

    async def execute(self, statement) -> _StubResult:
        """Record the statement and return the next canned result.

        @param statement: SQLAlchemy statement under test
        @returns The next scripted result
        """
        self.statements.append(statement)
        return self._results.pop(0)

    async def flush(self) -> None:
        """Record a flush."""
        self.flush_count += 1

    async def refresh(self, instance) -> None:
        """Accept a refresh without re-reading.

        @param instance: Instance the caller asked to refresh
        """
        return None

    def add(self, instance) -> None:
        """Record an added instance.

        @param instance: Instance added to the session
        """
        self.added.append(instance)


def _encounter(**overrides) -> Encounter:
    """Build an unsaved encounter with the fields the service reads.

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


def _raises(exception_type, callback):
    """Run a callback and return the exception it was expected to raise.

    @param exception_type: Exception class the call must raise
    @param callback: Zero-argument callable under test
    @returns The raised exception
    @raises AssertionError: When the call returns instead of raising
    """
    try:
        callback()
    except exception_type as error:
        return error
    raise AssertionError(f"{exception_type.__name__} was not raised")


def _compiled(statement) -> str:
    """Render a statement as PostgreSQL so a test can read its predicates.

    @param statement: SQLAlchemy statement
    @returns SQL text
    """
    return str(statement.compile(dialect=postgresql.dialect()))


async def _no_invoice(encounter_id):
    """Pretend an encounter carries no consultation invoice.

    @param encounter_id: Encounter UUID
    @returns None, meaning the fee gate passes
    """
    return None


def test_assessment_stage_lists_only_untriaged_patients():
    """The nurse board is the patients nobody has measured yet."""
    session = _ScriptedSession([_StubResult([])])
    service = EncounterService(session)

    asyncio.run(service.get_opd_queue(uuid.uuid4(), stage="assessment"))

    sql = _compiled(session.statements[0])
    assert "triaged_at IS NULL" in sql
    assert "triaged_at IS NOT NULL" not in sql


def test_consultation_stage_lists_only_triaged_patients():
    """The doctor queue is the patients whose observations are recorded."""
    session = _ScriptedSession([_StubResult([])])
    service = EncounterService(session)

    asyncio.run(service.get_opd_queue(uuid.uuid4(), stage="consultation"))

    sql = _compiled(session.statements[0])
    assert "triaged_at IS NOT NULL" in sql
    assert "triaged_at IS NULL" not in sql


def test_queue_without_a_stage_lists_both_desks():
    """Omitting the stage keeps the combined board so nobody disappears."""
    session = _ScriptedSession([_StubResult([])])
    service = EncounterService(session)

    asyncio.run(service.get_opd_queue(uuid.uuid4()))

    sql = _compiled(session.statements[0])
    assert "triaged_at IS NULL" not in sql
    assert "triaged_at IS NOT NULL" not in sql


def test_call_next_refuses_a_patient_still_with_opd():
    """Calling an unmeasured patient explains why nothing was called."""
    session = _ScriptedSession([_StubResult([]), _StubResult([3])])
    service = EncounterService(session)

    raised = _raises(
        ValueError,
        lambda: asyncio.run(
            service.call_next(uuid.uuid4(), uuid.uuid4(), facility_wide=True)
        ),
    )

    assert "3 patient(s) are still with OPD for assessment" in str(raised)


def test_call_next_returns_none_when_the_queue_is_empty():
    """An idle queue is not an error, even with nothing left to assess."""
    session = _ScriptedSession([_StubResult([]), _StubResult([0])])
    service = EncounterService(session)

    result = asyncio.run(
        service.call_next(uuid.uuid4(), uuid.uuid4(), facility_wide=True)
    )

    assert result is None


def test_call_next_claims_a_triaged_patient():
    """A measured patient is called in and the visit moves to the doctor."""
    doctor_id = uuid.uuid4()
    encounter = _encounter(triaged_at=datetime.now(UTC))
    session = _ScriptedSession([_StubResult([encounter])])
    service = EncounterService(session)
    service._consultation_invoice = _no_invoice

    result = asyncio.run(
        service.call_next(uuid.uuid4(), doctor_id, facility_wide=True)
    )

    assert result is encounter
    assert encounter.status == "in_consultation"
    assert encounter.attending_doctor_id == doctor_id


def test_complete_assessment_stamps_the_nurse_and_the_time():
    """The explicit hand-off records who closed the assessment."""
    nurse_id = uuid.uuid4()
    encounter = _encounter()
    session = _ScriptedSession([_StubResult([encounter])])
    service = EncounterService(session)

    result = asyncio.run(
        service.complete_assessment(encounter.id, encounter.facility_id, nurse_id)
    )

    assert result is encounter
    assert encounter.triaged_at is not None
    assert encounter.nurse_id == nurse_id
    events = [item for item in session.added if isinstance(item, EventBase)]
    assert [event.event_type for event in events] == ["AssessmentCompleted"]


def test_complete_assessment_leaves_an_already_assessed_visit_alone():
    """Vitals may have finished the assessment first; re-marking is a no-op."""
    triaged_at = datetime.now(UTC)
    encounter = _encounter(triaged_at=triaged_at, nurse_id=uuid.uuid4())
    session = _ScriptedSession([_StubResult([encounter])])
    service = EncounterService(session)

    result = asyncio.run(
        service.complete_assessment(encounter.id, encounter.facility_id, uuid.uuid4())
    )

    assert result is encounter
    assert encounter.triaged_at == triaged_at
    assert session.added == []
    assert session.flush_count == 0


def test_complete_assessment_refuses_a_closed_visit():
    """A discharged visit is not reopened by an assessment hand-off."""
    encounter = _encounter(status="discharged")
    session = _ScriptedSession([_StubResult([encounter])])
    service = EncounterService(session)

    _raises(
        ValueError,
        lambda: asyncio.run(
            service.complete_assessment(
                encounter.id, encounter.facility_id, uuid.uuid4()
            )
        ),
    )


def test_complete_assessment_returns_none_for_an_unknown_encounter():
    """An encounter outside the facility is missing, not an error."""
    session = _ScriptedSession([_StubResult([])])
    service = EncounterService(session)

    result = asyncio.run(
        service.complete_assessment(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    )

    assert result is None


def test_labels_for_names_the_triage_nurse():
    """The nurse who took the observations is looked up, not printed as a UUID."""
    encounter = _encounter(nurse_id=uuid.uuid4())
    session = _ScriptedSession([_StubResult([]), _StubResult([])])
    service = ClinicalWorkspaceService(session)

    departments, staff = asyncio.run(service.labels_for([encounter]))

    assert departments == {}
    assert staff == {}
    # No doctor and no department were routed, so the only reason a staff
    # lookup runs at all is the triage nurse being carried into it.
    assert len(session.statements) == 1


def test_labels_for_skips_the_staff_lookup_without_staff():
    """An encounter with nobody attached issues no staff query at all."""
    encounter = _encounter()
    session = _ScriptedSession([_StubResult([])])
    service = ClinicalWorkspaceService(session)

    departments, staff = asyncio.run(service.labels_for([encounter]))

    assert departments == {}
    assert staff == {}
    assert session.statements == []


def test_call_next_is_not_limited_to_opd_encounters():
    """A visit routed to Dental keeps its type, so the queue cannot filter on it.

    The workspace lists every waiting patient in a unit's reach. Filtering the
    call button to ``encounter_type = 'opd'`` hid routed and emergency visits
    from the queue while the workspace still showed them, which read as "I can
    see the patient but I cannot call them in".
    """
    session = _ScriptedSession([_StubResult([]), _StubResult([0])])
    service = EncounterService(session)

    asyncio.run(
        service.call_next(uuid.uuid4(), uuid.uuid4(), facility_wide=True)
    )

    sql = _compiled(session.statements[0])
    where = sql.split("WHERE", 1)[1]
    # encounter_type is still in the SELECT list; what matters is that it is
    # not a predicate that narrows the queue.
    assert "encounter_type =" not in where
    assert "triaged_at IS NOT NULL" in where


def test_callable_reach_matches_the_workspace_reach():
    """The queue and the workspace agree on who is callable, by construction."""
    session = _ScriptedSession([])
    service = EncounterService(session)

    filters = service.callable_filters(
        uuid.uuid4(), doctor_id=uuid.uuid4(), department_id=None,
        facility_wide=False,
    )
    sql = _compiled(select(Encounter).where(*filters))

    assert "encounters.status = " in sql
    assert "attending_doctor_id" in sql


def test_call_in_refuses_a_patient_outside_the_doctors_reach():
    """A visit that is not the doctor's is reported as absent, not taken."""
    session = _ScriptedSession([_StubResult([])])
    service = EncounterService(session)

    raised = _raises(
        LookupError,
        lambda: asyncio.run(
            service.call_in(
                uuid.uuid4(),
                facility_id=uuid.uuid4(),
                doctor_id=uuid.uuid4(),
                facility_wide=False,
            )
        ),
    )

    assert "not in your queue" in str(raised)


def test_call_in_refuses_a_patient_still_with_opd():
    """Choosing a row by hand cannot skip the nurse's assessment."""
    encounter = _encounter(triaged_at=None)
    session = _ScriptedSession([_StubResult([encounter])])
    service = EncounterService(session)

    raised = _raises(
        ValueError,
        lambda: asyncio.run(
            service.call_in(
                encounter.id,
                facility_id=encounter.facility_id,
                doctor_id=uuid.uuid4(),
                facility_wide=True,
            )
        ),
    )

    assert "still with OPD" in str(raised)
    assert encounter.status == "waiting"


def test_call_in_claims_a_triaged_patient():
    """A measured patient the doctor picked is claimed and moved to the room."""
    doctor_id = uuid.uuid4()
    encounter = _encounter(triaged_at=datetime.now(UTC))
    session = _ScriptedSession([_StubResult([encounter])])
    service = EncounterService(session)
    service._consultation_invoice = _no_invoice

    result = asyncio.run(
        service.call_in(
            encounter.id,
            facility_id=encounter.facility_id,
            doctor_id=doctor_id,
            facility_wide=True,
        )
    )

    assert result is encounter
    assert encounter.status == "in_consultation"
    assert encounter.attending_doctor_id == doctor_id
