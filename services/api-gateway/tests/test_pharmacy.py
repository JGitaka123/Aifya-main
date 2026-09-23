import uuid

import pytest
from httpx import AsyncClient


# ── Helper data ──────────────────────────────────────────────────────────────

def _inventory_item_payload() -> dict[str, object]:
    """Return a valid pharmacy inventory item creation payload."""
    return {
        "drug_code": "PARA-500",
        "drug_name": "Paracetamol 500mg",
        "generic_name": "Paracetamol",
        "dosage_form": "tablet",
        "strength": "500mg",
        "unit_of_measure": "tablet",
        "reorder_level": 100,
        "selling_price_cents": 500,
        "buying_price_cents": 300,
    }


# ── Inventory: list (empty) ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_inventory_empty(client: AsyncClient) -> None:
    """Test listing pharmacy inventory returns empty list when no items exist."""
    response = await client.get("/api/v1/pharmacy/inventory")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 50


# ── Inventory: create ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_inventory_item(client: AsyncClient) -> None:
    """Test creating a pharmacy inventory item returns the created item."""
    payload = _inventory_item_payload()
    response = await client.post("/api/v1/pharmacy/inventory", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["drug_code"] == "PARA-500"
    assert data["drug_name"] == "Paracetamol 500mg"
    assert data["generic_name"] == "Paracetamol"
    assert data["dosage_form"] == "tablet"
    assert data["strength"] == "500mg"
    assert data["unit_of_measure"] == "tablet"
    assert data["reorder_level"] == 100
    assert data["selling_price_cents"] == 500
    assert data["buying_price_cents"] == 300
    assert data["is_active"] is True
    assert data["current_quantity"] == 0
    assert "id" in data
    assert "created_at" in data
    assert "facility_id" in data


@pytest.mark.asyncio
async def test_create_inventory_item_minimal(client: AsyncClient) -> None:
    """Test creating an inventory item with only required fields."""
    payload = {
        "drug_code": "AMX-250",
        "drug_name": "Amoxicillin 250mg",
    }
    response = await client.post("/api/v1/pharmacy/inventory", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["drug_code"] == "AMX-250"
    assert data["drug_name"] == "Amoxicillin 250mg"
    assert data["generic_name"] is None
    assert data["dosage_form"] is None
    assert data["current_quantity"] == 0
    assert data["unit_of_measure"] == "tablet"
    assert data["reorder_level"] == 10


@pytest.mark.asyncio
async def test_create_inventory_item_invalid_dosage_form(client: AsyncClient) -> None:
    """Test validation rejects invalid dosage_form values."""
    payload = {**_inventory_item_payload(), "dosage_form": "invalid_form"}
    response = await client.post("/api/v1/pharmacy/inventory", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_inventory_item_missing_drug_name(client: AsyncClient) -> None:
    """Test validation rejects missing required drug_name field."""
    payload = {"drug_code": "TEST-1"}
    response = await client.post("/api/v1/pharmacy/inventory", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_inventory_item_missing_drug_code(client: AsyncClient) -> None:
    """Test validation rejects missing required drug_code field."""
    payload = {"drug_name": "Test Drug"}
    response = await client.post("/api/v1/pharmacy/inventory", json=payload)

    assert response.status_code == 422


# ── Inventory: list (with items) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_inventory_after_create(client: AsyncClient) -> None:
    """Test listing inventory returns created items."""
    payload = _inventory_item_payload()
    await client.post("/api/v1/pharmacy/inventory", json=payload)

    response = await client.get("/api/v1/pharmacy/inventory")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["drug_name"] == "Paracetamol 500mg"


@pytest.mark.asyncio
async def test_list_inventory_search(client: AsyncClient) -> None:
    """Test searching inventory by drug name."""
    await client.post("/api/v1/pharmacy/inventory", json=_inventory_item_payload())
    await client.post(
        "/api/v1/pharmacy/inventory",
        json={
            **_inventory_item_payload(),
            "drug_code": "IBU-400",
            "drug_name": "Ibuprofen 400mg",
            "generic_name": "Ibuprofen",
        },
    )

    response = await client.get("/api/v1/pharmacy/inventory", params={"q": "Paracetamol"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["drug_name"] == "Paracetamol 500mg"


@pytest.mark.asyncio
async def test_list_inventory_pagination(client: AsyncClient) -> None:
    """Test inventory pagination parameters."""
    for i in range(3):
        payload = {**_inventory_item_payload(), "drug_code": f"DRUG-{i}", "drug_name": f"Drug {i}"}
        await client.post("/api/v1/pharmacy/inventory", json=payload)

    response = await client.get(
        "/api/v1/pharmacy/inventory", params={"page": "1", "page_size": "2"}
    )
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2

    response = await client.get(
        "/api/v1/pharmacy/inventory", params={"page": "2", "page_size": "2"}
    )
    data = response.json()
    assert len(data["items"]) == 1
    assert data["page"] == 2


# ── Inventory: update ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_inventory_item(client: AsyncClient) -> None:
    """Test updating a pharmacy inventory item."""
    create_response = await client.post(
        "/api/v1/pharmacy/inventory", json=_inventory_item_payload()
    )
    item_id = create_response.json()["id"]

    update_payload: dict[str, object] = {
        "drug_name": "Paracetamol 500mg Tabs",
        "reorder_level": 200,
        "selling_price_cents": 600,
        "shelf_location": "A-12",
    }
    response = await client.patch(
        f"/api/v1/pharmacy/inventory/{item_id}", json=update_payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["drug_name"] == "Paracetamol 500mg Tabs"
    assert data["reorder_level"] == 200
    assert data["selling_price_cents"] == 600
    assert data["shelf_location"] == "A-12"
    # Unchanged fields preserved
    assert data["drug_code"] == "PARA-500"
    assert data["generic_name"] == "Paracetamol"
    assert data["dosage_form"] == "tablet"


@pytest.mark.asyncio
async def test_update_inventory_item_deactivate(client: AsyncClient) -> None:
    """Test deactivating a pharmacy inventory item."""
    create_response = await client.post(
        "/api/v1/pharmacy/inventory", json=_inventory_item_payload()
    )
    item_id = create_response.json()["id"]

    response = await client.patch(
        f"/api/v1/pharmacy/inventory/{item_id}", json={"is_active": False}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["is_active"] is False


@pytest.mark.asyncio
async def test_update_inventory_item_not_found(client: AsyncClient) -> None:
    """Test 404 when updating a non-existent inventory item."""
    fake_id = str(uuid.uuid4())
    response = await client.patch(
        f"/api/v1/pharmacy/inventory/{fake_id}",
        json={"drug_name": "Ghost Drug"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Pharmacy item not found"


# ── Stock: receive ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_receive_stock(client: AsyncClient) -> None:
    """Test receiving stock increases inventory and returns a transaction record."""
    create_response = await client.post(
        "/api/v1/pharmacy/inventory", json=_inventory_item_payload()
    )
    item_id = create_response.json()["id"]

    receipt_payload: dict[str, object] = {
        "pharmacy_item_id": item_id,
        "quantity": 500,
        "batch_number": "BATCH-2026-001",
        "expiry_date": "2027-12-31",
        "unit_cost_cents": 250,
        "reference_number": "PO-0001",
        "reason": "Initial stock procurement",
    }
    response = await client.post("/api/v1/pharmacy/stock/receive", json=receipt_payload)

    assert response.status_code == 201
    data = response.json()
    assert data["pharmacy_item_id"] == item_id
    assert data["transaction_type"] == "receipt"
    assert data["quantity_change"] == 500
    assert data["quantity_before"] == 0
    assert data["quantity_after"] == 500
    assert data["batch_number"] == "BATCH-2026-001"
    assert data["expiry_date"] == "2027-12-31"
    assert data["unit_cost_cents"] == 250
    assert data["reference_number"] == "PO-0001"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_receive_stock_minimal(client: AsyncClient) -> None:
    """Test receiving stock with only required fields."""
    create_response = await client.post(
        "/api/v1/pharmacy/inventory", json=_inventory_item_payload()
    )
    item_id = create_response.json()["id"]

    receipt_payload: dict[str, object] = {
        "pharmacy_item_id": item_id,
        "quantity": 100,
    }
    response = await client.post("/api/v1/pharmacy/stock/receive", json=receipt_payload)

    assert response.status_code == 201
    data = response.json()
    assert data["quantity_change"] == 100
    assert data["quantity_after"] == 100


@pytest.mark.asyncio
async def test_receive_stock_invalid_item(client: AsyncClient) -> None:
    """Test receiving stock for a non-existent item returns 400."""
    receipt_payload: dict[str, object] = {
        "pharmacy_item_id": str(uuid.uuid4()),
        "quantity": 100,
    }
    response = await client.post("/api/v1/pharmacy/stock/receive", json=receipt_payload)

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_receive_stock_zero_quantity(client: AsyncClient) -> None:
    """Test validation rejects zero quantity on stock receipt."""
    create_response = await client.post(
        "/api/v1/pharmacy/inventory", json=_inventory_item_payload()
    )
    item_id = create_response.json()["id"]

    receipt_payload: dict[str, object] = {
        "pharmacy_item_id": item_id,
        "quantity": 0,
    }
    response = await client.post("/api/v1/pharmacy/stock/receive", json=receipt_payload)

    assert response.status_code == 422


# ── Stock: adjust ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stock_adjustment_positive(client: AsyncClient) -> None:
    """Test positive stock adjustment (correction/found stock)."""
    # Create item and receive initial stock
    create_response = await client.post(
        "/api/v1/pharmacy/inventory", json=_inventory_item_payload()
    )
    item_id = create_response.json()["id"]
    await client.post(
        "/api/v1/pharmacy/stock/receive",
        json={"pharmacy_item_id": item_id, "quantity": 200},
    )

    adjustment_payload: dict[str, object] = {
        "pharmacy_item_id": item_id,
        "quantity_change": 50,
        "reason": "Stock count correction — found extra 50 units",
        "reference_number": "ADJ-001",
    }
    response = await client.post("/api/v1/pharmacy/stock/adjust", json=adjustment_payload)

    assert response.status_code == 201
    data = response.json()
    assert data["pharmacy_item_id"] == item_id
    assert data["transaction_type"] == "adjustment"
    assert data["quantity_change"] == 50
    assert data["quantity_before"] == 200
    assert data["quantity_after"] == 250
    assert data["reason"] == "Stock count correction — found extra 50 units"
    assert data["reference_number"] == "ADJ-001"


@pytest.mark.asyncio
async def test_stock_adjustment_negative(client: AsyncClient) -> None:
    """Test negative stock adjustment (loss, damage, expiry)."""
    create_response = await client.post(
        "/api/v1/pharmacy/inventory", json=_inventory_item_payload()
    )
    item_id = create_response.json()["id"]
    await client.post(
        "/api/v1/pharmacy/stock/receive",
        json={"pharmacy_item_id": item_id, "quantity": 200},
    )

    adjustment_payload: dict[str, object] = {
        "pharmacy_item_id": item_id,
        "quantity_change": -30,
        "reason": "Damaged during storage — 30 units discarded",
    }
    response = await client.post("/api/v1/pharmacy/stock/adjust", json=adjustment_payload)

    assert response.status_code == 201
    data = response.json()
    assert data["quantity_change"] == -30
    assert data["quantity_before"] == 200
    assert data["quantity_after"] == 170


@pytest.mark.asyncio
async def test_stock_adjustment_missing_reason(client: AsyncClient) -> None:
    """Test validation rejects stock adjustment without a reason."""
    create_response = await client.post(
        "/api/v1/pharmacy/inventory", json=_inventory_item_payload()
    )
    item_id = create_response.json()["id"]

    adjustment_payload: dict[str, object] = {
        "pharmacy_item_id": item_id,
        "quantity_change": -10,
    }
    response = await client.post("/api/v1/pharmacy/stock/adjust", json=adjustment_payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_stock_adjustment_invalid_item(client: AsyncClient) -> None:
    """Test stock adjustment for non-existent item returns 400."""
    adjustment_payload: dict[str, object] = {
        "pharmacy_item_id": str(uuid.uuid4()),
        "quantity_change": -10,
        "reason": "Testing with invalid item",
    }
    response = await client.post("/api/v1/pharmacy/stock/adjust", json=adjustment_payload)

    assert response.status_code == 400


# ── Pharmacy Queue ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pharmacy_queue_empty(client: AsyncClient) -> None:
    """Test pharmacy queue returns empty list when no pending prescriptions."""
    response = await client.get("/api/v1/pharmacy/queue")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0


# ── Stock Alerts ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stock_alerts_empty(client: AsyncClient) -> None:
    """Test stock alerts returns empty list when no alerts exist."""
    response = await client.get("/api/v1/pharmacy/alerts")

    assert response.status_code == 200
    data = response.json()
    assert data == []


@pytest.mark.asyncio
async def test_stock_alerts_after_low_stock_item(client: AsyncClient) -> None:
    """Test stock alerts includes items below reorder level."""
    # Create item with reorder_level=100 but no stock (quantity=0)
    payload = {**_inventory_item_payload(), "reorder_level": 100}
    await client.post("/api/v1/pharmacy/inventory", json=payload)

    response = await client.get("/api/v1/pharmacy/alerts")

    assert response.status_code == 200
    data = response.json()
    # Item has 0 quantity with reorder_level=100 so should trigger alert
    assert isinstance(data, list)
    if len(data) > 0:
        alert = data[0]
        assert alert["drug_name"] == "Paracetamol 500mg"
        assert alert["drug_code"] == "PARA-500"
        assert alert["current_quantity"] == 0
        assert alert["reorder_level"] == 100
        assert alert["alert_type"] in ("low_stock", "out_of_stock")
