"""Encounter outcome - what the department actually did.

A department closed a visit by flipping the status to completed, and nothing
was written down. So "completed" could not say what was done, by whom or when:
the filling, the dressing, the advice to return in a fortnight all lived in the
clinician's head, and the receiving department had no record that its work was
finished.

outcome is that closing note and completed_at is when it was written. The
outcome is required to complete a visit (enforced by the API, not the column),
so a completed encounter always says what was done.

Both columns are additive: a visit completed before this migration keeps a NULL
outcome and has completed_at backfilled from its last update, so yesterday's
closed visits do not read as unfinished.

Safe to re-run: every step is guarded with IF NOT EXISTS.

Revision ID: 035_encounter_outcome
Revises: 034_payroll_run_visibility
Create Date: 2026-09-28
"""

from alembic import op

revision = "035_encounter_outcome"
down_revision = "034_payroll_run_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE encounters ADD COLUMN IF NOT EXISTS outcome text")
    op.execute(
        "ALTER TABLE encounters ADD COLUMN IF NOT EXISTS completed_at "
        "timestamp with time zone"
    )
    # Closed visits were completed at the last time anyone touched them.
    op.execute(
        """
        UPDATE encounters
           SET completed_at = updated_at
         WHERE status = 'completed'
           AND completed_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE encounters DROP COLUMN IF EXISTS completed_at")
    op.execute("ALTER TABLE encounters DROP COLUMN IF EXISTS outcome")
