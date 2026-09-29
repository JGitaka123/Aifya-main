"""Aifya usage billing - inpatient bed-days and the monthly hospital invoice.

Two gaps in 037 are closed here.

**Inpatient bed-days.** 037 metered only the days an encounter was recorded, so
a patient admitted for four days with a single admission-day encounter counted
once. That under-bills an agreement priced per day in the ward. This migration
adds ``inpatient_patients`` to the daily ledger, and the service now counts
every calendar day a patient occupied a bed - admission day and discharge day
inclusive - taken from ``admissions.admitted_at`` / ``discharged_at``.

A patient in a bed on a given day is attributed to Inpatient for that day, so
the three channels stay a partition of one deduplicated daily total rather
than three overlapping counts.

**The monthly invoice.** The ledger could be finalized but nothing was issued
against it. ``aifya_usage_invoices`` holds one live invoice per facility per
calendar month, with a number, a status that tracks issued / paid / void, and
the payment record. A voided invoice does not block a replacement, which is
why the month uniqueness is a partial index.

Both tables are facility-scoped and carry the same FORCE ROW LEVEL SECURITY
policy as every other tenant table.

Safe to re-run: every step is guarded with IF NOT EXISTS / DROP POLICY IF
EXISTS.

Revision ID: 038_aifya_usage_bed_invoice
Revises: 037_aifya_usage_billing
Create Date: 2026-09-29
"""

from alembic import op

revision = "038_aifya_usage_bed_invoice"
down_revision = "037_aifya_usage_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE aifya_usage_daily ADD COLUMN IF NOT EXISTS "
        "inpatient_patients integer NOT NULL DEFAULT 0"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS aifya_usage_invoices (
            id uuid PRIMARY KEY,
            facility_id uuid NOT NULL,
            invoice_number varchar(30) NOT NULL,
            period_year integer NOT NULL,
            period_month integer NOT NULL,
            patient_days integer NOT NULL DEFAULT 0,
            registration_patient_days integer NOT NULL DEFAULT 0,
            emergency_patient_days integer NOT NULL DEFAULT 0,
            inpatient_patient_days integer NOT NULL DEFAULT 0,
            rate_cents integer,
            amount_cents integer NOT NULL DEFAULT 0,
            paid_cents integer NOT NULL DEFAULT 0,
            currency varchar(3) NOT NULL DEFAULT 'KES',
            status varchar(20) NOT NULL DEFAULT 'draft',
            issued_at timestamptz,
            due_at timestamptz,
            paid_at timestamptz,
            payment_reference varchar(100),
            notes text,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            created_by uuid,
            updated_by uuid,
            is_deleted boolean NOT NULL DEFAULT false,
            deleted_at timestamptz
        )
        """
    )
    # One live invoice per facility per month. A voided invoice is excluded so
    # a replacement can be raised without colliding with its predecessor.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_aifya_usage_invoices_live_period "
        "ON aifya_usage_invoices (facility_id, period_year, period_month) "
        "WHERE is_deleted = false AND status <> 'void'"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_aifya_usage_invoices_number "
        "ON aifya_usage_invoices (facility_id, invoice_number)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_aifya_usage_invoices_facility_status "
        "ON aifya_usage_invoices (facility_id, status)"
    )

    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE public.aifya_usage_invoices ENABLE ROW LEVEL SECURITY;
            ALTER TABLE public.aifya_usage_invoices FORCE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS facility_isolation
                ON public.aifya_usage_invoices;
            CREATE POLICY facility_isolation ON public.aifya_usage_invoices
                USING (facility_id::text = current_setting('app.current_facility_id', true))
                WITH CHECK (facility_id::text = current_setting('app.current_facility_id', true));
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aifya_usage_invoices")
    op.execute(
        "ALTER TABLE aifya_usage_daily DROP COLUMN IF EXISTS inpatient_patients"
    )
