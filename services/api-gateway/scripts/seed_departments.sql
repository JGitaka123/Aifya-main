-- ============================================================================
--  Aifya - seed departments and link staff to their unit
--
--  WHY THIS FILE EXISTS
--  The worklist shows a clinician the patients routed to *their unit*. A unit
--  is a row in `departments`, and a clinician's unit is `staff.department_id`.
--  When no departments exist:
--    * reception's routing picker is empty, so nobody can be sent anywhere,
--    * every clinician falls back to "unrouted" patients only, so the queue
--      looks empty even though patients were registered.
--  This script creates the standard unit set and links the staff who are
--  already in the database. It creates NO users and NO facilities.
--
--  HOW TO RUN
--      psql "$DATABASE_URL" -f services/api-gateway/scripts/seed_departments.sql
--
--  WHICH FACILITY
--  The facility is a parameter, so this file never has to be edited:
--
--      psql "$DATABASE_URL" -v facility_id=2b0b3fba-f1ad-48f2-919d-ac98c630db35 \
--           -f services/api-gateway/scripts/seed_departments.sql
--
--  Omit -v facility_id and it defaults to the facility in the \set line below.
--  Run it once per facility that needs units. It is safe to run repeatedly:
--  departments are matched on (facility_id, code) and staff are only touched
--  when their department_id is still empty, so a unit you set in HR is never
--  overwritten.
--
--  The facilities already in this database:
--      8f289f05-a5c3-487b-8684-3bf6931d1c4a  mku hospital      (4 units)
--      2b0b3fba-f1ad-48f2-919d-ac98c630db35  kenyatta hospital (0 units)
--      b38e33e6-1a1b-495d-9463-555ea41670cf  Aifya Platform    (platform tenant)
--      00000000-0000-0000-0000-000000000001  Aifya Platform KC (platform tenant)
--
--  THREE THINGS THAT BREAK A HAND-WRITTEN SEED HERE
--   1. `departments`, `staff` and `facilities` have NOT NULL columns with no
--      default: departments needs facility_id, code, name and department_type;
--      staff needs facility_id, keycloak_user_id, employee_number, first_name,
--      last_name, role and email. `facilities` likewise needs both `code` and
--      `facility_type` - so never hand-insert a facility to get a foreign key.
--   2. Row level security is FORCED on `departments` and `staff`. Inserts are
--      rejected unless the session sets app.current_facility_id to the very
--      facility being written. That is what set_config() below does.
--   3. There is already a unique index on (facility_id, code), so re-adding the
--      same department must go through ON CONFLICT.
-- ============================================================================

-- The facility to seed: whatever -v facility_id passed, else this default.
\if :{?facility_id}
\else
\set facility_id 8f289f05-a5c3-487b-8684-3bf6931d1c4a
\endif

-- Parked in a session setting so the DO block below can read it: psql does not
-- interpolate its variables inside a dollar-quoted body.
SELECT set_config('aifya.seed_facility', :'facility_id', false) AS seeding_facility;

DO $$
DECLARE
    v_facility uuid := current_setting('aifya.seed_facility')::uuid;
    v_created  int;
    v_linked   int;
    v_row      record;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM facilities WHERE id = v_facility) THEN
        RAISE EXCEPTION
            'No facility with id %. Pass -v facility_id=... or edit the \set line.', v_facility;
    END IF;

    -- Point RLS at this facility, for this transaction only.
    PERFORM set_config('app.current_facility_id', v_facility::text, true);

    -- 1. The standard unit set -----------------------------------------------
    INSERT INTO departments
        (id, facility_id, code, name, description, department_type, is_active)
    VALUES
        (gen_random_uuid(), v_facility, 'OPD',
         'Outpatient Department', 'General outpatient consultations',
         'clinical', true),
        (gen_random_uuid(), v_facility, 'DENT',
         'Dental Clinic', 'Dental consultations and procedures',
         'clinical', true),
        (gen_random_uuid(), v_facility, 'LAB',
         'Laboratory', 'Laboratory requests and results',
         'support', true),
        (gen_random_uuid(), v_facility, 'PHARM',
         'Pharmacy', 'Prescription dispensing',
         'support', true)
    ON CONFLICT (facility_id, code) DO UPDATE
       SET name            = EXCLUDED.name,
           description     = EXCLUDED.description,
           department_type = EXCLUDED.department_type,
           is_active       = true;

    GET DIAGNOSTICS v_created = ROW_COUNT;
    RAISE NOTICE 'departments upserted: %', v_created;

    -- 2. Link staff who have no unit yet -------------------------------------
    -- A clinician with no unit cannot be routed to, so this is what makes the
    -- queue start working. Roles are mapped to the unit that owns their work;
    -- anyone already linked (for example by the HR screen) is left alone.
    -- Move the dentist to a different unit later in HR > Employees.
    UPDATE staff s
       SET department_id         = d.id,
           primary_department_id = COALESCE(s.primary_department_id, d.id)
      FROM (VALUES
                ('doctor',       'OPD'),
                ('clinician',    'OPD'),
                ('specialist',   'OPD'),
                ('dentist',      'DENT'),
                ('nurse',        'OPD'),
                ('triage_nurse', 'OPD'),
                ('ward_nurse',   'OPD'),
                ('midwife',      'OPD'),
                ('lab_tech',     'LAB'),
                ('pathologist',  'LAB'),
                ('pharmacist',   'PHARM')
            ) AS m(role, code)
      JOIN departments d
        ON d.facility_id = v_facility
       AND d.code        = m.code
     WHERE s.facility_id  = v_facility
       AND s.is_deleted   = false
       AND s.department_id IS NULL
       AND s.role         = m.role;

    GET DIAGNOSTICS v_linked = ROW_COUNT;
    RAISE NOTICE 'staff linked to a unit: %', v_linked;

    -- 3. What the facility now looks like --------------------------------
    -- Reported from inside the block so the RLS context set above still
    -- applies: a bare SELECT after END reads nothing at all, because these
    -- tables are forced under row level security.
    RAISE NOTICE 'units now configured for this facility:';
    FOR v_row IN
        SELECT d.code, d.name, COUNT(s.id) AS staff
          FROM departments d
          LEFT JOIN staff s
            ON s.department_id = d.id
           AND s.is_deleted = false
         WHERE d.facility_id = v_facility
           AND d.is_deleted = false
         GROUP BY d.code, d.name
         ORDER BY d.code
    LOOP
        RAISE NOTICE '  % % - % staff',
            rpad(v_row.code, 6), rpad(v_row.name, 26), v_row.staff;
    END LOOP;
END
$$;
