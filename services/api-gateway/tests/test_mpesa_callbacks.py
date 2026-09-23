"""Tests for M-Pesa STK/C2B callback payment recording.

Covers the critical money path: Safaricom callback → Payment row →
invoice paid/balance/status update, including receipt idempotency.
"""

import uuid
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.models.billing import Payment
from app.models.mpesa import MpesaStkRequest
from tests.conftest import FACILITY_ID, USER_ID
from tests.conftest import session_factory as _session_factory


async def _create_invoice(client: AsyncClient) -> tuple[str, str]:
    """Create patient, encounter, and a finalized KES 700.00 invoice.

    @param client: Async HTTP test client
    @returns Tuple of (invoice_id, invoice_number)
    """
    patient = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Mpesa",
            "last_name": "Callback",
            "date_of_birth": "1985-01-01",
            "gender": "female",
            "phone_number": "0700000001",
        },
    )
    assert patient.status_code == 201
    patient_id = patient.json()["id"]

    encounter = await client.post(
        "/api/v1/encounters",
        json={
            "patient_id": patient_id,
            "encounter_type": "opd",
            "chief_complaint": "Billing test",
        },
    )
    assert encounter.status_code == 201
    encounter_id = encounter.json()["id"]

    invoice = await client.post(
        "/api/v1/billing/invoices",
        json={
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "items": [
                {
                    "description": "Consultation",
                    "quantity": 1,
                    "unit_price_cents": 50000,
                    "item_type": "consultation",
                },
                {
                    "description": "Lab test",
                    "quantity": 1,
                    "unit_price_cents": 20000,
                    "item_type": "lab",
                },
            ],
        },
    )
    assert invoice.status_code == 201
    invoice_id = invoice.json()["id"]
    invoice_number = invoice.json()["invoice_number"]

    finalize = await client.post(f"/api/v1/billing/invoices/{invoice_id}/finalize")
    assert finalize.status_code == 200
    return invoice_id, invoice_number


async def _create_stk_request(invoice_id: str, checkout_request_id: str) -> None:
    """Insert a pending MpesaStkRequest row linked to an invoice.

    @param invoice_id: Invoice UUID string
    @param checkout_request_id: Daraja checkout request ID
    """
    async with _session_factory() as session:
        session.add(
            MpesaStkRequest(
                facility_id=FACILITY_ID,
                invoice_id=uuid.UUID(invoice_id),
                phone_number="254700000001",
                amount=Decimal("700.00"),
                reference="TEST-REF",
                description="Test STK",
                checkout_request_id=checkout_request_id,
                merchant_request_id="m-1",
                status="pending",
                created_by=USER_ID,
            )
        )
        await session.commit()


def _stk_callback_body(
    checkout_request_id: str, amount: float, receipt: str
) -> dict:
    """Build a Safaricom STK success callback envelope.

    @param checkout_request_id: Daraja checkout request ID
    @param amount: Paid amount in KES
    @param receipt: M-Pesa receipt number
    @returns Callback JSON body
    """
    return {
        "Body": {
            "stkCallback": {
                "MerchantRequestID": "m-1",
                "CheckoutRequestID": checkout_request_id,
                "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {
                    "Item": [
                        {"Name": "Amount", "Value": amount},
                        {"Name": "MpesaReceiptNumber", "Value": receipt},
                        {"Name": "PhoneNumber", "Value": 254700000001},
                        {"Name": "TransactionDate", "Value": 20260707120000},
                    ]
                },
            }
        }
    }


async def _get_invoice(client: AsyncClient, invoice_id: str) -> dict:
    """Fetch invoice detail.

    @param client: Async HTTP test client
    @param invoice_id: Invoice UUID string
    @returns Invoice JSON (inner "invoice" object of the detail response)
    """
    response = await client.get(f"/api/v1/billing/invoices/{invoice_id}")
    assert response.status_code == 200
    return response.json()["invoice"]


async def _count_payments(invoice_id: str) -> int:
    """Count non-deleted Payment rows for an invoice.

    @param invoice_id: Invoice UUID string
    @returns Number of payments recorded
    """
    async with _session_factory() as session:
        result = await session.execute(
            select(func.count(Payment.id)).where(
                Payment.invoice_id == uuid.UUID(invoice_id),
                Payment.is_deleted == False,  # noqa: E712
            )
        )
        return int(result.scalar_one())


@pytest.mark.asyncio
async def test_stk_callback_records_payment(client: AsyncClient) -> None:
    """A successful STK callback pays the linked invoice in full."""
    invoice_id, _ = await _create_invoice(client)
    await _create_stk_request(invoice_id, "chk-full-payment")

    response = await client.post(
        "/api/v1/mpesa/callback/stk",
        json=_stk_callback_body("chk-full-payment", 700.0, "QAB1CDEF11"),
    )
    assert response.status_code == 200
    assert response.json()["ResultCode"] == 0

    invoice = await _get_invoice(client, invoice_id)
    assert invoice["paid_cents"] == 70000
    assert invoice["balance_cents"] == 0
    assert invoice["status"] == "paid"


@pytest.mark.asyncio
async def test_stk_callback_partial_payment(client: AsyncClient) -> None:
    """A partial STK payment moves the invoice to partially_paid."""
    invoice_id, _ = await _create_invoice(client)
    await _create_stk_request(invoice_id, "chk-partial")

    response = await client.post(
        "/api/v1/mpesa/callback/stk",
        json=_stk_callback_body("chk-partial", 300.0, "QAB2CDEF22"),
    )
    assert response.status_code == 200

    invoice = await _get_invoice(client, invoice_id)
    assert invoice["paid_cents"] == 30000
    assert invoice["balance_cents"] == 40000
    assert invoice["status"] == "partially_paid"


@pytest.mark.asyncio
async def test_stk_callback_duplicate_is_idempotent(client: AsyncClient) -> None:
    """A replayed STK callback must not double-record the payment."""
    invoice_id, _ = await _create_invoice(client)
    await _create_stk_request(invoice_id, "chk-dup")

    body = _stk_callback_body("chk-dup", 700.0, "QAB3CDEF33")
    first = await client.post("/api/v1/mpesa/callback/stk", json=body)
    assert first.status_code == 200
    second = await client.post("/api/v1/mpesa/callback/stk", json=body)
    assert second.status_code == 200

    invoice = await _get_invoice(client, invoice_id)
    assert invoice["paid_cents"] == 70000
    assert invoice["status"] == "paid"
    assert await _count_payments(invoice_id) == 1


@pytest.mark.asyncio
async def test_c2b_confirmation_records_payment(client: AsyncClient) -> None:
    """A C2B confirmation matching an invoice number records the payment."""
    invoice_id, invoice_number = await _create_invoice(client)

    response = await client.post(
        "/api/v1/mpesa/callback/c2b/confirm",
        json={
            "TransID": "QC2B111AAA",
            "TransAmount": "700.00",
            "MSISDN": "254700000001",
            "BillRefNumber": invoice_number,
        },
    )
    assert response.status_code == 200

    invoice = await _get_invoice(client, invoice_id)
    assert invoice["paid_cents"] == 70000
    assert invoice["balance_cents"] == 0
    assert invoice["status"] == "paid"


@pytest.mark.asyncio
async def test_c2b_confirmation_duplicate_receipt(client: AsyncClient) -> None:
    """Replaying the same C2B TransID must not double-pay the invoice."""
    invoice_id, invoice_number = await _create_invoice(client)

    body = {
        "TransID": "QC2B222BBB",
        "TransAmount": "300.00",
        "MSISDN": "254700000001",
        "BillRefNumber": invoice_number,
    }
    first = await client.post("/api/v1/mpesa/callback/c2b/confirm", json=body)
    assert first.status_code == 200
    second = await client.post("/api/v1/mpesa/callback/c2b/confirm", json=body)
    assert second.status_code == 200

    invoice = await _get_invoice(client, invoice_id)
    assert invoice["paid_cents"] == 30000
    assert invoice["status"] == "partially_paid"
    assert await _count_payments(invoice_id) == 1


@pytest.mark.asyncio
async def test_c2b_overpayment_clamps_balance(client: AsyncClient) -> None:
    """An overpayment is still recorded; balance clamps to zero."""
    invoice_id, invoice_number = await _create_invoice(client)

    response = await client.post(
        "/api/v1/mpesa/callback/c2b/confirm",
        json={
            "TransID": "QC2B333CCC",
            "TransAmount": "1000.00",
            "MSISDN": "254700000001",
            "BillRefNumber": invoice_number,
        },
    )
    assert response.status_code == 200

    invoice = await _get_invoice(client, invoice_id)
    assert invoice["paid_cents"] == 100000
    assert invoice["balance_cents"] == 0
    assert invoice["status"] == "paid"


# ── Callback IP enforcement ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_callback_ip_enforcement_blocks_non_safaricom(
    client: AsyncClient, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """With enforcement on, a callback from a non-Safaricom IP is rejected."""
    from app.routers import mpesa as mpesa_router

    monkeypatch.setattr(
        mpesa_router.settings, "mpesa_callback_ip_enforce", True
    )
    response = await client.post(
        "/api/v1/mpesa/callback/stk",
        json={"Body": {"stkCallback": {"ResultCode": 0}}},
        headers={"X-Forwarded-For": "8.8.8.8"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_callback_ip_enforcement_allows_safaricom(
    client: AsyncClient, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """A callback from a documented Safaricom range is admitted."""
    from app.routers import mpesa as mpesa_router

    monkeypatch.setattr(
        mpesa_router.settings, "mpesa_callback_ip_enforce", True
    )
    response = await client.post(
        "/api/v1/mpesa/callback/stk",
        json={"Body": {"stkCallback": {"CheckoutRequestID": "x", "ResultCode": 1}}},
        headers={"X-Forwarded-For": "196.201.214.200"},
    )
    # Not 403 — the IP passed; body is a harmless failed-result envelope.
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_extra_allowlist_entry_admitted(
    client: AsyncClient, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """An IP added via mpesa_callback_ip_allowlist is admitted."""
    from app.routers import mpesa as mpesa_router

    monkeypatch.setattr(
        mpesa_router.settings, "mpesa_callback_ip_enforce", True
    )
    monkeypatch.setattr(
        mpesa_router.settings, "mpesa_callback_ip_allowlist", "10.0.0.0/8"
    )
    response = await client.post(
        "/api/v1/mpesa/callback/stk",
        json={"Body": {"stkCallback": {"CheckoutRequestID": "x", "ResultCode": 1}}},
        headers={"X-Forwarded-For": "10.1.2.3"},
    )
    assert response.status_code == 200
