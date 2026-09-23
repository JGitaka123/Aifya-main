"""Startup self-healing DB fixes for encrypted employee columns.

The Employee model stores National ID / KRA PIN / bank account as Fernet
ciphertext (108+ chars). Databases whose `employees` / `staff_profiles`
columns were created at VARCHAR(20) reject those inserts with
`StringDataRightTruncationError`. Running these idempotent ALTERs at startup
widens the columns so the payroll Employees module works without manual SQL.
"""

import logging

from sqlalchemy import text

from app.database import engine

logger = logging.getLogger(__name__)


def _job_title_role_case(column: str) -> str:
    """Build a SQL CASE that maps a payroll job title to the staff role."""
    return f"""
        CASE
            WHEN lower({column}) LIKE '%midwife%' THEN 'midwife'
            WHEN lower({column}) LIKE '%nurse%' THEN 'nurse'
            WHEN lower({column}) LIKE '%doctor%'
                 OR lower({column}) LIKE '%physician%'
                 OR lower({column}) LIKE '%medical officer%'
                 OR lower({column}) LIKE '%consultant%'
                 OR lower({column}) LIKE '%general practitioner%'
                 OR lower({column}) LIKE '%medical practitioner%'
                 OR lower({column}) LIKE '%family practitioner%'
                 OR lower({column}) LIKE '%medical specialist%'
                 OR lower({column}) LIKE '%registrar%'
                 OR lower({column}) LIKE '%surgeon%'
                 OR lower({column}) LIKE '%pediatric%'
                 OR lower({column}) LIKE '%paediatric%'
                 OR lower({column}) LIKE '%gynecolog%'
                 OR lower({column}) LIKE '%gynaecolog%'
                 OR lower({column}) LIKE '%obstetric%'
                 OR lower({column}) LIKE '%dermatolog%'
                 OR lower({column}) LIKE '%cardiolog%'
                 OR lower({column}) LIKE '%neurolog%'
                 OR lower({column}) LIKE '%psychiatr%'
                 OR lower({column}) LIKE '%anesthes%'
                 OR lower({column}) LIKE '%anaesthet%'
                 OR lower({column}) LIKE '%ophthalmolog%'
                 OR lower({column}) LIKE '%otolaryng%'
                 OR lower({column}) LIKE '%orthoped%'
                 OR lower({column}) LIKE '%orthopaed%'
                 OR lower({column}) LIKE '%gastroenterolog%'
                 OR lower({column}) LIKE '%urolog%'
                 OR lower({column}) LIKE '%endocrinolog%'
                 OR lower({column}) LIKE '%nephrolog%'
                 OR lower({column}) LIKE '%pulmonolog%'
                 OR lower({column}) LIKE '%rheumatolog%'
                 OR lower({column}) LIKE '%oncolog%'
                 OR lower({column}) LIKE '%hematolog%'
                 OR lower({column}) LIKE '%haematolog%'
                 OR lower({column}) LIKE '%internist%'
                 OR lower({column}) LIKE '%family medicine%'
                 OR lower({column}) LIKE '%emergency medicine%' THEN 'doctor'
            WHEN lower({column}) LIKE '%pharmac%' THEN 'pharmacist'
            WHEN lower({column}) LIKE '%laborat%'
                 OR lower({column}) LIKE '%lab %' THEN 'lab_tech'
            WHEN lower({column}) LIKE '%radiolog%' THEN 'radiologist'
            WHEN lower({column}) LIKE '%cashier%' THEN 'cashier'
            WHEN lower({column}) LIKE '%reception%' THEN 'receptionist'
            WHEN lower({column}) LIKE '%record%' THEN 'records'
            ELSE 'staff'
        END
    """


# (table, column) pairs that store (or receive) Fernet ciphertext.
_WIDEN_TARGETS = [
    ("employees", "id_number"),
    ("employees", "kra_pin"),
    ("employees", "bank_account"),
    ("staff_profiles", "national_id"),
    ("staff_profiles", "kra_pin"),
]

_TRIGGER_SQL = f"""
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
    v_role := {_job_title_role_case('NEW.job_title')};

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

    IF v_role = 'doctor' THEN
        PERFORM ensure_doctor_default_availability(NEW.facility_id, v_staff_id);
    END IF;

    RETURN NEW;
END;
$func$ LANGUAGE plpgsql;
"""


_DEFAULT_AVAILABILITY_SQL = """
CREATE OR REPLACE FUNCTION ensure_doctor_default_availability(
    p_facility_id uuid,
    p_staff_id uuid
) RETURNS void AS $func$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM doctor_schedules AS ds
        WHERE ds.facility_id = p_facility_id
          AND ds.doctor_id = p_staff_id
          AND ds.is_deleted = false
    ) THEN
        INSERT INTO doctor_schedules (
            id, facility_id, doctor_id, department_id,
            day_of_week, start_time, end_time, slot_duration_minutes,
            max_patients, room, consultation_type, is_active,
            effective_from, effective_until, notes,
            created_at, updated_at, is_deleted
        )
        SELECT
            gen_random_uuid(), p_facility_id, p_staff_id, NULL,
            dow, '08:00'::time, '17:00'::time, 15,
            NULL, NULL, 'general', true,
            NULL, NULL,
            'Auto-created default availability (Mon-Fri 08:00-17:00)',
            now(), now(), false
        FROM generate_series(0, 4) AS dow;
    END IF;
END;
$func$ LANGUAGE plpgsql;
"""


async def ensure_employee_db_fixes() -> None:
    """Widen ciphertext columns and refresh the employee sync trigger."""
    # Each statement runs in its own transaction so one missing table cannot
    # poison the rest of the startup sequence.
    for table, column in _WIDEN_TARGETS:
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    text(
                        f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
                        "TYPE VARCHAR(255)"
                    )
                )
            logger.info("db_fix: widened %s.%s to VARCHAR(255)", table, column)
        except Exception:  # noqa: BLE001 - startup fix must never crash the app
            logger.warning(
                "db_fix: could not widen %s.%s (table may not exist yet)",
                table,
                column,
            )

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            # Recreate function + trigger (kept as one statement so the
            # trigger is replaced atomically with the function).
            await conn.execute(text(_TRIGGER_SQL))
            await conn.execute(
                text(
                    """
                    CREATE OR REPLACE TRIGGER trg_sync_employee_to_staff
                    AFTER INSERT ON employees
                    FOR EACH ROW EXECUTE FUNCTION sync_employee_to_staff();
                    """
                )
            )
            # Backfill roles for staff rows created before the role mapping
            # existed (previously every mirrored employee became role 'staff').
            role_case = _job_title_role_case("e.job_title")
            await conn.execute(
                text(
                    f"""
                    UPDATE staff AS s
                    SET role = {role_case},
                        updated_at = now()
                    FROM employees AS e
                    WHERE s.employee_number = e.staff_id
                      AND s.facility_id = e.facility_id
                      AND s.is_deleted = false
                      AND e.is_deleted = false
                      AND {role_case} <> 'staff'
                    """
                )
            )
            # Every active doctor needs a weekly availability schedule so they
            # show up in the Appointments "choose doctor" flow and can be booked.
            await conn.execute(text(_DEFAULT_AVAILABILITY_SQL))
            await conn.execute(
                text(
                    """
                    SELECT ensure_doctor_default_availability(s.facility_id, s.id)
                    FROM staff AS s
                    WHERE s.role = 'doctor'
                      AND s.is_active = true
                      AND s.is_deleted = false
                    """
                )
            )
        logger.info("db_fix: refreshed sync_employee_to_staff trigger")
    except Exception:  # noqa: BLE001
        logger.warning("db_fix: could not refresh employee sync trigger")
