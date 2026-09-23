import uuid
from datetime import datetime

from pydantic import BaseModel, Field

# ── Inventory Items ─────────────────────────────────────────────────────────


class InventoryItemCreate(BaseModel):
    """Schema for creating an inventory item."""

    name: str = Field(..., max_length=200)
    description: str | None = Field(None, max_length=2000)
    category: str = Field(
        ...,
        pattern=r"^(consumable|equipment|surgical|linen|stationery|reagent|other)$",
    )
    sub_category: str | None = Field(None, max_length=100)
    unit_of_measure: str = Field(..., max_length=30)
    unit_cost: int = Field(0, ge=0)
    reorder_level: int = Field(10, ge=0)
    reorder_quantity: int = Field(50, ge=1)
    max_stock: int | None = Field(None, ge=0)
    store_location: str | None = Field(None, max_length=100)
    department_id: uuid.UUID | None = None
    specifications: dict | None = None


class InventoryItemResponse(BaseModel):
    """Schema for inventory item API responses."""

    id: uuid.UUID
    item_code: str
    name: str
    description: str | None
    category: str
    sub_category: str | None
    unit_of_measure: str
    unit_cost: int
    current_stock: int
    reorder_level: int
    reorder_quantity: int
    max_stock: int | None
    store_location: str | None
    department_id: uuid.UUID | None
    is_active: bool
    specifications: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InventoryItemListItem(BaseModel):
    """Inventory item in list view."""

    id: uuid.UUID
    item_code: str
    name: str
    category: str
    unit_of_measure: str
    unit_cost: int
    current_stock: int
    reorder_level: int
    is_active: bool
    stock_status: str  # ok, low, out

    model_config = {"from_attributes": True}


class InventoryItemListResponse(BaseModel):
    """Inventory item list response."""

    items: list[InventoryItemListItem]
    total: int


# ── Transactions ────────────────────────────────────────────────────────────


class InventoryTransactionCreate(BaseModel):
    """Schema for creating an inventory transaction."""

    item_id: uuid.UUID
    transaction_type: str = Field(
        ...,
        pattern=r"^(receipt|issue|return|adjustment|transfer|write_off|opening)$",
    )
    quantity: int = Field(...)
    unit_cost: int = Field(0, ge=0)
    department_id: uuid.UUID | None = None
    issued_to: str | None = Field(None, max_length=200)
    reason: str | None = Field(None, max_length=1000)
    batch_number: str | None = Field(None, max_length=50)
    expiry_date: datetime | None = None


class InventoryTransactionResponse(BaseModel):
    """Schema for transaction API responses."""

    id: uuid.UUID
    item_id: uuid.UUID
    transaction_type: str
    quantity: int
    balance_after: int
    unit_cost: int
    total_cost: int
    transaction_date: datetime
    reference_number: str | None
    department_id: uuid.UUID | None
    issued_to: str | None
    reason: str | None
    batch_number: str | None
    expiry_date: datetime | None

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    """Transaction list response."""

    items: list[InventoryTransactionResponse]
    total: int


# ── Suppliers ───────────────────────────────────────────────────────────────


class SupplierCreate(BaseModel):
    """Schema for creating a supplier."""

    name: str = Field(..., max_length=200)
    contact_person: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=30)
    email: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=500)
    kra_pin: str | None = Field(None, max_length=20)
    payment_terms: str | None = Field(None, max_length=100)
    category: str | None = Field(None, max_length=50)
    notes: str | None = Field(None, max_length=1000)


class SupplierResponse(BaseModel):
    """Schema for supplier API responses."""

    id: uuid.UUID
    name: str
    supplier_code: str | None
    contact_person: str | None
    phone: str | None
    email: str | None
    address: str | None
    kra_pin: str | None
    payment_terms: str | None
    category: str | None
    rating: int | None
    is_active: bool
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SupplierListResponse(BaseModel):
    """Supplier list response."""

    items: list[SupplierResponse]
    total: int


# ── Purchase Orders ─────────────────────────────────────────────────────────


class PurchaseOrderItemCreate(BaseModel):
    """Line item for a purchase order."""

    item_id: uuid.UUID
    quantity_ordered: int = Field(..., ge=1)
    unit_cost: int = Field(..., ge=0)


class PurchaseOrderCreate(BaseModel):
    """Schema for creating a purchase order."""

    supplier_id: uuid.UUID
    expected_delivery: datetime | None = None
    delivery_address: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=1000)
    items: list[PurchaseOrderItemCreate] = Field(..., min_length=1)


class POItemResponse(BaseModel):
    """Purchase order line item response."""

    id: uuid.UUID
    item_id: uuid.UUID
    item_name: str | None = None
    quantity_ordered: int
    quantity_received: int
    unit_cost: int
    total_cost: int

    model_config = {"from_attributes": True}


class PurchaseOrderResponse(BaseModel):
    """Schema for purchase order API responses."""

    id: uuid.UUID
    po_number: str
    supplier_id: uuid.UUID
    supplier_name: str | None = None
    order_date: datetime
    expected_delivery: datetime | None
    status: str
    subtotal: int
    tax_amount: int
    total_amount: int
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    delivery_address: str | None
    notes: str | None
    items: list[POItemResponse] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class PurchaseOrderListItem(BaseModel):
    """Purchase order in list view."""

    id: uuid.UUID
    po_number: str
    supplier_name: str | None = None
    order_date: datetime
    status: str
    total_amount: int
    item_count: int = 0

    model_config = {"from_attributes": True}


class PurchaseOrderListResponse(BaseModel):
    """Purchase order list response."""

    items: list[PurchaseOrderListItem]
    total: int


class ReceiveItemRequest(BaseModel):
    """Schema for receiving items against a PO."""

    po_item_id: uuid.UUID
    quantity_received: int = Field(..., ge=1)
    batch_number: str | None = Field(None, max_length=50)
    expiry_date: datetime | None = None


# ── Summary ─────────────────────────────────────────────────────────────────


class InventorySummary(BaseModel):
    """Inventory department summary stats."""

    total_items: int = 0
    active_items: int = 0
    low_stock_items: int = 0
    out_of_stock_items: int = 0
    total_stock_value: int = 0
    pending_orders: int = 0
    suppliers_count: int = 0
    transactions_today: int = 0
