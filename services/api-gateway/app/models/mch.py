import uuid
from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class ANCProfile(AuditMixin, Base):
    """
    Antenatal Care profile — one per pregnancy episode.
    Tracks the mother through ANC visits, delivery, and postnatal period.
    Follows Kenya MOH ANC register (MOH 405) format.
    """

    __tablename__ = "anc_profiles"
    __table_args__ = (
        Index("ix_anc_profiles_patient", "facility_id", "patient_id"),
        Index("ix_anc_profiles_status", "facility_id", "status"),
        Index("ix_anc_profiles_edd", "facility_id", "expected_delivery_date"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id")
    )

    # Registration
    anc_number: Mapped[str] = mapped_column(String(50), nullable=False)
    gravida: Mapped[int] = mapped_column(Integer, nullable=False)  # Total pregnancies
    parity: Mapped[int] = mapped_column(Integer, nullable=False)  # Previous deliveries
    living_children: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Dates
    lmp_date: Mapped[date | None] = mapped_column(Date)  # Last menstrual period
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)  # EDD
    first_visit_date: Mapped[date | None] = mapped_column(Date)
    gestation_at_first_visit: Mapped[int | None] = mapped_column(Integer)  # Weeks

    # Risk factors
    risk_level: Mapped[str] = mapped_column(
        String(20), default="low", nullable=False
    )  # low, moderate, high
    risk_factors: Mapped[dict | None] = mapped_column(JSONB)
    # e.g. ["previous_cs", "hypertension", "diabetes", "hiv_positive", "age_over_35", "rh_negative"]

    # Medical history
    blood_group: Mapped[str | None] = mapped_column(String(10))  # A+, A-, B+, B-, AB+, AB-, O+, O-
    hiv_status: Mapped[str | None] = mapped_column(
        String(20)
    )  # positive, negative, unknown, declined
    hiv_test_date: Mapped[date | None] = mapped_column(Date)
    on_art: Mapped[bool] = mapped_column(default=False, nullable=False)
    vdrl_status: Mapped[str | None] = mapped_column(String(20))  # reactive, non_reactive
    hepatitis_b: Mapped[str | None] = mapped_column(String(20))  # positive, negative
    rhesus: Mapped[str | None] = mapped_column(String(10))  # positive, negative

    # PMTCT (Prevention of Mother-to-Child Transmission)
    pmtct_enrolled: Mapped[bool] = mapped_column(default=False, nullable=False)
    partner_hiv_status: Mapped[str | None] = mapped_column(String(20))

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active, delivered, postnatal, closed, transferred

    # Outcome
    pregnancy_outcome: Mapped[str | None] = mapped_column(
        String(20)
    )  # live_birth, stillbirth, miscarriage, abortion, ectopic

    # Notes
    notes: Mapped[str | None] = mapped_column(Text)


class ANCVisit(AuditMixin, Base):
    """
    Individual ANC visit record.
    Follows Kenya MOH ANC card structure with mandatory assessments.
    """

    __tablename__ = "anc_visits"
    __table_args__ = (
        Index("ix_anc_visits_profile", "facility_id", "anc_profile_id"),
    )

    anc_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anc_profiles.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id")
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )

    # Visit details
    visit_number: Mapped[int] = mapped_column(Integer, nullable=False)
    visit_date: Mapped[date] = mapped_column(Date, nullable=False)
    gestation_weeks: Mapped[int | None] = mapped_column(Integer)

    # Vitals
    weight_kg: Mapped[float | None] = mapped_column(Float)
    bp_systolic: Mapped[int | None] = mapped_column(Integer)
    bp_diastolic: Mapped[int | None] = mapped_column(Integer)
    pulse_rate: Mapped[int | None] = mapped_column(Integer)
    temperature: Mapped[float | None] = mapped_column(Float)

    # Urine tests
    urine_protein: Mapped[str | None] = mapped_column(String(20))  # nil, trace, 1+, 2+, 3+, 4+
    urine_glucose: Mapped[str | None] = mapped_column(String(20))

    # Obstetric exam
    fundal_height_cm: Mapped[float | None] = mapped_column(Float)
    fetal_heart_rate: Mapped[int | None] = mapped_column(Integer)
    fetal_presentation: Mapped[str | None] = mapped_column(
        String(30)
    )  # cephalic, breech, transverse, oblique
    fetal_movement: Mapped[str | None] = mapped_column(String(20))  # present, absent, reduced
    oedema: Mapped[str | None] = mapped_column(String(20))  # none, mild, moderate, severe

    # Haemoglobin
    hb_level: Mapped[float | None] = mapped_column(Float)  # g/dL

    # Interventions
    iron_folate_given: Mapped[bool] = mapped_column(default=False, nullable=False)
    tetanus_dose: Mapped[str | None] = mapped_column(String(20))  # TT1, TT2, TT3, TT4, TT5
    ipt_malaria_dose: Mapped[str | None] = mapped_column(String(20))  # IPT1, IPT2, IPT3
    deworming_given: Mapped[bool] = mapped_column(default=False, nullable=False)
    llins_given: Mapped[bool] = mapped_column(default=False, nullable=False)  # Long-lasting insecticidal nets

    # Counselling
    birth_plan_discussed: Mapped[bool] = mapped_column(default=False, nullable=False)
    danger_signs_counselled: Mapped[bool] = mapped_column(default=False, nullable=False)
    breastfeeding_counselled: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Next appointment
    next_visit_date: Mapped[date | None] = mapped_column(Date)

    # Clinical notes
    clinical_notes: Mapped[str | None] = mapped_column(Text)
    complications: Mapped[str | None] = mapped_column(Text)

    # Referral
    referred: Mapped[bool] = mapped_column(default=False, nullable=False)
    referral_reason: Mapped[str | None] = mapped_column(Text)


class DeliveryRecord(AuditMixin, Base):
    """
    Delivery / birth record — links ANC profile to birth outcome.
    Follows Kenya MOH maternity register (MOH 333).
    """

    __tablename__ = "delivery_records"
    __table_args__ = (
        Index("ix_delivery_records_profile", "facility_id", "anc_profile_id"),
        Index("ix_delivery_records_patient", "facility_id", "patient_id"),
    )

    anc_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("anc_profiles.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    encounter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id")
    )
    delivered_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )

    # Delivery details
    delivery_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    gestation_weeks: Mapped[int | None] = mapped_column(Integer)
    mode_of_delivery: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # svd, assisted_vaginal, elective_cs, emergency_cs, breech
    duration_of_labour_hours: Mapped[float | None] = mapped_column(Float)
    place_of_delivery: Mapped[str] = mapped_column(
        String(30), default="facility", nullable=False
    )  # facility, home, bba (born before arrival), other

    # Mother outcome
    maternal_outcome: Mapped[str] = mapped_column(
        String(20), default="alive", nullable=False
    )  # alive, deceased
    maternal_complications: Mapped[str | None] = mapped_column(Text)
    # e.g. PPH, eclampsia, obstructed_labour, sepsis, ruptured_uterus
    blood_loss_ml: Mapped[int | None] = mapped_column(Integer)
    episiotomy: Mapped[bool] = mapped_column(default=False, nullable=False)
    tears: Mapped[str | None] = mapped_column(String(20))  # none, first_degree, second_degree, third_degree, fourth_degree

    # Baby outcome
    baby_outcome: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # live_birth, fresh_stillbirth, macerated_stillbirth
    baby_sex: Mapped[str | None] = mapped_column(String(10))  # male, female, ambiguous
    birth_weight_grams: Mapped[int | None] = mapped_column(Integer)
    apgar_1min: Mapped[int | None] = mapped_column(Integer)
    apgar_5min: Mapped[int | None] = mapped_column(Integer)
    apgar_10min: Mapped[int | None] = mapped_column(Integer)
    resuscitation_needed: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Immediate newborn care
    skin_to_skin: Mapped[bool] = mapped_column(default=False, nullable=False)
    breastfed_within_1hr: Mapped[bool] = mapped_column(default=False, nullable=False)
    vitamin_k_given: Mapped[bool] = mapped_column(default=False, nullable=False)
    eye_prophylaxis: Mapped[bool] = mapped_column(default=False, nullable=False)
    bcg_given: Mapped[bool] = mapped_column(default=False, nullable=False)
    opv_0_given: Mapped[bool] = mapped_column(default=False, nullable=False)

    # PMTCT at delivery
    arv_prophylaxis_baby: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text)


class ChildRecord(AuditMixin, Base):
    """
    Child health record — tracks growth monitoring, immunizations, and milestones.
    Follows Kenya MOH child health card.
    """

    __tablename__ = "child_records"
    __table_args__ = (
        Index("ix_child_records_patient", "facility_id", "patient_id"),
        Index("ix_child_records_mother", "facility_id", "mother_patient_id"),
    )

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    mother_patient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id")
    )
    delivery_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("delivery_records.id")
    )

    # Registration
    child_number: Mapped[str] = mapped_column(String(50), nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    birth_weight_grams: Mapped[int | None] = mapped_column(Integer)
    sex: Mapped[str] = mapped_column(String(10), nullable=False)  # male, female

    # Birth details
    place_of_birth: Mapped[str | None] = mapped_column(String(30))
    birth_notification_number: Mapped[str | None] = mapped_column(String(50))

    # HIV exposure
    hiv_exposed: Mapped[bool] = mapped_column(default=False, nullable=False)
    pcr_test_date: Mapped[date | None] = mapped_column(Date)
    pcr_result: Mapped[str | None] = mapped_column(String(20))  # positive, negative, pending

    # Feeding
    feeding_method: Mapped[str | None] = mapped_column(
        String(30)
    )  # exclusive_breastfeeding, mixed, replacement

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active, transferred, deceased, closed

    notes: Mapped[str | None] = mapped_column(Text)


class Immunization(AuditMixin, Base):
    """
    Immunization record — individual vaccine dose administration.
    Follows Kenya Expanded Programme on Immunization (KEPI) schedule.
    """

    __tablename__ = "immunizations"
    __table_args__ = (
        Index("ix_immunizations_child", "facility_id", "child_record_id"),
        Index("ix_immunizations_vaccine", "facility_id", "vaccine_code"),
    )

    child_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("child_records.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    administered_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )

    # Vaccine
    vaccine_code: Mapped[str] = mapped_column(String(30), nullable=False)
    # BCG, OPV_0, OPV_1, OPV_2, OPV_3, IPV, PENTA_1, PENTA_2, PENTA_3,
    # PCV_1, PCV_2, PCV_3, ROTA_1, ROTA_2, MEASLES_1, MEASLES_2,
    # YELLOW_FEVER, VITAMIN_A, MR_1, MR_2
    vaccine_name: Mapped[str] = mapped_column(String(100), nullable=False)
    dose_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Administration
    date_given: Mapped[date] = mapped_column(Date, nullable=False)
    age_at_dose_weeks: Mapped[int | None] = mapped_column(Integer)
    batch_number: Mapped[str | None] = mapped_column(String(50))
    site: Mapped[str | None] = mapped_column(String(50))  # left_thigh, right_thigh, left_arm, right_arm, oral
    route: Mapped[str | None] = mapped_column(String(20))  # im, sc, oral, id

    # Schedule tracking
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    is_overdue: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Adverse event
    adverse_event: Mapped[bool] = mapped_column(default=False, nullable=False)
    adverse_event_description: Mapped[str | None] = mapped_column(Text)

    notes: Mapped[str | None] = mapped_column(Text)
