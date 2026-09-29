"""Aifya usage billing - patient-day metering for the hospital's own bill.

Aifya charges the hospital, not the patient, for patient-days of use. This
migration adds the two tables that make that bill auditable:

    aifya_usage_daily   one row per facility per day, holding the number of
                        billable patients, the rate that was applied and the
                        resulting amount. The rate is snapshotted on the row so
                        a later rate change cannot silently rewrite a month
                        that has already been billed.
    aifya_usage_config  the per-facility rate, defaulting to KES 20 per
                        patient-day when no row exists.

A "patient-day" is one patient on one calendar day. A patient who is seen in
both Registration and Emergency on the same day is one patient-day, not two.
Across a month the sum of the daily counts is the patient-day total.

Both tables are facility-scoped and therefore carry the same FORCE ROW LEVEL
SECURITY policy as every other tenant table (migrations 008/018/022/030/031).

Safe to re-run: every step is guarded with IF NOT EXISTS / DROP POLICY IF
EXISTS.

Revision ID: 037_aifya_usage_billing
Revises: 036_rls_aware_backfills
Create Date: 2026-09-29
"""

from alembic import op

revision = "037_aifya_usage_billing"
down_revision = "036_rls_aware_backfills"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS aifya_usage_daily (
            id uuid PRIMARY KEY,
            facility_id uuid NOT NULL,
            usage_date date NOT NULL,
            registration_patients integer NOT NULL DEFAULT 0,
            emergency_patients integer NOT NULL DEFAULT 0,
            total_billable_patients integer NOT NULL DEFAULT 0,
            rate_cents integer NOT NULL DEFAULT 2000,
            currency varchar(3) NOT NULL DEFAULT 'KES',
            amount_cents integer NOT NULL DEFAULT 0,
            is_finalized boolean NOT NULL DEFAULT false,
            finalized_at timestamptz,
            computed_at timestamptz NOT NULL DEFAULT now(),
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            created_by uuid,
            updated_by uuid,
            is_deleted boolean NOT NULL DEFAULT false,
            deleted_at timestamptz
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_aifya_usage_daily_facility_date "
        "ON aifya_usage_daily (facility_id, usage_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_aifya_usage_daily_facility_date "
        "ON aifya_usage_daily (facility_id, usage_date DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS aifya_usage_config (
            id uuid PRIMARY KEY,
            facility_id uuid NOT NULL,
            rate_cents integer NOT NULL DEFAULT 2000,
            currency varchar(3) NOT NULL DEFAULT 'KES',
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
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_aifya_usage_config_facility "
        "ON aifya_usage_config (facility_id)"
    )

    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE public.aifya_usage_daily ENABLE ROW LEVEL SECURITY;
            ALTER TABLE public.aifya_usage_daily FORCE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS facility_isolation
                ON public.aifya_usage_daily;
            CREATE POLICY facility_isolation ON public.aifya_usage_daily
                USING (facility_id::text = current_setting('app.current_facility_id', true))
                WITH CHECK (facility_id::text = current_setting('app.current_facility_id', true));

            ALTER TABLE public.aifya_usage_config ENABLE ROW LEVEL SECURITY;
            ALTER TABLE public.aifya_usage_config FORCE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS facility_isolation
                ON public.aifya_usage_config;
            CREATE POLICY facility_isolation ON public.aifya_usage_config
                USING (facility_id::text = current_setting('app.current_facility_id', true))
                WITH CHECK (facility_id::text = current_setting('app.current_facility_id', true));
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS aifya_usage_config")
    op.execute("DROP TABLE IF EXISTS aifya_usage_daily")
