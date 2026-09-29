"""Request and response shapes for Aifya usage billing (hospital-facing)."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Guard rail on the configurable rate: KES 10,000 per patient-day. A typo that
#: adds two zeros must not be able to produce a five-figure daily bill.
MAX_RATE_CENTS = 1_000_000


class UsageConfigResponse(BaseModel):
    """The rate the hospital is currently billed at."""

    rate_cents: int
    currency: str
    notes: str | None = None
    is_configured: bool = Field(
        description=(
            "False while the built-in placeholder rate is in force. An "
            "unconfirmed rate must not be used for real hospital billing."
        )
    )


class UsageConfigUpdate(BaseModel):
    """New rate for the hospital. Applies to days computed from now on."""

    rate_cents: int = Field(..., ge=0, le=MAX_RATE_CENTS)
    currency: str = Field("KES", min_length=3, max_length=3)
    notes: str | None = Field(None, max_length=500)


class UsageAccrualRequest(BaseModel):
    """Range to (re)compute. Both ends are inclusive calendar dates."""

    start_date: date
    end_date: date
    force: bool = Field(
        False,
        description="Recompute days that are already finalized",
    )

    @model_validator(mode="after")
    def _check_order(self) -> "UsageAccrualRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be before start_date")
        if (self.end_date - self.start_date).days > 366:
            raise ValueError("range must not exceed 366 days")
        return self


class UsageFinalizeRequest(BaseModel):
    """Month to close, given as a calendar month."""

    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)


class UsageDayResponse(BaseModel):
    """One day of billable usage."""

    model_config = ConfigDict(from_attributes=True)

    usage_date: date
    registration_patients: int
    emergency_patients: int
    inpatient_patients: int
    total_billable_patients: int
    rate_cents: int
    currency: str
    amount_cents: int
    is_finalized: bool
    computed_at: datetime | None = None


class UsageRangeResponse(BaseModel):
    """Daily usage over an arbitrary range, with the range totals."""

    start_date: date
    end_date: date
    currency: str
    rate_cents: int
    total_patient_days: int
    registration_patient_days: int
    emergency_patient_days: int
    inpatient_patient_days: int
    total_amount_cents: int
    days: list[UsageDayResponse]


class UsageMonthResponse(BaseModel):
    """The hospital's Aifya bill for one calendar month."""

    year: int
    month: int
    period_label: str
    facility_id: str
    facility_name: str
    currency: str
    rate_cents: int
    rate_is_confirmed: bool = Field(
        description="False while the placeholder rate is in force"
    )
    rate_changed_mid_month: bool = Field(
        description="True when days in this month were priced at more than one rate"
    )
    total_patient_days: int
    registration_patient_days: int
    emergency_patient_days: int
    inpatient_patient_days: int
    total_amount_cents: int
    is_finalized: bool
    invoice: "UsageInvoiceResponse | None" = None
    days: list[UsageDayResponse]


class UsageInvoiceCreate(BaseModel):
    """Raise (or refresh) the invoice for one calendar month."""

    year: int = Field(..., ge=2000, le=2100)
    month: int = Field(..., ge=1, le=12)
    notes: str | None = Field(None, max_length=500)


class UsageInvoicePayment(BaseModel):
    """Record money received against an issued invoice."""

    amount_cents: int = Field(..., gt=0)
    reference: str | None = Field(None, max_length=100)


class UsageInvoiceResponse(BaseModel):
    """Aifya's monthly invoice to the hospital."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    invoice_number: str
    period_year: int
    period_month: int
    period_label: str
    status: str
    patient_days: int
    registration_patient_days: int
    emergency_patient_days: int
    inpatient_patient_days: int
    rate_cents: int | None = None
    amount_cents: int
    paid_cents: int
    balance_cents: int
    currency: str
    issued_at: datetime | None = None
    due_at: datetime | None = None
    paid_at: datetime | None = None
    payment_reference: str | None = None
    notes: str | None = None


UsageMonthResponse.model_rebuild()
