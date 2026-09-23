import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.facility import Facility
from app.models.patient import Patient
from app.models.referral import Referral
from app.schemas.referral import (
    ReferralCreate,
    ReferralListItem,
    ReferralSummary,
    ReferralUpdateStatus,
)


def _incoming_for(facility_id: uuid.UUID):
    """
    Build the predicate for referrals that are incoming for a facility.

    A referral counts as incoming when the facility owns it and flagged it
    incoming, or when another facility raised it addressed to this one.

    @param facility_id: Facility UUID
    @returns SQLAlchemy boolean expression
    """
    return or_(
        and_(
            Referral.facility_id == facility_id,
            Referral.direction == "incoming",
        ),
        and_(
            Referral.facility_id != facility_id,
            Referral.receiving_facility_id == facility_id,
        ),
    )


def _outgoing_for(facility_id: uuid.UUID):
    """
    Build the predicate for referrals that are outgoing from a facility.

    A referral counts as outgoing when the facility owns it and flagged it
    outgoing, or when this facility sent it to another facility that owns it.

    @param facility_id: Facility UUID
    @returns SQLAlchemy boolean expression
    """
    return or_(
        and_(
            Referral.facility_id == facility_id,
            Referral.direction == "outgoing",
        ),
        and_(
            Referral.facility_id != facility_id,
            Referral.receiving_facility_id == facility_id,
            Referral.direction == "incoming",
        ),
    )


class ReferralService:
    """Service for patient referral management."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_referral(
        self,
        data: ReferralCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
        initial_status: str = "draft",
    ) -> Referral:
        """
        Create a new referral.

        @param data: Referral data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @param initial_status: Workflow status for the new record. Callers
            other than the referrals API use this so an arriving ED referral
            is "received" and an onward transfer is "sent" straight away.
        @returns Created referral
        """
        referring_facility_name = data.referring_facility_name
        if data.direction == "outgoing" and not referring_facility_name:
            facility_result = await self.db.execute(
                select(Facility.name).where(Facility.id == facility_id)
            )
            referring_facility_name = facility_result.scalar_one_or_none()

        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")
        count_result = await self.db.execute(
            select(func.count(Referral.id)).where(
                Referral.facility_id == facility_id,
                Referral.referral_number.like(f"REF-{date_part}-%"),
                Referral.is_deleted == False,  # noqa: E712
            )
        )
        seq = (count_result.scalar() or 0) + 1
        referral_number = f"REF-{date_part}-{seq:04d}"

        referral = Referral(
            facility_id=facility_id,
            referral_number=referral_number,
            patient_id=data.patient_id,
            encounter_id=data.encounter_id,
            emergency_visit_id=data.emergency_visit_id,
            referral_type=data.referral_type,
            direction=data.direction,
            referring_doctor_id=data.referring_doctor_id,
            referring_department_id=data.referring_department_id,
            referring_facility_name=referring_facility_name,
            receiving_doctor_id=data.receiving_doctor_id,
            receiving_department_id=data.receiving_department_id,
            receiving_facility_id=data.receiving_facility_id,
            receiving_facility_name=data.receiving_facility_name,
            receiving_facility_mfl=data.receiving_facility_mfl,
            reason=data.reason,
            clinical_notes=data.clinical_notes,
            diagnosis=data.diagnosis,
            urgency=data.urgency,
            referral_date=now,
            status=initial_status,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(referral)
        await self.db.flush()
        await self.db.refresh(referral)

        event = EventBase(
            facility_id=facility_id,
            stream_type="referral",
            stream_id=data.patient_id,
            event_type="ReferralCreated",
            event_data={"referral_id": str(referral.id), "referral_number": referral_number, "direction": data.direction},
            version=1,
            created_by=created_by,
        )
        self.db.add(event)
        return referral

    async def get_referrals(
        self,
        facility_id: uuid.UUID,
        direction: str | None = None,
        status: str | None = None,
    ) -> list[ReferralListItem]:
        """
        Get referrals with patient names.

        @param facility_id: Facility UUID
        @param direction: Optional direction filter
        @param status: Optional status filter
        @returns List of referrals
        """
        query = (
            select(
                Referral,
                Patient.first_name.label("p_first"),
                Patient.last_name.label("p_last"),
            )
            .join(Patient, Referral.patient_id == Patient.id)
            .where(
                Referral.is_deleted == False,  # noqa: E712
                or_(
                    Referral.facility_id == facility_id,
                    Referral.receiving_facility_id == facility_id,
                ),
            )
        )
        if direction == "incoming":
            query = query.where(_incoming_for(facility_id))
        elif direction == "outgoing":
            query = query.where(_outgoing_for(facility_id))
        if status:
            query = query.where(Referral.status == status)
        query = query.order_by(Referral.referral_date.desc())

        result = await self.db.execute(query)
        rows = result.all()

        return [
            ReferralListItem(
                id=r.id,
                referral_number=r.referral_number,
                patient_id=r.patient_id,
                patient_name=f"{pf or ''} {pl or ''}".strip() or None,
                referral_type=r.referral_type,
                direction=(
                    r.direction
                    if r.facility_id == facility_id
                    else ("incoming" if r.direction == "outgoing" else "outgoing")
                ),
                reason=r.reason,
                urgency=r.urgency,
                referring_facility_name=r.referring_facility_name,
                receiving_facility_name=r.receiving_facility_name,
                referral_date=r.referral_date,
                status=r.status,
            )
            for r, pf, pl in rows
        ]

    async def get_referral(
        self, referral_id: uuid.UUID, facility_id: uuid.UUID
    ) -> Referral | None:
        """
        Get a single referral owned by, or addressed to, a facility.

        @param referral_id: Referral UUID
        @param facility_id: Facility UUID
        @returns Referral or None
        """
        result = await self.db.execute(
            select(Referral).where(
                Referral.id == referral_id,
                Referral.is_deleted == False,  # noqa: E712
                or_(
                    Referral.facility_id == facility_id,
                    Referral.receiving_facility_id == facility_id,
                ),
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self,
        referral_id: uuid.UUID,
        data: ReferralUpdateStatus,
        facility_id: uuid.UUID,
        updated_by: uuid.UUID,
    ) -> Referral | None:
        """
        Update referral status.

        @param referral_id: Referral UUID
        @param data: Status update data
        @param facility_id: Facility UUID
        @param updated_by: Staff UUID
        @returns Updated referral or None
        """
        referral = await self.get_referral(referral_id, facility_id)
        if not referral:
            return None

        referral.status = data.status
        if data.response_notes:
            referral.response_notes = data.response_notes
        if data.feedback:
            referral.feedback = data.feedback
        if data.status in ("accepted", "declined", "completed"):
            referral.response_date = datetime.now(UTC)
        referral.updated_by = updated_by
        await self.db.flush()
        await self.db.refresh(referral)
        return referral

    async def get_summary(self, facility_id: uuid.UUID) -> ReferralSummary:
        """
        Get referral summary stats.

        @param facility_id: Facility UUID
        @returns Summary stats
        """
        base = [
            Referral.is_deleted == False,  # noqa: E712
            or_(
                Referral.facility_id == facility_id,
                Referral.receiving_facility_id == facility_id,
            ),
        ]

        total = await self.db.execute(select(func.count(Referral.id)).where(*base))
        outgoing = await self.db.execute(
            select(func.count(Referral.id)).where(*base, _outgoing_for(facility_id))
        )
        incoming = await self.db.execute(
            select(func.count(Referral.id)).where(*base, _incoming_for(facility_id))
        )
        pending = await self.db.execute(
            select(func.count(Referral.id)).where(*base, Referral.status.in_(["draft", "sent", "received"]))
        )
        accepted = await self.db.execute(
            select(func.count(Referral.id)).where(*base, Referral.status == "accepted")
        )
        completed = await self.db.execute(
            select(func.count(Referral.id)).where(*base, Referral.status == "completed")
        )

        return ReferralSummary(
            total_referrals=total.scalar() or 0,
            outgoing=outgoing.scalar() or 0,
            incoming=incoming.scalar() or 0,
            pending=pending.scalar() or 0,
            accepted=accepted.scalar() or 0,
            completed=completed.scalar() or 0,
        )

    async def search_facilities(
        self,
        query: str,
        limit: int = 10,
    ) -> list[Facility]:
        """
        Find candidate receiving facilities in the facility register.

        Lets a referring clinician check that the receiving hospital exists in
        the register, and pick up its MFL code, before the referral is sent -
        the same way pharmacy stock is confirmed before a medicine is promised.

        @param query: Free-text facility name, MFL code or facility code
        @param limit: Maximum number of matches to return
        @returns Active, approved facilities, shortest name first
        """
        term = f"%{query.strip()}%"
        stmt = (
            select(Facility)
            .where(
                Facility.is_active == True,  # noqa: E712
                Facility.onboarding_status == "approved",
                or_(
                    Facility.name.ilike(term),
                    Facility.mfl_code.ilike(term),
                    Facility.code.ilike(term),
                ),
            )
            .order_by(func.length(Facility.name).asc(), Facility.name.asc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
