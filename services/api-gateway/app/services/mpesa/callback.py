"""
M-Pesa STK Push callback handler.
Processes the JSON Safaricom POSTs to our CallBackURL after the customer
completes (or cancels) an STK Push prompt. Updates `mpesa_stk_requests`
and, on success, posts a Payment against the linked invoice.

This module is the bridge between the raw Daraja callback (parsed by
DarajaClient.parse_stk_callback) and our domain.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from structlog import get_logger

from app.models.mpesa import MpesaStkRequest
from app.services.mpesa.daraja import DarajaClient, STKCallbackData
from app.services.mpesa.stk_push import StkPushService

logger = get_logger(__name__)


async def handle_stk_callback(
    db: AsyncSession,
    body: dict,
) -> dict:
    """
    Handle a parsed M-Pesa STK Push callback body.

    Steps:
    1. Parse the Safaricom JSON envelope
    2. Update the matching mpesa_stk_requests row
    3. On success, post a Payment to the linked invoice and update its status

    @param db: Async database session
    @param body: Raw JSON body posted by Safaricom
    @returns Acknowledgement dict that we return to Safaricom
    """
    callback = DarajaClient.parse_stk_callback(body)

    logger.info(
        "stk_callback_handled",
        checkout_request_id=callback.checkout_request_id,
        result_code=callback.result_code,
        receipt=callback.mpesa_receipt,
    )

    await apply_stk_result(db, callback)

    return {"ResultCode": 0, "ResultDesc": "Accepted"}


async def apply_stk_result(
    db: AsyncSession,
    callback: STKCallbackData,
) -> MpesaStkRequest | None:
    """
    Mark an STK Push finished and post the money it brought in.

    Split out from the HTTP callback so the till can drive the same work from
    a status query when Safaricom's callback is delayed or lost. Both paths
    are idempotent, so whichever arrives first wins and the other is a no-op.

    @param db: Async database session
    @param callback: Parsed callback (or status query) data
    @returns The updated request row, or None when we never saw the request
    """
    # 1) Update the stored request row (idempotent)
    row = await StkPushService(db).mark_completed(
        checkout_request_id=callback.checkout_request_id,
        result_code=callback.result_code,
        result_desc=callback.result_desc,
        mpesa_receipt=callback.mpesa_receipt,
        transaction_date=callback.transaction_date,
    )

    # 2) On success with a linked invoice, record the Payment and release
    #    whatever ordered services that money paid for
    if (
        row is not None
        and callback.result_code == 0
        and callback.mpesa_receipt
        and row.invoice_id is not None
    ):
        await _record_invoice_payment(db, row, callback)

    return row


async def _record_invoice_payment(
    db: AsyncSession,
    row,
    callback: STKCallbackData,
) -> None:
    """
    Post the M-Pesa receipt as a Payment against the linked Invoice via
    BillingService.record_external_payment (idempotent per receipt).

    @param db: Async database session
    @param row: The stored MpesaStkRequest row that triggered the payment
    @param callback: Parsed callback data from Safaricom
    """
    from app.services.billing_service import BillingService
    from app.services.service_billing import (
        ServiceBillingService,
        parse_service_reference,
    )

    try:
        amount_cents = int(Decimal(str(callback.amount or 0)) * 100)
        payment = await BillingService(db).record_external_payment(
            invoice_id=row.invoice_id,
            amount_cents=amount_cents,
            mpesa_receipt=callback.mpesa_receipt,
            phone_number=callback.phone_number,
            received_by=row.created_by,
        )
        if payment is not None:
            # Release the lab, imaging or pharmacy requests this money paid
            # for. Without this the invoice would read "paid" while the lab
            # desk still refused to hand over the results.
            named = parse_service_reference(row.reference)
            settled = await ServiceBillingService(db).settle_invoice_requests(
                facility_id=row.facility_id,
                invoice_id=row.invoice_id,
                payment_id=payment.id,
                amount_cents=amount_cents,
                created_by=row.created_by,
                reference_type=named[0] if named else None,
                reference_id=named[1] if named else None,
            )
            logger.info(
                "stk_invoice_payment_recorded",
                invoice_id=str(row.invoice_id),
                amount_cents=amount_cents,
                receipt=callback.mpesa_receipt,
                services_released=len(settled),
            )
    except Exception:
        logger.exception(
            "stk_invoice_payment_error",
            receipt=callback.mpesa_receipt,
        )
        # Don't re-raise — Safaricom must always get a 200 ack, but the
        # session may be unusable now; roll back so the ack can commit.
        await db.rollback()
