import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.inventory import (
    InventoryItemCreate,
    InventoryItemListResponse,
    InventoryItemResponse,
    InventorySummary,
    InventoryTransactionCreate,
    InventoryTransactionResponse,
    PurchaseOrderCreate,
    PurchaseOrderListResponse,
    PurchaseOrderResponse,
    ReceiveItemRequest,
    SupplierCreate,
    SupplierListResponse,
    SupplierResponse,
    TransactionListResponse,
)
from app.services.inventory_service import InventoryService

router = APIRouter(dependencies=[Depends(require_module("inventory"))])


# ── Summary ──────────────────────────────────────────────────────────────────


@router.get("/summary", response_model=InventorySummary)
async def get_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InventorySummary:
    """
    Get inventory summary stats.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Inventory summary
    """
    service = InventoryService(db)
    return await service.get_summary(facility_id=current_user.facility_id)


# ── Items ────────────────────────────────────────────────────────────────────


@router.get("/items", response_model=InventoryItemListResponse)
async def list_items(
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search by name or code"),
    low_stock: bool = Query(False, description="Show only low/out of stock"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InventoryItemListResponse:
    """
    Get inventory items.

    @param category: Optional category filter
    @param search: Optional search query
    @param low_stock: Low stock filter flag
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Item list
    """
    service = InventoryService(db)
    items = await service.get_items(
        facility_id=current_user.facility_id,
        category=category,
        search=search,
        low_stock_only=low_stock,
    )
    return InventoryItemListResponse(items=items, total=len(items))


@router.post("/items", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    data: InventoryItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "store_keeper")
    ),
) -> InventoryItemResponse:
    """
    Create a new inventory item.

    @param data: Item data
    @param db: Database session
    @param current_user: Authenticated admin/store keeper
    @returns Created item
    """
    service = InventoryService(db)
    item = await service.create_item(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return InventoryItemResponse.model_validate(item)


@router.get("/items/{item_id}", response_model=InventoryItemResponse)
async def get_item(
    item_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InventoryItemResponse:
    """
    Get a single inventory item.

    @param item_id: Item UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Item details
    """
    service = InventoryService(db)
    item = await service.get_item(item_id=item_id, facility_id=current_user.facility_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return InventoryItemResponse.model_validate(item)


# ── Transactions ─────────────────────────────────────────────────────────────


@router.get("/transactions", response_model=TransactionListResponse)
async def list_transactions(
    item_id: uuid.UUID | None = Query(None, description="Filter by item"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> TransactionListResponse:
    """
    Get inventory transactions.

    @param item_id: Optional item filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Transaction list
    """
    service = InventoryService(db)
    items = await service.get_transactions(
        facility_id=current_user.facility_id,
        item_id=item_id,
    )
    return TransactionListResponse(
        items=[InventoryTransactionResponse.model_validate(t) for t in items],
        total=len(items),
    )


@router.post(
    "/transactions",
    response_model=InventoryTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transaction(
    data: InventoryTransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "store_keeper", "nurse")
    ),
) -> InventoryTransactionResponse:
    """
    Record a stock transaction.

    @param data: Transaction data
    @param db: Database session
    @param current_user: Authenticated staff
    @returns Created transaction
    """
    service = InventoryService(db)
    try:
        txn = await service.create_transaction(
            data=data,
            facility_id=current_user.facility_id,
            created_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    if not txn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found")
    return InventoryTransactionResponse.model_validate(txn)


# ── Suppliers ────────────────────────────────────────────────────────────────


@router.get("/suppliers", response_model=SupplierListResponse)
async def list_suppliers(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> SupplierListResponse:
    """
    Get active suppliers.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Supplier list
    """
    service = InventoryService(db)
    suppliers = await service.get_suppliers(facility_id=current_user.facility_id)
    return SupplierListResponse(
        items=[SupplierResponse.model_validate(s) for s in suppliers],
        total=len(suppliers),
    )


@router.post(
    "/suppliers",
    response_model=SupplierResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_supplier(
    data: SupplierCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "store_keeper")
    ),
) -> SupplierResponse:
    """
    Create a supplier.

    @param data: Supplier data
    @param db: Database session
    @param current_user: Authenticated admin/store keeper
    @returns Created supplier
    """
    service = InventoryService(db)
    supplier = await service.create_supplier(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return SupplierResponse.model_validate(supplier)


# ── Purchase Orders ──────────────────────────────────────────────────────────


@router.get("/purchase-orders", response_model=PurchaseOrderListResponse)
async def list_purchase_orders(
    po_status: str | None = Query(None, alias="status", description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PurchaseOrderListResponse:
    """
    Get purchase orders.

    @param po_status: Optional status filter
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns PO list
    """
    service = InventoryService(db)
    items = await service.get_purchase_orders(
        facility_id=current_user.facility_id,
        status=po_status,
    )
    return PurchaseOrderListResponse(items=items, total=len(items))


@router.post(
    "/purchase-orders",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "store_keeper")
    ),
) -> PurchaseOrderResponse:
    """
    Create a purchase order.

    @param data: PO data with items
    @param db: Database session
    @param current_user: Authenticated admin/store keeper
    @returns Created PO
    """
    service = InventoryService(db)
    po = await service.create_purchase_order(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    detail = await service.get_purchase_order(po.id, current_user.facility_id)
    if not detail:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="PO creation failed")
    return detail


@router.get("/purchase-orders/{po_id}", response_model=PurchaseOrderResponse)
async def get_purchase_order(
    po_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PurchaseOrderResponse:
    """
    Get a purchase order detail.

    @param po_id: PO UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns PO details
    """
    service = InventoryService(db)
    po = await service.get_purchase_order(po_id, current_user.facility_id)
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    return po


@router.post("/purchase-orders/{po_id}/approve", response_model=PurchaseOrderResponse)
async def approve_purchase_order(
    po_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> PurchaseOrderResponse:
    """
    Approve a purchase order.

    @param po_id: PO UUID
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Updated PO
    """
    service = InventoryService(db)
    po = await service.approve_po(po_id, current_user.facility_id, current_user.user_id)
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    detail = await service.get_purchase_order(po.id, current_user.facility_id)
    return detail  # type: ignore[return-value]


@router.post("/purchase-orders/receive", response_model=InventoryTransactionResponse)
async def receive_po_item(
    data: ReceiveItemRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin", "store_keeper")
    ),
) -> InventoryTransactionResponse:
    """
    Receive items against a purchase order.

    @param data: Receive data
    @param db: Database session
    @param current_user: Authenticated store keeper
    @returns Updated PO item
    """
    service = InventoryService(db)
    po_item = await service.receive_po_item(
        data=data,
        facility_id=current_user.facility_id,
        received_by=current_user.user_id,
    )
    if not po_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PO item not found")
    # Return the latest transaction for this receipt
    txns = await service.get_transactions(current_user.facility_id, po_item.item_id)
    return InventoryTransactionResponse.model_validate(txns[0])
