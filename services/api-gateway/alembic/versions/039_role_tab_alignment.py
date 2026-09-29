"""Align the role matrix with the navigation's role destinations

Revision ID: 039_role_tab_alignment
Revises: 038_aifya_usage_bed_invoice
Create Date: 2026-09-29

The navigation groups Aifya into destinations that belong to one kind of
worker: Clinical Trials belongs to the clinical team, Appointments and
Referrals belong to HR, and the Finance destinations belong to the money desk.
Several roles could already reach those destinations and several could not, so
this revision adds only the missing grants.

It adds rows, never removes them. A missing row keeps the code baseline in
``app.auth.permissions.ROLE_PERMISSIONS``, and no role loses a permission a
hospital may already be relying on.

Idempotent: re-running it changes nothing.
"""

from alembic import op

revision = "039_role_tab_alignment"
down_revision = "038_aifya_usage_bed_invoice"
branch_labels = None
depends_on = None

#: Role -> permissions to add, mirroring the same additions in
#: ``app.auth.permissions.ROLE_PERMISSIONS``. tests/test_permissions.py fails if
#: this frozen copy drifts from the code.
_ROLE_PERMISSIONS_ADDITIONS: dict[str, tuple[str, ...]] = {
    # Clinical Trials is a clinical-team destination.
    "doctor": ("trials.view",),
    "clinician": ("trials.view",),
    "nurse": ("trials.view",),
    "triage_nurse": ("trials.view",),
    "ward_nurse": ("trials.view",),
    # Appointments, Referrals, Analytics, Performance, Communications,
    # Integrations and Setting are all HR destinations.
    "hr": (
        "appointments.view",
        "referrals.view",
        "analytics.view",
        "communications.view",
        "settings.manage",
    ),
    "hr_admin": (
        "appointments.view",
        "referrals.view",
        "analytics.view",
        "communications.view",
        "settings.manage",
    ),
    "hr_officer": (
        "appointments.view",
        "referrals.view",
        "analytics.view",
        "communications.view",
        "settings.manage",
    ),
    # The money desk: Billing, Finance, Chart of Accounts, GL Transactions,
    # Finance Reports, Budgets, Fixed Assets, Periods, Reconciliation,
    # Insurance and Inventory share one destination set.
    "cashier": ("finance.view", "inventory.view"),
    "billing": ("finance.view", "inventory.view"),
    "billing_clerk": ("finance.view", "inventory.view"),
    "billing_officer": ("finance.view", "inventory.view"),
}

_INSERT_TEMPLATE = """
INSERT INTO role_permissions (facility_id, role, permission, is_allowed)
SELECT NULL, seed.role, seed.permission, TRUE
  FROM (VALUES
__VALUES__
       ) AS seed(role, permission)
 WHERE NOT EXISTS (
       SELECT 1 FROM role_permissions existing
        WHERE existing.role = seed.role
          AND existing.permission = seed.permission
          AND existing.facility_id IS NULL
          AND NOT existing.is_deleted
 )
"""

_DELETE_TEMPLATE = """
DELETE FROM role_permissions
 WHERE facility_id IS NULL
   AND (role, permission) IN (VALUES
__VALUES__
       )
"""


def _values_sql(mapping: dict[str, tuple[str, ...]]) -> str:
    """
    Render a role-to-permissions mapping as a SQL VALUES list.

    @param mapping: Role to permissions to render
    @returns One ``('role', 'permission')`` tuple per line
    """
    rows = [
        f"        ('{role}', '{permission}')"
        for role in sorted(mapping)
        for permission in mapping[role]
    ]
    return ",\n".join(rows)


def upgrade() -> None:
    # Global rows carry no facility, so the facility-scoped write policy would
    # reject them under FORCE RLS. Lifting it for the insert is what makes the
    # statement work at all; the re-enable below puts the policy back.
    op.execute("ALTER TABLE role_permissions DISABLE ROW LEVEL SECURITY")
    op.execute(_INSERT_TEMPLATE.replace("__VALUES__", _values_sql(_ROLE_PERMISSIONS_ADDITIONS)))
    op.execute("ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE role_permissions FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE role_permissions DISABLE ROW LEVEL SECURITY")
    op.execute(_DELETE_TEMPLATE.replace("__VALUES__", _values_sql(_ROLE_PERMISSIONS_ADDITIONS)))
    op.execute("ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE role_permissions FORCE ROW LEVEL SECURITY")