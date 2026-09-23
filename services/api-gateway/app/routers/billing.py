import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user, require_roles
from app.auth.license_check import require_module
from app.database import get_db
from app.schemas.billing import (
    BillingSummary,
    InvoiceCreate,
    InvoiceDetail,
    InvoiceItemResponse,
    InvoiceListResponse,
    InvoiceResponse,
    InvoiceWaiveRequest,
    PaymentCreate,
    PaymentResponse,
    ServiceChargeListResponse,
    ServiceChargeResponse,
    ServicePaymentRequest,
    ServicePaymentResponse,
)
from app.services.billing_service import BillingService
from app.services.service_billing import ServiceBillingService, ServiceCharge

router = APIRouter(dependencies=[Depends(require_module("billing"))])


# ── Dashboard Summary ─────────────────────────────────────────────────────────


@router.get("/summary", response_model=BillingSummary)
async def get_billing_summary(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> BillingSummary:
    """
    Get billing dashboard summary stats.

    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Billing summary with counts and totals
    """
    service = BillingService(db)
    return await service.get_summary(current_user.facility_id)


# ── Invoice List ──────────────────────────────────────────────────────────────


@router.get("/invoices", response_model=InvoiceListResponse)
async def list_invoices(
    status_filter: str | None = Query(None, alias="status"),
    patient_id: uuid.UUID | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InvoiceListResponse:
    """
    List invoices with optional filtering and pagination.

    @param status_filter: Filter by invoice status
    @param patient_id: Filter by patient
    @param page: Page number
    @param page_size: Items per page
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Paginated invoice list
    """
    service = BillingService(db)
    items, total = await service.get_invoices(
        facility_id=current_user.facility_id,
        status_filter=status_filter,
        patient_id=patient_id,
        page=page,
        page_size=page_size,
    )
    return InvoiceListResponse(
        items=items, total=total, page=page, page_size=page_size
    )


# ── Create Invoice ────────────────────────────────────────────────────────────


@router.post(
    "/invoices",
    response_model=InvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invoice(
    data: InvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("billing_clerk", "cashier", "admin", "facility_admin")
    ),
    x_idempotency_key: str | None = Header(None),
) -> InvoiceResponse:
    """
    Create a new invoice with line items.

    @param data: Invoice data with items
    @param db: Database session
    @param current_user: Authenticated billing staff
    @param x_idempotency_key: Optional idempotency key
    @returns Created invoice
    """
    service = BillingService(db)
    invoice = await service.create_invoice(
        data=data,
        facility_id=current_user.facility_id,
        created_by=current_user.user_id,
        idempotency_key=x_idempotency_key,
    )
    return InvoiceResponse.model_validate(invoice)


# ── Invoice Detail ────────────────────────────────────────────────────────────


@router.get("/invoices/{invoice_id}", response_model=InvoiceDetail)
async def get_invoice_detail(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InvoiceDetail:
    """
    Get invoice with all line items and patient info.

    @param invoice_id: Invoice UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Full invoice detail
    """
    service = BillingService(db)
    invoice, items, patient_name, patient_mrn = await service.get_invoice_detail(
        invoice_id=invoice_id,
        facility_id=current_user.facility_id,
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    return InvoiceDetail(
        invoice=InvoiceResponse.model_validate(invoice),
        items=[InvoiceItemResponse.model_validate(i) for i in items],
        patient_name=patient_name,
        patient_mrn=patient_mrn,
    )


@router.get("/invoices/{invoice_id}/receipt")
async def get_invoice_receipt(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """
    Render a printable A4 PDF receipt for an invoice with its payments.

    @param invoice_id: Invoice UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns application/pdf response
    """
    from sqlalchemy import select as sa_select

    from app.models.facility import Facility
    from app.services.receipt_pdf import receipt_filename, render_receipt_pdf

    service = BillingService(db)
    invoice, items, patient_name, patient_mrn = await service.get_invoice_detail(
        invoice_id=invoice_id,
        facility_id=current_user.facility_id,
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    payments = await service.get_invoice_payments(
        invoice_id=invoice_id, facility_id=current_user.facility_id
    )

    facility_row = await db.execute(
        sa_select(Facility.name).where(Facility.id == current_user.facility_id)
    )
    facility_name = facility_row.scalar_one_or_none() or "Aifya Health Facility"

    pdf = render_receipt_pdf(
        facility_name=facility_name,
        invoice={
            "id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "status": invoice.status,
            "subtotal_cents": invoice.subtotal_cents,
            "discount_cents": invoice.discount_cents,
            "total_cents": invoice.total_cents,
            "paid_cents": invoice.paid_cents,
            "balance_cents": invoice.balance_cents,
        },
        items=[
            {
                "description": i.description,
                "quantity": i.quantity,
                "unit_price_cents": i.unit_price_cents,
                "total_cents": i.total_cents,
            }
            for i in items
        ],
        payments=[
            {
                "paid_at": p.paid_at.strftime("%Y-%m-%d %H:%M") if p.paid_at else "",
                "payment_method": p.payment_method,
                "reference_number": p.reference_number,
                "amount_cents": p.amount_cents,
            }
            for p in payments
        ],
        patient_name=patient_name,
        patient_mrn=patient_mrn,
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'inline; filename="{receipt_filename(invoice.invoice_number)}"'
            )
        },
    )


# ── Finalize Invoice ─────────────────────────────────────────────────────────


@router.post(
    "/invoices/{invoice_id}/finalize",
    response_model=InvoiceResponse,
)
async def finalize_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("billing_clerk", "cashier", "admin", "facility_admin")
    ),
) -> InvoiceResponse:
    """
    Finalize a draft invoice (locks for payment collection).

    @param invoice_id: Invoice UUID
    @param db: Database session
    @param current_user: Authenticated billing staff
    @returns Finalized invoice
    """
    service = BillingService(db)
    try:
        invoice = await service.finalize_invoice(
            invoice_id=invoice_id,
            facility_id=current_user.facility_id,
            finalized_by=current_user.user_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    return InvoiceResponse.model_validate(invoice)


# ── Record Payment ────────────────────────────────────────────────────────────


@router.post(
    "/invoices/{invoice_id}/pay",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_payment(
    invoice_id: uuid.UUID,
    data: PaymentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(
            "receptionist", "billing_clerk", "cashier", "admin", "facility_admin"
        )
    ),
    x_idempotency_key: str | None = Header(None),
) -> PaymentResponse:
    """
    Record a payment against an invoice. Supports partial payments.

    @param invoice_id: Invoice UUID
    @param data: Payment data
    @param db: Database session
    @param current_user: Authenticated cashier / billing staff
    @param x_idempotency_key: Optional idempotency key
    @returns Created payment record
    """
    service = BillingService(db)
    try:
        payment = await service.record_payment(
            invoice_id=invoice_id,
            data=data,
            facility_id=current_user.facility_id,
            received_by=current_user.user_id,
            idempotency_key=x_idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    return PaymentResponse.model_validate(payment)


# ── Waive Invoice ─────────────────────────────────────────────────────────────


@router.post(
    "/invoices/{invoice_id}/waive",
    response_model=InvoiceResponse,
)
async def waive_invoice(
    invoice_id: uuid.UUID,
    data: InvoiceWaiveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles("admin", "facility_admin")
    ),
) -> InvoiceResponse:
    """
    Waive remaining balance on an invoice (exemption/charity).
    Restricted to admin roles.

    @param invoice_id: Invoice UUID
    @param data: Waiver reason
    @param db: Database session
    @param current_user: Authenticated admin
    @returns Updated invoice
    """
    service = BillingService(db)
    invoice = await service.waive_invoice(
        invoice_id=invoice_id,
        facility_id=current_user.facility_id,
        waived_by=current_user.user_id,
        reason=data.reason,
    )
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found",
        )
    return InvoiceResponse.model_validate(invoice)

# Point of sale: ordered services (lab, imaging, pharmacy)


def _charge_list(charges: list[ServiceCharge]) -> ServiceChargeListResponse:
    """
    Shape service charges for the point-of-sale screen.

    @param charges: Charges to report (paid or unpaid)
    @returns Response with lines and the outstanding total
    """
    return ServiceChargeListResponse(
        items=[ServiceChargeResponse.model_validate(c) for c in charges],
        total_outstanding_cents=sum(c.balance_cents for c in charges),
    )


@router.get(
    "/pos/encounters/{encounter_id}/charges",
    response_model=ServiceChargeListResponse,
)
async def get_pos_encounter_charges(
    encounter_id: uuid.UUID,
    include_paid: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ServiceChargeListResponse:
    """
    List what a visit still owes for ordered services.

    Covers lab requests, imaging studies and prescriptions, so the cashier can
    collect before the patient reaches the service desk.

    @param encounter_id: Encounter UUID
    @param include_paid: Keep settled requests in the result
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Charges with the outstanding total
    """
    charges = await ServiceBillingService(db).list_charges(
        encounter_id, current_user.facility_id
    )
    if not include_paid:
        charges = [c for c in charges if not c.paid]
    return _charge_list(charges)


@router.get(
    "/pos/patients/{patient_id}/charges",
    response_model=ServiceChargeListResponse,
)
async def get_pos_patient_charges(
    patient_id: uuid.UUID,
    include_paid: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ServiceChargeListResponse:
    """
    List what a patient still owes across recent visits.

    This is what the front desk searches on when a patient walks up with a
    prescription or a lab slip.

    @param patient_id: Patient UUID
    @param include_paid: Keep settled requests in the result
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Charges with the outstanding total
    """
    charges = await ServiceBillingService(db).list_patient_charges(
        patient_id, current_user.facility_id, include_paid=include_paid
    )
    return _charge_list(charges)


@router.post(
    "/pos/encounters/{encounter_id}/pay",
    response_model=ServicePaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def collect_service_payment(
    encounter_id: uuid.UUID,
    data: ServicePaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(
        require_roles(
            "receptionist", "cashier", "billing_clerk", "admin", "facility_admin"
        )
    ),
    x_idempotency_key: str | None = Header(None),
) -> ServicePaymentResponse:
    """
    Take payment for an ordered service and hand back its receipt.

    Naming a request settles exactly that request; omitting both reference
    fields settles the whole outstanding bill. A request that is already
    settled returns already_paid instead of charging the patient twice.

    @param encounter_id: Encounter UUID
    @param data: Payment details plus the request being settled
    @param db: Database session
    @param current_user: Authenticated front-desk user
    @param x_idempotency_key: Optional idempotency key
    @returns Settled invoice with a printable receipt URL
    """
    try:
        invoice, payment, charge = await ServiceBillingService(db).collect(
            encounter_id=encounter_id,
            facility_id=current_user.facility_id,
            received_by=current_user.user_id,
            payment_method=data.payment_method,
            reference_type=data.reference_type,
            reference_id=data.reference_id,
            reference_number=data.reference_number,
            mpesa_transaction_id=data.mpesa_transaction_id,
            notes=data.notes,
            idempotency_key=x_idempotency_key,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc

    return ServicePaymentResponse(
        payment_id=payment.id if payment else None,
        invoice_id=invoice.id,
        invoice_number=invoice.invoice_number,
        encounter_id=encounter_id,
        description=charge.description if charge else None,
        amount_cents=payment.amount_cents if payment else 0,
        payment_method=payment.payment_method if payment else None,
        reference_number=payment.reference_number if payment else None,
        received_by=payment.received_by if payment else None,
        paid_at=payment.paid_at if payment else None,
        invoice_status=invoice.status,
        balance_cents=invoice.balance_cents,
        already_paid=payment is None,
        receipt_url=(
            "/billing/pos/payments/" + str(payment.id) + "/receipt"
            if payment
            else ""
        ),
    )


@router.get("/pos/payments/{payment_id}/receipt")
async def get_service_receipt(
    payment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    """
    Render the receipt a patient shows at the lab, x-ray or pharmacy desk.

    The receipt lists only the request the payment settled, so the service
    desk can see at a glance what has been released.

    @param payment_id: Payment UUID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns application/pdf response
    """
    from sqlalchemy import select as sa_select

    from app.models.facility import Facility
    from app.services.receipt_pdf import receipt_filename, render_receipt_pdf

    data = await ServiceBillingService(db).service_receipt_data(
        payment_id=payment_id, facility_id=current_user.facility_id
    )
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    payment, invoice, items = data
    if not items:
        # A bill-wide payment names no single request, so there is no service
        # receipt to print; the invoice receipt covers that case.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This payment has no service receipt; use the invoice receipt",
        )

    _invoice, _items, patient_name, patient_mrn = await BillingService(
        db
    ).get_invoice_detail(
        invoice_id=invoice.id, facility_id=current_user.facility_id
    )

    facility_row = await db.execute(
        sa_select(Facility.name).where(Facility.id == current_user.facility_id)
    )
    facility_name = facility_row.scalar_one_or_none() or "Aifya Health Facility"

    subtotal = sum(int(i.total_cents or 0) for i in items)
    amount = int(payment.amount_cents or 0)

    pdf = render_receipt_pdf(
        facility_name=facility_name,
        invoice={
            "id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "status": invoice.status,
            "subtotal_cents": subtotal,
            "discount_cents": 0,
            "total_cents": subtotal,
            "paid_cents": amount,
            "balance_cents": max(subtotal - amount, 0),
        },
        items=[
            {
                "description": i.description,
                "quantity": i.quantity,
                "unit_price_cents": i.unit_price_cents,
                "total_cents": i.total_cents,
            }
            for i in items
        ],
        payments=[
            {
                "paid_at": (
                    payment.paid_at.strftime("%Y-%m-%d %H:%M")
                    if payment.paid_at
                    else ""
                ),
                "payment_method": payment.payment_method,
                "reference_number": payment.reference_number,
                "amount_cents": amount,
            }
        ],
        patient_name=patient_name,
        patient_mrn=patient_mrn,
        title="SERVICE RECEIPT",
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                'inline; filename="'
                + receipt_filename(invoice.invoice_number)
                + '"'
            )
        },
    )
