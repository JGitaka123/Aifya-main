import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.encounter import Encounter
from app.models.mch import (
    ANCProfile,
    ANCVisit,
    ChildRecord,
    DeliveryRecord,
    Immunization,
)
from app.models.patient import Patient
from app.models.staff import Department
from app.schemas.mch import (
    ANCProfileCreate,
    ANCProfileDetail,
    ANCProfileListItem,
    ANCProfileResponse,
    ANCVisitCreate,
    ANCVisitResponse,
    ChildRecordCreate,
    ChildRecordListItem,
    DeliveryRecordCreate,
    ImmunizationCreate,
    ImmunizationScheduleItem,
    ImmunizationUpdate,
    MCHSummary,
)
from app.services.anc_fee import (
    load_anc_visit_enforce_payment,
    load_anc_visit_fee_cents,
)
from app.services.queue.queue_service import QueueService
from app.services.service_billing import (
    MCH_ANC_VISIT,
    ServiceBillingService,
    post_service_charge,
)

# ── Kenya EPI (KEPI) routine immunization schedule ──────────────────────────────

# (vaccine_code, vaccine_name, due_age_weeks, route, site)
KEPI_SCHEDULE: tuple[tuple[str, str, int, str | None, str | None], ...] = (
    ("BCG", "BCG", 0, "id", "right_arm"),
    ("OPV_0", "OPV Birth Dose", 0, "oral", "oral"),
    ("OPV_1", "OPV 1", 6, "oral", "oral"),
    ("PENTA_1", "Pentavalent 1", 6, "im", "left_thigh"),
    ("PCV_1", "PCV10 1", 6, "im", "right_thigh"),
    ("ROTA_1", "Rotavirus 1", 6, "oral", "oral"),
    ("OPV_2", "OPV 2", 10, "oral", "oral"),
    ("PENTA_2", "Pentavalent 2", 10, "im", "left_thigh"),
    ("PCV_2", "PCV10 2", 10, "im", "right_thigh"),
    ("ROTA_2", "Rotavirus 2", 10, "oral", "oral"),
    ("OPV_3", "OPV 3", 14, "oral", "oral"),
    ("PENTA_3", "Pentavalent 3", 14, "im", "left_thigh"),
    ("PCV_3", "PCV10 3", 14, "im", "right_thigh"),
    ("IPV", "IPV", 14, "im", "right_thigh"),
    ("ROTA_3", "Rotavirus 3", 14, "oral", "oral"),
    ("VITAMIN_A_1", "Vitamin A 1", 26, "oral", "oral"),
    ("MR_1", "Measles-Rubella 1", 39, "sc", "left_arm"),
    ("YELLOW_FEVER", "Yellow Fever", 39, "sc", "left_arm"),
    ("MR_2", "Measles-Rubella 2", 78, "sc", "left_arm"),
    ("VITAMIN_A_2", "Vitamin A 2", 78, "oral", "oral"),
)

# Codes that facilities use for the same scheduled dose.
KEPI_CODE_ALIASES: dict[str, frozenset[str]] = {
    "MR_1": frozenset({"MR_1", "MEASLES_1", "MEASLES_RUBELLA_1"}),
    "MR_2": frozenset({"MR_2", "MEASLES_2", "MEASLES_RUBELLA_2"}),
    "VITAMIN_A_1": frozenset({"VITAMIN_A_1", "VITAMIN_A"}),
    "VITAMIN_A_2": frozenset({"VITAMIN_A_2"}),
}

# A dose only counts as overdue once this many weeks have passed since it was due.
KEPI_GRACE_WEEKS = 2


def normalise_vaccine_code(vaccine_code: str) -> str:
    """
    Normalise a recorded vaccine code to its canonical KEPI schedule code.

    @param vaccine_code: Raw code captured at administration
    @returns Canonical schedule code
    """
    wanted = vaccine_code.strip().upper().replace(" ", "_").replace("-", "_")
    for entry in KEPI_SCHEDULE:
        codes = KEPI_CODE_ALIASES.get(entry[0], frozenset({entry[0]}))
        if wanted in codes:
            return entry[0]
    return wanted


def kepi_schedule_entry(
    vaccine_code: str,
) -> tuple[str, str, int, str | None, str | None] | None:
    """
    Look up the KEPI schedule row for a vaccine code.

    @param vaccine_code: Raw or canonical vaccine code
    @returns Schedule row, or None when the code is off-schedule
    """
    canonical = normalise_vaccine_code(vaccine_code)
    for entry in KEPI_SCHEDULE:
        if entry[0] == canonical:
            return entry
    return None


def kepi_outstanding_doses(
    date_of_birth: date,
    given_codes: set[str],
    today: date,
) -> list[tuple[str, str, int, bool]]:
    """
    Work out which routine doses a child still needs.

    @param date_of_birth: Child date of birth
    @param given_codes: Vaccine codes already recorded for the child
    @param today: Reference date
    @returns (code, name, due_age_weeks, is_overdue) in schedule order
    """
    given = {normalise_vaccine_code(code) for code in given_codes}
    age_weeks = (today - date_of_birth).days // 7
    outstanding: list[tuple[str, str, int, bool]] = []
    for code, name, due_week, _route, _site in KEPI_SCHEDULE:
        if code in given:
            continue
        outstanding.append((code, name, due_week, age_weeks >= due_week + KEPI_GRACE_WEEKS))
    return outstanding


#: Units maternal patients wait in, in the order we prefer them. Codes are
#: matched first, then names, so a facility that words its department
#: differently still lands on the right queue.
MCH_DEPARTMENT_CODES = ("MCH", "ANC", "MAT", "OBGYN", "REPRO")
MCH_DEPARTMENT_NAME_HINTS = (
    "maternal",
    "child health",
    "obstetric",
    "antenatal",
)

#: Risk level -> the queue's triage vocabulary and priority. Deliberately the
#: same scale the encounter queue uses, so a high-risk pregnancy is called
#: before a routine visit rather than after it.
MCH_RISK_TRIAGE = {"low": "non_urgent", "moderate": "standard", "high": "urgent"}
MCH_RISK_PRIORITY = {"low": 2, "moderate": 3, "high": 4}


class MCHService:
    """
    Service for Maternal & Child Health: ANC profiles, visits, delivery,
    child records, and immunization tracking.
    Follows Kenya MOH registers (MOH 405, MOH 333, MOH 510).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── ANC Profile ───────────────────────────────────────────────────────

    async def _mch_department_id(self, facility_id: uuid.UUID) -> uuid.UUID | None:
        """Find the unit maternal patients wait in, if the facility has one.

        @param facility_id: Facility to search
        @returns The maternal unit's id, or None when the facility has none
        """

        rows = (
            await self.db.execute(
                select(Department.id, Department.code, Department.name).where(
                    Department.facility_id == facility_id,
                    Department.is_deleted == False,  # noqa: E712
                    Department.is_active == True,  # noqa: E712
                )
            )
        ).all()
        if not rows:
            return None
        by_code = {code.upper(): dept_id for dept_id, code, _name in rows}
        for code in MCH_DEPARTMENT_CODES:
            if code in by_code:
                return by_code[code]
        for dept_id, _code, name in rows:
            lowered = (name or "").lower()
            if any(hint in lowered for hint in MCH_DEPARTMENT_NAME_HINTS):
                return dept_id
        return None

    async def _active_encounter_id(
        self,
        *,
        facility_id: uuid.UUID,
        patient_id: uuid.UUID,
        encounter_id: uuid.UUID | None,
    ) -> uuid.UUID | None:
        """Resolve the visit an ANC record should be billed against.

        A clinician usually names the encounter, but a visit recorded from the
        maternal register may not carry one. In that case the patient's live
        visit is used, so the fee lands on the bill the desk is already
        holding rather than on a second, orphan invoice.

        @param facility_id: Facility UUID
        @param patient_id: Patient the record belongs to
        @param encounter_id: Encounter the caller named, if any
        @returns A facility-scoped encounter id, or None when there is none
        """

        conditions = [
            Encounter.facility_id == facility_id,
            Encounter.is_deleted == False,  # noqa: E712
        ]
        if encounter_id is not None:
            conditions.append(Encounter.id == encounter_id)
        else:
            conditions.append(Encounter.patient_id == patient_id)
            conditions.append(
                Encounter.status.in_(("waiting", "in_consultation"))
            )
        return (
            await self.db.execute(
                select(Encounter.id)
                .where(*conditions)
                .order_by(Encounter.encounter_date.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

    async def _bill_anc_visit(
        self,
        *,
        facility_id: uuid.UUID,
        patient_id: uuid.UUID,
        encounter_id: uuid.UUID,
        provider_id: uuid.UUID,
        risk_level: str | None,
    ) -> None:
        """Put one ANC visit on the encounter bill, exactly once.

        The charge is keyed on the encounter so a day of ANC reviews shares a
        single collectable line rather than posting a fee per keystroke. When
        the facility enforces payment, an ANC balance left over on that
        encounter from an earlier visit blocks a further visit until the desk
        collects it; the line posted by this visit never blocks itself.

        @param facility_id: Facility UUID
        @param patient_id: Patient being billed
        @param encounter_id: Encounter carrying the ANC visit
        @param provider_id: Clinician recording the visit
        @param risk_level: Profile risk level, used to price the visit
        @raises ValueError: When an earlier ANC charge is still unpaid
        """

        billing = ServiceBillingService(self.db)
        existing = await billing.charge_for(
            facility_id, MCH_ANC_VISIT, encounter_id
        )
        if existing is not None:
            if not existing.paid and await load_anc_visit_enforce_payment(
                self.db, facility_id
            ):
                await billing.assert_service_paid(
                    facility_id, MCH_ANC_VISIT, encounter_id
                )
            return

        price = await load_anc_visit_fee_cents(
            self.db, facility_id, risk_level=risk_level
        )
        if price <= 0:
            return
        await post_service_charge(
            self.db,
            facility_id=facility_id,
            encounter_id=encounter_id,
            patient_id=patient_id,
            item_type="procedure",
            description="MCH: ANC visit",
            unit_price_cents=price,
            reference_type=MCH_ANC_VISIT,
            reference_id=encounter_id,
            created_by=provider_id,
        )

    async def _queue_maternal_wait(
        self,
        *,
        facility_id: uuid.UUID,
        patient_id: uuid.UUID,
        risk_level: str | None,
        actor_id: uuid.UUID | None,
        idempotency_key: str,
    ) -> None:
        """Put a maternal patient on the unit's board while they wait.

        The maternal clinic records pregnancies and visits directly, so there
        is no encounter to hang a ticket on. When the facility has no maternal
        unit configured the ticket still carries the MCH prefix, so the patient
        is never invisible and the speaker still calls a clean number.

        @param facility_id: Facility the patient is waiting in
        @param patient_id: The patient who is waiting
        @param risk_level: ANC risk level, used for triage and priority
        @param actor_id: Staff member registering the wait
        @param idempotency_key: Retry key for this registration
        """

        department_id = await self._mch_department_id(facility_id)
        prefix = None if department_id is not None else "MCH"
        priority = MCH_RISK_PRIORITY.get(risk_level or "low", 2)
        triage_category = MCH_RISK_TRIAGE.get(
            risk_level or "low", "non_urgent"
        )
        queue = QueueService(self.db)
        # A visit recorded for a patient who is already on the board re-ranks
        # the ticket they hold instead of leaving it behind: a waiting patient
        # escalated to high risk jumps the line, and one already called or in
        # the chair keeps that place while their priority rises. Only a patient
        # with no live ticket needs a brand new one.
        retriaged = await queue.retriage_patient(
            facility_id=facility_id,
            patient_id=patient_id,
            department_id=department_id,
            prefix=prefix,
            actor_id=actor_id,
            priority=priority,
            triage_category=triage_category,
            reason="mch_anc_visit",
            source_id=idempotency_key,
        )
        if retriaged is not None:
            return
        await queue.enqueue_patient(
            facility_id=facility_id,
            patient_id=patient_id,
            actor_id=actor_id,
            department_id=department_id,
            triage_category=triage_category,
            priority=priority,
            prefix=prefix,
            idempotency_key=idempotency_key,
        )

    async def create_anc_profile(
        self,
        data: ANCProfileCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> ANCProfile:
        """
        Register a new pregnancy / ANC profile.

        @param data: ANC profile creation data
        @param facility_id: Facility UUID from JWT
        @param created_by: Staff UUID
        @returns Created ANC profile
        @raises ValueError: If the patient does not exist in this facility
        """
        patient_exists = await self.db.execute(
            select(Patient.id).where(
                Patient.id == data.patient_id,
                Patient.facility_id == facility_id,
                Patient.is_deleted == False,  # noqa: E712
            )
        )
        if patient_exists.scalar_one_or_none() is None:
            raise ValueError("Patient not found")

        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")

        # Auto-generate ANC number
        count_result = await self.db.execute(
            select(func.count(ANCProfile.id)).where(
                ANCProfile.facility_id == facility_id,
                ANCProfile.anc_number.like(f"ANC-{date_part}-%"),
            )
        )
        seq = (count_result.scalar() or 0) + 1
        anc_number = f"ANC-{date_part}-{seq:04d}"

        # Calculate EDD from LMP if not provided (Naegele's rule: +280 days)
        edd = data.expected_delivery_date
        gestation_at_first: int | None = None
        if data.lmp_date:
            if not edd:
                from datetime import timedelta
                edd = data.lmp_date + timedelta(days=280)
            # Calculate gestation at first visit
            days_since_lmp = (now.date() - data.lmp_date).days
            gestation_at_first = days_since_lmp // 7

        profile = ANCProfile(
            facility_id=facility_id,
            patient_id=data.patient_id,
            encounter_id=data.encounter_id,
            anc_number=anc_number,
            gravida=data.gravida,
            parity=data.parity,
            living_children=data.living_children,
            lmp_date=data.lmp_date,
            expected_delivery_date=edd,
            first_visit_date=now.date(),
            gestation_at_first_visit=gestation_at_first,
            risk_level=data.risk_level,
            risk_factors=data.risk_factors,
            blood_group=data.blood_group,
            hiv_status=data.hiv_status,
            on_art=data.on_art,
            pmtct_enrolled=data.hiv_status == "positive",
            status="active",
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)

        event = EventBase(
            facility_id=facility_id,
            stream_type="mch",
            stream_id=data.patient_id,
            event_type="ANCProfileCreated",
            event_data={
                "profile_id": str(profile.id),
                "anc_number": anc_number,
                "gravida": data.gravida,
                "parity": data.parity,
                "risk_level": data.risk_level,
            },
            version=1,
            created_by=created_by,
        )
        self.db.add(event)

        # A pregnancy registration is a patient now waiting in the maternal
        # clinic, so it must show on the board and be callable by the speaker.
        await self._queue_maternal_wait(
            facility_id=facility_id,
            patient_id=profile.patient_id,
            risk_level=profile.risk_level,
            actor_id=created_by,
            idempotency_key=f"anc-profile:{profile.id}",
        )

        return profile

    async def get_anc_profiles(
        self,
        facility_id: uuid.UUID,
        status: str | None = None,
    ) -> list[ANCProfileListItem]:
        """
        Get ANC profiles with patient info and visit counts.

        @param facility_id: Facility UUID
        @param status: Optional status filter
        @returns List of ANC profiles
        """
        # Subquery: count visits per ANC profile (eliminates N+1)
        visit_counts_sq = (
            select(
                ANCVisit.anc_profile_id,
                func.count(ANCVisit.id).label("visit_count"),
            )
            .where(ANCVisit.is_deleted == False)  # noqa: E712
            .group_by(ANCVisit.anc_profile_id)
            .subquery()
        )

        query = (
            select(
                ANCProfile,
                Patient.first_name,
                Patient.last_name,
                Patient.mrn,
                func.coalesce(visit_counts_sq.c.visit_count, 0).label("visit_count"),
            )
            .join(Patient, ANCProfile.patient_id == Patient.id)
            .outerjoin(
                visit_counts_sq,
                ANCProfile.id == visit_counts_sq.c.anc_profile_id,
            )
            .where(
                ANCProfile.facility_id == facility_id,
                ANCProfile.is_deleted == False,  # noqa: E712
            )
        )

        if status:
            query = query.where(ANCProfile.status == status)

        query = query.order_by(ANCProfile.created_at.desc())
        result = await self.db.execute(query)
        rows = result.all()

        items: list[ANCProfileListItem] = []
        for profile, first_name, last_name, mrn, visit_count in rows:
            # Calculate current gestation weeks
            gestation_weeks: int | None = None
            if profile.lmp_date and profile.status == "active":
                days = (date.today() - profile.lmp_date).days
                gestation_weeks = days // 7

            patient_name = f"{first_name or ''} {last_name or ''}".strip() or None
            items.append(
                ANCProfileListItem(
                    id=profile.id,
                    anc_number=profile.anc_number,
                    patient_id=profile.patient_id,
                    patient_name=patient_name,
                    patient_mrn=mrn,
                    gravida=profile.gravida,
                    parity=profile.parity,
                    expected_delivery_date=profile.expected_delivery_date,
                    gestation_weeks=gestation_weeks,
                    risk_level=profile.risk_level,
                    status=profile.status,
                    visit_count=visit_count,
                    created_at=profile.created_at,
                )
            )

        return items

    async def get_anc_profile_detail(
        self,
        profile_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> ANCProfileDetail | None:
        """
        Get full ANC profile with visits, delivery, and patient info.

        @param profile_id: ANC profile UUID
        @param facility_id: Facility UUID
        @returns Profile detail, or None
        """
        result = await self.db.execute(
            select(ANCProfile, Patient.first_name, Patient.last_name, Patient.mrn)
            .join(Patient, ANCProfile.patient_id == Patient.id)
            .where(
                ANCProfile.id == profile_id,
                ANCProfile.facility_id == facility_id,
                ANCProfile.is_deleted == False,  # noqa: E712
            )
        )
        row = result.first()
        if not row:
            return None

        profile, first_name, last_name, mrn = row
        patient_name = f"{first_name or ''} {last_name or ''}".strip() or None

        # Get visits
        visits_result = await self.db.execute(
            select(ANCVisit)
            .where(
                ANCVisit.anc_profile_id == profile_id,
                ANCVisit.is_deleted == False,  # noqa: E712
            )
            .order_by(ANCVisit.visit_number.asc())
        )
        visits = [
            ANCVisitResponse.model_validate(v)
            for v in visits_result.scalars().all()
        ]

        # Get delivery record
        delivery_result = await self.db.execute(
            select(DeliveryRecord).where(
                DeliveryRecord.anc_profile_id == profile_id,
                DeliveryRecord.is_deleted == False,  # noqa: E712
            )
        )
        delivery_record = delivery_result.scalar_one_or_none()

        from app.schemas.mch import DeliveryRecordResponse

        return ANCProfileDetail(
            profile=ANCProfileResponse.model_validate(profile),
            visits=visits,
            delivery=DeliveryRecordResponse.model_validate(delivery_record) if delivery_record else None,
            patient_name=patient_name,
            patient_mrn=mrn,
        )

    # ── ANC Visit ─────────────────────────────────────────────────────────

    async def add_anc_visit(
        self,
        data: ANCVisitCreate,
        facility_id: uuid.UUID,
        provider_id: uuid.UUID,
    ) -> ANCVisit:
        """
        Record an ANC visit. Auto-increments visit number.

        @param data: ANC visit data
        @param facility_id: Facility UUID
        @param provider_id: Provider UUID
        @returns Created ANC visit
        """
        # Get profile to verify and get patient_id
        profile_result = await self.db.execute(
            select(ANCProfile).where(
                ANCProfile.id == data.anc_profile_id,
                ANCProfile.facility_id == facility_id,
                ANCProfile.is_deleted == False,  # noqa: E712
            )
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise ValueError("ANC profile not found")

        # Count existing visits for auto-numbering
        count_result = await self.db.execute(
            select(func.count(ANCVisit.id)).where(
                ANCVisit.anc_profile_id == data.anc_profile_id,
                ANCVisit.is_deleted == False,  # noqa: E712
            )
        )
        visit_number = (count_result.scalar() or 0) + 1

        # Bill the visit against the encounter the clinician named, or the
        # patient's live visit when the maternal register did not name one.
        encounter_id = await self._active_encounter_id(
            facility_id=facility_id,
            patient_id=profile.patient_id,
            encounter_id=data.encounter_id,
        )

        visit = ANCVisit(
            facility_id=facility_id,
            anc_profile_id=data.anc_profile_id,
            patient_id=profile.patient_id,
            encounter_id=encounter_id,
            provider_id=provider_id,
            visit_number=visit_number,
            visit_date=data.visit_date,
            gestation_weeks=data.gestation_weeks,
            weight_kg=data.weight_kg,
            bp_systolic=data.bp_systolic,
            bp_diastolic=data.bp_diastolic,
            pulse_rate=data.pulse_rate,
            temperature=data.temperature,
            urine_protein=data.urine_protein,
            urine_glucose=data.urine_glucose,
            fundal_height_cm=data.fundal_height_cm,
            fetal_heart_rate=data.fetal_heart_rate,
            fetal_presentation=data.fetal_presentation,
            fetal_movement=data.fetal_movement,
            oedema=data.oedema,
            hb_level=data.hb_level,
            iron_folate_given=data.iron_folate_given,
            tetanus_dose=data.tetanus_dose,
            ipt_malaria_dose=data.ipt_malaria_dose,
            deworming_given=data.deworming_given,
            llins_given=data.llins_given,
            birth_plan_discussed=data.birth_plan_discussed,
            danger_signs_counselled=data.danger_signs_counselled,
            breastfeeding_counselled=data.breastfeeding_counselled,
            next_visit_date=data.next_visit_date,
            clinical_notes=data.clinical_notes,
            complications=data.complications,
            referred=data.referred,
            referral_reason=data.referral_reason,
            created_by=provider_id,
            updated_by=provider_id,
        )
        self.db.add(visit)
        await self.db.flush()
        await self.db.refresh(visit)

        # Auto-escalate risk level on concerning findings
        if data.bp_systolic and data.bp_systolic >= 140 and profile.risk_level == "low":
            profile.risk_level = "moderate"
        if data.bp_systolic and data.bp_systolic >= 160:
            profile.risk_level = "high"
        if data.oedema and data.oedema in ("moderate", "severe"):
            profile.risk_level = "high"

        event = EventBase(
            facility_id=facility_id,
            stream_type="mch",
            stream_id=profile.patient_id,
            event_type="ANCVisitRecorded",
            event_data={
                "profile_id": str(data.anc_profile_id),
                "visit_number": visit_number,
                "gestation_weeks": data.gestation_weeks,
                "bp": f"{data.bp_systolic}/{data.bp_diastolic}" if data.bp_systolic else None,
            },
            version=1,
            created_by=provider_id,
        )
        self.db.add(event)

        # The visit is a billable service: put it on the visit's bill so the
        # cashier can collect for it, and let an enforcing facility refuse a
        # further ANC visit while an earlier ANC balance is still open.
        if encounter_id is not None:
            await self._bill_anc_visit(
                facility_id=facility_id,
                patient_id=profile.patient_id,
                encounter_id=encounter_id,
                provider_id=provider_id,
                risk_level=profile.risk_level,
            )

        # A recorded visit is the patient sitting in the clinic; keep them on
        # the board so the speaker can call them in.
        await self._queue_maternal_wait(
            facility_id=facility_id,
            patient_id=profile.patient_id,
            risk_level=profile.risk_level,
            actor_id=provider_id,
            idempotency_key=f"anc-visit:{visit.id}",
        )

        return visit

    # ── Delivery ──────────────────────────────────────────────────────────

    async def record_delivery(
        self,
        data: DeliveryRecordCreate,
        facility_id: uuid.UUID,
        delivered_by: uuid.UUID,
    ) -> DeliveryRecord:
        """
        Record a delivery. Updates ANC profile status and outcome.

        @param data: Delivery record data
        @param facility_id: Facility UUID
        @param delivered_by: Staff UUID
        @returns Created delivery record
        """
        # Get profile
        profile_result = await self.db.execute(
            select(ANCProfile).where(
                ANCProfile.id == data.anc_profile_id,
                ANCProfile.facility_id == facility_id,
                ANCProfile.is_deleted == False,  # noqa: E712
            )
        )
        profile = profile_result.scalar_one_or_none()
        if not profile:
            raise ValueError("ANC profile not found")

        delivery = DeliveryRecord(
            facility_id=facility_id,
            anc_profile_id=data.anc_profile_id,
            patient_id=profile.patient_id,
            encounter_id=data.encounter_id,
            delivered_by=delivered_by,
            delivery_date=data.delivery_date,
            gestation_weeks=data.gestation_weeks,
            mode_of_delivery=data.mode_of_delivery,
            duration_of_labour_hours=data.duration_of_labour_hours,
            place_of_delivery=data.place_of_delivery,
            maternal_outcome=data.maternal_outcome,
            maternal_complications=data.maternal_complications,
            blood_loss_ml=data.blood_loss_ml,
            episiotomy=data.episiotomy,
            tears=data.tears,
            baby_outcome=data.baby_outcome,
            baby_sex=data.baby_sex,
            birth_weight_grams=data.birth_weight_grams,
            apgar_1min=data.apgar_1min,
            apgar_5min=data.apgar_5min,
            apgar_10min=data.apgar_10min,
            resuscitation_needed=data.resuscitation_needed,
            skin_to_skin=data.skin_to_skin,
            breastfed_within_1hr=data.breastfed_within_1hr,
            vitamin_k_given=data.vitamin_k_given,
            eye_prophylaxis=data.eye_prophylaxis,
            bcg_given=data.bcg_given,
            opv_0_given=data.opv_0_given,
            arv_prophylaxis_baby=data.arv_prophylaxis_baby,
            notes=data.notes,
            created_by=delivered_by,
            updated_by=delivered_by,
        )
        self.db.add(delivery)

        # Update ANC profile
        profile.status = "delivered"
        if data.baby_outcome == "live_birth":
            profile.pregnancy_outcome = "live_birth"
        elif data.baby_outcome in ("fresh_stillbirth", "macerated_stillbirth"):
            profile.pregnancy_outcome = "stillbirth"

        await self.db.flush()
        await self.db.refresh(delivery)

        event = EventBase(
            facility_id=facility_id,
            stream_type="mch",
            stream_id=profile.patient_id,
            event_type="DeliveryRecorded",
            event_data={
                "delivery_id": str(delivery.id),
                "profile_id": str(data.anc_profile_id),
                "mode": data.mode_of_delivery,
                "baby_outcome": data.baby_outcome,
                "baby_sex": data.baby_sex,
                "birth_weight": data.birth_weight_grams,
            },
            version=1,
            created_by=delivered_by,
        )
        self.db.add(event)

        return delivery

    # ── Child Records ─────────────────────────────────────────────────────

    async def create_child_record(
        self,
        data: ChildRecordCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> ChildRecord:
        """
        Create a child health record.

        @param data: Child record data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created child record
        @raises ValueError: If the child, mother, or delivery record is unknown to this facility
        """
        patient_exists = await self.db.execute(
            select(Patient.id).where(
                Patient.id == data.patient_id,
                Patient.facility_id == facility_id,
                Patient.is_deleted == False,  # noqa: E712
            )
        )
        if patient_exists.scalar_one_or_none() is None:
            raise ValueError("Patient not found")

        if data.mother_patient_id:
            mother_exists = await self.db.execute(
                select(Patient.id).where(
                    Patient.id == data.mother_patient_id,
                    Patient.facility_id == facility_id,
                    Patient.is_deleted == False,  # noqa: E712
                )
            )
            if mother_exists.scalar_one_or_none() is None:
                raise ValueError("Mother not found")

        if data.delivery_record_id:
            delivery_exists = await self.db.execute(
                select(DeliveryRecord.id).where(
                    DeliveryRecord.id == data.delivery_record_id,
                    DeliveryRecord.facility_id == facility_id,
                )
            )
            if delivery_exists.scalar_one_or_none() is None:
                raise ValueError("Delivery record not found")

        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")

        count_result = await self.db.execute(
            select(func.count(ChildRecord.id)).where(
                ChildRecord.facility_id == facility_id,
                ChildRecord.child_number.like(f"CWC-{date_part}-%"),
            )
        )
        seq = (count_result.scalar() or 0) + 1
        child_number = f"CWC-{date_part}-{seq:04d}"

        child = ChildRecord(
            facility_id=facility_id,
            patient_id=data.patient_id,
            mother_patient_id=data.mother_patient_id,
            delivery_record_id=data.delivery_record_id,
            child_number=child_number,
            date_of_birth=data.date_of_birth,
            birth_weight_grams=data.birth_weight_grams,
            sex=data.sex,
            place_of_birth=data.place_of_birth,
            birth_notification_number=data.birth_notification_number,
            hiv_exposed=data.hiv_exposed,
            feeding_method=data.feeding_method,
            status="active",
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(child)
        await self.db.flush()
        await self.db.refresh(child)

        event = EventBase(
            facility_id=facility_id,
            stream_type="mch",
            stream_id=data.patient_id,
            event_type="ChildRecordCreated",
            event_data={
                "child_id": str(child.id),
                "child_number": child_number,
                "dob": str(data.date_of_birth),
                "sex": data.sex,
            },
            version=1,
            created_by=created_by,
        )
        self.db.add(event)

        return child

    async def get_child_records(
        self,
        facility_id: uuid.UUID,
    ) -> list[ChildRecordListItem]:
        """
        Get child health records with immunization counts.

        @param facility_id: Facility UUID
        @returns List of child records
        """
        # Subquery: count immunizations per child record (eliminates N+1)
        imm_counts_sq = (
            select(
                Immunization.child_record_id,
                func.count(Immunization.id).label("imm_count"),
            )
            .where(Immunization.is_deleted == False)  # noqa: E712
            .group_by(Immunization.child_record_id)
            .subquery()
        )

        result = await self.db.execute(
            select(
                ChildRecord,
                Patient.first_name,
                Patient.last_name,
                func.coalesce(imm_counts_sq.c.imm_count, 0).label("imm_count"),
            )
            .join(Patient, ChildRecord.patient_id == Patient.id)
            .outerjoin(
                imm_counts_sq,
                ChildRecord.id == imm_counts_sq.c.child_record_id,
            )
            .where(
                ChildRecord.facility_id == facility_id,
                ChildRecord.is_deleted == False,  # noqa: E712
                ChildRecord.status == "active",
            )
            .order_by(ChildRecord.created_at.desc())
        )
        rows = result.all()

        # Vaccine codes per child so we can derive the next due dose.
        child_ids = [row[0].id for row in rows]
        given_by_child: dict[uuid.UUID, set[str]] = {}
        if child_ids:
            imm_rows = await self.db.execute(
                select(
                    Immunization.child_record_id,
                    Immunization.vaccine_code,
                ).where(
                    Immunization.facility_id == facility_id,
                    Immunization.is_deleted == False,  # noqa: E712
                    Immunization.child_record_id.in_(child_ids),
                )
            )
            for child_id, code in imm_rows.all():
                given_by_child.setdefault(child_id, set()).add(code)

        items: list[ChildRecordListItem] = []
        for child, first_name, last_name, imm_count in rows:
            # Calculate age in months
            age_months: int | None = None
            if child.date_of_birth:
                today = date.today()
                age_months = (today.year - child.date_of_birth.year) * 12 + (
                    today.month - child.date_of_birth.month
                )

            outstanding = kepi_outstanding_doses(
                child.date_of_birth,
                given_by_child.get(child.id, set()),
                date.today(),
            )
            patient_name = f"{first_name or ''} {last_name or ''}".strip() or None
            items.append(
                ChildRecordListItem(
                    id=child.id,
                    child_number=child.child_number,
                    patient_id=child.patient_id,
                    patient_name=patient_name,
                    date_of_birth=child.date_of_birth,
                    sex=child.sex,
                    age_months=age_months,
                    hiv_exposed=child.hiv_exposed,
                    immunization_count=imm_count,
                    next_immunization=outstanding[0][1] if outstanding else None,
                    status=child.status,
                    created_at=child.created_at,
                )
            )

        return items

    # ── Immunization ──────────────────────────────────────────────────────

    async def record_immunization(
        self,
        data: ImmunizationCreate,
        facility_id: uuid.UUID,
        administered_by: uuid.UUID,
    ) -> Immunization:
        """
        Record an immunization dose for a child.

        @param data: Immunization data
        @param facility_id: Facility UUID
        @param administered_by: Staff UUID
        @returns Created immunization record
        """
        # Get child record
        child_result = await self.db.execute(
            select(ChildRecord).where(
                ChildRecord.id == data.child_record_id,
                ChildRecord.facility_id == facility_id,
                ChildRecord.is_deleted == False,  # noqa: E712
            )
        )
        child = child_result.scalar_one_or_none()
        if not child:
            raise ValueError("Child record not found")

        # Anchor the dose to the KEPI schedule so scheduled_date and
        # is_overdue carry real values instead of the column defaults.
        entry = kepi_schedule_entry(data.vaccine_code)
        scheduled_date: date | None = None
        age_at_dose_weeks = data.age_at_dose_weeks
        if entry:
            scheduled_date = child.date_of_birth + timedelta(weeks=entry[2])
            if age_at_dose_weeks is None:
                age_at_dose_weeks = (data.date_given - child.date_of_birth).days // 7
        is_overdue = bool(
            scheduled_date
            and data.date_given > scheduled_date + timedelta(weeks=KEPI_GRACE_WEEKS)
        )

        immunization = Immunization(
            facility_id=facility_id,
            child_record_id=data.child_record_id,
            patient_id=child.patient_id,
            administered_by=administered_by,
            vaccine_code=entry[0] if entry else data.vaccine_code,
            vaccine_name=data.vaccine_name,
            dose_number=data.dose_number,
            date_given=data.date_given,
            age_at_dose_weeks=age_at_dose_weeks,
            batch_number=data.batch_number,
            site=data.site or (entry[4] if entry else None),
            route=data.route or (entry[3] if entry else None),
            scheduled_date=scheduled_date,
            is_overdue=is_overdue,
            adverse_event=data.adverse_event,
            adverse_event_description=data.adverse_event_description,
            notes=data.notes,
            created_by=administered_by,
            updated_by=administered_by,
        )
        self.db.add(immunization)
        await self.db.flush()
        await self.db.refresh(immunization)

        event = EventBase(
            facility_id=facility_id,
            stream_type="mch",
            stream_id=child.patient_id,
            event_type="ImmunizationRecorded",
            event_data={
                "immunization_id": str(immunization.id),
                "child_id": str(data.child_record_id),
                "vaccine": data.vaccine_code,
                "dose": data.dose_number,
            },
            version=1,
            created_by=administered_by,
        )
        self.db.add(event)

        return immunization

    async def update_immunization(
        self,
        immunization_id: uuid.UUID,
        data: ImmunizationUpdate,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> Immunization:
        """
        Correct a recorded immunization dose.

        Only the supplied fields change. The KEPI anchors (canonical vaccine
        code, scheduled date, age at dose, overdue flag) are recomputed so the
        dose keeps agreeing with the schedule after the correction.

        @param immunization_id: Immunization UUID
        @param data: Fields to correct
        @param facility_id: Facility UUID from JWT
        @param updated_by: Staff UUID
        @returns Updated immunization record
        @raises ValueError: If the dose is unknown to this facility
        """
        result = await self.db.execute(
            select(Immunization).where(
                Immunization.id == immunization_id,
                Immunization.facility_id == facility_id,
                Immunization.is_deleted == False,  # noqa: E712
            )
        )
        immunization = result.scalar_one_or_none()
        if immunization is None:
            raise ValueError("Immunization not found")

        changes = data.model_dump(exclude_unset=True)

        entry = kepi_schedule_entry(changes.get("vaccine_code", immunization.vaccine_code))
        if entry:
            changes["vaccine_code"] = entry[0]
            if not changes.get("vaccine_name"):
                changes["vaccine_name"] = immunization.vaccine_name
            if changes.get("site") is None and immunization.site is None:
                changes["site"] = entry[4]
            if changes.get("route") is None and immunization.route is None:
                changes["route"] = entry[3]

        date_given = changes.get("date_given") or immunization.date_given

        child_result = await self.db.execute(
            select(ChildRecord).where(
                ChildRecord.id == immunization.child_record_id,
                ChildRecord.facility_id == facility_id,
            )
        )
        child = child_result.scalar_one_or_none()
        scheduled_date: date | None = None
        if child:
            if entry:
                scheduled_date = child.date_of_birth + timedelta(weeks=entry[2])
            changes["age_at_dose_weeks"] = (date_given - child.date_of_birth).days // 7
        changes["scheduled_date"] = scheduled_date
        changes["is_overdue"] = bool(
            scheduled_date
            and date_given > scheduled_date + timedelta(weeks=KEPI_GRACE_WEEKS)
        )

        for field, value in changes.items():
            setattr(immunization, field, value)
        immunization.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(immunization)

        self.db.add(
            EventBase(
                facility_id=facility_id,
                stream_type="mch",
                stream_id=immunization.patient_id,
                event_type="ImmunizationUpdated",
                event_data={
                    "immunization_id": str(immunization.id),
                    "changed": sorted(changes.keys()),
                },
                version=1,
                created_by=updated_by,
            )
        )

        return immunization

    async def delete_immunization(
        self,
        immunization_id: uuid.UUID,
        facility_id: uuid.UUID,
        deleted_by: uuid.UUID,
    ) -> None:
        """
        Soft-delete a dose recorded in error.

        @param immunization_id: Immunization UUID
        @param facility_id: Facility UUID from JWT
        @param deleted_by: Staff UUID
        @raises ValueError: If the dose is unknown to this facility
        """
        result = await self.db.execute(
            select(Immunization).where(
                Immunization.id == immunization_id,
                Immunization.facility_id == facility_id,
                Immunization.is_deleted == False,  # noqa: E712
            )
        )
        immunization = result.scalar_one_or_none()
        if immunization is None:
            raise ValueError("Immunization not found")

        immunization.is_deleted = True
        immunization.deleted_at = datetime.now(UTC)
        immunization.updated_by = deleted_by
        await self.db.flush()

        self.db.add(
            EventBase(
                facility_id=facility_id,
                stream_type="mch",
                stream_id=immunization.patient_id,
                event_type="ImmunizationDeleted",
                event_data={
                    "immunization_id": str(immunization.id),
                    "vaccine": immunization.vaccine_code,
                    "dose": immunization.dose_number,
                },
                version=1,
                created_by=deleted_by,
            )
        )

    async def get_immunizations(
        self,
        child_record_id: uuid.UUID,
        facility_id: uuid.UUID,
    ) -> list[Immunization]:
        """
        Get all immunizations for a child.

        @param child_record_id: Child record UUID
        @param facility_id: Facility UUID
        @returns List of immunization records
        """
        result = await self.db.execute(
            select(Immunization)
            .where(
                Immunization.child_record_id == child_record_id,
                Immunization.facility_id == facility_id,
                Immunization.is_deleted == False,  # noqa: E712
            )
            .order_by(Immunization.date_given.asc())
        )
        return list(result.scalars().all())

    def get_immunization_schedule(self) -> list[ImmunizationScheduleItem]:
        """
        Get the KEPI routine immunization schedule.

        @returns Scheduled doses in due order
        """
        return [
            ImmunizationScheduleItem(
                vaccine_code=code,
                vaccine_name=name,
                due_age_weeks=due_week,
                route=route,
                site=site,
            )
            for code, name, due_week, route, site in KEPI_SCHEDULE
        ]

    # ── Summary ───────────────────────────────────────────────────────────

    async def get_summary(
        self, facility_id: uuid.UUID
    ) -> MCHSummary:
        """
        Get MCH department dashboard summary.

        @param facility_id: Facility UUID
        @returns Summary stats
        """
        today = date.today()
        month_start = today.replace(day=1)

        # Active ANC profiles
        active_anc = await self.db.execute(
            select(func.count(ANCProfile.id)).where(
                ANCProfile.facility_id == facility_id,
                ANCProfile.is_deleted == False,  # noqa: E712
                ANCProfile.status == "active",
            )
        )

        # High risk
        high_risk = await self.db.execute(
            select(func.count(ANCProfile.id)).where(
                ANCProfile.facility_id == facility_id,
                ANCProfile.is_deleted == False,  # noqa: E712
                ANCProfile.status == "active",
                ANCProfile.risk_level == "high",
            )
        )

        # Deliveries this month
        deliveries = await self.db.execute(
            select(func.count(DeliveryRecord.id)).where(
                DeliveryRecord.facility_id == facility_id,
                DeliveryRecord.is_deleted == False,  # noqa: E712
                func.date(DeliveryRecord.delivery_date) >= month_start,
            )
        )

        # Live births this month
        live_births = await self.db.execute(
            select(func.count(DeliveryRecord.id)).where(
                DeliveryRecord.facility_id == facility_id,
                DeliveryRecord.is_deleted == False,  # noqa: E712
                func.date(DeliveryRecord.delivery_date) >= month_start,
                DeliveryRecord.baby_outcome == "live_birth",
            )
        )

        # Active children
        active_children = await self.db.execute(
            select(func.count(ChildRecord.id)).where(
                ChildRecord.facility_id == facility_id,
                ChildRecord.is_deleted == False,  # noqa: E712
                ChildRecord.status == "active",
            )
        )

        # Overdue immunizations: routine doses past their KEPI due date (plus
        # grace) that have no matching record for an active child.
        child_rows = await self.db.execute(
            select(ChildRecord.id, ChildRecord.date_of_birth).where(
                ChildRecord.facility_id == facility_id,
                ChildRecord.is_deleted == False,  # noqa: E712
                ChildRecord.status == "active",
            )
        )
        active_child_rows = child_rows.all()
        overdue_immunizations = 0
        if active_child_rows:
            given_rows = await self.db.execute(
                select(
                    Immunization.child_record_id,
                    Immunization.vaccine_code,
                ).where(
                    Immunization.facility_id == facility_id,
                    Immunization.is_deleted == False,  # noqa: E712
                    Immunization.child_record_id.in_(
                        [row[0] for row in active_child_rows]
                    ),
                )
            )
            given_by_child: dict[uuid.UUID, set[str]] = {}
            for child_id, code in given_rows.all():
                given_by_child.setdefault(child_id, set()).add(code)
            for child_id, dob in active_child_rows:
                overdue_immunizations += sum(
                    1
                    for dose in kepi_outstanding_doses(
                        dob, given_by_child.get(child_id, set()), today
                    )
                    if dose[3]
                )

        return MCHSummary(
            active_anc_profiles=active_anc.scalar() or 0,
            high_risk_pregnancies=high_risk.scalar() or 0,
            deliveries_this_month=deliveries.scalar() or 0,
            live_births_this_month=live_births.scalar() or 0,
            active_children=active_children.scalar() or 0,
            overdue_immunizations=overdue_immunizations,
        )
