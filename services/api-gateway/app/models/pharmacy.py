import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class PharmacyItem(AuditMixin, Base):
    """
    Pharmacy formulary / inventory item.
    Tracks stock per batch with KEML tagging and expiry.
    """

    __tablename__ = "pharmacy_items"
    __table_args__ = (
        Index("ix_pharmacy_items_facility_drug", "facility_id", "drug_code"),
        Index("ix_pharmacy_items_facility_name", "facility_id", "drug_name"),
        Index("ix_pharmacy_items_expiry", "facility_id", "expiry_date"),
        # No-negative-stock guard (defense-in-depth for the app-level checks).
        CheckConstraint(
            "current_quantity >= 0", name="ck_pharmacy_items_qty_nonneg"
        ),
    )

    # Drug identity
    drug_code: Mapped[str] = mapped_column(String(50), nullable=False)
    drug_name: Mapped[str] = mapped_column(String(300), nullable=False)
    generic_name: Mapped[str | None] = mapped_column(String(300))
    atc_code: Mapped[str | None] = mapped_column(String(20))
    is_keml: Mapped[bool] = mapped_column(default=False, nullable=False)
    dosage_form: Mapped[str | None] = mapped_column(String(50))  # tablet, capsule, syrup, injection, etc.
    strength: Mapped[str | None] = mapped_column(String(50))  # e.g., "500mg", "250mg/5ml"

    # Stock
    batch_number: Mapped[str | None] = mapped_column(String(50))
    current_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_of_measure: Mapped[str] = mapped_column(
        String(30), default="tablet", nullable=False
    )  # tablet, capsule, ml, vial, tube, sachet
    reorder_level: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    max_stock_level: Mapped[int | None] = mapped_column(Integer)

    # Pricing (KES cents)
    buying_price_cents: Mapped[int | None] = mapped_column(Integer)
    selling_price_cents: Mapped[int | None] = mapped_column(Integer)

    # Expiry
    expiry_date: Mapped[date | None] = mapped_column(Date)
    manufacturer: Mapped[str | None] = mapped_column(String(200))
    supplier: Mapped[str | None] = mapped_column(String(200))

    # Storage
    storage_conditions: Mapped[str | None] = mapped_column(String(100))  # room temp, refrigerate, etc.
    shelf_location: Mapped[str | None] = mapped_column(String(50))

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)


class PharmacyBatch(AuditMixin, Base):
    """
    Stock batch (lot) for a pharmacy item. Each stock receipt creates a
    batch; dispensing consumes batches earliest-expiry-first (FEFO).
    pharmacy_items.current_quantity remains the denormalized total of
    remaining batch quantities.
    """

    __tablename__ = "pharmacy_batches"
    __table_args__ = (
        Index("ix_pharmacy_batches_item", "facility_id", "pharmacy_item_id"),
        Index("ix_pharmacy_batches_expiry", "facility_id", "expiry_date"),
        # No-negative-stock guard: a batch can never be consumed below zero.
        CheckConstraint(
            "quantity_remaining >= 0", name="ck_pharmacy_batches_qty_nonneg"
        ),
    )

    pharmacy_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_items.id"), nullable=False
    )
    batch_number: Mapped[str | None] = mapped_column(String(50))
    expiry_date: Mapped[date | None] = mapped_column(Date)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_remaining: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost_cents: Mapped[int | None] = mapped_column(Integer)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reference_number: Mapped[str | None] = mapped_column(String(100))


class Dispensing(AuditMixin, Base):
    """
    Pharmacy dispensing record linked to a prescription.
    Event-sourced for audit trail per CLAUDE.md.
    """

    __tablename__ = "dispensings"
    __table_args__ = (
        Index("ix_dispensings_prescription", "facility_id", "prescription_id"),
        Index("ix_dispensings_patient", "facility_id", "patient_id"),
        Index("ix_dispensings_status", "facility_id", "status"),
    )

    prescription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prescriptions.id"), nullable=False
    )
    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False
    )
    pharmacy_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_items.id")
    )
    dispensed_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("staff.id"), nullable=False
    )

    # Dispensing details
    drug_name: Mapped[str] = mapped_column(String(300), nullable=False)
    quantity_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_dispensed: Mapped[int] = mapped_column(Integer, nullable=False)
    substitution_drug: Mapped[str | None] = mapped_column(String(300))
    substitution_reason: Mapped[str | None] = mapped_column(Text)

    # Dosage label
    dosage_instructions: Mapped[str | None] = mapped_column(Text)

    # Patient counseling
    counseling_done: Mapped[bool] = mapped_column(default=False, nullable=False)
    counseling_notes: Mapped[str | None] = mapped_column(Text)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="dispensed", nullable=False
    )  # dispensed, returned, cancelled

    # Cost (KES cents)
    unit_price_cents: Mapped[int | None] = mapped_column(Integer)
    total_price_cents: Mapped[int | None] = mapped_column(Integer)

    # Payment
    payment_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, paid, insurance, exempted, waived
    payment_method: Mapped[str | None] = mapped_column(
        String(20)
    )  # cash, mpesa, insurance, exemption

    # Timestamps
    dispensed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StockTransaction(AuditMixin, Base):
    """
    Immutable stock transaction log for pharmacy inventory.
    Tracks receipts, dispensing deductions, adjustments, and expiry write-offs.
    """

    __tablename__ = "stock_transactions"
    __table_args__ = (
        Index("ix_stock_transactions_item", "facility_id", "pharmacy_item_id"),
        Index("ix_stock_transactions_type", "facility_id", "transaction_type"),
    )

    pharmacy_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pharmacy_items.id"), nullable=False
    )
    dispensing_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dispensings.id")
    )

    # Transaction
    transaction_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # receipt, dispensing, adjustment, expiry_writeoff, return, transfer
    quantity_change: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # positive for in, negative for out
    quantity_before: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)

    # Reference
    reference_number: Mapped[str | None] = mapped_column(String(100))  # PO number, GRN, etc.
    reason: Mapped[str | None] = mapped_column(Text)

    # Cost
    unit_cost_cents: Mapped[int | None] = mapped_column(Integer)

    # Batch (for receipts)
    batch_number: Mapped[str | None] = mapped_column(String(50))
    expiry_date: Mapped[date | None] = mapped_column(Date)
