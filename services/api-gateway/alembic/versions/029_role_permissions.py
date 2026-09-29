"""Who may do what, per facility, layered on top of the role baseline.

Until now every signed-in user at a facility saw every module their
subscription tier allowed. Tier gating answers "did the hospital buy this?";
nothing answered "is this person allowed to use it?". So a receptionist could
open the clinical workspace and a cashier could read a consultation note -
which the Kenya Data Protection Act 2019 (minimum necessary access) and plain
clinical governance both frown on.

This migration adds ``role_permissions``: one row per role + permission, with
``facility_id IS NULL`` meaning the platform default that every facility
inherits and a facility UUID meaning that hospital's own statement about the
role. It is seeded with the baseline that ``app.auth.permissions`` also ships
in code, so the system is correctly gated whether or not the seed ran, and a
hospital that wants its nurses to prescribe can grant it without a release.

The table is read as an *override*: a missing row keeps the baseline rather
than denying, so an empty table degrades to the shipped defaults instead of
locking a hospital out. Administrator roles (``admin``, ``facility_admin``,
``super_admin``) are resolved as "everything" in code and never consult this
table, so a stray deny row cannot shut an administrator out of their own
system.

Row-level security uses the standard ``facility_isolation`` shape, widened so
global rows (``facility_id IS NULL``) are readable by every tenant. Writes
require the row to belong to the caller's facility, so no hospital can rewrite
another hospital's access rules. Seeding runs before RLS is enabled because
the global rows have no facility to match against.

Revision ID: 029_role_permissions
Revises: 028_referral_patient_read
Create Date: 2026-09-25
"""

from alembic import op

revision = "029_role_permissions"
down_revision = "028_referral_patient_read"
branch_labels = None
depends_on = None

# Frozen copy of the permission vocabulary. app.auth.permissions.Permission is
# the live definition; tests/test_permissions.py fails if the two drift, so a
# migration stays reproducible without importing application code.
_ALL_PERMISSIONS: tuple[str, ...] = (
    "patients.view",
    "patients.register",
    "patients.update",
    "encounters.create",
    "clinical.view",
    "clinical.consult",
    "triage.record",
    "opd.view",
    "opd.manage",
    "ipd.view",
    "ipd.record",
    "emergency.view",
    "emergency.record",
    "dental.view",
    "dental.record",
    "mch.view",
    "mch.record",
    "theatre.view",
    "theatre.record",
    "pharmacy.view",
    "pharmacy.dispense",
    "laboratory.view",
    "laboratory.result",
    "radiology.view",
    "radiology.result",
    "billing.view",
    "billing.charge",
    "billing.payment",
    "insurance.view",
    "insurance.manage",
    "finance.view",
    "finance.manage",
    "inventory.view",
    "inventory.manage",
    "hr.view",
    "hr.manage",
    "appointments.view",
    "appointments.manage",
    "referrals.view",
    "referrals.manage",
    "reports.view",
    "analytics.view",
    "communications.view",
    "trials.view",
    "knowledge.view",
    "settings.manage",
)

_SUPERUSER_ROLES = (
    "super_admin",
    "admin",
    "facility_admin",
    "hospital_administrator",
)

_FRONT_DESK = (
    "patients.view",
    "patients.register",
    "patients.update",
    "encounters.create",
    "triage.record",
    "opd.view",
    "opd.manage",
    "appointments.view",
    "appointments.manage",
    "billing.view",
    "billing.charge",
    "billing.payment",
    "insurance.view",
    "insurance.manage",
    "referrals.view",
    "referrals.manage",
    "knowledge.view",
)

_NURSING = (
    "patients.view",
    "patients.update",
    "triage.record",
    "clinical.view",
    "opd.view",
    "ipd.view",
    "ipd.record",
    "emergency.view",
    "emergency.record",
    "mch.view",
    "mch.record",
    "laboratory.view",
    "radiology.view",
    "pharmacy.view",
    "appointments.view",
    "referrals.view",
    "knowledge.view",
)

_CLINICIAN = (
    "patients.view",
    "patients.update",
    "clinical.view",
    "clinical.consult",
    "triage.record",
    "opd.view",
    "opd.manage",
    "ipd.view",
    "ipd.record",
    "emergency.view",
    "emergency.record",
    "mch.view",
    "mch.record",
    "dental.view",
    "laboratory.view",
    "radiology.view",
    "pharmacy.view",
    "appointments.view",
    "referrals.view",
    "referrals.manage",
    "reports.view",
    "knowledge.view",
)

_LABORATORY = (
    "patients.view",
    "laboratory.view",
    "laboratory.result",
    "knowledge.view",
)

_RADIOLOGY = (
    "patients.view",
    "radiology.view",
    "radiology.result",
    "knowledge.view",
)

_PHARMACY = (
    "patients.view",
    "pharmacy.view",
    "pharmacy.dispense",
    "inventory.view",
    "billing.view",
    "knowledge.view",
)

_CASHIER = (
    "patients.view",
    "billing.view",
    "billing.charge",
    "billing.payment",
    "insurance.view",
    "insurance.manage",
    "reports.view",
    "knowledge.view",
)

_FINANCE = (
    "patients.view",
    "billing.view",
    "billing.charge",
    "billing.payment",
    "insurance.view",
    "insurance.manage",
    "finance.view",
    "finance.manage",
    "inventory.view",
    "reports.view",
    "analytics.view",
    "knowledge.view",
)

_HR = ("hr.view", "hr.manage", "reports.view", "knowledge.view")

_STORES = (
    "inventory.view",
    "inventory.manage",
    "pharmacy.view",
    "knowledge.view",
)

_RESEARCH = (
    "patients.view",
    "clinical.view",
    "trials.view",
    "reports.view",
    "analytics.view",
    "communications.view",
    "knowledge.view",
)

# The residual bucket: the employee sync maps an unrecognised job title to the
# role ``staff``, and an account with no permissions at all reads as a broken
# system. Deliberately narrow, and deliberately not empty.
_UNCLASSIFIED = ("patients.view", "knowledge.view")


def _merged(*groups: tuple[str, ...]) -> tuple[str, ...]:
    """
    Union permission groups, keeping the vocabulary order for stable diffs.

    @param groups: Permission tuples to merge
    @returns Sorted, de-duplicated permission tuple
    """
    wanted = {permission for group in groups for permission in group}
    return tuple(
        permission for permission in _ALL_PERMISSIONS if permission in wanted
    )


#: Role to permissions. Mirrors app.auth.permissions.ROLE_PERMISSIONS, with
#: the same alias keys so a hospital that typed ``triage_nurse`` into the role
#: field is still gated sensibly rather than dropped to no permissions.
_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "super_admin": _ALL_PERMISSIONS,
    "admin": _ALL_PERMISSIONS,
    "facility_admin": _ALL_PERMISSIONS,
    "hospital_administrator": _ALL_PERMISSIONS,
    "receptionist": _FRONT_DESK,
    "records": _FRONT_DESK,
    "medical_records": _FRONT_DESK,
    "nurse": _NURSING,
    "triage_nurse": _NURSING,
    "ward_nurse": _NURSING,
    "midwife": _merged(_NURSING, ("mch.record",)),
    "doctor": _CLINICIAN,
    "clinician": _CLINICIAN,
    "specialist": _merged(_CLINICIAN, ("theatre.view",)),
    "dentist": _merged(_CLINICIAN, ("dental.record",)),
    "lab_tech": _LABORATORY,
    "pathologist": _LABORATORY,
    "rad_tech": _RADIOLOGY,
    "radiologist": _RADIOLOGY,
    "pharmacist": _PHARMACY,
    "cashier": _CASHIER,
    "billing": _CASHIER,
    "billing_clerk": _CASHIER,
    "billing_officer": _merged(_CASHIER, ("reports.view",)),
    "finance_admin": _FINANCE,
    "hr": _HR,
    "hr_admin": _HR,
    "hr_officer": _HR,
    "store_keeper": _STORES,
    "research_coordinator": _RESEARCH,
    "principal_investigator": _RESEARCH,
    "staff": _UNCLASSIFIED,
}

_CREATE_TABLE = """
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
)
"""

_CREATE_INDEXES = (
    # One statement per role + permission + facility. NULL is the global row,
    # and NULLs are never equal in an index, so the global scope is folded to
    # the nil UUID before uniqueness is applied.
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_role_permissions_scope "
    "ON role_permissions ("
    "    COALESCE(facility_id, '00000000-0000-0000-0000-000000000000'::uuid),"
    "    role,"
    "    permission"
    ") WHERE NOT is_deleted",
    "CREATE INDEX IF NOT EXISTS ix_role_permissions_lookup "
    "ON role_permissions (role, permission)",
    "CREATE INDEX IF NOT EXISTS ix_role_permissions_facility "
    "ON role_permissions (facility_id)",
)

_SEED_TEMPLATE = """
INSERT INTO role_permissions (facility_id, role, permission, is_allowed)
SELECT NULL, seed.role, seed.permission, TRUE
  FROM (VALUES
__VALUES__
       ) AS seed(role, permission)
 WHERE NOT EXISTS (SELECT 1 FROM role_permissions)
"""

_ENABLE_RLS = (
    "ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE role_permissions FORCE ROW LEVEL SECURITY",
    "DROP POLICY IF EXISTS role_permissions_read ON role_permissions",
    # Every tenant may read the global defaults, but only its own overrides.
    (
        "CREATE POLICY role_permissions_read ON role_permissions FOR SELECT "
        "USING ("
        "    facility_id IS NULL "
        "    OR facility_id::text "
        "       = NULLIF(current_setting('app.current_facility_id', true), '')"
        ")"
    ),
    "DROP POLICY IF EXISTS role_permissions_write ON role_permissions",
    # Global rows are platform-owned: under FORCE RLS a tenant cannot insert
    # or rewrite them because they carry no facility to match.
    (
        "CREATE POLICY role_permissions_write ON role_permissions "
        "USING ("
        "    facility_id::text "
        "    = NULLIF(current_setting('app.current_facility_id', true), '')"
        ") "
        "WITH CHECK ("
        "    facility_id::text "
        "    = NULLIF(current_setting('app.current_facility_id', true), '')"
        ")"
    ),
)

_GRANTS = """
DO $do$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'aifya_app_role') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE
            ON public.role_permissions TO aifya_app_role;
    END IF;
END
$do$
"""


def _seed_sql() -> str:
    """
    Render the baseline matrix as one idempotent INSERT.

    @returns SQL that seeds the table only when it holds no rows yet
    """
    rows: list[str] = []
    for role in sorted(_ROLE_PERMISSIONS):
        for permission in _ROLE_PERMISSIONS[role]:
            rows.append(f"            ('{role}', '{permission}')")
    return _SEED_TEMPLATE.replace("__VALUES__", ",\n".join(rows))


def upgrade() -> None:
    op.execute(_CREATE_TABLE)
    for statement in _CREATE_INDEXES:
        op.execute(statement)
    # Seeded before RLS is enabled: the global rows have facility_id NULL and
    # so cannot satisfy the facility-scoped write policy.
    op.execute(_seed_sql())
    for statement in _ENABLE_RLS:
        op.execute(statement)
    op.execute(_GRANTS)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS role_permissions")
