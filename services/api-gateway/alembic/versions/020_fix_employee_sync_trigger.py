"""Fix employee-to-staff sync trigger for encrypted PII

Revision ID: 020_fix_employee_sync_trigger
Revises: 019_internal_auth_accounts
Create Date: 2026-09-09
"""
import sqlalchemy as sa
from alembic import op

revision = "020_fix_employee_sync_trigger"
down_revision = "019_internal_auth_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The original trigger copied employees.id_number / employees.kra_pin
    # into staff_profiles.national_id / kra_pin. Since 011 those columns on
    # `employees` hold Fernet ciphertext (~140+ chars), which overflowed the
    # varchar(20) staff_profiles columns and turned every employee insert
    # into a 500. The sync only needs directory-safe columns, so write NULLs
    # for the PII fields (payroll keeps its own encrypted copy).
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_employee_to_staff()
        RETURNS TRIGGER AS $func$
        DECLARE
            v_staff_id uuid;
            v_first_name varchar;
            v_last_name varchar;
            v_role varchar;
        BEGIN
            v_first_name := split_part(NEW.full_name, ' ', 1);
            v_last_name := substr(NEW.full_name, length(v_first_name) + 2);
            v_role := CASE
            WHEN lower(NEW.job_title) LIKE '%doctor%'
                 OR lower(NEW.job_title) LIKE '%physician%'
                 OR lower(NEW.job_title) LIKE '%medical officer%'
                 OR lower(NEW.job_title) LIKE '%consultant%' THEN 'doctor'
            WHEN lower(NEW.job_title) LIKE '%midwife%' THEN 'midwife'
            WHEN lower(NEW.job_title) LIKE '%nurse%' THEN 'nurse'
            WHEN lower(NEW.job_title) LIKE '%pharmac%' THEN 'pharmacist'
            WHEN lower(NEW.job_title) LIKE '%laborat%'
                 OR lower(NEW.job_title) LIKE '%lab %' THEN 'lab_tech'
            WHEN lower(NEW.job_title) LIKE '%radiolog%' THEN 'radiologist'
            WHEN lower(NEW.job_title) LIKE '%cashier%' THEN 'cashier'
            WHEN lower(NEW.job_title) LIKE '%reception%' THEN 'receptionist'
            WHEN lower(NEW.job_title) LIKE '%record%' THEN 'records'
            ELSE 'staff'
        END;

            INSERT INTO staff (
                id, facility_id, keycloak_user_id, employee_number,
                first_name, last_name, role, email, phone, is_active,
                created_at, updated_at, is_deleted
            ) VALUES (
                gen_random_uuid(),
                NEW.facility_id,
                gen_random_uuid(),
                NEW.staff_id,
                v_first_name,
                v_last_name,
                v_role,
                COALESCE(NEW.email, NEW.staff_id || '@aifya.co.ke'),
                NEW.phone,
                NEW.is_active,
                now(), now(), false
            )
            ON CONFLICT DO NOTHING
            RETURNING id INTO v_staff_id;

            IF v_staff_id IS NOT NULL THEN
                INSERT INTO staff_profiles (
                    id, facility_id, staff_id, employment_type,
                    employment_date, nssf_number,
                    created_at, updated_at, is_deleted
                ) VALUES (
                    gen_random_uuid(),
                    NEW.facility_id,
                    v_staff_id,
                    NEW.employment_type,
                    NEW.hire_date,
                    NEW.nssf_number,
                    now(), now(), false
                );
            END IF;

            RETURN NEW;
        END;
        $func$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE TRIGGER trg_sync_employee_to_staff
        AFTER INSERT ON employees
        FOR EACH ROW EXECUTE FUNCTION sync_employee_to_staff();
        """
    )


    # Belt-and-braces: widen any column that can hold Fernet ciphertext so
    # inserts never hit VARCHAR(20) truncation, including databases created
    # outside the normal Alembic flow.
    op.alter_column(
        "employees", "id_number",
        existing_type=sa.String(length=188),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "employees", "kra_pin",
        existing_type=sa.String(length=188),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "employees", "bank_account",
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "staff_profiles", "national_id",
        existing_type=sa.String(length=20),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "staff_profiles", "kra_pin",
        existing_type=sa.String(length=20),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    # Backfill roles for employee-mirrored staff created before the role
    # mapping existed (previously every mirrored employee became 'staff').
    op.execute(
        """
        WITH derived AS (
            SELECT e.staff_id, e.facility_id, CASE
            WHEN lower(e.job_title) LIKE '%doctor%'
                 OR lower(e.job_title) LIKE '%physician%'
                 OR lower(e.job_title) LIKE '%medical officer%'
                 OR lower(e.job_title) LIKE '%consultant%' THEN 'doctor'
            WHEN lower(e.job_title) LIKE '%midwife%' THEN 'midwife'
            WHEN lower(e.job_title) LIKE '%nurse%' THEN 'nurse'
            WHEN lower(e.job_title) LIKE '%pharmac%' THEN 'pharmacist'
            WHEN lower(e.job_title) LIKE '%laborat%'
                 OR lower(e.job_title) LIKE '%lab %' THEN 'lab_tech'
            WHEN lower(e.job_title) LIKE '%radiolog%' THEN 'radiologist'
            WHEN lower(e.job_title) LIKE '%cashier%' THEN 'cashier'
            WHEN lower(e.job_title) LIKE '%reception%' THEN 'receptionist'
            WHEN lower(e.job_title) LIKE '%record%' THEN 'records'
            ELSE 'staff'
        END AS new_role
            FROM employees AS e
            WHERE e.is_deleted = false
        )
        UPDATE staff AS s
        SET role = d.new_role,
            updated_at = now()
        FROM derived AS d
        WHERE s.employee_number = d.staff_id
          AND s.facility_id = d.facility_id
          AND s.is_deleted = false
          AND d.new_role <> 'staff'
        """,
    )
def downgrade() -> None:
    # Restore the original function that mirrored PII into staff_profiles.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_employee_to_staff()
        RETURNS TRIGGER AS $func$
        DECLARE
            v_staff_id uuid;
            v_first_name varchar;
            v_last_name varchar;
        BEGIN
            v_first_name := split_part(NEW.full_name, ' ', 1);
            v_last_name := substr(NEW.full_name, length(v_first_name) + 2);

            INSERT INTO staff (
                id, facility_id, keycloak_user_id, employee_number,
                first_name, last_name, role, email, phone, is_active,
                created_at, updated_at, is_deleted
            ) VALUES (
                gen_random_uuid(),
                NEW.facility_id,
                gen_random_uuid(),
                NEW.staff_id,
                v_first_name,
                v_last_name,
                'staff',
                COALESCE(NEW.email, NEW.staff_id || '@aifya.co.ke'),
                NEW.phone,
                NEW.is_active,
                now(), now(), false
            )
            ON CONFLICT DO NOTHING
            RETURNING id INTO v_staff_id;

            IF v_staff_id IS NOT NULL THEN
                INSERT INTO staff_profiles (
                    id, facility_id, staff_id, employment_type,
                    employment_date, national_id, kra_pin, nssf_number,
                    created_at, updated_at, is_deleted
                ) VALUES (
                    gen_random_uuid(),
                    NEW.facility_id,
                    v_staff_id,
                    NEW.employment_type,
                    NEW.hire_date,
                    NEW.id_number,
                    NEW.kra_pin,
                    NEW.nssf_number,
                    now(), now(), false
                );
            END IF;

            RETURN NEW;
        END;
        $func$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE OR REPLACE TRIGGER trg_sync_employee_to_staff
        AFTER INSERT ON employees
        FOR EACH ROW EXECUTE FUNCTION sync_employee_to_staff();
        """
    )


