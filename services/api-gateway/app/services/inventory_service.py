import uuid
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import (
    InventoryItem,
    InventoryTransaction,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
)
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemListItem,
    InventorySummary,
    InventoryTransactionCreate,
    POItemResponse,
    PurchaseOrderCreate,
    PurchaseOrderListItem,
    PurchaseOrderResponse,
    ReceiveItemRequest,
    SupplierCreate,
)


class InventoryService:
    """
    Service for inventory management: items, stock transactions,
    suppliers, and purchase orders.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Items ────────────────────────────────────────────────────────────

    async def create_item(
        self,
        data: InventoryItemCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> InventoryItem:
        """
        Create a new inventory item with auto-generated item code.

        @param data: Item data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created inventory item
        """
        count_result = await self.db.execute(
            select(func.count(InventoryItem.id)).where(
                InventoryItem.facility_id == facility_id,
                InventoryItem.is_deleted == False,  # noqa: E712
            )
        )
        seq = (count_result.scalar() or 0) + 1
        item_code = f"INV-{seq:06d}"

        item = InventoryItem(
            facility_id=facility_id,
            item_code=item_code,
            name=data.name,
            description=data.description,
            category=data.category,
            sub_category=data.sub_category,
            unit_of_measure=data.unit_of_measure,
            unit_cost=data.unit_cost,
            reorder_level=data.reorder_level,
            reorder_quantity=data.reorder_quantity,
            max_stock=data.max_stock,
            store_location=data.store_location,
            department_id=data.department_id,
            specifications=data.specifications,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        return item

    async def get_items(
        self,
        facility_id: uuid.UUID,
        category: str | None = None,
        search: str | None = None,
        low_stock_only: bool = False,
    ) -> list[InventoryItemListItem]:
        """
        Get inventory items with stock status.

        @param facility_id: Facility UUID
        @param category: Optional category filter
        @param search: Optional search query
        @param low_stock_only: Only show low/out of stock items
        @returns List of inventory items
        """
        query = select(InventoryItem).where(
            InventoryItem.facility_id == facility_id,
            InventoryItem.is_deleted == False,  # noqa: E712
        )

        if category:
            query = query.where(InventoryItem.category == category)
        if search:
            pattern = f"%{search}%"
            query = query.where(
                (InventoryItem.name.ilike(pattern)) | (InventoryItem.item_code.ilike(pattern))
            )
        if low_stock_only:
            query = query.where(InventoryItem.current_stock <= InventoryItem.reorder_level)

        query = query.order_by(InventoryItem.name.asc())
        result = await self.db.execute(query)
        items = result.scalars().all()

        return [
            InventoryItemListItem(
                id=i.id,
                item_code=i.item_code,
                name=i.name,
                category=i.category,
                unit_of_measure=i.unit_of_measure,
                unit_cost=i.unit_cost,
                current_stock=i.current_stock,
                reorder_level=i.reorder_level,
                is_active=i.is_active,
                stock_status=(
                    "out" if i.current_stock <= 0
                    else "low" if i.current_stock <= i.reorder_level
                    else "ok"
                ),
            )
            for i in items
        ]

    async def get_item(
        self, item_id: uuid.UUID, facility_id: uuid.UUID
    ) -> InventoryItem | None:
        """
        Get a single inventory item.

        @param item_id: Item UUID
        @param facility_id: Facility UUID
        @returns Inventory item or None
        """
        result = await self.db.execute(
            select(InventoryItem).where(
                InventoryItem.id == item_id,
                InventoryItem.facility_id == facility_id,
                InventoryItem.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    # ── Transactions ─────────────────────────────────────────────────────

    async def create_transaction(
        self,
        data: InventoryTransactionCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> InventoryTransaction | None:
        """
        Record a stock transaction and update item balance.

        @param data: Transaction data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created transaction or None if item not found
        """
        # Lock the item row to prevent concurrent stock miscalculations
        result = await self.db.execute(
            select(InventoryItem).where(
                InventoryItem.id == data.item_id,
                InventoryItem.facility_id == facility_id,
                InventoryItem.is_deleted == False,  # noqa: E712
            ).with_for_update()
        )
        item = result.scalar_one_or_none()
        if not item:
            return None

        # Determine signed quantity
        outgoing = {"issue", "write_off", "transfer"}
        qty = -abs(data.quantity) if data.transaction_type in outgoing else abs(data.quantity)

        new_balance = item.current_stock + qty
        if new_balance < 0:
            raise ValueError(
                f"Insufficient stock: {item.current_stock} on hand, "
                f"{abs(qty)} requested for {data.transaction_type}"
            )
        total_cost = abs(qty) * data.unit_cost

        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")
        count_result = await self.db.execute(
            select(func.count(InventoryTransaction.id)).where(
                InventoryTransaction.facility_id == facility_id,
                InventoryTransaction.reference_number.like(f"TXN-{date_part}-%"),
            )
        )
        seq = (count_result.scalar() or 0) + 1
        ref = f"TXN-{date_part}-{seq:04d}"

        txn = InventoryTransaction(
            facility_id=facility_id,
            item_id=data.item_id,
            transaction_type=data.transaction_type,
            quantity=qty,
            balance_after=new_balance,
            unit_cost=data.unit_cost,
            total_cost=total_cost,
            transaction_date=now,
            reference_number=ref,
            department_id=data.department_id,
            issued_to=data.issued_to,
            reason=data.reason,
            batch_number=data.batch_number,
            expiry_date=data.expiry_date,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(txn)

        item.current_stock = new_balance
        item.updated_by = created_by
        await self.db.flush()
        await self.db.refresh(txn)
        return txn

    async def get_transactions(
        self,
        facility_id: uuid.UUID,
        item_id: uuid.UUID | None = None,
    ) -> list[InventoryTransaction]:
        """
        Get inventory transactions.

        @param facility_id: Facility UUID
        @param item_id: Optional item filter
        @returns List of transactions
        """
        query = select(InventoryTransaction).where(
            InventoryTransaction.facility_id == facility_id,
            InventoryTransaction.is_deleted == False,  # noqa: E712
        )
        if item_id:
            query = query.where(InventoryTransaction.item_id == item_id)
        query = query.order_by(InventoryTransaction.transaction_date.desc()).limit(200)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # ── Suppliers ────────────────────────────────────────────────────────

    async def get_suppliers(self, facility_id: uuid.UUID) -> list[Supplier]:
        """
        Get all active suppliers.

        @param facility_id: Facility UUID
        @returns List of suppliers
        """
        result = await self.db.execute(
            select(Supplier).where(
                Supplier.facility_id == facility_id,
                Supplier.is_deleted == False,  # noqa: E712
                Supplier.is_active == True,  # noqa: E712
            ).order_by(Supplier.name.asc())
        )
        return list(result.scalars().all())

    async def create_supplier(
        self,
        data: SupplierCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> Supplier:
        """
        Create a new supplier.

        @param data: Supplier data
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created supplier
        """
        count_result = await self.db.execute(
            select(func.count(Supplier.id)).where(
                Supplier.facility_id == facility_id,
                Supplier.is_deleted == False,  # noqa: E712
            )
        )
        seq = (count_result.scalar() or 0) + 1
        code = f"SUP-{seq:04d}"

        supplier = Supplier(
            facility_id=facility_id,
            name=data.name,
            supplier_code=code,
            contact_person=data.contact_person,
            phone=data.phone,
            email=data.email,
            address=data.address,
            kra_pin=data.kra_pin,
            payment_terms=data.payment_terms,
            category=data.category,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(supplier)
        await self.db.flush()
        await self.db.refresh(supplier)
        return supplier

    # ── Purchase Orders ──────────────────────────────────────────────────

    async def create_purchase_order(
        self,
        data: PurchaseOrderCreate,
        facility_id: uuid.UUID,
        created_by: uuid.UUID,
    ) -> PurchaseOrder:
        """
        Create a purchase order with line items.

        @param data: PO data with items
        @param facility_id: Facility UUID
        @param created_by: Staff UUID
        @returns Created purchase order
        """
        now = datetime.now(UTC)
        date_part = now.strftime("%Y%m%d")
        count_result = await self.db.execute(
            select(func.count(PurchaseOrder.id)).where(
                PurchaseOrder.facility_id == facility_id,
                PurchaseOrder.po_number.like(f"PO-{date_part}-%"),
            )
        )
        seq = (count_result.scalar() or 0) + 1
        po_number = f"PO-{date_part}-{seq:04d}"

        subtotal = sum(i.quantity_ordered * i.unit_cost for i in data.items)
        tax = int(subtotal * 0.16)  # 16% VAT Kenya
        total = subtotal + tax

        po = PurchaseOrder(
            facility_id=facility_id,
            po_number=po_number,
            supplier_id=data.supplier_id,
            order_date=now,
            expected_delivery=data.expected_delivery,
            status="draft",
            subtotal=subtotal,
            tax_amount=tax,
            total_amount=total,
            delivery_address=data.delivery_address,
            notes=data.notes,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(po)
        await self.db.flush()

        for line in data.items:
            po_item = PurchaseOrderItem(
                facility_id=facility_id,
                purchase_order_id=po.id,
                item_id=line.item_id,
                quantity_ordered=line.quantity_ordered,
                unit_cost=line.unit_cost,
                total_cost=line.quantity_ordered * line.unit_cost,
                created_by=created_by,
                updated_by=created_by,
            )
            self.db.add(po_item)

        await self.db.flush()
        await self.db.refresh(po)
        return po

    async def get_purchase_orders(
        self,
        facility_id: uuid.UUID,
        status: str | None = None,
    ) -> list[PurchaseOrderListItem]:
        """
        Get purchase orders with supplier names.

        @param facility_id: Facility UUID
        @param status: Optional status filter
        @returns List of purchase orders
        """
        query = (
            select(
                PurchaseOrder,
                Supplier.name.label("supplier_name"),
                func.count(PurchaseOrderItem.id).label("item_count"),
            )
            .join(Supplier, PurchaseOrder.supplier_id == Supplier.id)
            .outerjoin(PurchaseOrderItem, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
            .where(
                PurchaseOrder.facility_id == facility_id,
                PurchaseOrder.is_deleted == False,  # noqa: E712
            )
            .group_by(PurchaseOrder.id, Supplier.name)
        )
        if status:
            query = query.where(PurchaseOrder.status == status)
        query = query.order_by(PurchaseOrder.order_date.desc())

        result = await self.db.execute(query)
        rows = result.all()

        return [
            PurchaseOrderListItem(
                id=po.id,
                po_number=po.po_number,
                supplier_name=s_name,
                order_date=po.order_date,
                status=po.status,
                total_amount=po.total_amount,
                item_count=count,
            )
            for po, s_name, count in rows
        ]

    async def get_purchase_order(
        self, po_id: uuid.UUID, facility_id: uuid.UUID
    ) -> PurchaseOrderResponse | None:
        """
        Get a purchase order with items and supplier name.

        @param po_id: PO UUID
        @param facility_id: Facility UUID
        @returns PO response or None
        """
        result = await self.db.execute(
            select(PurchaseOrder, Supplier.name.label("supplier_name"))
            .join(Supplier, PurchaseOrder.supplier_id == Supplier.id)
            .where(
                PurchaseOrder.id == po_id,
                PurchaseOrder.facility_id == facility_id,
                PurchaseOrder.is_deleted == False,  # noqa: E712
            )
        )
        row = result.one_or_none()
        if not row:
            return None

        po, supplier_name = row

        items_result = await self.db.execute(
            select(PurchaseOrderItem, InventoryItem.name.label("item_name"))
            .join(InventoryItem, PurchaseOrderItem.item_id == InventoryItem.id)
            .where(PurchaseOrderItem.purchase_order_id == po.id)
        )
        po_items = [
            POItemResponse(
                id=pi.id,
                item_id=pi.item_id,
                item_name=iname,
                quantity_ordered=pi.quantity_ordered,
                quantity_received=pi.quantity_received,
                unit_cost=pi.unit_cost,
                total_cost=pi.total_cost,
            )
            for pi, iname in items_result.all()
        ]

        return PurchaseOrderResponse(
            id=po.id,
            po_number=po.po_number,
            supplier_id=po.supplier_id,
            supplier_name=supplier_name,
            order_date=po.order_date,
            expected_delivery=po.expected_delivery,
            status=po.status,
            subtotal=po.subtotal,
            tax_amount=po.tax_amount,
            total_amount=po.total_amount,
            approved_by=po.approved_by,
            approved_at=po.approved_at,
            delivery_address=po.delivery_address,
            notes=po.notes,
            items=po_items,
            created_at=po.created_at,
        )

    async def approve_po(
        self, po_id: uuid.UUID, facility_id: uuid.UUID, approved_by: uuid.UUID
    ) -> PurchaseOrder | None:
        """
        Approve a purchase order.

        @param po_id: PO UUID
        @param facility_id: Facility UUID
        @param approved_by: Staff UUID
        @returns Updated PO or None
        """
        result = await self.db.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.id == po_id,
                PurchaseOrder.facility_id == facility_id,
                PurchaseOrder.is_deleted == False,  # noqa: E712
            )
        )
        po = result.scalar_one_or_none()
        if not po:
            return None

        po.status = "approved"
        po.approved_by = approved_by
        po.approved_at = datetime.now(UTC)
        po.updated_by = approved_by
        await self.db.flush()
        await self.db.refresh(po)
        return po

    async def receive_po_item(
        self,
        data: ReceiveItemRequest,
        facility_id: uuid.UUID,
        received_by: uuid.UUID,
    ) -> PurchaseOrderItem | None:
        """
        Receive items against a PO line and update inventory.

        @param data: Receive data
        @param facility_id: Facility UUID
        @param received_by: Staff UUID
        @returns Updated PO item or None
        """
        # Verify PO item belongs to this facility via parent PurchaseOrder
        result = await self.db.execute(
            select(PurchaseOrderItem)
            .join(PurchaseOrder, PurchaseOrderItem.purchase_order_id == PurchaseOrder.id)
            .where(
                PurchaseOrderItem.id == data.po_item_id,
                PurchaseOrder.facility_id == facility_id,
            )
        )
        po_item = result.scalar_one_or_none()
        if not po_item:
            return None

        po_item.quantity_received += data.quantity_received
        po_item.updated_by = received_by

        # Create inventory transaction for receipt
        txn_data = InventoryTransactionCreate(
            item_id=po_item.item_id,
            transaction_type="receipt",
            quantity=data.quantity_received,
            unit_cost=po_item.unit_cost,
            reason="PO receipt",
            batch_number=data.batch_number,
            expiry_date=data.expiry_date,
        )
        await self.create_transaction(txn_data, facility_id, received_by)

        # Check if full PO is received
        po_result = await self.db.execute(
            select(PurchaseOrder).where(PurchaseOrder.id == po_item.purchase_order_id)
        )
        po = po_result.scalar_one_or_none()
        if po:
            all_items = await self.db.execute(
                select(PurchaseOrderItem).where(
                    PurchaseOrderItem.purchase_order_id == po.id
                )
            )
            items = all_items.scalars().all()
            fully_received = all(i.quantity_received >= i.quantity_ordered for i in items)
            partially_received = any(i.quantity_received > 0 for i in items)

            if fully_received:
                po.status = "received"
            elif partially_received:
                po.status = "partial"
            po.updated_by = received_by

        await self.db.flush()
        await self.db.refresh(po_item)
        return po_item

    # ── Summary ──────────────────────────────────────────────────────────

    async def get_summary(self, facility_id: uuid.UUID) -> InventorySummary:
        """
        Get inventory summary stats.

        @param facility_id: Facility UUID
        @returns Summary stats
        """
        today = date.today()
        base = [InventoryItem.facility_id == facility_id, InventoryItem.is_deleted == False]  # noqa: E712

        total = await self.db.execute(select(func.count(InventoryItem.id)).where(*base))
        active = await self.db.execute(
            select(func.count(InventoryItem.id)).where(*base, InventoryItem.is_active == True)  # noqa: E712
        )
        low = await self.db.execute(
            select(func.count(InventoryItem.id)).where(
                *base,
                InventoryItem.current_stock > 0,
                InventoryItem.current_stock <= InventoryItem.reorder_level,
            )
        )
        out = await self.db.execute(
            select(func.count(InventoryItem.id)).where(*base, InventoryItem.current_stock <= 0)
        )
        value = await self.db.execute(
            select(func.sum(InventoryItem.current_stock * InventoryItem.unit_cost)).where(*base)
        )
        pending_po = await self.db.execute(
            select(func.count(PurchaseOrder.id)).where(
                PurchaseOrder.facility_id == facility_id,
                PurchaseOrder.is_deleted == False,  # noqa: E712
                PurchaseOrder.status.in_(["draft", "submitted", "approved", "ordered", "partial"]),
            )
        )
        suppliers = await self.db.execute(
            select(func.count(Supplier.id)).where(
                Supplier.facility_id == facility_id,
                Supplier.is_deleted == False,  # noqa: E712
                Supplier.is_active == True,  # noqa: E712
            )
        )
        txns = await self.db.execute(
            select(func.count(InventoryTransaction.id)).where(
                InventoryTransaction.facility_id == facility_id,
                func.date(InventoryTransaction.transaction_date) == today,
            )
        )

        return InventorySummary(
            total_items=total.scalar() or 0,
            active_items=active.scalar() or 0,
            low_stock_items=low.scalar() or 0,
            out_of_stock_items=out.scalar() or 0,
            total_stock_value=value.scalar() or 0,
            pending_orders=pending_po.scalar() or 0,
            suppliers_count=suppliers.scalar() or 0,
            transactions_today=txns.scalar() or 0,
        )
