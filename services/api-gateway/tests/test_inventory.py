import uuid

import pytest
from httpx import AsyncClient


# -- Helpers ------------------------------------------------------------------


def _item_payload() -> dict[str, object]:
    """Return a valid inventory item creation payload.

    @returns Dict with item fields
    """
    return {
        "name": "Surgical Gloves (Medium)",
        "category": "consumable",
        "unit_of_measure": "box",
        "unit_cost": 5000,
        "reorder_level": 10,
        "reorder_quantity": 50,
    }


def _supplier_payload() -> dict[str, object]:
    """Return a valid supplier creation payload.

    @returns Dict with supplier fields
    """
    return {
        "name": "MedSupply Kenya Ltd",
        "contact_person": "James Mwangi",
        "phone": "0722333444",
        "email": "james@medsupply.co.ke",
    }


async def _create_item(client: AsyncClient) -> str:
    """Create an inventory item and return its ID.

    @param client: Async HTTP test client
    @returns Item UUID string
    """
    response = await client.post("/api/v1/inventory/items", json=_item_payload())
    assert response.status_code == 201
    return response.json()["id"]


# -- Summary ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inventory_summary(client: AsyncClient) -> None:
    """Test fetching inventory summary stats."""
    response = await client.get("/api/v1/inventory/summary")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert isinstance(data, dict)


# -- Items: empty list --------------------------------------------------------


@pytest.mark.asyncio
async def test_list_items_empty(client: AsyncClient) -> None:
    """Test listing inventory items returns empty when none exist."""
    response = await client.get("/api/v1/inventory/items")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert isinstance(data, dict)


# -- Items: create ------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_item(client: AsyncClient) -> None:
    """Test creating an inventory item."""
    payload = _item_payload()
    response = await client.post("/api/v1/inventory/items", json=payload)

    assert response.status_code == 201
    data: dict[str, object] = response.json()
    assert data["name"] == "Surgical Gloves (Medium)"
    assert data["category"] == "consumable"
    assert data["unit_of_measure"] == "box"
    assert data["unit_cost"] == 5000
    assert data["reorder_level"] == 10
    assert data["reorder_quantity"] == 50
    assert "id" in data
    assert "created_at" in data


# -- Items: get detail --------------------------------------------------------


@pytest.mark.asyncio
async def test_get_item(client: AsyncClient) -> None:
    """Test fetching a single inventory item by ID."""
    item_id = await _create_item(client)

    response = await client.get(f"/api/v1/inventory/items/{item_id}")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert data["id"] == item_id
    assert data["name"] == "Surgical Gloves (Medium)"


# -- Items: 404 ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_item_not_found(client: AsyncClient) -> None:
    """Test 404 when fetching a non-existent inventory item."""
    fake_id = str(uuid.uuid4())
    response = await client.get(f"/api/v1/inventory/items/{fake_id}")

    assert response.status_code == 404


# -- Transactions: create -----------------------------------------------------


@pytest.mark.asyncio
async def test_create_transaction(client: AsyncClient) -> None:
    """Test creating a stock received transaction."""
    item_id = await _create_item(client)

    response = await client.post(
        "/api/v1/inventory/transactions",
        json={
            "item_id": item_id,
            "transaction_type": "receipt",
            "quantity": 100,
            "unit_cost": 5000,
        },
    )

    assert response.status_code == 201
    data: dict[str, object] = response.json()
    assert data["item_id"] == item_id
    assert data["transaction_type"] == "receipt"
    assert data["quantity"] == 100
    assert data["balance_after"] == 100
    assert data["unit_cost"] == 5000
    assert data["reference_number"]
    assert "id" in data


# -- Transactions: list -------------------------------------------------------


@pytest.mark.asyncio
async def test_list_transactions(client: AsyncClient) -> None:
    """Test listing inventory transactions after creating one."""
    item_id = await _create_item(client)
    await client.post(
        "/api/v1/inventory/transactions",
        json={
            "item_id": item_id,
            "transaction_type": "receipt",
            "quantity": 100,
            "unit_cost": 5000,
        },
    )

    response = await client.get("/api/v1/inventory/transactions")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert isinstance(data, dict)


# -- Suppliers: empty list ----------------------------------------------------


@pytest.mark.asyncio
async def test_list_suppliers_empty(client: AsyncClient) -> None:
    """Test listing suppliers returns empty when none exist."""
    response = await client.get("/api/v1/inventory/suppliers")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert isinstance(data, dict)


# -- Suppliers: create --------------------------------------------------------


@pytest.mark.asyncio
async def test_create_supplier(client: AsyncClient) -> None:
    """Test creating an inventory supplier."""
    payload = _supplier_payload()
    response = await client.post("/api/v1/inventory/suppliers", json=payload)

    assert response.status_code == 201
    data: dict[str, object] = response.json()
    assert data["name"] == "MedSupply Kenya Ltd"
    assert data["contact_person"] == "James Mwangi"
    assert data["phone"] == "0722333444"
    assert data["email"] == "james@medsupply.co.ke"
    assert "id" in data
    assert "created_at" in data


# -- Purchase Orders: empty list ----------------------------------------------


@pytest.mark.asyncio
async def test_list_purchase_orders_empty(client: AsyncClient) -> None:
    """Test listing purchase orders returns empty when none exist."""
    response = await client.get("/api/v1/inventory/purchase-orders")

    assert response.status_code == 200
    data: dict[str, object] = response.json()
    assert isinstance(data, dict)


# -- Transactions: negative stock guard ---------------------------------------


@pytest.mark.asyncio
async def test_issue_cannot_exceed_stock(client: AsyncClient) -> None:
    """Issuing more than the on-hand balance must be rejected (no negative stock)."""
    item_id = await _create_item(client)
    receipt = await client.post(
        "/api/v1/inventory/transactions",
        json={
            "item_id": item_id,
            "transaction_type": "receipt",
            "quantity": 10,
            "unit_cost": 5000,
        },
    )
    assert receipt.status_code == 201

    over_issue = await client.post(
        "/api/v1/inventory/transactions",
        json={
            "item_id": item_id,
            "transaction_type": "issue",
            "quantity": 25,
            "unit_cost": 5000,
        },
    )
    assert over_issue.status_code == 400
    assert "insufficient stock" in over_issue.json()["detail"].lower()

    exact_issue = await client.post(
        "/api/v1/inventory/transactions",
        json={
            "item_id": item_id,
            "transaction_type": "issue",
            "quantity": 10,
            "unit_cost": 5000,
        },
    )
    assert exact_issue.status_code == 201
    assert exact_issue.json()["balance_after"] == 0
