"""
M-Pesa Daraja integration router.
Provides STK Push payments, C2B callbacks, transaction status, and reconciliation.
Callbacks are public endpoints (no auth) — Safaricom sends them directly.

Security:
- Callback endpoints MUST be protected at the network edge with an IP allow-list
  for Safaricom's documented production ranges (e.g. 196.201.214.0/24,
  196.201.213.0/24, 196.201.212.0/24, 196.201.214.200/29). The TODO below
  enforces this at the application layer when MPESA_CALLBACK_IP_ALLOWLIST is set.
- Callbacks are idempotent: handle_stk_callback short-circuits when the row is
  already in a terminal state.
- Callbacks always return 200 to Safaricom (so they don't retry) but log internal
  errors for follow-up.
- Payload structure is validated by DarajaClient.parse_stk_callback before use.
"""

import ipaddress
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.auth import CurrentUser, get_current_user
from app.models.billing import Invoice
from app.config import settings
from app.database import get_db
from app.services.mpesa.callback import apply_stk_result, handle_stk_callback
from app.services.mpesa.daraja import (
    DarajaClient,
    STKCallbackData,
    STKPushResponse,
    TransactionStatus,
    get_daraja_config,
)
from app.services.mpesa.stk_push import StkPushService
from app.services.service_billing import build_service_reference

logger = get_logger(__name__)

router = APIRouter()


# Safaricom Daraja documented production callback source ranges (CIDR).
# Extra IPs/CIDRs can be appended via MPESA_CALLBACK_IP_ALLOWLIST.
_DEFAULT_SAFARICOM_CIDRS: tuple[str, ...] = (
    "196.201.214.0/24",
    "196.201.213.0/24",
    "196.201.212.0/24",
    "196.201.214.200/29",
)


def _allowed_networks() -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    """
    Build the effective allow-list: built-in Safaricom ranges plus any
    configured extras (individual IPs or CIDRs).

    @returns Parsed networks to match callback source IPs against
    """
    entries = list(_DEFAULT_SAFARICOM_CIDRS)
    extra = settings.mpesa_callback_ip_allowlist.strip()
    if extra:
        entries.extend(e.strip() for e in extra.split(",") if e.strip())
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for entry in entries:
        try:
            networks.append(ipaddress.ip_network(entry, strict=False))
        except ValueError:
            logger.warning("mpesa_allowlist_bad_entry", entry=entry)
    return networks


def _client_ip(request: Request) -> str:
    """Resolve the originating client IP, honouring X-Forwarded-For when present."""
    fwd = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if fwd:
        return fwd
    return request.client.host if request.client else ""


def _enforce_callback_ip(request: Request) -> None:
    """
    Reject the callback unless its source IP is within an allowed network.

    Enforced by default (settings.mpesa_callback_ip_enforce). Disable only
    in dev/test where the source is not Safaricom. Supports X-Forwarded-For
    (trusts the first hop — the edge proxy must strip client-supplied XFF).
    """
    src = _client_ip(request)
    if not settings.mpesa_callback_ip_enforce:
        logger.info("mpesa_callback_inbound", source_ip=src, enforced=False)
        return

    try:
        src_addr = ipaddress.ip_address(src)
    except ValueError:
        logger.warning("mpesa_callback_blocked_ip", source_ip=src, reason="unparseable")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Source IP not allowed",
        ) from None

    if not any(src_addr in net for net in _allowed_networks()):
        logger.warning("mpesa_callback_blocked_ip", source_ip=src)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Source IP not allowed",
        )


# ── Request / Response Schemas ───────────────────────────────────────────────


class STKPushApiRequest(BaseModel):
    """
    API request to initiate an STK Push payment.

    @param phone_number: Customer phone (07XX or +254XX)
    @param amount_kes: Amount in KES (whole number)
    @param invoice_id: Invoice UUID to pay (optional)
    @param patient_id: Patient UUID linked to payment (optional)
    @param reference: Account reference shown on M-Pesa (typically invoice number)
    @param description: Optional transaction description
    @param reference_type: Ordered service being paid for (optional)
    @param reference_id: The lab order, imaging order or prescription UUID
    """
    phone_number: str
    amount_kes: int = Field(gt=0)
    invoice_id: str | None = None
    patient_id: str | None = None
    reference: str | None = None
    description: str = "Hospital Payment"
    reference_type: str | None = None
    reference_id: str | None = None


class STKRequestStatusResponse(BaseModel):
    """
    Local view of an STK Push, read from our own records.

    The Daraja query endpoint reports what Safaricom thinks happened; this
    reports what we actually recorded, so the till knows whether the money
    reached the patient's bill before it tells anyone the payment succeeded.

    @param checkout_request_id: Daraja checkout request ID
    @param status: pending, success, failed or timeout
    @param result_code: 0 on success, else the Daraja failure code
    @param result_desc: Human-readable outcome from Safaricom
    @param receipt_number: M-Pesa receipt, once the payment is confirmed
    @param amount_kes: Amount the customer was asked to pay
    @param phone_number: Phone the prompt was sent to
    @param invoice_id: Invoice the payment is posted against
    @param invoice_number: Human-readable invoice number
    @param payment_id: Payment recorded against the invoice, if any
    @param recorded: Whether the money has reached the bill
    """
    checkout_request_id: str
    status: str
    result_code: int | None = None
    result_desc: str | None = None
    receipt_number: str | None = None
    amount_kes: float
    phone_number: str
    invoice_id: str | None = None
    invoice_number: str | None = None
    payment_id: str | None = None
    recorded: bool = False


class MPesaStatusResponse(BaseModel):
    """
    M-Pesa configuration status.

    @param configured: Whether Daraja credentials are set
    @param environment: sandbox or production
    @param shortcode: Configured business shortcode
    """
    configured: bool
    environment: str = ""
    shortcode: str = ""


# ── STK Push Endpoint ────────────────────────────────────────────────────────


@router.post("/stk-push", response_model=STKPushResponse)
async def initiate_stk_push(
    request: STKPushApiRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> STKPushResponse:
    """
    Initiate M-Pesa STK Push (Lipa Na M-Pesa Online) to collect payment.
    Sends a USSD prompt to the patient's phone and persists the request
    in mpesa_stk_requests for callback reconciliation.

    @param request: STK Push request with phone, amount, optional invoice ID
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns STK Push response with checkout request ID for tracking
    """
    invoice_uuid: uuid.UUID | None = None
    if request.invoice_id:
        try:
            invoice_uuid = uuid.UUID(request.invoice_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invoice_id must be a valid UUID",
            ) from exc
    patient_uuid: uuid.UUID | None = None
    if request.patient_id:
        try:
            patient_uuid = uuid.UUID(request.patient_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id must be a valid UUID",
            ) from exc

    # The account reference is what greets the patient on the M-Pesa SMS, so
    # prefer the invoice number over its opaque UUID, and tag on the ordered
    # service being paid for so the callback knows exactly which request to
    # release at the lab, the x-ray room or the pharmacy.
    base_reference = request.reference or request.invoice_id or str(uuid.uuid4())
    if invoice_uuid is not None:
        invoice_number = (
            await db.execute(
                select(Invoice.invoice_number).where(
                    Invoice.id == invoice_uuid,
                    Invoice.facility_id == current_user.facility_id,
                )
            )
        ).scalar_one_or_none()
        if invoice_number is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found",
            )
        if not request.reference:
            base_reference = invoice_number

    reference = build_service_reference(
        base_reference,
        request.reference_type,
        request.reference_id,
    )

    service = StkPushService(db)
    api_response, _row = await service.initiate_stk_push(
        facility_id=current_user.facility_id,
        phone_number=request.phone_number,
        amount=request.amount_kes,
        reference=reference,
        description=request.description,
        invoice_id=invoice_uuid,
        patient_id=patient_uuid,
        created_by=current_user.user_id,
    )

    if api_response.success:
        logger.info(
            "stk_push_initiated",
            checkout_id=api_response.checkout_request_id,
            invoice_id=request.invoice_id,
            facility_id=str(current_user.facility_id),
        )
    return api_response


# ── STK Push Status Query ────────────────────────────────────────────────────


@router.get("/stk-status/{checkout_request_id}")
async def query_stk_status(
    checkout_request_id: str,
    current_user: CurrentUser = Depends(get_current_user),
) -> TransactionStatus:
    """
    Query the status of an STK Push transaction.

    @param checkout_request_id: Checkout request ID from STK Push response
    @param current_user: Authenticated user from JWT
    @returns Transaction status with result code
    """
    config = get_daraja_config()
    if not config:
        return TransactionStatus(result_code=-1, result_desc="M-Pesa not configured")

    client = DarajaClient(config)
    return await client.stk_query(checkout_request_id)


# ── STK Callback (Public — No Auth) ─────────────────────────────────────────


@router.get(
    "/stk-requests/{checkout_request_id}",
    response_model=STKRequestStatusResponse,
)
async def get_stk_request(
    checkout_request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> STKRequestStatusResponse:
    """
    Read the local state of an STK Push the till started.

    Unlike the Daraja query endpoint this reports what we recorded - whether
    the money actually reached the patient's bill - which is what decides
    whether it is safe to tell the patient the payment succeeded.

    @param checkout_request_id: Checkout request ID from STK Push response
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Local STK Push state
    @raises HTTPException 404: When this facility never started that request
    """
    snapshot = await _stk_snapshot(
        db, current_user.facility_id, checkout_request_id
    )
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown checkout request id",
        )
    return snapshot


@router.post(
    "/stk-requests/{checkout_request_id}/reconcile",
    response_model=STKRequestStatusResponse,
)
async def reconcile_stk_request(
    checkout_request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> STKRequestStatusResponse:
    """
    Ask Safaricom what happened and post the money if it was received.

    A callback can be delayed or lost on a flaky link. The till calls this
    while it waits, so a patient who really did pay is never told otherwise.

    @param checkout_request_id: Checkout request ID from STK Push response
    @param db: Database session
    @param current_user: Authenticated user from JWT
    @returns Local STK Push state after reconciliation
    @raises HTTPException 404: When this facility never started that request
    """
    service = StkPushService(db)
    row = await service.get_status(
        current_user.facility_id, checkout_request_id
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown checkout request id",
        )

    config = get_daraja_config()
    if config is not None and row.status == "pending":
        queried = await DarajaClient(config).stk_query(checkout_request_id)
        if queried.result_code == 0 and queried.receipt_number:
            logger.info(
                "stk_reconciled_from_query",
                checkout_id=checkout_request_id,
                receipt=queried.receipt_number,
            )
            await apply_stk_result(
                db,
                STKCallbackData(
                    merchant_request_id=row.merchant_request_id,
                    checkout_request_id=checkout_request_id,
                    result_code=0,
                    result_desc=queried.result_desc or "Confirmed by query",
                    amount=float(row.amount or 0),
                    mpesa_receipt=queried.receipt_number,
                    phone_number=row.phone_number,
                ),
            )

    snapshot = await _stk_snapshot(
        db, current_user.facility_id, checkout_request_id
    )
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unknown checkout request id",
        )
    return snapshot


async def _stk_snapshot(
    db: AsyncSession,
    facility_id: uuid.UUID,
    checkout_request_id: str,
) -> STKRequestStatusResponse | None:
    """
    Build the local status view for one STK Push.

    @param db: Database session
    @param facility_id: Facility UUID (multi-tenant scope)
    @param checkout_request_id: Daraja checkout request ID
    @returns Status snapshot, or None when this facility never started it
    """
    from app.models.billing import Payment

    row = await StkPushService(db).get_status(facility_id, checkout_request_id)
    if row is None:
        return None

    invoice_number: str | None = None
    if row.invoice_id is not None:
        invoice_number = (
            await db.execute(
                select(Invoice.invoice_number).where(
                    Invoice.id == row.invoice_id
                )
            )
        ).scalar_one_or_none()

    payment_id: uuid.UUID | None = None
    if row.mpesa_receipt_number:
        payment_id = (
            await db.execute(
                select(Payment.id).where(
                    Payment.facility_id == facility_id,
                    Payment.mpesa_transaction_id == row.mpesa_receipt_number,
                    Payment.is_deleted == False,  # noqa: E712
                )
            )
        ).scalar_one_or_none()

    return STKRequestStatusResponse(
        checkout_request_id=row.checkout_request_id,
        status=row.status,
        result_code=row.result_code,
        result_desc=row.result_desc,
        receipt_number=row.mpesa_receipt_number,
        amount_kes=float(row.amount or 0),
        phone_number=row.phone_number,
        invoice_id=str(row.invoice_id) if row.invoice_id else None,
        invoice_number=invoice_number,
        payment_id=str(payment_id) if payment_id else None,
        recorded=payment_id is not None,
    )


@router.post("/callback/stk")
@router.post("/callback")
async def stk_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Safaricom STK Push callback endpoint.
    Called by M-Pesa servers after customer completes payment.
    No auth required — Safaricom calls this directly.

    Updates the mpesa_stk_requests row and posts a Payment if the
    transaction was tied to an invoice.

    @param request: Raw HTTP request from Safaricom
    @param db: Database session
    @returns JSON acknowledgement
    """
    try:
        _enforce_callback_ip(request)
    except HTTPException:
        raise

    try:
        body = await request.json()
        # Defensive: validate we have an stkCallback envelope before processing
        if not isinstance(body, dict) or "Body" not in body:
            logger.warning("stk_callback_malformed")
            return JSONResponse(content={"ResultCode": 0, "ResultDesc": "Accepted"})
        ack = await handle_stk_callback(db, body)
        return JSONResponse(content=ack)
    except Exception as exc:
        logger.error("stk_callback_error", error=str(exc))
        # Always ack to Safaricom so they don't retry endlessly
        return JSONResponse(content={"ResultCode": 0, "ResultDesc": "Accepted"})


# ── C2B Validation Callback (Public — No Auth) ──────────────────────────────


@router.post("/callback/c2b/validate")
async def c2b_validation(request: Request) -> JSONResponse:
    """
    C2B validation callback — Safaricom asks if we accept this payment.
    Always accept (Completed response type configured during registration).

    @param request: Raw HTTP request from Safaricom
    @returns JSON validation response
    """
    try:
        _enforce_callback_ip(request)
    except HTTPException:
        raise
    try:
        body = await request.json()
    except Exception:
        body = {}
    # Don't echo full body in production logs (may contain MSISDN PII)
    logger.info("c2b_validation", trans_id=str(body.get("TransID", "")))

    # Accept all payments (validation can be extended for amount/account checks)
    return JSONResponse(content={"ResultCode": 0, "ResultDesc": "Accepted"})


# ── C2B Confirmation Callback (Public — No Auth) ────────────────────────────


@router.post("/callback/c2b/confirm")
async def c2b_confirmation(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    C2B confirmation callback — customer paid via Paybill/Till.
    Record the payment against the referenced invoice.

    @param request: Raw HTTP request from Safaricom
    @param db: Database session
    @returns JSON confirmation response
    """
    try:
        _enforce_callback_ip(request)
    except HTTPException:
        raise

    try:
        body = await request.json()
        # Don't log MSISDN (PII) — only the receipt/account ref
        logger.info(
            "c2b_confirmation",
            trans_id=str(body.get("TransID", "")),
            account_ref=str(body.get("BillRefNumber", "")),
        )

        # Extract C2B fields with defensive type coercion
        receipt = str(body.get("TransID", "")).strip()
        try:
            amount = float(body.get("TransAmount", 0) or 0)
        except (TypeError, ValueError):
            amount = 0.0
        if amount < 0:
            amount = 0.0
        phone = str(body.get("MSISDN", "")).strip()
        account_ref = str(body.get("BillRefNumber", "")).strip()

        if receipt and amount > 0:
            callback_data = STKCallbackData(
                merchant_request_id="C2B",
                checkout_request_id=f"C2B-{receipt}",
                result_code=0,
                result_desc="C2B Payment",
                amount=amount,
                mpesa_receipt=receipt,
                phone_number=phone,
            )
            await _record_mpesa_payment(db, callback_data, account_ref=account_ref)

        return JSONResponse(content={"ResultCode": 0, "ResultDesc": "Accepted"})

    except Exception as exc:
        logger.error("c2b_confirm_error", error=str(exc))
        return JSONResponse(content={"ResultCode": 0, "ResultDesc": "Accepted"})


# ── M-Pesa Status ───────────────────────────────────────────────────────────


@router.get("/status")
async def mpesa_status(
    current_user: CurrentUser = Depends(get_current_user),
) -> MPesaStatusResponse:
    """
    Check M-Pesa Daraja configuration status.

    @param current_user: Authenticated user from JWT
    @returns Configuration status
    """
    config = get_daraja_config()
    if not config:
        return MPesaStatusResponse(configured=False)

    return MPesaStatusResponse(
        configured=True,
        environment=config.environment,
        shortcode=config.shortcode,
    )


# ── Internal Helpers ─────────────────────────────────────────────────────────


async def _record_mpesa_payment(
    db: AsyncSession,
    callback: STKCallbackData,
    account_ref: str = "",
) -> None:
    """
    Record an M-Pesa payment in the billing system.
    Matches the payment to an invoice by reference number.

    @param db: Database session
    @param callback: Parsed M-Pesa callback data
    @param account_ref: Account reference from C2B (invoice number)
    """
    from decimal import Decimal

    from sqlalchemy import select

    from app.models.billing import Invoice
    from app.services.billing_service import BillingService

    try:
        # Try to find invoice by reference
        if account_ref:
            result = await db.execute(
                select(Invoice).where(
                    Invoice.invoice_number == account_ref,
                    Invoice.is_deleted == False,  # noqa: E712
                )
            )
            invoice = result.scalar_one_or_none()

            if invoice:
                amount_cents = int(Decimal(str(callback.amount or 0)) * 100)
                # Idempotent per M-Pesa receipt inside the service.
                payment = await BillingService(db).record_external_payment(
                    invoice_id=invoice.id,
                    amount_cents=amount_cents,
                    mpesa_receipt=callback.mpesa_receipt,
                    phone_number=callback.phone_number,
                )
                if payment is not None:
                    # A paybill payment quoted with the invoice number must
                    # release the orders it paid for, not just clear the bill.
                    from app.services.service_billing import (
                        ServiceBillingService,
                    )

                    await ServiceBillingService(db).settle_invoice_requests(
                        facility_id=invoice.facility_id,
                        invoice_id=invoice.id,
                        payment_id=payment.id,
                        amount_cents=amount_cents,
                        created_by=None,
                    )
                    logger.info(
                        "mpesa_payment_recorded",
                        receipt=callback.mpesa_receipt,
                        invoice=invoice.invoice_number,
                        amount_cents=amount_cents,
                    )
                return

        # No matching invoice — log as unmatched for reconciliation
        logger.warning(
            "mpesa_payment_unmatched",
            receipt=callback.mpesa_receipt,
            amount=callback.amount,
            account_ref=account_ref,
        )

    except Exception:
        logger.exception(
            "mpesa_payment_record_error",
            receipt=callback.mpesa_receipt,
        )
        await db.rollback()
