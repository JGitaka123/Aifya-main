import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.encounter import Encounter
from app.models.referral import Referral
from app.models.staff import Department
from app.schemas.encounter import (
    EncounterCreate,
    EncounterRouteRequest,
    EncounterUpdate,
)
from app.schemas.referral import ReferralCreate
from app.services.clinical_workspace import SCOPE_MINE, scope_filter
from app.services.consultation_fee import load_consultation_fee_cents
from app.services.provider_directory import ProviderDirectoryService
from app.services.queue.queue_service import ENCOUNTER_QUEUE_PREFIXES, QueueService
from app.services.referral_service import ReferralService

_logger = logging.getLogger(__name__)

# How urgent a hand-off is, as a queue priority. Deliberately lower than the
# triage scale top end so routing a red-triage patient never demotes them.
URGENCY_PRIORITY = {"emergency": 5, "urgent": 4, "routine": 2}

#: Encounter types whose patients wait to be called into a room. IPD and
#: surgical are admissions and emergency runs its own triage board, so they
#: are deliberately not put on the call board.
QUEUE_ENCOUNTER_TYPES = frozenset({"opd", "mch", "dental", "follow_up"})

#: Statuses that mean the visit is over for queueing purposes.
_CLOSED_ENCOUNTER_STATUSES = frozenset(
    {"completed", "cancelled", "admitted", "discharged"}
)


def todays_encounters():
    """
    Restrict a live queue to encounters registered today.

    A queue is a one-day thing: numbers restart at 1 each morning, so an
    unfiltered query can match "queue #1" from weeks ago and offer the doctor a
    patient who left the building long ago. A visit that was never finished
    stays in the patient's record and in an explicit history view, not in the
    working queue.
    """
    return func.date(Encounter.encounter_date) == func.current_date()


class OutcomeRequiredError(Exception):
    """A visit was completed without saying what the department did."""


class EncounterService:
    """Service layer for OPD encounter and queue management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_encounter(
        self,
        data: EncounterCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
        idempotency_key: str | None = None,
    ) -> Encounter:
        """
        Create a new encounter and add to OPD queue.

        @param data: Encounter creation data
        @param facility_id: Facility UUID from JWT
        @param created_by: Staff UUID
        @param idempotency_key: Optional idempotency key
        @returns Created encounter
        """
        # Generate queue number for today
        queue_number = await self._next_queue_number(facility_id)

        encounter = Encounter(
            facility_id=facility_id,
            patient_id=data.patient_id,
            encounter_type=data.encounter_type,
            department_id=data.department_id,
            attending_doctor_id=getattr(data, "attending_doctor_id", None),
            chief_complaint=data.chief_complaint,
            triage_category=data.triage_category,
            priority=self._triage_priority(data.triage_category),
            queue_number=queue_number,
            status="waiting",
            created_by=created_by,
            updated_by=created_by,
        )

        self.db.add(encounter)
        await self.db.flush()
        await self.db.refresh(encounter)


        # Fee quoted at the desk for this department / doctor combination.
        # Resolved once so the invoice and the GL entry always agree.
        fee_cents = await self._get_consultation_fee_cents(
            facility_id,
            department_id=encounter.department_id,
            doctor_id=encounter.attending_doctor_id,
        )

        # GL auto-post: DR 1100 AR / CR 4000 Consultation Revenue
        await self._post_encounter_to_gl(
            encounter=encounter,
            facility_id=facility_id,
            user_id=created_by,
            fee_cents=fee_cents,
        )


        # Auto-create consultation invoice
        await self._create_consultation_invoice(
            encounter=encounter,
            facility_id=facility_id,
            created_by=created_by,
            fee_cents=fee_cents,
        )

        # Emit event
        event = EventBase(
            facility_id=facility_id,
            stream_type="encounter",
            stream_id=encounter.id,
            event_type="EncounterCreated",
            event_data={
                "patient_id": str(data.patient_id),
                "encounter_type": data.encounter_type,
                "chief_complaint": data.chief_complaint,
                "triage_category": data.triage_category,
                "queue_number": queue_number,
            },
            version=1,
            created_by=created_by,
            idempotency_key=idempotency_key,
        )
        self.db.add(event)

        # Bridge the visit onto the call board: a patient who is waiting in a
        # unit must own a queue ticket, or the waiting room and the wall
        # speakers never learn they are there.
        if encounter.encounter_type in QUEUE_ENCOUNTER_TYPES:
            await QueueService(self.db).enqueue_encounter(
                facility_id=facility_id,
                encounter=encounter,
                actor_id=created_by,
                prefix=(
                    None
                    if encounter.department_id
                    else ENCOUNTER_QUEUE_PREFIXES.get(encounter.encounter_type)
                ),
            )
            # enqueue() writes and flushes, which expires the visit's
            # server-set timestamps on a dirty object; reload them so the
            # response is fully populated.
            await self.db.refresh(encounter)

        return encounter

    async def _post_encounter_to_gl(
        self, encounter, facility_id, user_id, fee_cents: int
    ):
        from decimal import Decimal
        if fee_cents <= 0:
            return
        amount = Decimal(str(fee_cents)) / 100
        try:
            from app.services.finance import post_compound_transaction
        except ImportError:
            _logger.warning('encounter.gl.unavailable encounter_id=%s', encounter.id)
            return
        entries = [
            {'account_code': '1100', 'debit': amount, 'credit': Decimal('0')},
            {'account_code': '4000', 'debit': Decimal('0'), 'credit': amount},
        ]
        enc_date = encounter.encounter_date
        date_str = enc_date.date().isoformat() if hasattr(enc_date, 'date') else str(enc_date)
        metadata = {
            'date': date_str,
            'event_type': 'encounter_created',
            'reference_type': 'encounter',
            'reference_id': str(encounter.id),
            'description': f'OPD Encounter #{encounter.queue_number}',
        }
        try:
            txn = await post_compound_transaction(
                db=self.db, facility_id=facility_id, entries=entries,
                metadata=metadata,
                idempotency_key=f'encounter_created:{encounter.id}',
                user_id=user_id,
            )
            _logger.info('encounter.gl.posted encounter=%s txn=%s', encounter.id, getattr(txn, 'id', None))
        except Exception as exc:
            _logger.warning('encounter.gl.post_failed encounter=%s error=%s', encounter.id, exc)


    async def get_opd_queue(
        self,
        facility_id: uuid.UUID,
        status_filter: str | None = None,
        department_id: uuid.UUID | None = None,
        stage: str | None = None,
        include_past: bool = False,
    ) -> list[Encounter]:
        """
        Get the OPD queue ordered by triage priority then queue number.

        The board covers two stages of one journey. "assessment" is the nurse
        preparing the patient - registered, nothing measured yet. "consultation"
        is the hand-off: the assessment is done and the patient is waiting for a
        doctor. Splitting them is what stops the consultation room reading as a
        second registration desk.

        @param facility_id: Facility UUID
        @param status_filter: Optional status filter
        @param department_id: Optional department to show one unit's queue
        @param stage: assessment, consultation, or None for both
        @param include_past: Include earlier days instead of only today
        @returns List of encounters in queue order
        """
        if stage == "assessment":
            stage_filter = Encounter.triaged_at.is_(None)
        elif stage == "consultation":
            stage_filter = Encounter.triaged_at.is_not(None)
        else:
            stage_filter = None
        from sqlalchemy.orm import selectinload
        stmt = (
            select(Encounter)
            .options(selectinload(Encounter.patient))
            .where(
                Encounter.facility_id == facility_id,
                Encounter.encounter_type == "opd",
                Encounter.is_deleted == False,  # noqa: E712
            )
            .order_by(
                Encounter.priority.desc(),
                Encounter.queue_number.asc(),
            )
        )

        if stage_filter is not None:
            stmt = stmt.where(stage_filter)

        if department_id is not None:
            # A unit's own board: the patients routed to that unit.
            stmt = stmt.where(Encounter.department_id == department_id)
        else:
            # The front-door board. Once a clinician hands the patient to
            # Dental, Laboratory or another unit the encounter carries that
            # unit's id, so it belongs to that unit's queue - leaving it here
            # as well would tell the OPD doctor that a patient they already
            # referred is still waiting for them.
            stmt = stmt.where(Encounter.department_id.is_(None))

        if not include_past:
            stmt = stmt.where(todays_encounters())

        if status_filter:
            stmt = stmt.where(Encounter.status == status_filter)
        else:
            stmt = stmt.where(
                Encounter.status.in_(["waiting", "in_consultation"])
            )

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_encounter(
        self, encounter_id: uuid.UUID, facility_id: uuid.UUID
    ) -> Encounter | None:
        """
        Get a single encounter by ID.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @returns Encounter or None
        """
        result = await self.db.execute(
            select(Encounter).where(
                Encounter.id == encounter_id,
                Encounter.facility_id == facility_id,
                Encounter.is_deleted == False,  # noqa: E712
            )
        )
        encounter = result.scalar_one_or_none()
        if encounter:
            from app.models.patient import Patient
            p_result = await self.db.execute(
                select(Patient).where(Patient.id == encounter.patient_id)
            )
            patient = p_result.scalar_one_or_none()
            if patient:
                encounter.patient_name = f"{patient.first_name} {patient.last_name}".strip()  # type: ignore[attr-defined]
                encounter.patient_mrn = patient.mrn  # type: ignore[attr-defined]
        return encounter

    async def update_encounter(
        self,
        encounter_id: uuid.UUID,
        data: EncounterUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> Encounter | None:
        """
        Update encounter (status, triage, disposition, etc.).

        @param encounter_id: Encounter UUID
        @param data: Fields to update
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated encounter or None
        """
        encounter = await self.get_encounter(encounter_id, facility_id)
        if not encounter:
            return None

        update_data = data.model_dump(exclude_unset=True)
        if update_data.get("outcome") is not None:
            update_data["outcome"] = update_data["outcome"].strip()

        # A completed visit has to say what was done: the receiving
        # department's whole record of its responsibility is this one line,
        # and "completed" on its own tells the next clinician nothing. Checked
        # before anything is written, so a refused completion leaves the visit
        # exactly as it was.
        if data.status == "completed":
            outcome = update_data.get("outcome")
            if not outcome and not (encounter.outcome or "").strip():
                raise OutcomeRequiredError(
                    "An outcome note is required to complete a visit"
                )
            if not outcome:
                update_data.pop("outcome", None)

        for field, value in update_data.items():
            setattr(encounter, field, value)

        if data.status == "completed" and encounter.completed_at is None:
            encounter.completed_at = datetime.now(UTC)

        if data.triage_category:
            encounter.priority = self._triage_priority(data.triage_category)

        # Starting a consultation claims the patient, so the clinical worklist
        # can show who is holding them. Reception's pre-assignment and any
        # earlier claim are kept, so this never steals a patient from a doctor.
        if data.status == "in_consultation" and encounter.attending_doctor_id is None:
            encounter.attending_doctor_id = updated_by

        encounter.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(encounter)

        # A visit closed from the clinical workspace is over; clear its place
        # on the board so a finished patient does not sit in the waiting count.
        if encounter.status in _CLOSED_ENCOUNTER_STATUSES:
            await QueueService(self.db).close_for_encounter(
                facility_id=facility_id,
                encounter_id=encounter.id,
                actor_id=updated_by,
                reason=f"visit {encounter.status}",
            )
        elif data.triage_category:
            # Re-triage is a change of call order, not just a note.
            await QueueService(self.db).sync_encounter_triage(
                facility_id=facility_id,
                encounter_id=encounter.id,
                priority=encounter.priority,
                triage_category=encounter.triage_category,
                actor_id=updated_by,
            )

        return encounter

    async def call_next(
        self,
        facility_id: uuid.UUID,
        doctor_id: uuid.UUID,
        *,
        department_id: uuid.UUID | None = None,
        facility_wide: bool = False,
    ) -> Encounter | None:
        """
        Call the next patient the doctor can treat (highest priority waiting).

        A doctor only calls a patient they can treat: one already assigned to
        them, one reception routed to their department, or - for a doctor with
        no department of their own - one nobody routed anywhere. Otherwise a
        patient waiting for Dental could be pulled into an OPD room. Only a
        patient the nurse has assessed is called; an untriaged one raises so
        the workspace can say why instead of silently skipping them.

        @param facility_id: Facility UUID
        @param doctor_id: Doctor's staff UUID
        @param department_id: The doctor's department UUID, when they have one
        @param facility_wide: Whether the caller may work the whole facility
        @returns Next encounter or None if queue empty
        """
        filters = self.callable_filters(
            facility_id,
            doctor_id=doctor_id,
            department_id=department_id,
            facility_wide=facility_wide,
        )

        # OPD prepares the patient; the doctor only picks up a patient the
        # nurse has finished with. Without this the consultation room becomes
        # a second registration desk and the vitals are taken after the
        # decision they were meant to inform.
        result = await self.db.execute(
            select(Encounter)
            .where(*filters, Encounter.triaged_at.is_not(None))
            .order_by(
                Encounter.priority.desc(),
                Encounter.queue_number.asc(),
            )
            .limit(1)
        )
        encounter = result.scalar_one_or_none()
        if not encounter:
            pending = (
                await self.db.execute(
                    select(func.count())
                    .select_from(Encounter)
                    .where(*filters, Encounter.triaged_at.is_(None))
                )
            ).scalar() or 0
            if pending:
                raise ValueError(
                    f"{pending} patient(s) are still with OPD for assessment. "
                    "Record their vitals, or mark the assessment complete, "
                    "before calling them into the consultation room."
                )
            return None

        return await self._bring_into_room(encounter, doctor_id)

    def callable_filters(
        self,
        facility_id: uuid.UUID,
        *,
        doctor_id: uuid.UUID,
        department_id: uuid.UUID | None,
        facility_wide: bool,
    ) -> list:
        """
        The patients a doctor may bring into the room at all.

        Deliberately the same reach the worklist uses - the doctor's own
        assignments plus the unclaimed patients routed to their unit - so a
        patient the workspace shows is a patient the room can take. It is
        shared by :meth:`call_next` and :meth:`call_in` so "the next patient"
        and "this patient" can never disagree about who is callable.

        The encounter's ``encounter_type`` is NOT part of this: routing a visit
        to Dental or Physiotherapy keeps the original type, and an emergency
        visit waiting in a unit is still that unit's work. Filtering on "opd"
        hid real patients from the queue while the workspace still listed them.

        @param facility_id: Facility UUID
        @param doctor_id: Doctor's staff UUID
        @param department_id: The doctor's department UUID, when they have one
        @param facility_wide: Whether the caller may work the whole facility
        @returns SQLAlchemy predicates to AND together
        """
        filters = [
            Encounter.facility_id == facility_id,
            Encounter.status == "waiting",
            Encounter.is_deleted == False,  # noqa: E712
            todays_encounters(),
        ]
        if not facility_wide:
            filters.append(
                scope_filter(
                    SCOPE_MINE,
                    staff_id=doctor_id,
                    department_id=department_id,
                )
            )
        return filters

    async def call_in(
        self,
        encounter_id: uuid.UUID,
        *,
        facility_id: uuid.UUID,
        doctor_id: uuid.UUID,
        department_id: uuid.UUID | None = None,
        facility_wide: bool = False,
    ) -> Encounter:
        """
        Bring one named patient into the room.

        "Call next" is queue order; this is the doctor picking a patient off
        their own list - a patient they were told about, or one they are
        returning to. The gates are the same as :meth:`call_next`, so choosing
        a row by hand cannot do anything the queue button would refuse.

        @param encounter_id: Encounter UUID the doctor chose
        @param facility_id: Facility UUID
        @param doctor_id: Doctor's staff UUID
        @param department_id: The doctor's department UUID, when they have one
        @param facility_wide: Whether the caller may work the whole facility
        @returns The claimed encounter
        @raises LookupError: When the patient is not in the doctor's queue
        @raises ValueError: When the visit is not waiting, not assessed, or unpaid
        """
        filters = self.callable_filters(
            facility_id,
            doctor_id=doctor_id,
            department_id=department_id,
            facility_wide=facility_wide,
        )
        encounter = (
            await self.db.execute(
                select(Encounter).where(*filters, Encounter.id == encounter_id)
            )
        ).scalar_one_or_none()
        if encounter is None:
            # Covers "no such visit" and "not yours" alike: a doctor has no
            # business learning whether a patient exists outside their reach.
            raise LookupError("That patient is not in your queue.")
        if encounter.triaged_at is None:
            raise ValueError(
                "This patient is still with OPD for assessment. Record their "
                "vitals, or mark the assessment complete, before calling them "
                "into the consultation room."
            )
        return await self._bring_into_room(encounter, doctor_id)

    async def _bring_into_room(
        self, encounter: Encounter, doctor_id: uuid.UUID
    ) -> Encounter:
        """
        Claim a patient the gates have already cleared and start the consultation.

        @param encounter: Encounter to claim
        @param doctor_id: Doctor taking the patient
        @returns The claimed encounter
        @raises ValueError: When the consultation fee is still outstanding
        """
        await self.assert_consultation_paid(encounter)

        encounter.status = "in_consultation"
        encounter.attending_doctor_id = doctor_id
        encounter.updated_by = doctor_id
        await self.db.flush()
        await self.db.refresh(encounter)

        return encounter

    async def complete_assessment(
        self,
        encounter_id: uuid.UUID,
        facility_id: uuid.UUID,
        nurse_id: uuid.UUID,
    ) -> Encounter | None:
        """
        Mark the OPD assessment finished so the patient joins the doctor's queue.

        Vitals are the usual evidence that a nurse has seen the patient, but
        they are not always the right thing to take - a follow-up review needs
        no blood pressure cuff. This is the explicit alternative, so a patient
        can never be stranded in a stage nobody can clear.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @param nurse_id: Nurse marking the assessment complete
        @returns The updated encounter, or None when it does not exist
        @raises ValueError: When the visit is closed
        """
        # Read the row directly: refresh() below drops the display labels
        # get_encounter() decorates onto the instance, and this response does
        # not carry them anyway.
        encounter = (
            await self.db.execute(
                select(Encounter).where(
                    Encounter.id == encounter_id,
                    Encounter.facility_id == facility_id,
                    Encounter.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if encounter is None:
            return None
        if encounter.status in ("discharged", "cancelled"):
            raise ValueError("This visit is closed.")

        # Already assessed, by vitals or by this call: nothing to move.
        if encounter.triaged_at is None:
            encounter.triaged_at = datetime.now(UTC)
            encounter.nurse_id = nurse_id
            encounter.updated_by = nurse_id
            await self.db.flush()
            await self.db.refresh(encounter)
            self.db.add(
                EventBase(
                    facility_id=facility_id,
                    stream_type="encounter",
                    stream_id=encounter.id,
                    event_type="AssessmentCompleted",
                    event_data={"nurse_id": str(nurse_id)},
                    version=1,
                    created_by=nurse_id,
                )
            )
        return encounter

    async def route_to_department(
        self,
        encounter_id: uuid.UUID,
        data: EncounterRouteRequest,
        facility_id: uuid.UUID,
        routed_by: uuid.UUID,
    ) -> tuple[Encounter, Referral, str | None]:
        """
        Direct a patient from this room to another unit.

        Reception routes a patient once, at registration. This is the
        clinician's hand-off: it records an internal referral so the trail
        shows who sent the patient where and why, then re-queues the encounter
        in the destination unit so that unit's worklist picks the patient up.

        @param encounter_id: Encounter UUID
        @param data: Destination, optional clinician, urgency and reason
        @param facility_id: Facility UUID
        @param routed_by: Staff UUID of the clinician handing the patient over
        @returns Tuple of (updated encounter, internal referral, dept name)
        @raises LookupError: When the encounter does not exist
        @raises ValueError: When the destination is invalid or already current
        """
        encounter = await self.get_encounter(encounter_id, facility_id)
        if encounter is None:
            raise LookupError("Encounter not found")
        if encounter.status in ("discharged", "cancelled"):
            raise ValueError("This visit is closed and cannot be routed.")

        # get_encounter joins the display labels onto the instance; refresh()
        # below reloads only the mapped columns, so keep them to hand back.
        patient_name = getattr(encounter, "patient_name", None)
        patient_mrn = getattr(encounter, "patient_mrn", None)

        destination_id = data.receiving_department_id
        if encounter.department_id == destination_id:
            raise ValueError("The patient is already in this department.")

        department = (
            await self.db.execute(
                select(Department).where(
                    Department.id == destination_id,
                    Department.facility_id == facility_id,
                    Department.is_deleted == False,  # noqa: E712
                    Department.is_active == True,  # noqa: E712
                )
            )
        ).scalar_one_or_none()
        if department is None:
            raise ValueError("Destination department not found")

        # A named receiver has to be able to take the patient: active, a
        # clinical provider, and posted to this unit. Without this check a
        # hand-off could be addressed to any UUID - a clinician in another
        # department, or a deactivated account - and the patient would wait
        # in a queue nobody owns.
        if data.receiving_doctor_id is not None:
            eligible = await ProviderDirectoryService(
                self.db
            ).is_eligible_receiver(
                facility_id=facility_id,
                staff_id=data.receiving_doctor_id,
                department_id=destination_id,
            )
            if not eligible:
                raise ValueError(
                    "The chosen clinician is not an active provider in this unit."
                )

        referral = await ReferralService(self.db).create_referral(
            data=ReferralCreate(
                patient_id=encounter.patient_id,
                encounter_id=encounter.id,
                referral_type="internal",
                direction="outgoing",
                initial_status="sent",
                referring_doctor_id=routed_by,
                referring_department_id=encounter.department_id,
                receiving_doctor_id=data.receiving_doctor_id,
                receiving_department_id=destination_id,
                reason=data.reason,
                notes=data.notes,
                urgency=data.urgency,
            ),
            facility_id=facility_id,
            created_by=routed_by,
            initial_status="sent",
        )

        # Re-queue in the destination unit. The holder is replaced unless a
        # named clinician was chosen, so the unit can claim the patient
        # instead of the visit silently staying with the sender.
        encounter.department_id = destination_id
        encounter.attending_doctor_id = data.receiving_doctor_id
        encounter.status = "waiting"
        encounter.queue_number = await self._next_queue_number(facility_id)
        encounter.priority = max(
            encounter.priority or 0, URGENCY_PRIORITY[data.urgency]
        )
        encounter.updated_by = routed_by
        await self.db.flush()
        await self.db.refresh(encounter)
        encounter.patient_name = patient_name  # type: ignore[attr-defined]
        encounter.patient_mrn = patient_mrn  # type: ignore[attr-defined]

        self.db.add(
            EventBase(
                facility_id=facility_id,
                stream_type="encounter",
                stream_id=encounter.id,
                event_type="EncounterRouted",
                event_data={
                    "referral_number": referral.referral_number,
                    "from_department_id": (
                        str(referral.referring_department_id)
                        if referral.referring_department_id
                        else None
                    ),
                    "to_department_id": str(destination_id),
                    "to_doctor_id": (
                        str(data.receiving_doctor_id)
                        if data.receiving_doctor_id
                        else None
                    ),
                    "urgency": data.urgency,
                    "reason": data.reason,
                },
                version=1,
                created_by=routed_by,
            )
        )

        # Move the visit's place on the board with it: the unit the patient
        # left loses the ticket, and the receiving unit picks them up.
        await QueueService(self.db).enqueue_encounter(
            facility_id=facility_id,
            encounter=encounter,
            actor_id=routed_by,
        )
        await self.db.refresh(encounter)
        encounter.patient_name = patient_name  # type: ignore[attr-defined]
        encounter.patient_mrn = patient_mrn  # type: ignore[attr-defined]
        return encounter, referral, department.name

    async def get_encounter_routes(
        self, encounter_id: uuid.UUID, facility_id: uuid.UUID
    ) -> list[Referral]:
        """
        Internal routings recorded for an encounter, newest first.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @returns Internal referrals raised from this encounter
        """
        result = await self.db.execute(
            select(Referral)
            .where(
                Referral.encounter_id == encounter_id,
                Referral.facility_id == facility_id,
                Referral.referral_type == "internal",
                Referral.is_deleted == False,  # noqa: E712
            )
            .order_by(Referral.referral_date.desc())
        )
        return list(result.scalars().all())

    async def department_names(
        self, department_ids: set[uuid.UUID | None]
    ) -> dict[uuid.UUID, str]:
        """
        Resolve department labels for a page of routings.

        @param department_ids: Department UUIDs to label
        @returns Department name by id
        """
        ids = {
            department_id
            for department_id in department_ids
            if department_id is not None
        }
        if not ids:
            return {}
        rows = (
            await self.db.execute(
                select(Department.id, Department.name).where(
                    Department.id.in_(ids)
                )
            )
        ).all()
        return {row[0]: row[1] for row in rows}

    async def _get_consultation_fee_cents(
        self, facility_id, department_id=None, doctor_id=None
    ) -> int:
        """
        Resolve the consultation fee for a department / doctor combination.

        @param facility_id: Facility UUID
        @param department_id: Target department UUID (optional override)
        @param doctor_id: Target doctor's staff UUID (optional override)
        @returns Fee in KES cents
        """
        return await load_consultation_fee_cents(
            self.db,
            facility_id,
            department_id=department_id,
            doctor_id=doctor_id,
        )

    async def _consultation_invoice(self, encounter_id):
        """
        Fetch the invoice carrying an encounter's consultation fee.

        @param encounter_id: Encounter UUID
        @returns Invoice, or None when the encounter was never consultation-billed
        """
        from app.models.billing import Invoice, InvoiceItem

        result = await self.db.execute(
            select(Invoice)
            .join(InvoiceItem, InvoiceItem.invoice_id == Invoice.id)
            .where(
                Invoice.encounter_id == encounter_id,
                InvoiceItem.item_type == "consultation",
                Invoice.is_deleted == False,  # noqa: E712
            )
            .order_by(Invoice.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def assert_consultation_paid(self, encounter) -> None:
        """
        Block a consultation that has not been settled at reception.

        Encounters without a consultation invoice (facility fee configured as
        0, or encounters billed before this feature existed) pass through, so
        the gate can never strand a patient with no way to proceed.

        @param encounter: Encounter about to be seen
        @raises ValueError: When the consultation fee is still outstanding
        """
        invoice = await self._consultation_invoice(encounter.id)
        if invoice is None or invoice.balance_cents <= 0:
            return
        balance = invoice.balance_cents / 100
        raise ValueError(
            "Consultation fee not settled at reception: invoice "
            f"{invoice.invoice_number} has a balance of {balance:,.2f} KES."
        )

    async def get_consultation_fee_quote(
        self, encounter_id: uuid.UUID, facility_id: uuid.UUID
    ) -> dict | None:
        """
        Quote the consultation fee for an encounter plus its payment state.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @returns Quote dict, or None when the encounter does not exist
        """
        encounter = await self.get_encounter(encounter_id, facility_id)
        if encounter is None:
            return None

        invoice = await self._consultation_invoice(encounter.id)
        if invoice is None:
            fee = await self._get_consultation_fee_cents(
                facility_id,
                department_id=encounter.department_id,
                doctor_id=encounter.attending_doctor_id,
            )
            return {
                "encounter": encounter,
                "fee_cents": fee,
                "invoice": None,
                "paid": fee == 0,
            }

        return {
            "encounter": encounter,
            "fee_cents": invoice.total_cents,
            "invoice": invoice,
            "paid": invoice.balance_cents <= 0,
        }

    async def collect_consultation_payment(
        self,
        encounter_id: uuid.UUID,
        facility_id: uuid.UUID,
        received_by: uuid.UUID,
        payment_method: str,
        reference_number: str | None = None,
        mpesa_transaction_id: str | None = None,
        notes: str | None = None,
        amount_cents: int | None = None,
        idempotency_key: str | None = None,
    ):
        """
        Record the reception payment for an encounter's consultation fee.

        An invoice that is already settled is returned untouched, so a double
        click at the desk cannot take the patient's money twice.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @param received_by: Staff UUID of the receptionist taking payment
        @param payment_method: cash, mpesa, insurance or exemption
        @param reference_number: Optional receipt / M-Pesa reference
        @param mpesa_transaction_id: Optional M-Pesa transaction id
        @param notes: Optional free-text note
        @param amount_cents: Amount to collect (defaults to the full balance)
        @param idempotency_key: Optional client key for safe retries
        @raises ValueError: When the encounter or its invoice is missing
        @returns Tuple of (invoice, payment) - payment is None when settled
        """
        from app.schemas.billing import PaymentCreate
        from app.services.billing_service import BillingService

        encounter = await self.get_encounter(encounter_id, facility_id)
        if encounter is None:
            raise ValueError("Encounter not found")

        invoice = await self._consultation_invoice(encounter.id)
        if invoice is None:
            raise ValueError("This encounter has no consultation invoice to pay")

        if invoice.balance_cents <= 0:
            return invoice, None

        payable = amount_cents if amount_cents is not None else invoice.balance_cents
        payment = await BillingService(self.db).record_payment(
            invoice_id=invoice.id,
            data=PaymentCreate(
                amount_cents=payable,
                payment_method=payment_method,
                reference_number=reference_number,
                mpesa_transaction_id=mpesa_transaction_id,
                notes=notes,
            ),
            facility_id=facility_id,
            received_by=received_by,
            idempotency_key=idempotency_key,
        )
        return invoice, payment

    async def set_consultation_fee(
        self,
        encounter_id: uuid.UUID,
        facility_id: uuid.UUID,
        amount_cents: int,
        updated_by: uuid.UUID,
    ) -> dict | None:
        """
        Set the consultation fee charged for an encounter.

        The front desk corrects the quoted fee here: a negotiated amount, a
        follow-up rate, a doctor who charges differently. The visit's
        consultation invoice is re-priced, so the money taken, the patient's
        bill and the printed receipt all show the same amount.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @param amount_cents: New fee in KES cents (must be positive)
        @param updated_by: Staff UUID making the change
        @raises ValueError: When the amount is not positive, or is below what
            the patient has already paid
        @returns Fresh fee quote, or None when the encounter does not exist
        """
        encounter = await self.get_encounter(encounter_id, facility_id)
        if encounter is None:
            return None

        if amount_cents <= 0:
            raise ValueError("Enter a consultation fee greater than zero")

        invoice = await self._consultation_invoice(encounter.id)
        if invoice is None:
            await self._create_consultation_invoice(
                encounter, facility_id, updated_by, amount_cents
            )
            invoice = await self._consultation_invoice(encounter.id)
            if invoice is None:
                raise ValueError("Could not raise a consultation invoice")
        else:
            paid_cents = invoice.paid_cents or 0
            if amount_cents < paid_cents:
                raise ValueError(
                    "The fee cannot be less than the "
                    f"{paid_cents / 100:,.2f} KES already collected"
                )
            await self._reprice_consultation_invoice(
                invoice, amount_cents, updated_by
            )
            # A correction that leaves money owing reopens the bill.
            if invoice.balance_cents > 0 and encounter.billing_status == "paid":
                encounter.billing_status = "billed"

        self.db.add(
            EventBase(
                facility_id=facility_id,
                stream_type="billing",
                stream_id=encounter.patient_id,
                event_type="ConsultationFeeSet",
                event_data={
                    "encounter_id": str(encounter.id),
                    "invoice_number": invoice.invoice_number,
                    "fee_cents": amount_cents,
                },
                version=1,
                created_by=updated_by,
            )
        )
        await self.db.flush()
        return await self.get_consultation_fee_quote(encounter_id, facility_id)

    async def _reprice_consultation_invoice(
        self, invoice, fee_cents: int, updated_by: uuid.UUID
    ) -> None:
        """
        Re-price the consultation line on a visit's invoice.

        Any other line the visit accrued keeps its own price, and the invoice
        totals are recomputed exactly the way a payment recomputes them.

        @param invoice: The encounter's consultation invoice
        @param fee_cents: New fee in KES cents
        @param updated_by: Staff UUID making the change
        """
        from app.models.billing import InvoiceItem

        result = await self.db.execute(
            select(InvoiceItem).where(
                InvoiceItem.invoice_id == invoice.id,
                InvoiceItem.is_deleted == False,  # noqa: E712
            )
        )
        items = list(result.scalars().all())
        for item in items:
            if item.item_type != "consultation":
                continue
            item.unit_price_cents = fee_cents
            item.total_cents = fee_cents * max(item.quantity, 1)
            item.updated_by = updated_by

        subtotal = sum(item.total_cents for item in items)
        invoice.subtotal_cents = subtotal
        invoice.total_cents = (
            subtotal - (invoice.discount_cents or 0) + (invoice.tax_cents or 0)
        )
        invoice.balance_cents = max(invoice.total_cents - invoice.paid_cents, 0)
        if invoice.balance_cents <= 0:
            if invoice.paid_cents > 0:
                invoice.status = "paid"
        elif invoice.paid_cents > 0:
            invoice.status = "partially_paid"
        invoice.updated_by = updated_by

    async def _create_consultation_invoice(
        self, encounter, facility_id, created_by, fee_cents: int
    ):
        """
        Auto-create a draft invoice for the fee quoted at the front desk.
        Failures never block the clinical flow.

        @param encounter: The encounter being billed
        @param facility_id: Facility UUID
        @param created_by: Staff UUID starting the consultation
        @param fee_cents: Fee resolved for this department / doctor
        """
        try:
            from app.models.billing import Invoice, InvoiceItem

            fee = fee_cents
            if fee == 0:
                return
            inv_num = await self._next_invoice_number(facility_id)
            inv = Invoice(
                facility_id=facility_id,
                encounter_id=encounter.id,
                patient_id=encounter.patient_id,
                invoice_number=inv_num,
                status="draft",
                subtotal_cents=fee,
                total_cents=fee,
                balance_cents=fee,
                created_by=created_by,
                updated_by=created_by,
            )
            self.db.add(inv)
            await self.db.flush()
            await self.db.refresh(inv)
            item = InvoiceItem(
                facility_id=facility_id,
                invoice_id=inv.id,
                item_type="consultation",
                description=f"OPD Consultation Fee - {encounter.chief_complaint or 'General'}",
                quantity=1,
                unit_price_cents=fee,
                total_cents=fee,
                discount_cents=0,
                reference_id=encounter.id,
                reference_type="encounter",
                created_by=created_by,
                updated_by=created_by,
            )
            self.db.add(item)
            await self.db.flush()
            encounter.billing_status = "billed"
            _logger.info("encounter.invoice.created %s", inv.invoice_number)
        except Exception as exc:
            _logger.warning("encounter.invoice.failed %s %s", encounter.id, exc)

    async def _next_invoice_number(self, facility_id):
        from datetime import datetime

        from sqlalchemy import func as sqlfunc
        from sqlalchemy import select

        from app.models.billing import Invoice

        today = datetime.now(UTC).strftime("%Y%m%d")
        prefix = f'INV-{today}-'
        result = await self.db.execute(
            select(sqlfunc.count()).select_from(Invoice).where(
                Invoice.facility_id == facility_id,
                Invoice.invoice_number.like(f'{prefix}%'),
            )
        )
        count = result.scalar_one()
        return f'{prefix}{count + 1:04d}'


    async def _next_queue_number(self, facility_id: uuid.UUID) -> int:
        """Generate the next queue number for today."""
        result = await self.db.execute(
            select(func.coalesce(func.max(Encounter.queue_number), 0))
            .where(
                Encounter.facility_id == facility_id,
                Encounter.encounter_type == "opd",
                func.date(Encounter.encounter_date) == func.current_date(),
            )
        )
        return (result.scalar_one() or 0) + 1

    @staticmethod
    def _triage_priority(category: str | None) -> int:
        """Map SATS triage category to numeric priority."""
        mapping = {
            "emergency": 5,   # Red
            "urgent": 4,      # Orange
            "standard": 3,    # Yellow
            "non_urgent": 2,  # Green
            "dead": 1,        # Blue
        }
        return mapping.get(category or "", 2)
