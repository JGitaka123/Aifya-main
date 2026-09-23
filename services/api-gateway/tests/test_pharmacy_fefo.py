"""FEFO batch-stock tests for pharmacy dispensing.

Clinical-safety path: dispensing must consume the earliest-expiring
batch first, must never dispense expired stock, and must not let a
fresher receipt mask an expired batch.
"""

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.pharmacy import PharmacyBatch
from tests.conftest import session_factory as _session_factory
from tests.test_pharmacy_dispense import (
    _create_patient,
    _create_prescription,
    _create_stock_item,
    _dispense_payload,
)


async def _receive(
    client: AsyncClient,
    item_id: str,
    quantity: int,
    batch_number: str,
    expiry_days: int | None,
) -> None:
    """Receive a stock batch via the API.

    @param client: Async HTTP test client
    @param item_id: Pharmacy item UUID string
    @param quantity: Units received
    @param batch_number: Batch/lot number
    @param expiry_days: Days until expiry (negative = already expired)
    """
    payload: dict = {
        "pharmacy_item_id": item_id,
        "quantity": quantity,
        "batch_number": batch_number,
    }
    if expiry_days is not None:
        payload["expiry_date"] = (
            date.today() + timedelta(days=expiry_days)
        ).isoformat()
    response = await client.post("/api/v1/pharmacy/stock/receive", json=payload)
    assert response.status_code in (200, 201), response.text


async def _batch_remaining(item_id: str) -> dict[str, int]:
    """Map batch_number → quantity_remaining for an item.

    @param item_id: Pharmacy item UUID string
    @returns Batch quantities by batch number
    """
    async with _session_factory() as session:
        result = await session.execute(
            select(PharmacyBatch).where(
                PharmacyBatch.pharmacy_item_id == uuid.UUID(item_id)
            )
        )
        return {
            (b.batch_number or "unbatched"): b.quantity_remaining
            for b in result.scalars().all()
        }


@pytest.mark.asyncio
async def test_dispense_consumes_earliest_expiry_first(
    client: AsyncClient,
) -> None:
    """FEFO: the batch expiring soonest is drawn down before later ones."""
    patient_id = await _create_patient(client)
    rx_id = await _create_prescription(client, patient_id, quantity=30)
    item_id = await _create_stock_item(client, quantity=0)
    await _receive(client, item_id, 20, "LATE", expiry_days=365)
    await _receive(client, item_id, 20, "SOON", expiry_days=30)

    response = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, item_id, 25),
    )
    assert response.status_code == 201, response.text

    remaining = await _batch_remaining(item_id)
    assert remaining["SOON"] == 0  # consumed first despite arriving second
    assert remaining["LATE"] == 15


@pytest.mark.asyncio
async def test_expired_batch_never_dispensed(client: AsyncClient) -> None:
    """Expired stock is invisible to dispensing even when on hand."""
    patient_id = await _create_patient(client)
    rx_id = await _create_prescription(client, patient_id, quantity=30)
    item_id = await _create_stock_item(client, quantity=0)
    await _receive(client, item_id, 50, "EXPIRED", expiry_days=-1)
    await _receive(client, item_id, 10, "FRESH", expiry_days=90)

    over = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, item_id, 20),
    )
    assert over.status_code == 400
    assert "non-expired" in over.json()["detail"].lower()

    ok = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, item_id, 10),
    )
    assert ok.status_code == 201

    remaining = await _batch_remaining(item_id)
    assert remaining["EXPIRED"] == 50  # untouched
    assert remaining["FRESH"] == 0


@pytest.mark.asyncio
async def test_fresh_receipt_does_not_mask_expired_batch(
    client: AsyncClient,
) -> None:
    """A newer receipt must not make older expired stock dispensable
    (the old single-batch model overwrote the expiry and did exactly that)."""
    patient_id = await _create_patient(client)
    rx_id = await _create_prescription(client, patient_id, quantity=30)
    item_id = await _create_stock_item(client, quantity=0)
    await _receive(client, item_id, 30, "OLD-EXPIRED", expiry_days=-10)
    await _receive(client, item_id, 5, "NEW-OK", expiry_days=180)

    # Item-level total is 35, but only 5 units are legally dispensable.
    response = await client.post(
        "/api/v1/pharmacy/dispense",
        json=_dispense_payload(rx_id, patient_id, item_id, 6),
    )
    assert response.status_code == 400
    assert "5 available" in response.json()["detail"]


@pytest.mark.asyncio
async def test_negative_adjustment_writes_off_expired_first(
    client: AsyncClient,
) -> None:
    """Stock write-offs draw down expired batches before fresh ones."""
    item_id = await _create_stock_item(client, quantity=0)
    await _receive(client, item_id, 30, "EXPIRED", expiry_days=-5)
    await _receive(client, item_id, 30, "FRESH", expiry_days=180)

    response = await client.post(
        "/api/v1/pharmacy/stock/adjust",
        json={
            "pharmacy_item_id": item_id,
            "quantity_change": -30,
            "adjustment_type": "expiry",
            "reason": "Expired stock write-off",
        },
    )
    assert response.status_code in (200, 201), response.text

    remaining = await _batch_remaining(item_id)
    assert remaining["EXPIRED"] == 0
    assert remaining["FRESH"] == 30


@pytest.mark.asyncio
async def test_opening_stock_creates_batch(client: AsyncClient) -> None:
    """Items created with opening stock get an opening batch (FEFO source)."""
    item_id = await _create_stock_item(client, quantity=40)
    remaining = await _batch_remaining(item_id)
    assert sum(remaining.values()) == 40
