import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

# ── Pharmacy Item / Inventory schemas ──────────────────────────────────────


class PharmacyItemCreate(BaseModel):
    """Schema for adding a drug to pharmacy inventory."""

    drug_code: str = Field(..., min_length=1, max_length=50)
    drug_name: str = Field(..., min_length=1, max_length=300)
    generic_name: str | None = Field(None, max_length=300)
    atc_code: str | None = Field(None, max_length=20)
    is_keml: bool = False
    dosage_form: str | None = Field(
        None, pattern=r"^(tablet|capsule|syrup|suspension|injection|cream|ointment|drops|inhaler|suppository|sachet|solution|powder)$"
    )
    strength: str | None = Field(None, max_length=50)
    batch_number: str | None = Field(None, max_length=50)
    current_quantity: int = Field(0, ge=0)
    unit_of_measure: str = Field(
        "tablet",
        pattern=r"^(tablet|capsule|ml|vial|tube|sachet|bottle|ampoule|dose)$",
    )
    reorder_level: int = Field(10, ge=0)
    max_stock_level: int | None = Field(None, ge=0)
    buying_price_cents: int | None = Field(None, ge=0)
    selling_price_cents: int | None = Field(None, ge=0)
    expiry_date: date | None = None
    manufacturer: str | None = Field(None, max_length=200)
    supplier: str | None = Field(None, max_length=200)
    storage_conditions: str | None = Field(None, max_length=100)
    shelf_location: str | None = Field(None, max_length=50)


class PharmacyItemUpdate(BaseModel):
    """Schema for updating a pharmacy inventory item."""

    drug_name: str | None = Field(None, min_length=1, max_length=300)
    generic_name: str | None = Field(None, max_length=300)
    is_keml: bool | None = None
    current_quantity: int | None = Field(None, ge=0)
    reorder_level: int | None = Field(None, ge=0)
    selling_price_cents: int | None = Field(None, ge=0)
    expiry_date: date | None = None
    shelf_location: str | None = Field(None, max_length=50)
    is_active: bool | None = None


class PharmacyItemResponse(BaseModel):
    """Schema for pharmacy item API responses."""

    id: uuid.UUID
    facility_id: uuid.UUID
    drug_code: str
    drug_name: str
    generic_name: str | None
    atc_code: str | None
    is_keml: bool
    dosage_form: str | None
    strength: str | None
    batch_number: str | None
    current_quantity: int
    unit_of_measure: str
    reorder_level: int
    max_stock_level: int | None
    buying_price_cents: int | None
    selling_price_cents: int | None
    expiry_date: date | None
    manufacturer: str | None
    supplier: str | None
    storage_conditions: str | None
    shelf_location: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class InventoryListResponse(BaseModel):
    """Paginated pharmacy inventory list."""

    items: list[PharmacyItemResponse]
    total: int
    page: int
    page_size: int


class StockAlert(BaseModel):
    """Low stock or expiry alert."""

    item_id: uuid.UUID
    drug_name: str
    drug_code: str
    current_quantity: int
    reorder_level: int
    expiry_date: date | None
    alert_type: str  # low_stock, expiring_soon, expired, out_of_stock


# ── Dispensing schemas ─────────────────────────────────────────────────────


class DispenseRequest(BaseModel):
    """Schema for dispensing a prescription."""

    prescription_id: uuid.UUID
    patient_id: uuid.UUID
    pharmacy_item_id: uuid.UUID | None = None
    quantity_dispensed: int = Field(..., ge=1)
    substitution_drug: str | None = Field(None, max_length=300)
    substitution_reason: str | None = Field(None, max_length=500)
    dosage_instructions: str | None = Field(None, max_length=1000)
    counseling_done: bool = False
    counseling_notes: str | None = Field(None, max_length=2000)
    payment_method: str | None = Field(
        None, pattern=r"^(cash|mpesa|insurance|exemption)$"
    )


class DispensingResponse(BaseModel):
    """Schema for dispensing API responses."""

    id: uuid.UUID
    prescription_id: uuid.UUID
    patient_id: uuid.UUID
    pharmacy_item_id: uuid.UUID | None
    dispensed_by: uuid.UUID
    drug_name: str
    quantity_requested: int
    quantity_dispensed: int
    substitution_drug: str | None
    substitution_reason: str | None
    dosage_instructions: str | None
    counseling_done: bool
    counseling_notes: str | None
    status: str
    unit_price_cents: int | None
    total_price_cents: int | None
    payment_status: str
    payment_method: str | None
    dispensed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Pharmacy Queue schemas ────────────────────────────────────────────────


class PharmacyQueueItem(BaseModel):
    """A pending prescription in the pharmacy queue."""

    prescription_id: uuid.UUID
    encounter_id: uuid.UUID
    patient_id: uuid.UUID
    patient_name: str | None = None
    patient_mrn: str | None = None
    drug_name: str
    generic_name: str | None
    is_keml: bool
    dosage: str
    route: str
    frequency: str
    duration_days: int | None
    quantity: int | None
    instructions: str | None
    prescriber_id: uuid.UUID
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PharmacyQueueResponse(BaseModel):
    """Pharmacy queue list response."""

    items: list[PharmacyQueueItem]
    total: int


# ── Stock Transaction schemas ─────────────────────────────────────────────


class StockReceiptRequest(BaseModel):
    """Schema for receiving new stock."""

    pharmacy_item_id: uuid.UUID
    quantity: int = Field(..., ge=1)
    batch_number: str | None = Field(None, max_length=50)
    expiry_date: date | None = None
    unit_cost_cents: int | None = Field(None, ge=0)
    reference_number: str | None = Field(None, max_length=100)
    reason: str | None = Field(None, max_length=500)


class StockAdjustmentRequest(BaseModel):
    """Schema for stock adjustments (loss, damage, transfer, correction)."""

    pharmacy_item_id: uuid.UUID
    quantity_change: int  # positive for add, negative for deduct
    reason: str = Field(..., min_length=1, max_length=500)
    reference_number: str | None = Field(None, max_length=100)


class StockTransactionResponse(BaseModel):
    """Schema for stock transaction API responses."""

    id: uuid.UUID
    pharmacy_item_id: uuid.UUID
    dispensing_id: uuid.UUID | None
    transaction_type: str
    quantity_change: int
    quantity_before: int
    quantity_after: int
    reference_number: str | None
    reason: str | None
    unit_cost_cents: int | None
    batch_number: str | None
    expiry_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}
