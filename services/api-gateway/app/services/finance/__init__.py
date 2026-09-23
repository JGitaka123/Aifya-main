"""
Hospital Finance Module v2.0 — service package.

Exports the canonical posting entry point so other modules
(billing, payroll, inventory) can call into the GL.
"""

from app.services.finance.posting_engine import (
    FinanceError,
    NoOpenPeriodError,
    PeriodLockedError,
    PostingRuleNotFoundError,
    UnbalancedTransactionError,
    post_compound_transaction,
    post_transaction,
    reverse_transaction,
)

__all__ = [
    "FinanceError",
    "NoOpenPeriodError",
    "PeriodLockedError",
    "PostingRuleNotFoundError",
    "UnbalancedTransactionError",
    "post_compound_transaction",
    "post_transaction",
    "reverse_transaction",
]
