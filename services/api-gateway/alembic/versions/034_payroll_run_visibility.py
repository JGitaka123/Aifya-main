"""Payroll run visibility - skipped employees and GL posting outcome.

A payroll run could look complete while two things had silently gone wrong.
Employees with no salary record (or a zero gross) were skipped with only a log
line, so the run total came out short with nothing on screen to say who was
missing. Approving a run also attempted the Finance general-ledger post and
swallowed any failure, leaving the run marked "approved" with no indication
that nothing had reached the ledger - and no way to retry it.

These columns keep both facts on the run itself:

    skipped_employees  who was left out and why, captured at calculation time
    gl_posting_error   why the ledger post failed, NULL once it succeeds
    gl_attempted_at    when the ledger post was last tried

Safe to re-run: every step is guarded with IF NOT EXISTS.

Revision ID: 034_payroll_run_visibility
Revises: 033_encounter_triage
Create Date: 2026-09-28
"""

from alembic import op

revision = "034_payroll_run_visibility"
down_revision = "033_encounter_triage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE payroll_runs ADD COLUMN IF NOT EXISTS skipped_employees "
        "jsonb NOT NULL DEFAULT '[]'::jsonb"
    )
    op.execute(
        "ALTER TABLE payroll_runs ADD COLUMN IF NOT EXISTS gl_posting_error text"
    )
    op.execute(
        "ALTER TABLE payroll_runs ADD COLUMN IF NOT EXISTS gl_attempted_at "
        "timestamp with time zone"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE payroll_runs DROP COLUMN IF EXISTS gl_attempted_at")
    op.execute("ALTER TABLE payroll_runs DROP COLUMN IF EXISTS gl_posting_error")
    op.execute("ALTER TABLE payroll_runs DROP COLUMN IF EXISTS skipped_employees")
