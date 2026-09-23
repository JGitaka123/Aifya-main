import uuid

import pytest
from httpx import AsyncClient


async def _create_patient(client: AsyncClient) -> str:
    """Create a test patient and return their ID.

    @param client: Async HTTP test client
    @returns Patient UUID string
    """
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Billing",
            "last_name": "TestPatient",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "phone_number": "0700000000",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_encounter(client: AsyncClient, patient_id: str) -> str:
    """Create a test encounter and return its ID.

    @param client: Async HTTP test client
    @param patient_id: Patient UUID string
    @returns Encounter UUID string
    """
    response = await client.post(
        "/api/v1/encounters",
        json={
            "patient_id": patient_id,
            "encounter_type": "opd",
            "chief_complaint": "General consultation",
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _create_invoice(client: AsyncClient) -> tuple[str, str, str]:
    """Create a patient, encounter, and invoice. Return all three IDs.

    @param client: Async HTTP test client
    @returns Tuple of (patient_id, encounter_id, invoice_id)
    """
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    response = await client.post(
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
                    "description": "Paracetamol",
                    "quantity": 2,
                    "unit_price_cents": 10000,
                    "item_type": "pharmacy",
                },
            ],
        },
    )
    assert response.status_code == 201
    return patient_id, encounter_id, response.json()["id"]


# ── GET /billing/summary ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_billing_summary_empty(client: AsyncClient) -> None:
    """Test billing summary returns zeroes when no invoices exist."""
    response = await client.get("/api/v1/billing/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["total_invoices"] == 0
    assert data["draft_count"] == 0
    assert data["finalized_count"] == 0
    assert data["paid_count"] == 0
    assert data["partially_paid_count"] == 0
    assert data["total_billed_cents"] == 0
    assert data["total_paid_cents"] == 0
    assert data["total_outstanding_cents"] == 0


# ── GET /billing/invoices ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_invoices_empty(client: AsyncClient) -> None:
    """Test listing invoices returns empty list when none exist."""
    response = await client.get("/api/v1/billing/invoices")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1


# ── POST /billing/invoices ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_invoice(client: AsyncClient) -> None:
    """Test creating an invoice with line items for a patient encounter."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)

    response = await client.post(
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
                    "description": "Paracetamol",
                    "quantity": 2,
                    "unit_price_cents": 10000,
                    "item_type": "pharmacy",
                },
            ],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["patient_id"] == patient_id
    assert data["encounter_id"] == encounter_id
    assert data["status"] == "draft"
    assert "invoice_number" in data
    assert "id" in data
    # Consultation (1 * 50000) + Paracetamol (2 * 10000) = 70000
    assert data["subtotal_cents"] == 70000
    assert data["total_cents"] >= 70000
    assert data["paid_cents"] == 0
    assert data["balance_cents"] == data["total_cents"]


@pytest.mark.asyncio
async def test_create_invoice_missing_items(client: AsyncClient) -> None:
    """Test validation rejects invoice creation without items."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)

    response = await client.post(
        "/api/v1/billing/invoices",
        json={
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "items": [],
        },
    )

    assert response.status_code == 422


# ── GET /billing/invoices/{id} ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_invoice_detail(client: AsyncClient) -> None:
    """Test fetching an invoice detail returns items and patient info."""
    patient_id, encounter_id, invoice_id = await _create_invoice(client)

    response = await client.get(f"/api/v1/billing/invoices/{invoice_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["invoice"]["id"] == invoice_id
    assert data["invoice"]["patient_id"] == patient_id
    assert data["invoice"]["encounter_id"] == encounter_id
    assert len(data["items"]) == 2
    # Verify item details
    descriptions = {item["description"] for item in data["items"]}
    assert "Consultation" in descriptions
    assert "Paracetamol" in descriptions
    # Patient info populated
    assert data["patient_name"] is not None
    assert data["patient_mrn"] is not None


@pytest.mark.asyncio
async def test_get_invoice_not_found(client: AsyncClient) -> None:
    """Test 404 returned for non-existent invoice."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/billing/invoices/{fake_id}")

    assert response.status_code == 404
    assert response.json()["detail"] == "Invoice not found"


# ── POST /billing/invoices/{id}/finalize ─────────────────────────────────────


@pytest.mark.asyncio
async def test_finalize_invoice(client: AsyncClient) -> None:
    """Test finalizing a draft invoice locks it for payment collection."""
    _patient_id, _encounter_id, invoice_id = await _create_invoice(client)

    response = await client.post(f"/api/v1/billing/invoices/{invoice_id}/finalize")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == invoice_id
    assert data["status"] == "finalized"
    assert data["finalized_at"] is not None


@pytest.mark.asyncio
async def test_finalize_invoice_not_found(client: AsyncClient) -> None:
    """Test 404 when finalizing a non-existent invoice."""
    fake_id = str(uuid.uuid4())
    response = await client.post(f"/api/v1/billing/invoices/{fake_id}/finalize")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_outstanding_excludes_draft_invoices(client: AsyncClient) -> None:
    """QA F8: outstanding AR counts only finalized/partially-paid invoices — a
    draft invoice is not a receivable and must not inflate the figure."""
    # Two identical 70,000-cent invoices; finalize only one.
    _p1, _e1, finalized_id = await _create_invoice(client)
    await _create_invoice(client)  # left as draft
    fin = await client.post(f"/api/v1/billing/invoices/{finalized_id}/finalize")
    assert fin.status_code == 200

    summary = await client.get("/api/v1/billing/summary")
    assert summary.status_code == 200
    data = summary.json()
    # Only the finalized invoice's balance counts — not the draft.
    assert data["total_outstanding_cents"] == 70000


# ── POST /billing/invoices/{id}/pay ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_record_payment(client: AsyncClient) -> None:
    """Test recording a cash payment against a finalized invoice."""
    _patient_id, _encounter_id, invoice_id = await _create_invoice(client)

    # Finalize first
    finalize_resp = await client.post(
        f"/api/v1/billing/invoices/{invoice_id}/finalize"
    )
    assert finalize_resp.status_code == 200
    total_cents: int = finalize_resp.json()["total_cents"]

    # Pay
    response = await client.post(
        f"/api/v1/billing/invoices/{invoice_id}/pay",
        json={
            "amount_cents": total_cents,
            "payment_method": "cash",
            "reference_number": "RCP-001",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["invoice_id"] == invoice_id
    assert data["amount_cents"] == total_cents
    assert data["payment_method"] == "cash"
    assert data["reference_number"] == "RCP-001"
    assert "paid_at" in data

    # Verify invoice is now paid
    detail_resp = await client.get(f"/api/v1/billing/invoices/{invoice_id}")
    assert detail_resp.status_code == 200
    invoice_data = detail_resp.json()["invoice"]
    assert invoice_data["paid_cents"] == total_cents
    assert invoice_data["balance_cents"] == 0


@pytest.mark.asyncio
async def test_record_partial_payment(client: AsyncClient) -> None:
    """Test recording a partial payment updates balance correctly."""
    _patient_id, _encounter_id, invoice_id = await _create_invoice(client)

    # Finalize first
    finalize_resp = await client.post(
        f"/api/v1/billing/invoices/{invoice_id}/finalize"
    )
    assert finalize_resp.status_code == 200
    total_cents: int = finalize_resp.json()["total_cents"]
    partial_amount: int = total_cents // 2

    # Pay partial
    response = await client.post(
        f"/api/v1/billing/invoices/{invoice_id}/pay",
        json={
            "amount_cents": partial_amount,
            "payment_method": "mpesa",
            "reference_number": "MPESA-ABC123",
        },
    )

    assert response.status_code == 201
    assert response.json()["amount_cents"] == partial_amount

    # Verify balance updated
    detail_resp = await client.get(f"/api/v1/billing/invoices/{invoice_id}")
    invoice_data = detail_resp.json()["invoice"]
    assert invoice_data["paid_cents"] == partial_amount
    assert invoice_data["balance_cents"] == total_cents - partial_amount


# ── POST /billing/invoices/{id}/waive ────────────────────────────────────────


@pytest.mark.asyncio
async def test_waive_invoice(client: AsyncClient) -> None:
    """Test waiving an invoice balance sets status to waived."""
    _patient_id, _encounter_id, invoice_id = await _create_invoice(client)

    response = await client.post(
        f"/api/v1/billing/invoices/{invoice_id}/waive",
        json={"reason": "Patient is a charity case with no ability to pay"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == invoice_id
    assert data["status"] == "waived"


@pytest.mark.asyncio
async def test_waive_invoice_not_found(client: AsyncClient) -> None:
    """Test 404 when waiving a non-existent invoice."""
    fake_id = str(uuid.uuid4())
    response = await client.post(
        f"/api/v1/billing/invoices/{fake_id}/waive",
        json={"reason": "Patient qualifies for government exemption"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_waive_invoice_reason_too_short(client: AsyncClient) -> None:
    """Test validation rejects waiver reason shorter than 5 characters."""
    _patient_id, _encounter_id, invoice_id = await _create_invoice(client)

    response = await client.post(
        f"/api/v1/billing/invoices/{invoice_id}/waive",
        json={"reason": "ok"},
    )

    assert response.status_code == 422


# ── Idempotency ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_invoice_with_idempotency_key(client: AsyncClient) -> None:
    """Test that create invoice accepts X-Idempotency-Key header."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)

    response = await client.post(
        "/api/v1/billing/invoices",
        json={
            "patient_id": patient_id,
            "encounter_id": encounter_id,
            "items": [
                {
                    "description": "Lab test - CBC",
                    "quantity": 1,
                    "unit_price_cents": 30000,
                    "item_type": "lab",
                },
            ],
        },
        headers={"X-Idempotency-Key": "billing-idem-001"},
    )

    assert response.status_code == 201


# ── List filtering ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_invoices_after_creation(client: AsyncClient) -> None:
    """Test that created invoices appear in the list endpoint."""
    await _create_invoice(client)

    response = await client.get("/api/v1/billing/invoices")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    invoice_item = data["items"][0]
    assert "invoice_number" in invoice_item
    assert "total_cents" in invoice_item
    assert "status" in invoice_item


@pytest.mark.asyncio
async def test_billing_summary_after_creation(client: AsyncClient) -> None:
    """Test billing summary reflects created invoices."""
    await _create_invoice(client)

    response = await client.get("/api/v1/billing/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["total_invoices"] >= 1
    assert data["draft_count"] >= 1
    assert data["total_billed_cents"] >= 70000
    # A draft invoice is billed but NOT yet a receivable (QA F8): it must not
    # count toward outstanding AR until finalized.
    assert data["total_outstanding_cents"] == 0


# ── Idempotency ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_payment_idempotency_key_prevents_double_charge(
    client: AsyncClient,
) -> None:
    """A retried payment with the same X-Idempotency-Key must not double-pay."""
    _, _, invoice_id = await _create_invoice(client)
    await client.post(f"/api/v1/billing/invoices/{invoice_id}/finalize")

    payload = {"amount_cents": 30000, "payment_method": "cash"}
    headers = {"X-Idempotency-Key": "pay-retry-001"}

    first = await client.post(
        f"/api/v1/billing/invoices/{invoice_id}/pay", json=payload, headers=headers
    )
    assert first.status_code == 201
    second = await client.post(
        f"/api/v1/billing/invoices/{invoice_id}/pay", json=payload, headers=headers
    )
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]

    detail = await client.get(f"/api/v1/billing/invoices/{invoice_id}")
    assert detail.json()["invoice"]["paid_cents"] == 30000


@pytest.mark.asyncio
async def test_invoice_idempotency_key_prevents_duplicate_invoice(
    client: AsyncClient,
) -> None:
    """A retried invoice creation with the same key returns the original."""
    patient_id = await _create_patient(client)
    encounter_id = await _create_encounter(client, patient_id)
    payload = {
        "patient_id": patient_id,
        "encounter_id": encounter_id,
        "items": [
            {
                "description": "Consultation",
                "quantity": 1,
                "unit_price_cents": 50000,
                "item_type": "consultation",
            }
        ],
    }
    headers = {"X-Idempotency-Key": "invoice-retry-001"}

    first = await client.post(
        "/api/v1/billing/invoices", json=payload, headers=headers
    )
    assert first.status_code == 201
    second = await client.post(
        "/api/v1/billing/invoices", json=payload, headers=headers
    )
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["invoice_number"] == first.json()["invoice_number"]


# ── Receipt PDF ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_invoice_receipt_pdf(client: AsyncClient) -> None:
    """The receipt endpoint returns a valid PDF with payments applied."""
    _, _, invoice_id = await _create_invoice(client)
    await client.post(f"/api/v1/billing/invoices/{invoice_id}/finalize")
    pay = await client.post(
        f"/api/v1/billing/invoices/{invoice_id}/pay",
        json={"amount_cents": 70000, "payment_method": "cash"},
    )
    assert pay.status_code == 201

    receipt = await client.get(f"/api/v1/billing/invoices/{invoice_id}/receipt")
    assert receipt.status_code == 200
    assert receipt.headers["content-type"] == "application/pdf"
    assert receipt.content.startswith(b"%PDF")
    assert len(receipt.content) > 1000


@pytest.mark.asyncio
async def test_invoice_receipt_not_found(client: AsyncClient) -> None:
    """Receipt for a nonexistent invoice returns 404."""
    response = await client.get(
        f"/api/v1/billing/invoices/{uuid.uuid4()}/receipt"
    )
    assert response.status_code == 404
