-- =============================================================================
-- Aifya - production readiness check (READ ONLY)
-- =============================================================================
--
-- Answers the open questions in section 7 ("Database readiness") and section 14
-- ("Data readiness") of docs/ACCESS-CONTROL-STATUS-REPORT.md, in one run.
--
-- HOW TO RUN
--   psql "$DATABASE_URL" -f services/api-gateway/scripts/production_readiness_check.sql
--
--   Strip "+asyncpg" from DATABASE_URL first, or psql will prompt for a password:
--     postgresql://user:pass@host:5432/dbname
--
-- SAFETY
--   Nothing here writes to your data. The only object created is a temporary
--   table, which lives in this session and disappears when you disconnect.
--
-- WHY THE LAST QUERY NEEDS A LOOP
--   patients, encounters, invoices, staff and departments are all under FORCED
--   row level security, so a plain COUNT(*) returns 0 for every tenant except
--   the one currently set. The loop republishes the tenant per facility so the
--   counts are real. A bare count is the usual reason these checks look like
--   "the data is missing" when it is not.
--
--   facilities is deliberately readable across tenants, so the loop can see
--   every hospital to iterate over.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Schema state - is the database actually at the migrated head?
-- -----------------------------------------------------------------------------
SELECT current_database() AS database_name,
       (SELECT version_num FROM alembic_version) AS alembic_version;

-- -----------------------------------------------------------------------------
-- 2. Column capacity - can these fields hold real hospital data?
--    Expected: payments.received_by is uuid; employees.id_number and
--    employees.kra_pin are both character varying(255).
-- -----------------------------------------------------------------------------
SELECT c.table_name,
       c.column_name,
       c.data_type,
       c.character_maximum_length AS max_length,
       c.is_nullable
FROM information_schema.columns AS c
WHERE c.table_schema = 'public'
  AND (
        (c.table_name = 'payments' AND c.column_name = 'received_by')
     OR (c.table_name = 'employees' AND c.column_name IN ('id_number', 'kra_pin'))
      )
ORDER BY c.table_name, c.column_name;

-- -----------------------------------------------------------------------------
-- 3. Row level security - enabled AND forced on the patient-data tables.
--    Both flags must be true. Enabled alone lets the table owner read across
--    facilities; forced closes that gap.
-- -----------------------------------------------------------------------------
SELECT c.relname AS table_name,
       c.relrowsecurity AS rls_enabled,
       c.relforcerowsecurity AS rls_forced
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'public'
  AND c.relname IN (
        'patients', 'encounters', 'invoices', 'lab_test_catalog', 'staff',
        'payments', 'employees'
      )
ORDER BY c.relname;

-- -----------------------------------------------------------------------------
-- 4. Which policies are actually in force on those tables.
--    One facility_isolation policy per table is expected. Any additional
--    SELECT policy is a deliberate exception and should be explainable.
-- -----------------------------------------------------------------------------
SELECT p.tablename,
       p.policyname,
       p.cmd,
       p.permissive,
       p.roles::text AS applies_to
FROM pg_policies AS p
WHERE p.schemaname = 'public'
  AND p.tablename IN (
        'patients', 'encounters', 'invoices', 'lab_test_catalog', 'staff',
        'payments', 'employees'
      )
ORDER BY p.tablename, p.policyname;

-- -----------------------------------------------------------------------------
-- 5. Access-control matrix - roles, permissions and assignments.
--    Expected: 32 roles, 46 permissions, 491 assignments.
--    Note 491 is the number of rows present; it is NOT 32 x 46 (1,472).
-- -----------------------------------------------------------------------------
SELECT count(DISTINCT role) AS roles,
       count(DISTINCT permission) AS permissions,
       count(*) AS assignments,
       count(*) FILTER (WHERE facility_id IS NOT NULL) AS facility_overrides,
       count(*) FILTER (WHERE is_allowed = false) AS explicit_denials
FROM role_permissions
WHERE is_deleted = false;

-- -----------------------------------------------------------------------------
-- 6. Per-facility readiness - data volumes and the configuration gaps that
--    block the clinical workflow.
-- -----------------------------------------------------------------------------
CREATE TEMP TABLE _aifya_readiness (
    facility               text,
    departments            bigint,
    staff_total            bigint,
    staff_no_department    bigint,
    doctors                bigint,
    patients               bigint,
    encounters             bigint,
    invoices               bigint
);

DO $$
DECLARE
    f RECORD;
BEGIN
    FOR f IN SELECT id, name FROM facilities ORDER BY name, code LOOP
        -- Publish the tenant so the RLS policies reveal this facility's rows.
        PERFORM set_config('app.current_facility_id', f.id::text, true);

        INSERT INTO _aifya_readiness
        SELECT f.name,
               (SELECT count(*) FROM departments),
               (SELECT count(*) FROM staff WHERE is_deleted = false),
               (SELECT count(*) FROM staff
                 WHERE is_deleted = false
                   AND department_id IS NULL
                   AND primary_department_id IS NULL),
               (SELECT count(*) FROM staff
                 WHERE is_deleted = false AND role IN ('doctor', 'clinician',
                                                       'specialist', 'dentist')),
               (SELECT count(*) FROM patients WHERE is_deleted = false),
               (SELECT count(*) FROM encounters WHERE is_deleted = false),
               (SELECT count(*) FROM invoices WHERE is_deleted = false);
    END LOOP;
END $$;

SELECT facility,
       departments,
       staff_total,
       staff_no_department,
       doctors,
       patients,
       encounters,
       invoices
FROM _aifya_readiness
ORDER BY facility;

-- -----------------------------------------------------------------------------
-- 7. Is this real patient data or demo data?
--    A heuristic, not proof: placeholder names, example domains and repeated
--    digits in a phone number are the usual fingerprints of seeded demo rows.
--    Read it alongside the total, not instead of it.
-- -----------------------------------------------------------------------------
CREATE TEMP TABLE _aifya_data_origin (
    facility            text,
    patients            bigint,
    looks_like_demo     bigint,
    first_created       timestamptz,
    last_created        timestamptz
);

DO $$
DECLARE
    f RECORD;
BEGIN
    FOR f IN SELECT id, name FROM facilities ORDER BY name, code LOOP
        PERFORM set_config('app.current_facility_id', f.id::text, true);

        INSERT INTO _aifya_data_origin
        SELECT f.name,
               count(*),
               count(*) FILTER (
                   WHERE first_name ILIKE '%test%'
                      OR last_name ILIKE '%test%'
                      OR first_name ILIKE '%demo%'
                      OR last_name ILIKE '%demo%'
                      OR email ILIKE '%@example.%'
                      OR phone_number IN ('0700000000', '0712345678',
                                          '254700000000')
               ),
               min(created_at),
               max(created_at)
        FROM patients
        WHERE is_deleted = false;
    END LOOP;
END $$;

SELECT facility,
       patients,
       looks_like_demo,
       first_created,
       last_created
FROM _aifya_data_origin
ORDER BY facility;

-- -----------------------------------------------------------------------------
-- 8. The dental workflow, specifically.
--    A dental patient cannot be routed without a department to route to and a
--    clinician in it. Expect Kenyatta to show zero departments.
-- -----------------------------------------------------------------------------
CREATE TEMP TABLE _aifya_dental (
    facility           text,
    has_dental_dept    boolean,
    dental_department  text,
    dentists           bigint
);

DO $$
DECLARE
    f RECORD;
BEGIN
    FOR f IN SELECT id, name FROM facilities ORDER BY name, code LOOP
        PERFORM set_config('app.current_facility_id', f.id::text, true);

        INSERT INTO _aifya_dental
        SELECT f.name,
               EXISTS (SELECT 1 FROM departments
                        WHERE name ILIKE '%dental%' OR code ILIKE 'DENT%'),
               (SELECT d.name FROM departments AS d
                 WHERE d.name ILIKE '%dental%' OR d.code ILIKE 'DENT%'
                 LIMIT 1),
               (SELECT count(*) FROM staff
                 WHERE is_deleted = false AND role = 'dentist');
    END LOOP;
END $$;

SELECT facility,
       has_dental_dept,
       dental_department,
       dentists
FROM _aifya_dental
ORDER BY facility;

-- -----------------------------------------------------------------------------
-- 9. Staff the identity-provider sign-in would refuse, or sign in unscoped.
--
--    The sign-in path looks up a staff row by the provider's user number and
--    refuses the session when there is no active match. Two conditions matter:
--
--      is_active = false  -> refused outright, which is intended (suspension
--                            in HR must remove access immediately)
--      no department      -> signs in, but the clinical queue is not scoped to
--                            a unit, so they see the unclaimed list instead
--
--    staff.keycloak_user_id is NOT NULL, so a *missing* link is impossible. A
--    *stale* link - one pointing at a user id the provider no longer issues,
--    for example after a realm re-import - cannot be detected from SQL alone.
--    Compare this output against the provider's user list to catch that case.
-- -----------------------------------------------------------------------------
CREATE TEMP TABLE _aifya_signin_gaps (
    facility        text,
    staff_email     text,
    staff_role      text,
    is_active       boolean,
    has_department  boolean
);

DO $$
DECLARE
    f RECORD;
BEGIN
    FOR f IN SELECT id, name FROM facilities ORDER BY name, code LOOP
        PERFORM set_config('app.current_facility_id', f.id::text, true);

        INSERT INTO _aifya_signin_gaps
        SELECT f.name,
               s.email,
               s.role,
               s.is_active,
               (s.department_id IS NOT NULL
                OR s.primary_department_id IS NOT NULL)
        FROM staff AS s
        WHERE s.is_deleted = false
          AND (
                s.is_active = false
             OR (s.department_id IS NULL AND s.primary_department_id IS NULL)
              )
        ORDER BY s.email;
    END LOOP;
END $$;

SELECT facility,
       staff_email,
       staff_role,
       is_active,
       has_department
FROM _aifya_signin_gaps
ORDER BY facility, staff_email;

SELECT count(*) FILTER (WHERE is_active = false) AS refused_at_sign_in,
       count(*) FILTER (WHERE is_active AND NOT has_department)
           AS signs_in_but_queue_unscoped
FROM _aifya_signin_gaps;
