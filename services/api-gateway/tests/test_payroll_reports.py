"""Tests for the payroll statutory report generators.

Each generator reads one payroll run's line items, so these tests stub the two
queries it makes (`_resolve_run`, `_period_lines`) and assert on the shaping,
the approved-run gate, and the totals instead of building a whole payroll run.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.services.payroll import reports


class _FakeRun:
    """Minimal stand-in for a PayrollRun row."""

    def __init__(self, status: str) -> None:
        self.id = uuid.uuid4()
        self.status = status


EMPLOYEE_A = uuid.uuid4()
EMPLOYEE_B = uuid.uuid4()

# (employee_id, name, kra_pin, gross, employee_levy, employer_levy)
HOUSING_LEVY_LINES = [
    (
        EMPLOYEE_A,
        "Alice Wanjiru",
        "A001",
        Decimal("50000"),
        Decimal("750"),
        Decimal("750"),
    ),
    (
        EMPLOYEE_B,
        "Brian Otieno",
        "A002",
        Decimal("120000"),
        Decimal("1800"),
        Decimal("1800"),
    ),
]


@pytest.fixture
def stubbed(monkeypatch):
    """Patch the run/line lookups and hand back the mutable run holder."""
    holder: dict[str, _FakeRun | None] = {"run": _FakeRun("approved")}

    async def _resolve_run(db, facility_id, month, year):
        return holder["run"]

    async def _period_lines(db, facility_id, run, columns):
        return HOUSING_LEVY_LINES

    monkeypatch.setattr(reports, "_resolve_run", _resolve_run)
    monkeypatch.setattr(reports, "_period_lines", _period_lines)
    return holder


@pytest.mark.asyncio
async def test_housing_levy_schedule_shapes_rows_and_totals(stubbed) -> None:
    """Both sides of the levy are reported per employee and totalled."""
    data = await reports.get_housing_levy_schedule(None, uuid.uuid4(), 9, 2026)

    assert [r["employee_name"] for r in data["rows"]] == [
        "Alice Wanjiru",
        "Brian Otieno",
    ]
    first = data["rows"][0]
    assert first["kra_pin"] == "A001"
    assert first["gross_salary"] == Decimal("50000")
    assert first["employee_contribution"] == Decimal("750")
    assert first["employer_contribution"] == Decimal("750")
    assert first["total"] == Decimal("1500")
    assert data["total_employee"] == Decimal("2550")
    assert data["total_employer"] == Decimal("2550")
    assert data["total"] == Decimal("5100")
    assert data["run_status"] == "approved"
    assert data["run_id"] is not None


@pytest.mark.asyncio
async def test_housing_levy_schedule_empty_until_run_is_approved(stubbed) -> None:
    """A draft run is not a returnable period."""
    stubbed["run"] = _FakeRun("draft")

    data = await reports.get_housing_levy_schedule(None, uuid.uuid4(), 9, 2026)

    assert data["rows"] == []
    assert data["total"] == Decimal("0")
    assert data["run_status"] == "draft"


@pytest.mark.asyncio
async def test_housing_levy_schedule_handles_period_with_no_run(stubbed) -> None:
    """No run at all yields an empty schedule, not an error."""
    stubbed["run"] = None

    data = await reports.get_housing_levy_schedule(None, uuid.uuid4(), 9, 2026)

    assert data["rows"] == []
    assert data["run_id"] is None
    assert data["run_status"] is None
