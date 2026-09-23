import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class Invoice(AuditMixin, Base):
    """
    Patient invoice aggregating charges from encounter services
    (consultation, pharmacy, lab, procedures).
    Money stored in KES cents per CLAUDE.md.
    """

    __tablename__ = "invoices"
    __table_args__ = (
        Index("ix_invoices_facility_patient", "facility_id", "patient_id"),
        Index("ix_invoices_facility_status", "facility_id", "status"),
        Index("ix_invoices_number", "facility_id", "invoice_number", unique=True),
    )

    encounter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    invoice_number: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft, finalized, partially_paid, paid, cancelled, waived
    payment_method: Mapped[str | None] = mapped_column(String(20))  # cash, mpesa, insurance, exemption
    insurance_provider: Mapped[str | None] = mapped_column(String(100))
    insurance_member_no: Mapped[str | None] = mapped_column(String(50))
    sha_claim_ref: Mapped[str | None] = mapped_column(String(100))

    # Totals (KES cents)
    subtotal_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tax_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    paid_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    balance_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    notes: Mapped[str | None] = mapped_column(Text)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class InvoiceItem(AuditMixin, Base):
    """
    Individual line item on an invoice (consultation fee, drug charge, lab test, etc.).
    Money stored in KES cents per CLAUDE.md.
    """

    __tablename__ = "invoice_items"
    __table_args__ = (
        Index("ix_invoice_items_invoice", "invoice_id"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False
    )
    item_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # consultation, pharmacy, lab, procedure, bed, nursing, other
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    discount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Optional references back to source records
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reference_type: Mapped[str | None] = mapped_column(String(30))  # dispensing, lab_order, encounter


class Payment(AuditMixin, Base):
    """
    Payment record against an invoice.
    Supports partial payments and multiple payment methods.
    Money stored in KES cents per CLAUDE.md.
    """

    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_invoice", "invoice_id"),
        Index("ix_payments_facility_date", "facility_id", "paid_at"),
    )

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_method: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # cash, mpesa, insurance, exemption
    reference_number: Mapped[str | None] = mapped_column(String(100))  # M-Pesa code, receipt #
    mpesa_transaction_id: Mapped[str | None] = mapped_column(String(50))
    # Nullable: machine-recorded payments (M-Pesa callbacks) have no staff receiver.
    received_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
