import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

# ── ANC Profile ──────────────────────────────────────────────────────────────


class ANCProfileCreate(BaseModel):
    """Schema for creating an ANC profile (new pregnancy registration)."""

    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None = None
    gravida: int = Field(..., ge=1)
    parity: int = Field(..., ge=0)
    living_children: int = Field(0, ge=0)
    lmp_date: date | None = None
    expected_delivery_date: date | None = None
    blood_group: str | None = Field(None, pattern=r"^(A|B|AB|O)[+-]$")
    hiv_status: str | None = Field(
        None, pattern=r"^(positive|negative|unknown|declined)$"
    )
    on_art: bool = False
    risk_level: str = Field(
        default="low", pattern=r"^(low|moderate|high)$"
    )
    risk_factors: list[str] | None = None
    notes: str | None = Field(None, max_length=2000)


class ANCProfileResponse(BaseModel):
    """Schema for ANC profile API responses."""

    id: uuid.UUID
    patient_id: uuid.UUID
    encounter_id: uuid.UUID | None
    anc_number: str
    gravida: int
    parity: int
    living_children: int
    lmp_date: date | None
    expected_delivery_date: date | None
    first_visit_date: date | None
    gestation_at_first_visit: int | None
    risk_level: str
    risk_factors: list[str] | None
    blood_group: str | None
    hiv_status: str | None
    on_art: bool
    vdrl_status: str | None
    hepatitis_b: str | None
    rhesus: str | None
    pmtct_enrolled: bool
    partner_hiv_status: str | None
    status: str
    pregnancy_outcome: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ANCProfileListItem(BaseModel):
    """ANC profile in list view with patient info."""

    id: uuid.UUID
    anc_number: str
    patient_id: uuid.UUID
    patient_name: str | None = None
    patient_mrn: str | None = None
    gravida: int
    parity: int
    expected_delivery_date: date | None
    gestation_weeks: int | None = None
    risk_level: str
    status: str
    visit_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class ANCProfileListResponse(BaseModel):
    """Paginated ANC profile list response."""

    items: list[ANCProfileListItem]
    total: int


# ── ANC Visit ────────────────────────────────────────────────────────────────


class ANCVisitCreate(BaseModel):
    """Schema for creating an ANC visit record."""

    anc_profile_id: uuid.UUID
    encounter_id: uuid.UUID | None = None
    visit_date: date
    gestation_weeks: int | None = Field(None, ge=1, le=45)

    # Vitals
    weight_kg: float | None = Field(None, ge=20, le=300)
    bp_systolic: int | None = Field(None, ge=50, le=300)
    bp_diastolic: int | None = Field(None, ge=20, le=200)
    pulse_rate: int | None = Field(None, ge=30, le=250)
    temperature: float | None = Field(None, ge=30.0, le=45.0)

    # Urine
    urine_protein: str | None = Field(
        None, pattern=r"^(nil|trace|1\+|2\+|3\+|4\+)$"
    )
    urine_glucose: str | None = Field(
        None, pattern=r"^(nil|trace|1\+|2\+|3\+|4\+)$"
    )

    # Obstetric exam
    fundal_height_cm: float | None = Field(None, ge=0, le=50)
    fetal_heart_rate: int | None = Field(None, ge=60, le=220)
    fetal_presentation: str | None = Field(
        None, pattern=r"^(cephalic|breech|transverse|oblique)$"
    )
    fetal_movement: str | None = Field(
        None, pattern=r"^(present|absent|reduced)$"
    )
    oedema: str | None = Field(
        None, pattern=r"^(none|mild|moderate|severe)$"
    )
    hb_level: float | None = Field(None, ge=1.0, le=25.0)

    # Interventions
    iron_folate_given: bool = False
    tetanus_dose: str | None = Field(
        None, pattern=r"^(TT1|TT2|TT3|TT4|TT5)$"
    )
    ipt_malaria_dose: str | None = Field(
        None, pattern=r"^(IPT1|IPT2|IPT3)$"
    )
    deworming_given: bool = False
    llins_given: bool = False

    # Counselling
    birth_plan_discussed: bool = False
    danger_signs_counselled: bool = False
    breastfeeding_counselled: bool = False

    # Next appointment
    next_visit_date: date | None = None

    # Notes
    clinical_notes: str | None = Field(None, max_length=5000)
    complications: str | None = Field(None, max_length=2000)
    referred: bool = False
    referral_reason: str | None = Field(None, max_length=1000)


class ANCVisitResponse(BaseModel):
    """Schema for ANC visit API responses."""

    id: uuid.UUID
    anc_profile_id: uuid.UUID
    patient_id: uuid.UUID
    provider_id: uuid.UUID
    visit_number: int
    visit_date: date
    gestation_weeks: int | None
    weight_kg: float | None
    bp_systolic: int | None
    bp_diastolic: int | None
    pulse_rate: int | None
    temperature: float | None
    urine_protein: str | None
    urine_glucose: str | None
    fundal_height_cm: float | None
    fetal_heart_rate: int | None
    fetal_presentation: str | None
    fetal_movement: str | None
    oedema: str | None
    hb_level: float | None
    iron_folate_given: bool
    tetanus_dose: str | None
    ipt_malaria_dose: str | None
    deworming_given: bool
    llins_given: bool
    birth_plan_discussed: bool
    danger_signs_counselled: bool
    breastfeeding_counselled: bool
    next_visit_date: date | None
    clinical_notes: str | None
    complications: str | None
    referred: bool
    referral_reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Delivery Record ──────────────────────────────────────────────────────────


class DeliveryRecordCreate(BaseModel):
    """Schema for creating a delivery record."""

    anc_profile_id: uuid.UUID
    encounter_id: uuid.UUID | None = None
    delivery_date: datetime
    gestation_weeks: int | None = Field(None, ge=20, le=45)
    mode_of_delivery: str = Field(
        ...,
        pattern=r"^(svd|assisted_vaginal|elective_cs|emergency_cs|breech)$",
    )
    duration_of_labour_hours: float | None = Field(None, ge=0)
    place_of_delivery: str = Field(
        default="facility",
        pattern=r"^(facility|home|bba|other)$",
    )

    # Mother outcome
    maternal_outcome: str = Field(
        default="alive", pattern=r"^(alive|deceased)$"
    )
    maternal_complications: str | None = Field(None, max_length=2000)
    blood_loss_ml: int | None = Field(None, ge=0)
    episiotomy: bool = False
    tears: str | None = Field(
        None,
        pattern=r"^(none|first_degree|second_degree|third_degree|fourth_degree)$",
    )

    # Baby outcome
    baby_outcome: str = Field(
        ...,
        pattern=r"^(live_birth|fresh_stillbirth|macerated_stillbirth)$",
    )
    baby_sex: str | None = Field(
        None, pattern=r"^(male|female|ambiguous)$"
    )
    birth_weight_grams: int | None = Field(None, ge=200, le=7000)
    apgar_1min: int | None = Field(None, ge=0, le=10)
    apgar_5min: int | None = Field(None, ge=0, le=10)
    apgar_10min: int | None = Field(None, ge=0, le=10)
    resuscitation_needed: bool = False

    # Immediate newborn care
    skin_to_skin: bool = False
    breastfed_within_1hr: bool = False
    vitamin_k_given: bool = False
    eye_prophylaxis: bool = False
    bcg_given: bool = False
    opv_0_given: bool = False
    arv_prophylaxis_baby: bool = False

    notes: str | None = Field(None, max_length=2000)


class DeliveryRecordResponse(BaseModel):
    """Schema for delivery record API responses."""

    id: uuid.UUID
    anc_profile_id: uuid.UUID
    patient_id: uuid.UUID
    delivered_by: uuid.UUID
    delivery_date: datetime
    gestation_weeks: int | None
    mode_of_delivery: str
    duration_of_labour_hours: float | None
    place_of_delivery: str
    maternal_outcome: str
    maternal_complications: str | None
    blood_loss_ml: int | None
    episiotomy: bool
    tears: str | None
    baby_outcome: str
    baby_sex: str | None
    birth_weight_grams: int | None
    apgar_1min: int | None
    apgar_5min: int | None
    apgar_10min: int | None
    resuscitation_needed: bool
    skin_to_skin: bool
    breastfed_within_1hr: bool
    vitamin_k_given: bool
    eye_prophylaxis: bool
    bcg_given: bool
    opv_0_given: bool
    arv_prophylaxis_baby: bool
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Child Record ─────────────────────────────────────────────────────────────


class ChildRecordCreate(BaseModel):
    """Schema for creating a child health record."""

    patient_id: uuid.UUID
    mother_patient_id: uuid.UUID | None = None
    delivery_record_id: uuid.UUID | None = None
    date_of_birth: date
    birth_weight_grams: int | None = Field(None, ge=200, le=7000)
    sex: str = Field(..., pattern=r"^(male|female)$")
    place_of_birth: str | None = Field(None, max_length=30)
    birth_notification_number: str | None = Field(None, max_length=50)
    hiv_exposed: bool = False
    feeding_method: str | None = Field(
        None,
        pattern=r"^(exclusive_breastfeeding|mixed|replacement)$",
    )
    notes: str | None = Field(None, max_length=2000)


class ChildRecordResponse(BaseModel):
    """Schema for child health record API responses."""

    id: uuid.UUID
    patient_id: uuid.UUID
    mother_patient_id: uuid.UUID | None
    delivery_record_id: uuid.UUID | None
    child_number: str
    date_of_birth: date
    birth_weight_grams: int | None
    sex: str
    place_of_birth: str | None
    birth_notification_number: str | None
    hiv_exposed: bool
    pcr_test_date: date | None
    pcr_result: str | None
    feeding_method: str | None
    status: str
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChildRecordListItem(BaseModel):
    """Child record in list view with patient info."""

    id: uuid.UUID
    child_number: str
    patient_id: uuid.UUID
    patient_name: str | None = None
    date_of_birth: date
    sex: str
    age_months: int | None = None
    hiv_exposed: bool
    immunization_count: int = 0
    next_immunization: str | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChildRecordListResponse(BaseModel):
    """Paginated child record list response."""

    items: list[ChildRecordListItem]
    total: int


# ── Immunization ─────────────────────────────────────────────────────────────


class ImmunizationCreate(BaseModel):
    """Schema for recording an immunization dose."""

    child_record_id: uuid.UUID
    vaccine_code: str = Field(..., min_length=1, max_length=30)
    vaccine_name: str = Field(..., min_length=1, max_length=100)
    dose_number: int = Field(..., ge=1)
    date_given: date
    age_at_dose_weeks: int | None = Field(None, ge=0)
    batch_number: str | None = Field(None, max_length=50)
    site: str | None = Field(
        None,
        pattern=r"^(left_thigh|right_thigh|left_arm|right_arm|oral)$",
    )
    route: str | None = Field(
        None, pattern=r"^(im|sc|oral|id)$"
    )
    adverse_event: bool = False
    adverse_event_description: str | None = Field(None, max_length=1000)
    notes: str | None = Field(None, max_length=1000)


class ImmunizationUpdate(BaseModel):
    """Schema for correcting a recorded immunization dose.

    Every field is optional and only the supplied ones are applied, so a
    mistyped batch number, site, or date can be fixed without deleting and
    re-recording the dose. Passing an explicit null clears a nullable field.
    """

    vaccine_code: str | None = Field(None, min_length=1, max_length=30)
    vaccine_name: str | None = Field(None, min_length=1, max_length=100)
    dose_number: int | None = Field(None, ge=1)
    date_given: date | None = None
    batch_number: str | None = Field(None, max_length=50)
    site: str | None = Field(
        None,
        pattern=r"^(left_thigh|right_thigh|left_arm|right_arm|oral)$",
    )
    route: str | None = Field(None, pattern=r"^(im|sc|oral|id)$")
    adverse_event: bool | None = None
    adverse_event_description: str | None = Field(None, max_length=1000)
    notes: str | None = Field(None, max_length=1000)


class ImmunizationResponse(BaseModel):
    """Schema for immunization API responses."""

    id: uuid.UUID
    child_record_id: uuid.UUID
    patient_id: uuid.UUID
    administered_by: uuid.UUID
    vaccine_code: str
    vaccine_name: str
    dose_number: int
    date_given: date
    age_at_dose_weeks: int | None
    batch_number: str | None
    site: str | None
    route: str | None
    scheduled_date: date | None
    is_overdue: bool
    adverse_event: bool
    adverse_event_description: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── ANC Profile Detail ──────────────────────────────────────────────────────


class ImmunizationScheduleItem(BaseModel):
    """One routine dose on the national EPI schedule."""

    vaccine_code: str
    vaccine_name: str
    due_age_weeks: int
    route: str | None = None
    site: str | None = None


class ANCProfileDetail(BaseModel):
    """Full ANC profile with visits, delivery, and patient info."""

    profile: ANCProfileResponse
    visits: list[ANCVisitResponse]
    delivery: DeliveryRecordResponse | None = None
    patient_name: str | None = None
    patient_mrn: str | None = None


# ── MCH Summary ──────────────────────────────────────────────────────────────


class MCHSummary(BaseModel):
    """Dashboard summary stats for MCH department."""

    active_anc_profiles: int = 0
    high_risk_pregnancies: int = 0
    deliveries_this_month: int = 0
    live_births_this_month: int = 0
    active_children: int = 0
    overdue_immunizations: int = 0
