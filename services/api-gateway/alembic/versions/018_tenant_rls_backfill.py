"""Tenant RLS backfill for tables added after 008.

Migration 008 enabled FORCE row-level security on every tenant table that
existed at the time. ``lab_test_catalog`` (added in 013) and any other
facility-scoped table created later were never covered, so when the API runs
under the restricted ``aifya_app`` role (see scripts/create-app-db-role.sh)
those rows are NOT isolated per facility. This backfill re-runs the same
idempotent enable/force/policy loop over the current schema so every table
with a ``facility_id`` column is tenant-isolated.

Safe to re-run: each step guards with IF NOT EXISTS / DROP POLICY IF EXISTS.

Revision ID: 018_tenant_rls_backfill
Revises: 017_facility_onboarding
Create Date: 2026-09-08
"""

from alembic import op

revision = "018_tenant_rls_backfill"
down_revision = "017_facility_onboarding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            table_record record;
        BEGIN
            FOR table_record IN
                SELECT
                    c.table_schema,
                    c.table_name,
                    bool_or(c.is_nullable = 'YES') AS nullable_facility
                FROM information_schema.columns c
                JOIN information_schema.tables t
                  ON t.table_schema = c.table_schema
                 AND t.table_name = c.table_name
                WHERE c.table_schema = 'public'
                  AND c.column_name = 'facility_id'
                  AND t.table_type = 'BASE TABLE'
                GROUP BY c.table_schema, c.table_name
            LOOP
                EXECUTE format(
                    'ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',
                    table_record.table_schema,
                    table_record.table_name
                );
                EXECUTE format(
                    'ALTER TABLE %I.%I FORCE ROW LEVEL SECURITY',
                    table_record.table_schema,
                    table_record.table_name
                );
                EXECUTE format(
                    'DROP POLICY IF EXISTS facility_isolation ON %I.%I',
                    table_record.table_schema,
                    table_record.table_name
                );

                IF table_record.nullable_facility THEN
                    EXECUTE format(
                        'CREATE POLICY facility_isolation ON %I.%I '
                        || 'USING (facility_id IS NULL OR facility_id::text = '
                        || 'current_setting(''app.current_facility_id'', true)) '
                        || 'WITH CHECK (facility_id::text = '
                        || 'current_setting(''app.current_facility_id'', true))',
                        table_record.table_schema,
                        table_record.table_name
                    );
                ELSE
                    EXECUTE format(
                        'CREATE POLICY facility_isolation ON %I.%I '
                        || 'USING (facility_id::text = '
                        || 'current_setting(''app.current_facility_id'', true)) '
                        || 'WITH CHECK (facility_id::text = '
                        || 'current_setting(''app.current_facility_id'', true))',
                        table_record.table_schema,
                        table_record.table_name
                    );
                END IF;
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    # Deliberately a no-op: dropping the policy here would remove tenant
    # isolation from tables that migration 008 originally protected.
    pass
