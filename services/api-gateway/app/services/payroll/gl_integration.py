"""Post approved payroll runs to the Finance General Ledger.

Falls back gracefully if the Finance module is not yet available — logs
a warning and leaves `payroll_run.gl_transaction_id = None`.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payroll import PayrollRun

_logger = logging.getLogger(__name__)
_ZERO = Decimal("0")

# Account codes (must match app.services.finance.seed_data DEFAULT_ACCOUNTS)
ACC_SALARIES_EXPENSE = "5000"
ACC_BANK = "1020"
ACC_PAYE_PAYABLE = "2200"
ACC_NSSF_PAYABLE = "2210"
ACC_SHIF_PAYABLE = "2220"
ACC_HL_PAYABLE = "2230"


def _build_salary_entries(run: PayrollRun) -> list[dict[str, Any]]:
    """Salary journal: DR Salaries Expense, CR all statutory + bank."""
    return [
        {"account_code": ACC_SALARIES_EXPENSE, "debit": run.total_gross, "credit": _ZERO},
        {"account_code": ACC_PAYE_PAYABLE, "debit": _ZERO, "credit": run.total_paye},
        {"account_code": ACC_NSSF_PAYABLE, "debit": _ZERO, "credit": run.total_nssf},
        {"account_code": ACC_SHIF_PAYABLE, "debit": _ZERO, "credit": run.total_shif},
        {"account_code": ACC_HL_PAYABLE, "debit": _ZERO, "credit": run.total_hl},
        {"account_code": ACC_BANK, "debit": _ZERO, "credit": run.total_net},
    ]


def _build_employer_entries(run: PayrollRun) -> list[dict[str, Any]]:
    """Employer statutory journal: DR Salaries Expense, CR NSSF + HL payable."""
    employer_total = run.total_employer_nssf + run.total_employer_hl
    return [
        {"account_code": ACC_SALARIES_EXPENSE, "debit": employer_total, "credit": _ZERO},
        {"account_code": ACC_NSSF_PAYABLE, "debit": _ZERO, "credit": run.total_employer_nssf},
        {"account_code": ACC_HL_PAYABLE, "debit": _ZERO, "credit": run.total_employer_hl},
    ]


async def post_payroll_to_gl(
    db: AsyncSession,
    run: PayrollRun,
    user_id: uuid.UUID,
) -> uuid.UUID | None:
    """Post the salary + employer-statutory journals to the Finance GL.

    Uses `app.services.finance.post_compound_transaction` if available.
    Returns the parent GL transaction id, or None if Finance is not
    available / posting failed (logged at WARNING).

    @param db: Async session
    @param run: Approved PayrollRun
    @param user_id: User triggering the post
    @returns Parent GL transaction id or None
    """
    try:
        from app.services.finance import (
            post_compound_transaction,
        )
    except ImportError:
        _logger.warning(
            "payroll.gl.unavailable",
            extra={
                "payroll_run_id": str(run.id),
                "reason": "finance.post_compound_transaction not importable",
            },
        )
        return None

    salary_entries = _build_salary_entries(run)
    employer_entries = _build_employer_entries(run)
    metadata = {
        "date": run.run_date.date().isoformat() if run.run_date else None,
        "reference_type": "payroll_run",
        "reference_id": str(run.id),
        "description": f"Payroll {run.year}-{run.month:02d}",
    }

    try:
        salary_txn = await post_compound_transaction(
            db=db,
            facility_id=run.facility_id,
            entries=salary_entries,
            metadata={**metadata, "event_type": "payroll_run"},
            idempotency_key=f"payroll_run:{run.id}:salary",
            user_id=user_id,
        )
        await post_compound_transaction(
            db=db,
            facility_id=run.facility_id,
            entries=employer_entries,
            metadata={**metadata, "event_type": "employer_statutory"},
            idempotency_key=f"payroll_run:{run.id}:employer",
            user_id=user_id,
        )
        return getattr(salary_txn, "id", None)
    except Exception as exc:
        _logger.warning(
            "payroll.gl.post_failed",
            extra={
                "payroll_run_id": str(run.id),
                "error": str(exc),
            },
        )
        return None
