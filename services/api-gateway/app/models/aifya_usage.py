"""Aifya usage billing - what the hospital owes Aifya, not what a patient owes.

Aifya is charged to the facility on a patient-day basis: one patient seen on
one calendar day is one billable patient-day, priced at the facility's rate.
A patient who passes through both Registration and Emergency on the same day,
or who is in a bed on a day they were also registered, is still a single
patient-day.

Three tables make that bill auditable:

    aifya_usage_daily       one row per facility per day - the counts, the rate
                            that was applied and the amount it produced
    aifya_usage_config      the per-facility patient-day rate
    aifya_usage_invoices    the monthly invoice raised against the ledger

Nothing here ever reaches a patient's invoice.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin

#: Price of one patient-day when the facility has not agreed a different rate.
#: A placeholder, not a contract: the API reports ``is_configured=False`` while
#: this is in force so the screen can say the rate is unconfirmed.
DEFAULT_USAGE_RATE_CENTS = 2000
DEFAULT_USAGE_CURRENCY = "KES"


class AifyaUsageDaily(AuditMixin, Base):
    """
    One facility's billable usage for one calendar day.

    The three channel counts partition ``total_billable_patients``: every
    patient counted that day sits in exactly one of them, and a patient who
    appears in more than one channel is attributed by priority
    (Inpatient, then Emergency, then Registration) so the arithmetic still
    adds up.

    The rate is copied onto the row when the day is computed. That snapshot is
    what makes the month reproducible: raising the rate in October must not
    restate September's already-issued bill.
    """

    __tablename__ = "aifya_usage_daily"
    __table_args__ = (
        Index(
            "uq_aifya_usage_daily_facility_date",
            "facility_id",
            "usage_date",
            unique=True,
        ),
        Index("ix_aifya_usage_daily_facility_date", "facility_id", "usage_date"),
    )

    usage_date: Mapped[date] = mapped_column(Date, nullable=False)

    #: Patients whose channel into the hospital that day was Registration.
    registration_patients: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    #: Patients who reached the hospital only through Emergency that day.
    emergency_patients: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    #: Patients occupying a bed that day - admission and discharge day both
    #: count, so a four-day stay contributes four bed-days.
    inpatient_patients: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    #: The deduplicated total: registration + emergency + inpatient.
    total_billable_patients: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    rate_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_USAGE_RATE_CENTS
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default=DEFAULT_USAGE_CURRENCY
    )
    #: total_billable_patients * rate_cents.
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: Set once the month has been billed. A finalized day is not recomputed
    #: unless the caller explicitly asks to force it.
    is_finalized: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AifyaUsageConfig(AuditMixin, Base):
    """
    The patient-day rate agreed with one facility.

    Absent row means the facility is on the placeholder rate, so no setup step
    is required before usage can be metered - but the rate is then unconfirmed.
    """

    __tablename__ = "aifya_usage_config"
    __table_args__ = (
        Index("uq_aifya_usage_config_facility", "facility_id", unique=True),
    )

    rate_cents: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_USAGE_RATE_CENTS
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default=DEFAULT_USAGE_CURRENCY
    )
    notes: Mapped[str | None] = mapped_column(Text)


class AifyaUsageInvoice(AuditMixin, Base):
    """
    Aifya's monthly invoice to the hospital for metered usage.

    Raised as a draft against a finalized month, then issued, then paid. The
    figures are copied from the ledger at generation time so an issued invoice
    is a statement of what was billed, not a live view that drifts.

    ``rate_cents`` is only recorded when the whole month was priced at one
    rate; a month that spans a rate change carries the amount and the
    patient-days, and reports the mixed rate through ``rate_cents = NULL``.
    """

    __tablename__ = "aifya_usage_invoices"
    __table_args__ = (
        Index("ix_aifya_usage_invoices_facility_status", "facility_id", "status"),
        Index(
            "uq_aifya_usage_invoices_number",
            "facility_id",
            "invoice_number",
            unique=True,
        ),
    )

    invoice_number: Mapped[str] = mapped_column(String(30), nullable=False)
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_month: Mapped[int] = mapped_column(Integer, nullable=False)

    patient_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    registration_patient_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    emergency_patient_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    inpatient_patient_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    rate_cents: Mapped[int | None] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paid_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default=DEFAULT_USAGE_CURRENCY
    )

    #: draft -> issued -> paid, or void.
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft"
    )
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payment_reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
