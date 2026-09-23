import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.vital import VitalSign
from app.schemas.vital import VitalSignCreate

# Critical value thresholds
CRITICAL_THRESHOLDS = {
    "systolic_bp_high": 180,
    "systolic_bp_low": 80,
    "diastolic_bp_high": 120,
    "diastolic_bp_low": 40,
    "heart_rate_high": 150,
    "heart_rate_low": 40,
    "temperature_high": 40.0,
    "temperature_low": 34.0,
    "oxygen_saturation_low": 90.0,
    "respiratory_rate_high": 30,
    "respiratory_rate_low": 8,
    "blood_glucose_high": 25.0,
    "blood_glucose_low": 3.0,
}


class VitalsService:
    """Service for recording and checking vital signs."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_vitals(
        self,
        data: VitalSignCreate,
        facility_id: uuid.UUID,
        recorded_by: uuid.UUID,
    ) -> VitalSign:
        """
        Record vital signs and check for critical values.
        Critical values MUST trigger immediate alert (CLAUDE.md: Clinical Safety).

        @param data: Vital signs data
        @param facility_id: Facility UUID
        @param recorded_by: Nurse/staff UUID
        @returns Recorded vital signs with critical alerts
        """
        # Calculate BMI
        bmi: float | None = None
        if data.weight_kg and data.height_cm and data.height_cm > 0:
            height_m = data.height_cm / 100
            bmi = round(data.weight_kg / (height_m * height_m), 1)

        vital = VitalSign(
            facility_id=facility_id,
            encounter_id=data.encounter_id,
            patient_id=data.patient_id,
            recorded_by=recorded_by,
            bmi=bmi,
            created_by=recorded_by,
            updated_by=recorded_by,
            **data.model_dump(exclude={"encounter_id", "patient_id"}),
        )

        # Check critical values
        alerts = self._check_critical_values(data)
        if alerts:
            vital.is_critical = True
            vital.critical_alerts = "; ".join(alerts)

        self.db.add(vital)
        await self.db.flush()
        await self.db.refresh(vital)

        # Emit event
        event_data = data.model_dump(mode="json")
        event_data["is_critical"] = vital.is_critical
        event_data["bmi"] = bmi

        event = EventBase(
            facility_id=facility_id,
            stream_type="vital_signs",
            stream_id=data.patient_id,
            event_type="VitalsRecorded",
            event_data=event_data,
            version=1,
            created_by=recorded_by,
        )
        self.db.add(event)

        return vital

    async def get_encounter_vitals(
        self, encounter_id: uuid.UUID, facility_id: uuid.UUID
    ) -> list[VitalSign]:
        """
        Get all vital signs for an encounter.

        @param encounter_id: Encounter UUID
        @param facility_id: Facility UUID
        @returns List of vital signs
        """
        result = await self.db.execute(
            select(VitalSign)
            .where(
                VitalSign.encounter_id == encounter_id,
                VitalSign.facility_id == facility_id,
                VitalSign.is_deleted == False,  # noqa: E712
            )
            .order_by(VitalSign.recorded_at.desc())
        )
        return list(result.scalars().all())

    @staticmethod
    def _check_critical_values(data: VitalSignCreate) -> list[str]:
        """
        Check vital signs against critical thresholds.

        @param data: Vital signs to check
        @returns List of alert messages for critical values
        """
        alerts: list[str] = []

        if data.systolic_bp is not None:
            if data.systolic_bp >= CRITICAL_THRESHOLDS["systolic_bp_high"]:
                alerts.append(f"Critical high systolic BP: {data.systolic_bp} mmHg")
            elif data.systolic_bp <= CRITICAL_THRESHOLDS["systolic_bp_low"]:
                alerts.append(f"Critical low systolic BP: {data.systolic_bp} mmHg")

        if data.diastolic_bp is not None:
            if data.diastolic_bp >= CRITICAL_THRESHOLDS["diastolic_bp_high"]:
                alerts.append(f"Critical high diastolic BP: {data.diastolic_bp} mmHg")
            elif data.diastolic_bp <= CRITICAL_THRESHOLDS["diastolic_bp_low"]:
                alerts.append(f"Critical low diastolic BP: {data.diastolic_bp} mmHg")

        if data.heart_rate is not None:
            if data.heart_rate >= CRITICAL_THRESHOLDS["heart_rate_high"]:
                alerts.append(f"Critical high heart rate: {data.heart_rate} bpm")
            elif data.heart_rate <= CRITICAL_THRESHOLDS["heart_rate_low"]:
                alerts.append(f"Critical low heart rate: {data.heart_rate} bpm")

        if data.temperature is not None:
            if data.temperature >= CRITICAL_THRESHOLDS["temperature_high"]:
                alerts.append(f"Critical high temperature: {data.temperature}°C")
            elif data.temperature <= CRITICAL_THRESHOLDS["temperature_low"]:
                alerts.append(f"Critical low temperature: {data.temperature}°C")

        if (
            data.oxygen_saturation is not None
            and data.oxygen_saturation <= CRITICAL_THRESHOLDS["oxygen_saturation_low"]
        ):
            alerts.append(f"Critical low SpO2: {data.oxygen_saturation}%")

        if data.respiratory_rate is not None:
            if data.respiratory_rate >= CRITICAL_THRESHOLDS["respiratory_rate_high"]:
                alerts.append(f"Critical high RR: {data.respiratory_rate}/min")
            elif data.respiratory_rate <= CRITICAL_THRESHOLDS["respiratory_rate_low"]:
                alerts.append(f"Critical low RR: {data.respiratory_rate}/min")

        if data.blood_glucose is not None:
            if data.blood_glucose >= CRITICAL_THRESHOLDS["blood_glucose_high"]:
                alerts.append(f"Critical high glucose: {data.blood_glucose} mmol/L")
            elif data.blood_glucose <= CRITICAL_THRESHOLDS["blood_glucose_low"]:
                alerts.append(f"Critical low glucose: {data.blood_glucose} mmol/L")

        return alerts
