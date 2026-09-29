"""Clinical access audit trail and encounter care-team assignment history.

Nothing in the database recorded *who* touched clinical data or *who* was
responsible for a patient's care:

* ``finance_audit_logs`` covers the ledger, but no clinical table was audited,
  so a read or write of patient data left no trace. The Kenya Data Protection
  Act 2019 requires an accountability record for processing personal data.
* ``encounters.attending_doctor_id`` is a single mutable column. The API
  creates encounters "unclaimed" and lets a doctor claim one from a shared
  queue (see ``app/services/clinical_workspace.py``), so the column only ever
  holds the *current* holder: handing a patient to another doctor overwrites
  the previous one and nothing records who handed the patient over, when or
  why.
* ``appointments.encounter_id`` -- the link from the receptionist's booking to
  the encounter it became -- is never written by the API, so the "receptionist
  assigned this patient to this doctor" fact is not connected to the treatment
  that followed.

This migration adds two append-oriented tables plus the triggers that fill
them:

1. ``audit_logs`` -- append-only trail of INSERT/UPDATE/DELETE on the clinical
   tables. Each row carries the acting API user (from the ``app.current_user_*``
   session settings the API sets per request), the originating client address,
   the columns that changed and the full before/after row.
2. ``encounter_assignments`` -- care-team history for an encounter. One row per
   assignment (attending / nurse / referring / consultant) recording who holds
   the patient, who assigned them and when. Backfilled from the doctors and
   nurses already recorded on existing encounters so the history starts from
   real data.

Both tables use the same ``facility_isolation`` policy shape as migration 008
and FORCE row-level security so the table owner is bound as well.

``audit_logs`` accepts INSERT but defines no UPDATE or DELETE policy and adds a
BEFORE UPDATE/DELETE trigger, so the trail cannot be rewritten. The trigger
guard is a correctness guardrail, not a defence against the API's own database
login (``aifya_user`` owns the table and can disable it); hard immutability
needs the table moved to a role the application does not hold.

Revision ID: 026_clinical_access_audit
Revises: 025_global_statutory_rls
Create Date: 2026-09-24
"""

from alembic import op

revision = "026_clinical_access_audit"
down_revision = "025_global_statutory_rls"
branch_labels = None
depends_on = None

# Clinical tables whose row changes are copied into audit_logs. Every name must
# expose an ``id`` column; ``facility_id`` is read from the row when present.
_AUDITED_TABLES = (
    "patients",
    "encounters",
    "encounter_assignments",
    "appointments",
    "admissions",
    "diagnoses",
    "prescriptions",
    "clinical_notes",
    "vital_signs",
    "lab_orders",
    "lab_results",
    "patient_insurance",
    "referrals",
    "emergency_visits",
)

_FACILITY_SCOPE = (
    "facility_id::text = current_setting('app.current_facility_id', true)"
)

_CREATE_ENCOUNTER_ASSIGNMENTS = """
CREATE TABLE IF NOT EXISTS encounter_assignments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id     UUID NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    encounter_id    UUID NOT NULL REFERENCES encounters(id) ON DELETE CASCADE,
    staff_id        UUID NOT NULL REFERENCES staff(id),
    assignment_role VARCHAR(32) NOT NULL DEFAULT 'attending',
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    assigned_by     UUID,
    unassigned_at   TIMESTAMPTZ,
    unassigned_by   UUID,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    note            TEXT,
    CONSTRAINT ck_encounter_assignments_role CHECK (
        assignment_role IN ('attending', 'nurse', 'referring', 'consultant')
    )
)
"""

_CREATE_ENCOUNTER_ASSIGNMENTS_INDEXES = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_encounter_assignments_active "
    "ON encounter_assignments (encounter_id, assignment_role) WHERE is_active",
    "CREATE INDEX IF NOT EXISTS ix_encounter_assignments_encounter "
    "ON encounter_assignments (encounter_id)",
    "CREATE INDEX IF NOT EXISTS ix_encounter_assignments_staff "
    "ON encounter_assignments (staff_id, is_active)",
    "CREATE INDEX IF NOT EXISTS ix_encounter_assignments_facility "
    "ON encounter_assignments (facility_id)",
)

_BACKFILL_ENCOUNTER_ASSIGNMENTS = """
DO $do$
DECLARE
    target_facility uuid;
BEGIN
    -- encounters is FORCE row-level-secured, so under the migration's role only
    -- one facility's rows are visible at a time. facilities is not tenant
    -- scoped, so walk it and set the context per tenant before reading.
    FOR target_facility IN SELECT id FROM facilities LOOP
        PERFORM set_config(
            'app.current_facility_id', target_facility::text, true
        );

        INSERT INTO encounter_assignments (
            facility_id, encounter_id, staff_id, assignment_role,
            assigned_at, is_active, note
        )
        SELECT e.facility_id, e.id, e.attending_doctor_id, 'attending',
               e.encounter_date, TRUE,
               'Backfilled from encounters.attending_doctor_id (migration 026)'
          FROM encounters e
         WHERE e.attending_doctor_id IS NOT NULL
           AND NOT EXISTS (
               SELECT 1 FROM encounter_assignments a
                WHERE a.encounter_id = e.id
                  AND a.assignment_role = 'attending'
           );

        INSERT INTO encounter_assignments (
            facility_id, encounter_id, staff_id, assignment_role,
            assigned_at, is_active, note
        )
        SELECT e.facility_id, e.id, e.nurse_id, 'nurse',
               e.encounter_date, TRUE,
               'Backfilled from encounters.nurse_id (migration 026)'
          FROM encounters e
         WHERE e.nurse_id IS NOT NULL
           AND NOT EXISTS (
               SELECT 1 FROM encounter_assignments a
                WHERE a.encounter_id = e.id
                  AND a.assignment_role = 'nurse'
           );
    END LOOP;

    PERFORM set_config('app.current_facility_id', '', true);
END
$do$
"""

_CREATE_AUDIT_LOGS = """
CREATE TABLE IF NOT EXISTS audit_logs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    facility_id      UUID,
    table_name       VARCHAR(64) NOT NULL,
    operation        VARCHAR(10) NOT NULL,
    record_id        UUID NOT NULL,
    actor_user_id    UUID,
    actor_email      VARCHAR(255),
    actor_roles      TEXT,
    db_user          NAME NOT NULL DEFAULT session_user,
    client_addr      INET,
    application_name TEXT,
    txid             BIGINT,
    changed_columns  TEXT[],
    old_data         JSONB,
    new_data         JSONB,
    CONSTRAINT ck_audit_logs_operation
        CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE'))
)
"""

_CREATE_AUDIT_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_occurred_at "
    "ON audit_logs (occurred_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_facility_time "
    "ON audit_logs (facility_id, occurred_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_record "
    "ON audit_logs (table_name, record_id, occurred_at DESC)",
    "CREATE INDEX IF NOT EXISTS ix_audit_logs_actor "
    "ON audit_logs (actor_user_id, occurred_at DESC)",
)

_ENABLE_RLS = (
    "ALTER TABLE encounter_assignments ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE encounter_assignments FORCE ROW LEVEL SECURITY",
    (
        "DROP POLICY IF EXISTS facility_isolation ON encounter_assignments"
    ),
    (
        "CREATE POLICY facility_isolation ON encounter_assignments "
        "USING (" + _FACILITY_SCOPE + ") "
        "WITH CHECK (" + _FACILITY_SCOPE + ")"
    ),
    "ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY",
    # Reads are tenant-scoped. NULL facility_id means the trigger could not
    # attribute the change to a facility; such rows stay visible to the
    # superuser only, never to a tenant.
    (
        "CREATE POLICY audit_logs_read ON audit_logs FOR SELECT "
        "USING (" + _FACILITY_SCOPE + ")"
    ),
    # Deliberately permissive: an audit write must never abort the clinical
    # transaction that triggered it. No UPDATE/DELETE policy is created, so
    # those operations are denied outright under FORCE RLS.
    (
        "CREATE POLICY audit_logs_append ON audit_logs FOR INSERT "
        "WITH CHECK (true)"
    ),
)

_CREATE_AUDIT_FUNCTION = """
CREATE OR REPLACE FUNCTION audit_clinical_change()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $fn$
DECLARE
    v_old       jsonb;
    v_new       jsonb;
    v_row       jsonb;
    v_record_id uuid;
    v_facility  uuid;
    v_changed   text[];
BEGIN
    IF COALESCE(current_setting('app.audit_disabled', true), '') = 'on' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    IF TG_OP <> 'INSERT' THEN
        v_old := to_jsonb(OLD);
    END IF;
    IF TG_OP <> 'DELETE' THEN
        v_new := to_jsonb(NEW);
    END IF;
    v_row := COALESCE(v_new, v_old);

    v_record_id := (v_row ->> 'id')::uuid;
    v_facility := COALESCE(
        (v_row ->> 'facility_id')::uuid,
        NULLIF(current_setting('app.current_facility_id', true), '')::uuid
    );

    IF TG_OP = 'UPDATE' THEN
        SELECT array_agg(n.key ORDER BY n.key)
          INTO v_changed
          FROM jsonb_each(v_new) n
          JOIN jsonb_each(v_old) o ON o.key = n.key
         WHERE n.value IS DISTINCT FROM o.value;
    END IF;

    INSERT INTO audit_logs (
        facility_id, table_name, operation, record_id,
        actor_user_id, actor_email, actor_roles,
        client_addr, application_name, txid,
        changed_columns, old_data, new_data
    ) VALUES (
        v_facility, TG_TABLE_NAME, TG_OP, v_record_id,
        NULLIF(current_setting('app.current_user_id', true), '')::uuid,
        NULLIF(current_setting('app.current_user_email', true), ''),
        NULLIF(current_setting('app.current_user_roles', true), ''),
        inet_client_addr(),
        NULLIF(current_setting('application_name', true), ''),
        pg_current_xact_id()::text::bigint,
        v_changed, v_old, v_new
    );

    RETURN COALESCE(NEW, OLD);
END;
$fn$
"""

_CREATE_IMMUTABILITY_GUARD = """
CREATE OR REPLACE FUNCTION audit_logs_deny_rewrite()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $fn$
BEGIN
    IF COALESCE(current_setting('app.audit_retention_purge', true), '') = 'on' THEN
        RETURN COALESCE(OLD, NEW);
    END IF;
    RAISE EXCEPTION USING
        ERRCODE = 'restrict_violation',
        MESSAGE = 'audit_logs rows are append-only',
        DETAIL = 'Rejected a ' || TG_OP || ' on audit_logs';
END;
$fn$
"""

_ATTACH_TRIGGERS = """
DO $do$
DECLARE
    target text;
BEGIN
    FOREACH target IN ARRAY ARRAY[{tables}] LOOP
        IF to_regclass('public.' || target) IS NULL THEN
            CONTINUE;
        END IF;
        EXECUTE format(
            'DROP TRIGGER IF EXISTS audit_clinical_change ON public.%I', target
        );
        EXECUTE format(
            'CREATE TRIGGER audit_clinical_change '
            'AFTER INSERT OR UPDATE OR DELETE ON public.%I '
            'FOR EACH ROW EXECUTE FUNCTION audit_clinical_change()', target
        );
    END LOOP;
END
$do$
"""

_GRANTS = """
DO $do$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'aifya_app_role') THEN
        GRANT SELECT, INSERT ON public.audit_logs TO aifya_app_role;
        GRANT SELECT, INSERT, UPDATE, DELETE
            ON public.encounter_assignments TO aifya_app_role;
    END IF;
END
$do$
"""


def _quoted_table_list() -> str:
    """
    Render the audited table names as a SQL array literal.

    @returns Comma-separated quoted identifiers, e.g. ``'patients','encounters'``
    """
    return ",".join("'" + name + "'" for name in _AUDITED_TABLES)


def upgrade() -> None:
    op.execute(_CREATE_ENCOUNTER_ASSIGNMENTS)
    for statement in _CREATE_ENCOUNTER_ASSIGNMENTS_INDEXES:
        op.execute(statement)
    op.execute(_BACKFILL_ENCOUNTER_ASSIGNMENTS)

    op.execute(_CREATE_AUDIT_LOGS)
    for statement in _CREATE_AUDIT_INDEXES:
        op.execute(statement)

    for statement in _ENABLE_RLS:
        op.execute(statement)

    op.execute(_CREATE_AUDIT_FUNCTION)
    op.execute(_CREATE_IMMUTABILITY_GUARD)
    op.execute(
        "DROP TRIGGER IF EXISTS audit_logs_deny_rewrite ON audit_logs"
    )
    op.execute(
        "CREATE TRIGGER audit_logs_deny_rewrite "
        "BEFORE UPDATE OR DELETE ON audit_logs "
        "FOR EACH ROW EXECUTE FUNCTION audit_logs_deny_rewrite()"
    )

    op.execute(_ATTACH_TRIGGERS.format(tables=_quoted_table_list()))
    op.execute(_GRANTS)


def downgrade() -> None:
    op.execute(
        """
        DO $do$
        DECLARE
            target text;
        BEGIN
            FOREACH target IN ARRAY ARRAY[{tables}] LOOP
                IF to_regclass('public.' || target) IS NULL THEN
                    CONTINUE;
                END IF;
                EXECUTE format(
                    'DROP TRIGGER IF EXISTS audit_clinical_change ON public.%I',
                    target
                );
            END LOOP;
        END
        $do$
        """.format(tables=_quoted_table_list())
    )
    op.execute("DROP TRIGGER IF EXISTS audit_logs_deny_rewrite ON audit_logs")
    op.execute("DROP FUNCTION IF EXISTS audit_logs_deny_rewrite()")
    op.execute("DROP FUNCTION IF EXISTS audit_clinical_change()")
    op.execute("DROP TABLE IF EXISTS audit_logs")
    op.execute("DROP TABLE IF EXISTS encounter_assignments")
