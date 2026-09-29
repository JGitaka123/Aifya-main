"""Bedside tests an OPD clinician performs and results in the room.

HIV, malaria RDT, urinalysis and pregnancy tests are done at the point of care
and are part of the consultation, not a laboratory workflow. They are recorded
against the encounter so the result is on the chart immediately, and an
abnormal result is flagged for the clinician rather than buried in notes.
Each test is also priced onto the visit's bill, so the receipt the patient is
given lists the tests that were actually run instead of one lump sum.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.point_of_care import PointOfCareTest
from app.schemas.point_of_care import PointOfCareTestCreate
from app.services.encounter_service import EncounterService

# Interpretations that mean the result needs a clinician's attention.
ABNORMAL_INTERPRETATIONS = frozenset({"abnormal", "positive", "reactive"})

# A visit that has left the clinician's hands cannot be rewritten.
CLOSED_STATUSES = frozenset({"discharged", "cancelled"})


class PointOfCareService:
    """Service layer for tests recorded and resulted at the bedside."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_test(
        self,
        *,
        encounter_id: uuid.UUID,
        data: PointOfCareTestCreate,
        facility_id: uuid.UUID,
        performed_by: uuid.UUID,
    ) -> PointOfCareTest:
        """
        Record a point-of-care test against an encounter.

        @param encounter_id: Encounter UUID (path)
        @param data: Test and result
        @param facility_id: Facility UUID from JWT
        @param performed_by: Staff UUID of the person who ran the test
        @returns The recorded test
        @raises ValueError: When the encounter is missing or already closed
        """
        encounter = await EncounterService(self.db).get_encounter(
            encounter_id, facility_id
        )
        if encounter is None:
            raise ValueError("Encounter not found")
        if encounter.status in CLOSED_STATUSES:
            raise ValueError(
                "This visit is closed; its tests can no longer be recorded."
            )

        interpretation = data.interpretation
        test = PointOfCareTest(
            facility_id=facility_id,
            encounter_id=encounter.id,
            patient_id=encounter.patient_id,
            performed_by=performed_by,
            test_code=data.test_code.strip(),
            test_name=data.test_name.strip(),
            category=data.category,
            specimen_type=data.specimen_type,
            result_value=data.result_value,
            result_numeric=data.result_numeric,
            result_unit=data.result_unit,
            interpretation=interpretation,
            is_abnormal=interpretation in ABNORMAL_INTERPRETATIONS,
            notes=data.notes,
            created_by=performed_by,
            updated_by=performed_by,
        )
        self.db.add(test)
        await self.db.flush()
        await self.db.refresh(test)

        # The test is part of the visit, so what was run is itemised on the
        # visit's bill and the printed receipt. A zero price posts nothing,
        # so a free screening never reaches the desk.
        charge_cents = await self._bill_test(
            encounter=encounter,
            test=test,
            facility_id=facility_id,
            performed_by=performed_by,
        )

        self.db.add(
            EventBase(
                facility_id=facility_id,
                stream_type="encounter",
                stream_id=encounter.id,
                event_type="PointOfCareTestRecorded",
                event_data={
                    "test_code": test.test_code,
                    "test_name": test.test_name,
                    "category": test.category,
                    "result_value": test.result_value,
                    "interpretation": test.interpretation,
                    "is_abnormal": test.is_abnormal,
                    "charge_cents": charge_cents,
                },
                version=1,
                created_by=performed_by,
            )
        )
        return test

    async def _bill_test(
        self,
        *,
        encounter,
        test: PointOfCareTest,
        facility_id: uuid.UUID,
        performed_by: uuid.UUID,
    ) -> int:
        """
        Add the test as a priced line on the visit's open invoice.

        Every point-of-care test in an encounter shares one charge keyed on the
        encounter, so the desk collects for all of them at once and the receipt
        lists each test that was run.

        @param encounter: Encounter the test belongs to
        @param test: The recorded test
        @param facility_id: Facility scope
        @param performed_by: Staff UUID who ran the test
        @returns Price in KES cents; 0 when the test is not charged
        """
        from app.services.point_of_care_fee import load_point_of_care_price_cents
        from app.services.service_billing import POINT_OF_CARE, post_service_charge

        price = await load_point_of_care_price_cents(
            self.db, facility_id, test_code=test.test_code
        )
        if price <= 0:
            return 0

        await post_service_charge(
            self.db,
            facility_id=facility_id,
            encounter_id=encounter.id,
            patient_id=encounter.patient_id,
            item_type="lab",
            description=f"OPD: {test.test_name}",
            unit_price_cents=price,
            reference_type=POINT_OF_CARE,
            reference_id=encounter.id,
            created_by=performed_by,
        )
        return price

    async def get_encounter_tests(
        self, encounter_id: uuid.UUID, facility_id: uuid.UUID
    ) -> list[PointOfCareTest]:
        """
        Every point-of-care test recorded for an encounter, newest first.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @returns List of recorded tests
        """
        result = await self.db.execute(
            select(PointOfCareTest)
            .where(
                PointOfCareTest.encounter_id == encounter_id,
                PointOfCareTest.facility_id == facility_id,
                PointOfCareTest.is_deleted == False,  # noqa: E712
            )
            .order_by(PointOfCareTest.performed_at.desc())
        )
        return list(result.scalars().all())
