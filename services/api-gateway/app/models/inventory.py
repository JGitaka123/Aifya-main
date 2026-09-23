import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.base import AuditMixin


class InventoryItem(AuditMixin, Base):
    """
    General inventory item (non-pharmacy supplies, consumables, equipment).
    Pharmacy items are in pharmacy module.
    """

    __tablename__ = "inventory_items"
    __table_args__ = (
        Index("ix_inventory_items_category", "facility_id", "category"),
        Index("ix_inventory_items_code", "facility_id", "item_code", unique=True),
    )

    item_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # consumable, equipment, surgical, linen, stationery, reagent, other
    sub_category: Mapped[str | None] = mapped_column(String(100))
    unit_of_measure: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # piece, box, pack, litre, kg, roll
    unit_cost: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # KES cents

    # Stock levels
    current_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reorder_level: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    reorder_quantity: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    max_stock: Mapped[int | None] = mapped_column(Integer)

    # Location
    store_location: Mapped[str | None] = mapped_column(String(100))
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id")
    )

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    specifications: Mapped[dict[str, object] | None] = mapped_column(JSONB)


class InventoryTransaction(AuditMixin, Base):
    """Stock movement for inventory items."""

    __tablename__ = "inventory_transactions"
    __table_args__ = (
        Index("ix_inventory_transactions_item", "facility_id", "item_id"),
        Index("ix_inventory_transactions_date", "facility_id", "transaction_date"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False
    )
    transaction_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # receipt, issue, return, adjustment, transfer, write_off, opening
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # positive for in, negative for out
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_cost: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # KES cents
    total_cost: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # KES cents

    transaction_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reference_number: Mapped[str | None] = mapped_column(String(50))
    department_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    issued_to: Mapped[str | None] = mapped_column(
        String(200)
    )  # person or department name
    reason: Mapped[str | None] = mapped_column(Text)
    batch_number: Mapped[str | None] = mapped_column(String(50))
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Supplier(AuditMixin, Base):
    """Vendor/supplier for procurement."""

    __tablename__ = "suppliers"
    __table_args__ = (Index("ix_suppliers_facility", "facility_id"),)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    supplier_code: Mapped[str | None] = mapped_column(String(50))
    contact_person: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text)
    kra_pin: Mapped[str | None] = mapped_column(
        String(20)
    )  # Kenya Revenue Authority PIN
    payment_terms: Mapped[str | None] = mapped_column(
        String(100)
    )  # net_30, net_60, cod
    category: Mapped[str | None] = mapped_column(
        String(50)
    )  # medical, surgical, general, equipment
    rating: Mapped[int | None] = mapped_column(Integer)  # 1-5
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class PurchaseOrder(AuditMixin, Base):
    """Purchase order for procurement."""

    __tablename__ = "purchase_orders"
    __table_args__ = (
        Index("ix_purchase_orders_status", "facility_id", "status"),
        Index("ix_purchase_orders_supplier", "facility_id", "supplier_id"),
    )

    po_number: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # PO-YYYYMMDD-XXXX
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False
    )
    order_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expected_delivery: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft, submitted, approved, ordered, partial, received, cancelled

    subtotal: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # KES cents
    tax_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivery_address: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)


class PurchaseOrderItem(AuditMixin, Base):
    """Line item on a purchase order."""

    __tablename__ = "purchase_order_items"
    __table_args__ = (Index("ix_po_items_order", "purchase_order_id"),)

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("purchase_orders.id"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inventory_items.id"), nullable=False
    )
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_cost: Mapped[int] = mapped_column(Integer, nullable=False)  # KES cents
    total_cost: Mapped[int] = mapped_column(Integer, nullable=False)  # KES cents
    notes: Mapped[str | None] = mapped_column(Text)
