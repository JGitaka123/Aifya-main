-- ============================================================================
--  Aifya - role based access control (who may do what)
-- ============================================================================
--  Run against the Aifya database as a superuser or the database owner, e.g.
--
--      psql "$DATABASE_URL" -f services/api-gateway/scripts/rbac_role_permissions.sql
--
--  Alembic migration 029 already creates and seeds this table, so a normal
--  deployment needs nothing from this file. Keep it for:
--
--    * standing a database up by hand,
--    * re-seeding the shipped defaults after someone deleted rows,
--    * seeing the whole matrix in one place before you change it.
--
--  Every statement is idempotent: running the file twice changes nothing.
--
--  HOW ACCESS IS DECIDED
--  ---------------------
--  1. The role's baseline below (and, in code, app/auth/permissions.py).
--  2. A row here for the same facility replaces that baseline for this role.
--  3. A row here with facility_id IS NULL is the platform default that every
--     facility inherits; a facility's own row wins over the global one.
--  4. staff.permissions (JSONB) is a per-person grant/deny, e.g.
--     '{"clinical.consult": true}' for one locum. It wins over everything.
--  5. admin / facility_admin / super_admin / hospital_administrator always hold
--     everything, whatever the rows say, so a bad row cannot lock a hospital
--     out of its own system.
--
--  A MISSING ROW KEEPS THE BASELINE - it does not deny. is_allowed = FALSE is
--  how you take something away.
--
--  Department is a separate axis: the role says "may consult", the department
--  on the staff record says "consults *here*", and the clinical queue is
--  filtered by it. Set each clinician's department in HR > Employees.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. The table
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS role_permissions (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id UUID REFERENCES facilities(id) ON DELETE CASCADE,
    role        VARCHAR(64) NOT NULL,
    permission  VARCHAR(96) NOT NULL,
    is_allowed  BOOLEAN NOT NULL DEFAULT TRUE,
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by  UUID,
    updated_by  UUID
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_role_permissions_scope
    ON role_permissions (
        COALESCE(facility_id, '00000000-0000-0000-0000-000000000000'::uuid),
        role,
        permission
    ) WHERE NOT is_deleted;

CREATE INDEX IF NOT EXISTS ix_role_permissions_lookup
    ON role_permissions (role, permission);
CREATE INDEX IF NOT EXISTS ix_role_permissions_facility
    ON role_permissions (facility_id);

-- ---------------------------------------------------------------------------
-- 2. The matrix - one array of permissions per role, seeded as global rows
--    (facility_id IS NULL) that every facility inherits.
-- ---------------------------------------------------------------------------
-- RLS is lifted while the defaults are written: the global rows carry no
-- facility, so the facility-scoped write policy would reject them. This is
-- what also makes the script safe to re-run - a previous run leaves RLS
-- forced on, and section 3 turns it back on again.
ALTER TABLE role_permissions DISABLE ROW LEVEL SECURITY;

WITH all_permissions AS (
    SELECT ARRAY[
        'patients.view', 'patients.register', 'patients.update',
        'encounters.create', 'clinical.view', 'clinical.consult',
        'triage.record', 'opd.view', 'opd.manage', 'ipd.view', 'ipd.record',
        'emergency.view', 'emergency.record', 'dental.view', 'dental.record',
        'mch.view', 'mch.record', 'theatre.view', 'theatre.record',
        'pharmacy.view', 'pharmacy.dispense', 'laboratory.view',
        'laboratory.result', 'radiology.view', 'radiology.result',
        'billing.view', 'billing.charge', 'billing.payment',
        'insurance.view', 'insurance.manage', 'finance.view',
        'finance.manage', 'inventory.view', 'inventory.manage', 'hr.view',
        'hr.manage', 'appointments.view', 'appointments.manage',
        'referrals.view', 'referrals.manage', 'reports.view',
        'analytics.view', 'communications.view', 'trials.view',
        'knowledge.view', 'settings.manage'
    ]::text[] AS permissions
),
base(role, permissions) AS (
    VALUES
    -- Administrators: everything, and not overridable.
    ('super_admin',            (SELECT permissions FROM all_permissions)),
    ('admin',                  (SELECT permissions FROM all_permissions)),
    ('facility_admin',         (SELECT permissions FROM all_permissions)),
    ('hospital_administrator', (SELECT permissions FROM all_permissions)),
    -- Front desk: register the patient, open the visit, route it, take the fee.
    -- No clinical.* - the front desk registers the visit, it does not read it.
    ('receptionist', ARRAY[
        'patients.view', 'patients.register', 'patients.update',
        'encounters.create', 'triage.record', 'opd.view', 'opd.manage',
        'appointments.view', 'appointments.manage',
        'billing.view', 'billing.charge', 'billing.payment',
        'insurance.view', 'insurance.manage',
        'referrals.view', 'referrals.manage', 'knowledge.view'
    ]::text[]),
    -- Nursing: triage, vitals and the ward. Sees the queue, prepares the
    -- patient and hands over; prescribing and diagnosing stay with clinicians.
    ('nurse', ARRAY[
        'patients.view', 'patients.update', 'triage.record', 'clinical.view',
        'opd.view', 'ipd.view', 'ipd.record',
        'emergency.view', 'emergency.record', 'mch.view', 'mch.record',
        'laboratory.view', 'radiology.view', 'pharmacy.view',
        'appointments.view', 'referrals.view', 'knowledge.view'
    ]::text[]),
    -- Clinicians: the clinical workspace, diagnoses, prescriptions and orders.
    -- WHICH patients they reach is decided by their department, not this role.
    ('doctor', ARRAY[
        'patients.view', 'patients.update', 'clinical.view', 'clinical.consult',
        'triage.record', 'opd.view', 'opd.manage', 'ipd.view', 'ipd.record',
        'emergency.view', 'emergency.record', 'mch.view', 'mch.record',
        'dental.view', 'laboratory.view', 'radiology.view', 'pharmacy.view',
        'appointments.view', 'referrals.view', 'referrals.manage',
        'reports.view', 'knowledge.view'
    ]::text[]),
    ('specialist', ARRAY[
        'patients.view', 'patients.update', 'clinical.view', 'clinical.consult',
        'triage.record', 'opd.view', 'opd.manage', 'ipd.view', 'ipd.record',
        'emergency.view', 'emergency.record', 'mch.view', 'mch.record',
        'dental.view', 'theatre.view', 'laboratory.view', 'radiology.view',
        'pharmacy.view', 'appointments.view',
        'referrals.view', 'referrals.manage', 'reports.view', 'knowledge.view'
    ]::text[]),
    ('dentist', ARRAY[
        'patients.view', 'patients.update', 'clinical.view', 'clinical.consult',
        'triage.record', 'opd.view', 'opd.manage', 'ipd.view', 'ipd.record',
        'emergency.view', 'emergency.record', 'mch.view', 'mch.record',
        'dental.view', 'dental.record', 'laboratory.view', 'radiology.view',
        'pharmacy.view', 'appointments.view',
        'referrals.view', 'referrals.manage', 'reports.view', 'knowledge.view'
    ]::text[]),
    -- Diagnostics: their own worklist only.
    ('lab_tech', ARRAY[
        'patients.view', 'laboratory.view', 'laboratory.result', 'knowledge.view'
    ]::text[]),
    ('rad_tech', ARRAY[
        'patients.view', 'radiology.view', 'radiology.result', 'knowledge.view'
    ]::text[]),
    -- Pharmacy: dispense and see stock; no consultations.
    ('pharmacist', ARRAY[
        'patients.view', 'pharmacy.view', 'pharmacy.dispense',
        'inventory.view', 'billing.view', 'knowledge.view'
    ]::text[]),
    -- Money: billing, payments and insurance. No clinical access at all.
    ('cashier', ARRAY[
        'patients.view', 'billing.view', 'billing.charge', 'billing.payment',
        'insurance.view', 'insurance.manage', 'reports.view', 'knowledge.view'
    ]::text[]),
    ('finance_admin', ARRAY[
        'patients.view', 'billing.view', 'billing.charge', 'billing.payment',
        'insurance.view', 'insurance.manage', 'finance.view', 'finance.manage',
        'inventory.view', 'reports.view', 'analytics.view', 'knowledge.view'
    ]::text[]),
    -- Back office: staff matters and stock. No patient records for HR.
    ('hr', ARRAY[
        'hr.view', 'hr.manage', 'reports.view', 'knowledge.view'
    ]::text[]),
    ('store_keeper', ARRAY[
        'inventory.view', 'inventory.manage', 'pharmacy.view', 'knowledge.view'
    ]::text[]),
    -- Research: read-only clinical access plus the trial workspace.
    ('research_coordinator', ARRAY[
        'patients.view', 'clinical.view', 'trials.view', 'reports.view',
        'analytics.view', 'communications.view', 'knowledge.view'
    ]::text[]),
    -- The residual bucket the employee sync writes for an unrecognised job
    -- title. Narrow on purpose, but never empty: an account with no
    -- permissions at all looks like a broken system rather than a missing role
    -- assignment. Give these people a real role in HR.
    ('staff', ARRAY['patients.view', 'knowledge.view']::text[])
),
"defaults"(role, permissions) AS (
    -- Every alias shares the baseline of the role it is a synonym for, so the
    -- matrix above is written once and the vocabulary stays honest.
    SELECT base.role, base.permissions FROM base
    UNION ALL
    SELECT alias.role, base.permissions
      FROM (VALUES
            ('records',             'receptionist'),
            ('medical_records',     'receptionist'),
            ('triage_nurse',        'nurse'),
            ('ward_nurse',          'nurse'),
            ('midwife',             'nurse'),
            ('clinician',           'doctor'),
            ('pathologist',         'lab_tech'),
            ('radiologist',         'rad_tech'),
            ('billing',             'cashier'),
            ('billing_clerk',       'cashier'),
            ('billing_officer',     'cashier'),
            ('hr_admin',            'hr'),
            ('hr_officer',          'hr'),
            ('principal_investigator', 'research_coordinator')
           ) AS alias(role, source_role)
      JOIN base ON base.role = alias.source_role
)
INSERT INTO role_permissions (facility_id, role, permission, is_allowed)
SELECT NULL, d.role, p.permission, TRUE
  FROM "defaults" AS d
  CROSS JOIN LATERAL unnest(d.permissions) AS p(permission)
 ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- 3. Row level security - each facility only manages its own rules
-- ---------------------------------------------------------------------------
ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permissions FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS role_permissions_read ON role_permissions;
CREATE POLICY role_permissions_read ON role_permissions
    FOR SELECT
    USING (
        facility_id IS NULL
        OR facility_id::text
           = NULLIF(current_setting('app.current_facility_id', true), '')
    );

DROP POLICY IF EXISTS role_permissions_write ON role_permissions;
CREATE POLICY role_permissions_write ON role_permissions
    USING (
        facility_id::text
        = NULLIF(current_setting('app.current_facility_id', true), '')
    )
    WITH CHECK (
        facility_id::text
        = NULLIF(current_setting('app.current_facility_id', true), '')
    );

DO $do$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'aifya_app_role') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE
            ON public.role_permissions TO aifya_app_role;
    END IF;
END
$do$;

-- ---------------------------------------------------------------------------
-- 3b. Destination alignment (migration 039)
-- ---------------------------------------------------------------------------
-- The navigation gives Clinical Trials to the clinical team, Appointments,
-- Referrals, Analytics, Communications, Integrations and Setting to HR, and the
-- Finance destinations to the money desk. These rows add what those roles were
-- missing so every destination the sidebar offers is one the API will answer.
-- Additive and idempotent: re-running changes nothing.
ALTER TABLE role_permissions DISABLE ROW LEVEL SECURITY;

INSERT INTO role_permissions (facility_id, role, permission, is_allowed)
SELECT NULL, seed.role, seed.permission, TRUE
  FROM (VALUES
        ('doctor',            'trials.view'),
        ('clinician',         'trials.view'),
        ('nurse',             'trials.view'),
        ('triage_nurse',      'trials.view'),
        ('ward_nurse',        'trials.view'),
        ('hr',                'appointments.view'),
        ('hr',                'referrals.view'),
        ('hr',                'analytics.view'),
        ('hr',                'communications.view'),
        ('hr',                'settings.manage'),
        ('hr_admin',          'appointments.view'),
        ('hr_admin',          'referrals.view'),
        ('hr_admin',          'analytics.view'),
        ('hr_admin',          'communications.view'),
        ('hr_admin',          'settings.manage'),
        ('hr_officer',        'appointments.view'),
        ('hr_officer',        'referrals.view'),
        ('hr_officer',        'analytics.view'),
        ('hr_officer',        'communications.view'),
        ('hr_officer',        'settings.manage'),
        ('cashier',           'finance.view'),
        ('cashier',           'inventory.view'),
        ('billing',           'finance.view'),
        ('billing',           'inventory.view'),
        ('billing_clerk',     'finance.view'),
        ('billing_clerk',     'inventory.view'),
        ('billing_officer',   'finance.view'),
        ('billing_officer',   'inventory.view')
       ) AS seed(role, permission)
 WHERE NOT EXISTS (
       SELECT 1 FROM role_permissions existing
        WHERE existing.role = seed.role
          AND existing.permission = seed.permission
          AND existing.facility_id IS NULL
          AND NOT existing.is_deleted
 );

ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE role_permissions FORCE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- 4. See the matrix
-- ---------------------------------------------------------------------------
--  SELECT role, COUNT(*) AS permissions
--    FROM role_permissions
--   WHERE NOT is_deleted
--   GROUP BY role ORDER BY role;
--
--  SELECT permission FROM role_permissions
--   WHERE NOT is_deleted AND role = 'receptionist' ORDER BY permission;

-- ---------------------------------------------------------------------------
-- 5. Change it - examples, edit the UUID and uncomment
-- ---------------------------------------------------------------------------
--  Give THIS facility's nurses prescribing rights:
--
--  INSERT INTO role_permissions (facility_id, role, permission, is_allowed)
--  VALUES ('11111111-1111-1111-1111-111111111111', 'nurse',
--          'clinical.consult', TRUE)
--  ON CONFLICT DO NOTHING;
--
--  Take billing away from THIS facility's cashiers:
--
--  INSERT INTO role_permissions (facility_id, role, permission, is_allowed)
--  VALUES ('11111111-1111-1111-1111-111111111111', 'cashier',
--          'billing.payment', FALSE)
--  ON CONFLICT DO NOTHING;
--
--  Grant ONE person a permission their role does not carry (staff.permissions
--  wins over the table and over the baseline):
--
--  UPDATE staff
--     SET permissions = COALESCE(permissions, '{}'::jsonb)
--                       || '{"clinical.consult": true}'::jsonb
--   WHERE id = '22222222-2222-2222-2222-222222222222';
--
--  Retire a row - the app only reads rows where is_deleted = false:
--
--  UPDATE role_permissions SET is_deleted = true, deleted_at = now()
--   WHERE role = 'cashier' AND permission = 'billing.payment'
--     AND facility_id = '11111111-1111-1111-1111-111111111111';
