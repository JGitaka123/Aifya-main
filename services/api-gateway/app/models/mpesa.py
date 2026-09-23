"""
M-Pesa STK Push request tracking model.
Stores the lifecycle of every STK Push from initiation through callback,
keyed by Safaricom's CheckoutRequestID for reconciliation.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class MpesaStkRequest(AuditMixin, Base):
    """
    M-Pesa STK Push request lifecycle row.
    One row per STK Push initiation. Updated on Safaricom callback.
    """

    __tablename__ = "mpesa_stk_requests"
    __table_args__ = (
        UniqueConstraint(
            "checkout_request_id", name="uq_mpesa_stk_checkout_request_id"
        ),
        Index("ix_mpesa_stk_facility_status", "facility_id", "status"),
        Index("ix_mpesa_stk_invoice", "facility_id", "invoice_id"),
        Index("ix_mpesa_stk_created_at", "facility_id", "created_at"),
    )

    invoice_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id")
    )
    patient_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    reference: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    checkout_request_id: Mapped[str] = mapped_column(String(100), nullable=False)
    merchant_request_id: Mapped[str] = mapped_column(
        String(100), nullable=False, default=""
    )

    # Lifecycle: pending | success | failed | timeout
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )

    # Callback fields — populated when Safaricom responds
    result_code: Mapped[int | None] = mapped_column(Integer)
    result_desc: Mapped[str | None] = mapped_column(Text)
    mpesa_receipt_number: Mapped[str | None] = mapped_column(String(50))
    transaction_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
