"""Post approved payroll runs to the Finance General Ledger.

A failed post is returned, not raised: the caller records the outcome on the
run so the operator sees that nothing reached the ledger, and can retry.
Posting is idempotent, so a retry never double-posts.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payroll import PayrollRun

_logger = logging.getLogger(__name__)
_ZERO = Decimal("0")


@dataclass(frozen=True)
class GLPostingResult:
    """Outcome of a payroll -> General Ledger posting attempt.

    A failed post is a normal outcome the operator has to see and retry, so it
    is returned rather than raised.

    @param transaction_id: Parent GL transaction id when the post succeeded
    @param error_code: finance_module_unavailable | posting_failed
    @param error_detail: Underlying exception text, for the operator to act on
    """

    transaction_id: uuid.UUID | None = None
    error_code: str | None = None
    error_detail: str | None = None

    @property
    def ok(self) -> bool:
        """Whether both journals reached the ledger."""
        return self.transaction_id is not None


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
) -> GLPostingResult:
    """Post the salary + employer-statutory journals to the Finance GL.

    Never raises: the caller records the outcome on the run so a failure is
    visible to the operator and can be retried. Posting is idempotent - both
    journals carry a stable `payroll_run:{id}:*` key, so replaying a retry
    returns the original transaction instead of double-posting.

    @param db: Async session
    @param run: Approved PayrollRun
    @param user_id: User triggering the post
    @returns GLPostingResult holding the parent transaction id, or the failure
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
        return GLPostingResult(error_code="finance_module_unavailable")

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
        # The employer journal is a second transaction; if it fails the
        # salary journal is already posted, and the idempotency key above
        # makes the retry safe rather than a double-post.
        await post_compound_transaction(
            db=db,
            facility_id=run.facility_id,
            entries=employer_entries,
            metadata={**metadata, "event_type": "employer_statutory"},
            idempotency_key=f"payroll_run:{run.id}:employer",
            user_id=user_id,
        )
        return GLPostingResult(
            transaction_id=getattr(salary_txn, "id", None)
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the operator
        _logger.warning(
            "payroll.gl.post_failed",
            extra={
                "payroll_run_id": str(run.id),
                "error": str(exc),
            },
        )
        return GLPostingResult(
            error_code="posting_failed",
            error_detail=f"{type(exc).__name__}: {exc}",
        )
