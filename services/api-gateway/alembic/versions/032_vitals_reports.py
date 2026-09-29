"""Vitals reports - the numbered slip a triage recording produces.

Recording vitals wrote a row and an event, but nothing the patient could be
handed and nothing a history could quote by reference. The nurse is the first
person most patients see, so their recording deserves the same treatment as
the consultation fee: a numbered document, kept in the patient's history and
issued to the patient.

This adds the report number and the one-line summary to vital_signs rather
than opening a parallel table, because a report is not a second observation -
it is the same measurement, addressed and phrased for a human.

Safe to re-run: every step is guarded with IF NOT EXISTS.

Revision ID: 032_vitals_reports
Revises: 031_admission_orders
Create Date: 2026-09-27
"""

from alembic import op

revision = "032_vitals_reports"
down_revision = "031_admission_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE vital_signs ADD COLUMN IF NOT EXISTS report_number varchar(30)"
    )
    op.execute(
        "ALTER TABLE vital_signs ADD COLUMN IF NOT EXISTS summary varchar(500)"
    )
    # The report is looked up by the number printed on the slip.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_vitals_report_number "
        "ON vital_signs (facility_id, report_number)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_vitals_report_number")
    op.execute("ALTER TABLE vital_signs DROP COLUMN IF EXISTS summary")
    op.execute("ALTER TABLE vital_signs DROP COLUMN IF EXISTS report_number")
