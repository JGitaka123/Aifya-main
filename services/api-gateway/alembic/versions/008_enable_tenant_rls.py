"""Enable tenant row-level security.

Revision ID: 008_enable_tenant_rls
Revises: 007_employee_staff_sync
Create Date: 2026-06-23
"""

from alembic import op

revision = "008_enable_tenant_rls"
down_revision = "007_employee_staff_sync"
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
    op.execute(
        """
        DO $$
        DECLARE
            table_record record;
        BEGIN
            FOR table_record IN
                SELECT DISTINCT c.table_schema, c.table_name
                FROM information_schema.columns c
                JOIN information_schema.tables t
                  ON t.table_schema = c.table_schema
                 AND t.table_name = c.table_name
                WHERE c.table_schema = 'public'
                  AND c.column_name = 'facility_id'
                  AND t.table_type = 'BASE TABLE'
            LOOP
                EXECUTE format(
                    'DROP POLICY IF EXISTS facility_isolation ON %I.%I',
                    table_record.table_schema,
                    table_record.table_name
                );
                EXECUTE format(
                    'ALTER TABLE %I.%I NO FORCE ROW LEVEL SECURITY',
                    table_record.table_schema,
                    table_record.table_name
                );
                EXECUTE format(
                    'ALTER TABLE %I.%I DISABLE ROW LEVEL SECURITY',
                    table_record.table_schema,
                    table_record.table_name
                );
            END LOOP;
        END $$;
        """
    )
