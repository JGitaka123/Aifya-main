import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import EventBase
from app.models.encounter import Encounter
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


def _gcs_total(vital: VitalSign) -> int | None:
    """
    Total the Glasgow Coma Scale when all three components were taken.

    @param vital: Vital signs row
    @returns Eye + verbal + motor, or None when the scale was not completed
    """
    if vital.gcs_eye is None or vital.gcs_verbal is None or vital.gcs_motor is None:
        return None
    return vital.gcs_eye + vital.gcs_verbal + vital.gcs_motor


def build_vitals_summary(vital: VitalSign) -> str:
    """
    Build the one-line digest of a vitals recording.

    This string is read three times over: by a clinician skimming the patient's
    history, by the nurse checking the slip they just handed over, and by the
    patient holding it. So it lists only the values that were actually taken,
    in the order a clinician reads them, and never invents a placeholder for a
    measurement nobody made.

    @param vital: Persisted vital signs row
    @returns Human-readable summary
    """
    parts: list[str] = []

    if vital.systolic_bp is not None or vital.diastolic_bp is not None:
        systolic = vital.systolic_bp if vital.systolic_bp is not None else "\u2014"
        diastolic = vital.diastolic_bp if vital.diastolic_bp is not None else "\u2014"
        parts.append(f"BP {systolic}/{diastolic} mmHg")
    if vital.heart_rate is not None:
        parts.append(f"HR {vital.heart_rate} bpm")
    if vital.temperature is not None:
        parts.append(f"Temp {vital.temperature}\u00b0C")
    if vital.oxygen_saturation is not None:
        parts.append(f"SpO2 {vital.oxygen_saturation}%")
    if vital.respiratory_rate is not None:
        parts.append(f"RR {vital.respiratory_rate}/min")
    if vital.blood_glucose is not None:
        parts.append(f"Glucose {vital.blood_glucose} mmol/L")
    if vital.pain_score is not None:
        parts.append(f"Pain {vital.pain_score}/10")
    if vital.weight_kg is not None:
        parts.append(f"Weight {vital.weight_kg} kg")
    if vital.height_cm is not None:
        parts.append(f"Height {vital.height_cm} cm")
    if vital.bmi is not None:
        parts.append(f"BMI {vital.bmi}")
    if vital.muac_cm is not None:
        parts.append(f"MUAC {vital.muac_cm} cm")
    if vital.head_circumference_cm is not None:
        parts.append(f"HC {vital.head_circumference_cm} cm")

    gcs = _gcs_total(vital)
    if gcs is not None:
        parts.append(f"GCS {gcs}/15")

    if not parts:
        return "Vitals recorded"
    return " \u00b7 ".join(parts)


def vitals_report_payload(vital: VitalSign) -> dict:
    """
    Shape a vitals row into the field map the report PDF renders.

    Keeping the mapping here means the printed slip, the patient's history and
    the API all describe the same recording with the same words.

    @param vital: Persisted vital signs row
    @returns Report fields
    """
    return {
        "id": str(vital.id),
        "report_number": vital.report_number or str(vital.id),
        "summary": vital.summary or build_vitals_summary(vital),
        "recorded_at": (
            vital.recorded_at.strftime("%Y-%m-%d %H:%M") if vital.recorded_at else ""
        ),
        "systolic_bp": vital.systolic_bp,
        "diastolic_bp": vital.diastolic_bp,
        "heart_rate": vital.heart_rate,
        "temperature": vital.temperature,
        "temperature_site": vital.temperature_site,
        "respiratory_rate": vital.respiratory_rate,
        "oxygen_saturation": vital.oxygen_saturation,
        "on_supplemental_o2": vital.on_supplemental_o2,
        "o2_flow_rate": vital.o2_flow_rate,
        "weight_kg": vital.weight_kg,
        "height_cm": vital.height_cm,
        "bmi": vital.bmi,
        "head_circumference_cm": vital.head_circumference_cm,
        "muac_cm": vital.muac_cm,
        "pain_score": vital.pain_score,
        "blood_glucose": vital.blood_glucose,
        "glucose_timing": vital.glucose_timing,
        "gcs_total": _gcs_total(vital),
        "is_critical": vital.is_critical,
        "critical_alerts": vital.critical_alerts,
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

        Every recording also produces the numbered vitals report the patient is
        issued: it is what the printed slip quotes and what the patient's
        history lists, so it is written in the same transaction as the
        observation itself.

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
            report_number=await self._next_report_number(facility_id),
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

        vital.summary = build_vitals_summary(vital)
        await self.db.flush()

        # Stamp the visit itself. The nurse is the first clinician most
        # patients see, and the OPD board has to tell a triaged patient from
        # an untriaged one without reading every vital_signs row. Only the
        # first recording sets it, so a re-check does not move the time the
        # patient entered the queue.
        await self.db.execute(
            update(Encounter)
            .where(
                Encounter.id == data.encounter_id,
                Encounter.facility_id == facility_id,
                Encounter.triaged_at.is_(None),
            )
            .values(
                triaged_at=func.now(),
                nurse_id=recorded_by,
                updated_by=recorded_by,
            )
        )

        # Emit event. The summary rides along so the patient's timeline can show
        # the report without re-reading the observation.
        event_data = data.model_dump(mode="json")
        event_data["is_critical"] = vital.is_critical
        event_data["bmi"] = bmi
        event_data["report_number"] = vital.report_number
        event_data["summary"] = vital.summary

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

    async def get_vital(
        self, vital_id: uuid.UUID, facility_id: uuid.UUID
    ) -> VitalSign | None:
        """
        Fetch one vitals recording.

        @param vital_id: Vitals UUID
        @param facility_id: Facility UUID
        @returns The recording, or None when it is not in this facility
        """
        result = await self.db.execute(
            select(VitalSign).where(
                VitalSign.id == vital_id,
                VitalSign.facility_id == facility_id,
                VitalSign.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def _next_report_number(self, facility_id: uuid.UUID) -> str:
        """
        Generate the next vitals report number for today.

        @param facility_id: Facility UUID
        @returns Report number like VR-20260927-0001
        """
        today = datetime.now(UTC).strftime("%Y%m%d")
        prefix = f"VR-{today}-"
        result = await self.db.execute(
            select(func.count())
            .select_from(VitalSign)
            .where(
                VitalSign.facility_id == facility_id,
                VitalSign.report_number.like(f"{prefix}%"),
            )
        )
        return f"{prefix}{result.scalar_one() + 1:04d}"

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
                alerts.append(f"Critical high temperature: {data.temperature}\u00b0C")
            elif data.temperature <= CRITICAL_THRESHOLDS["temperature_low"]:
                alerts.append(f"Critical low temperature: {data.temperature}\u00b0C")

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
