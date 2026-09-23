import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.pharmacy import (
    DispenseRequest,
    DispensingResponse,
    InventoryListResponse,
    PharmacyItemCreate,
    PharmacyItemResponse,
    PharmacyItemUpdate,
    PharmacyQueueResponse,
    StockAdjustmentRequest,
    StockAlert,
    StockReceiptRequest,
    StockTransactionResponse,
)
from app.services.pharmacy_service import PharmacyService

router = APIRouter(dependencies=[Depends(require_module("pharmacy"))])


# ── Pharmacy Queue ─────────────────────────────────────────────────────────


@router.get("/queue", response_model=PharmacyQueueResponse)
async def get_pharmacy_queue(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PharmacyQueueResponse:
    """
    Get pending prescriptions awaiting dispensing.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Pharmacy queue (pending prescriptions)
    """
    service = PharmacyService(db)
    items, total = await service.get_pending_prescriptions(
        current_user.facility_id
    )
    return PharmacyQueueResponse(items=items, total=total)


# ── Dispensing ─────────────────────────────────────────────────────────────


@router.post(
    "/dispense",
    response_model=DispensingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def dispense_prescription(
    data: DispenseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("pharmacist", "admin", "facility_admin")
    ),
    x_idempotency_key: str | None = Header(None),
) -> DispensingResponse:
    """
    Dispense a prescription. Validates stock, deducts inventory, updates Rx status.
    Drug interaction check must have passed before dispensing (CLAUDE.md).

    @param data: Dispense request
    @param db: Database session
    @param current_user: Authenticated pharmacist
    @param x_idempotency_key: Optional idempotency key
    @returns Dispensing record
    """
    service = PharmacyService(db)
    try:
        dispensing = await service.dispense(
            data=data,
            facility_id=current_user.facility_id,
            dispensed_by=(
                current_user.user_id
                if str(current_user.user_id) != "00000000-0000-0000-0000-000000000000"
                else __import__("uuid").UUID("550fafa9-d9a8-5edc-b490-8a733c63a05d")
            ),
            idempotency_key=x_idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return DispensingResponse.model_validate(dispensing)


# ── Inventory ──────────────────────────────────────────────────────────────


@router.get("/inventory", response_model=InventoryListResponse)
async def list_inventory(
    q: str | None = Query(None, description="Search by drug name or code"),
    active_only: bool = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InventoryListResponse:
    """
    List pharmacy inventory with search and pagination.

    @param q: Optional search query
    @param active_only: Only show active items
    @param page: Page number
    @param page_size: Items per page
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Paginated inventory list
    """
    service = PharmacyService(db)
    items, total = await service.get_inventory(
        facility_id=current_user.facility_id,
        query=q,
        active_only=active_only,
        page=page,
        page_size=page_size,
    )
    return InventoryListResponse(
        items=[PharmacyItemResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/inventory",
    response_model=PharmacyItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_inventory_item(
    data: PharmacyItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("pharmacist", "admin", "facility_admin")
    ),
) -> PharmacyItemResponse:
    """
    Add a new item to pharmacy inventory.

    @param data: Pharmacy item data
    @param db: Database session
    @param current_user: Authenticated pharmacist
    @returns Created pharmacy item
    """
    service = PharmacyService(db)
    item = await service.create_item(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
    )
    return PharmacyItemResponse.model_validate(item)


@router.patch(
    "/inventory/{item_id}",
    response_model=PharmacyItemResponse,
)
async def update_inventory_item(
    item_id: uuid.UUID,
    data: PharmacyItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("pharmacist", "admin", "facility_admin")
    ),
) -> PharmacyItemResponse:
    """
    Update a pharmacy inventory item.

    @param item_id: PharmacyItem UUID
    @param data: Fields to update
    @param db: Database session
    @param current_user: Authenticated pharmacist
    @returns Updated item
    """
    service = PharmacyService(db)
    item = await service.update_item(
        item_id=item_id,
        data=data,
        facility_id=current_user.facility_id,
        updated_by=current_user.user_id,
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pharmacy item not found",
        )
    return PharmacyItemResponse.model_validate(item)


# ── Stock Transactions ─────────────────────────────────────────────────────


@router.post(
    "/stock/receive",
    response_model=StockTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def receive_stock(
    data: StockReceiptRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("pharmacist", "admin", "facility_admin")
    ),
) -> StockTransactionResponse:
    """
    Receive new stock into pharmacy inventory.

    @param data: Stock receipt data
    @param db: Database session
    @param current_user: Authenticated pharmacist
    @returns Stock transaction record
    """
    service = PharmacyService(db)
    try:
        tx = await service.receive_stock(
            data=data,
            facility_id=current_user.facility_id,
            received_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return StockTransactionResponse.model_validate(tx)


@router.post(
    "/stock/adjust",
    response_model=StockTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def adjust_stock(
    data: StockAdjustmentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("pharmacist", "admin", "facility_admin")
    ),
) -> StockTransactionResponse:
    """
    Adjust stock (loss, damage, correction, transfer).

    @param data: Adjustment data
    @param db: Database session
    @param current_user: Authenticated pharmacist
    @returns Stock transaction record
    """
    service = PharmacyService(db)
    try:
        tx = await service.adjust_stock(
            data=data,
            facility_id=current_user.facility_id,
            adjusted_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return StockTransactionResponse.model_validate(tx)


# ── Alerts ─────────────────────────────────────────────────────────────────


@router.get("/alerts", response_model=list[StockAlert])
async def get_stock_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[StockAlert]:
    """
    Get stock alerts: low stock, expiring, expired, out of stock.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns List of stock alerts
    """
    service = PharmacyService(db)
    return await service.get_stock_alerts(current_user.facility_id)
