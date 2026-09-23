import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ── Invoice schemas ───────────────────────────────────────────────────────────


class InvoiceItemCreate(BaseModel):
    """Schema for adding a line item to an invoice."""

    item_type: str = Field(
        ...,
        pattern=r"^(consultation|pharmacy|lab|procedure|bed|nursing|other)$",
    )
    description: str = Field(..., min_length=1, max_length=500)
    quantity: int = Field(default=1, ge=1)
    unit_price_cents: int = Field(default=0, ge=0)
    discount_cents: int = Field(default=0, ge=0)
    reference_id: uuid.UUID | None = None
    reference_type: str | None = Field(
        None,
        pattern=r"^(dispensing|lab_order|imaging_order|prescription|encounter)$",
    )


class InvoiceCreate(BaseModel):
    """Schema for creating an invoice."""

    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    payment_method: str | None = Field(
        None, pattern=r"^(cash|mpesa|insurance|exemption)$"
    )
    insurance_provider: str | None = Field(None, max_length=100)
    insurance_member_no: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)
    items: list[InvoiceItemCreate] = Field(..., min_length=1)


class InvoiceItemResponse(BaseModel):
    """Schema for invoice item API responses."""

    id: uuid.UUID
    invoice_id: uuid.UUID
    item_type: str
    description: str
    quantity: int
    unit_price_cents: int
    total_cents: int
    discount_cents: int
    reference_id: uuid.UUID | None
    reference_type: str | None

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    """Schema for invoice API responses."""

    id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    invoice_number: str
    status: str
    payment_method: str | None
    insurance_provider: str | None
    insurance_member_no: str | None
    sha_claim_ref: str | None
    subtotal_cents: int
    discount_cents: int
    tax_cents: int
    total_cents: int
    paid_cents: int
    balance_cents: int
    notes: str | None
    finalized_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvoiceDetail(BaseModel):
    """Full invoice with line items and patient info."""

    invoice: InvoiceResponse
    items: list[InvoiceItemResponse]
    patient_name: str | None = None
    patient_mrn: str | None = None


class InvoiceListItem(BaseModel):
    """Invoice summary for list views."""

    id: uuid.UUID
    invoice_number: str
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = None
    patient_mrn: str | None = None
    status: str
    total_cents: int
    paid_cents: int
    balance_cents: int
    payment_method: str | None
    item_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class InvoiceListResponse(BaseModel):
    """Paginated invoice list response."""

    items: list[InvoiceListItem]
    total: int
    page: int
    page_size: int


# ── Payment schemas ───────────────────────────────────────────────────────────


class PaymentCreate(BaseModel):
    """Schema for recording a payment against an invoice."""

    amount_cents: int = Field(..., gt=0)
    payment_method: str = Field(
        ..., pattern=r"^(cash|mpesa|insurance|exemption)$"
    )
    reference_number: str | None = Field(None, max_length=100)
    mpesa_transaction_id: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)


class PaymentResponse(BaseModel):
    """Schema for payment API responses."""

    id: uuid.UUID
    invoice_id: uuid.UUID
    patient_id: uuid.UUID
    amount_cents: int
    payment_method: str
    reference_number: str | None
    mpesa_transaction_id: str | None
    received_by: uuid.UUID
    paid_at: datetime
    notes: str | None

    model_config = {"from_attributes": True}


# ── Billing Dashboard ─────────────────────────────────────────────────────────


class BillingSummary(BaseModel):
    """Dashboard summary stats."""

    total_invoices: int
    draft_count: int
    finalized_count: int
    paid_count: int
    partially_paid_count: int
    total_billed_cents: int
    total_paid_cents: int
    total_outstanding_cents: int


# ── Waive / Cancel ────────────────────────────────────────────────────────────


class InvoiceWaiveRequest(BaseModel):
    """Schema for waiving an invoice balance."""

    reason: str = Field(..., min_length=5, max_length=500)


# Point of sale: ordered services (lab, imaging, pharmacy)


class ServiceChargeResponse(BaseModel):
    """Money owed for one ordered service."""

    encounter_id: uuid.UUID
    reference_type: str
    reference_id: uuid.UUID
    invoice_id: uuid.UUID
    invoice_number: str
    description: str
    total_cents: int
    paid_cents: int
    balance_cents: int
    paid: bool

    model_config = {"from_attributes": True}


class ServiceChargeListResponse(BaseModel):
    """Outstanding service charges for a patient or a visit."""

    items: list[ServiceChargeResponse]
    total_outstanding_cents: int


class ServicePaymentRequest(BaseModel):
    """Cashier settling an ordered service at the point of sale."""

    payment_method: str = Field(
        ..., pattern=r"^(cash|mpesa|insurance|exemption)$"
    )
    reference_type: str | None = Field(
        None, pattern=r"^(lab_order|imaging_order|prescription)$"
    )
    reference_id: uuid.UUID | None = None
    reference_number: str | None = Field(None, max_length=100)
    mpesa_transaction_id: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=2000)


class ServicePaymentResponse(BaseModel):
    """Result of paying for a service request, carrying the receipt."""

    payment_id: uuid.UUID | None = None
    invoice_id: uuid.UUID
    invoice_number: str
    encounter_id: uuid.UUID
    description: str | None = None
    amount_cents: int
    payment_method: str | None = None
    reference_number: str | None = None
    received_by: uuid.UUID | None = None
    paid_at: datetime | None = None
    invoice_status: str
    balance_cents: int
    already_paid: bool = False
    receipt_url: str
