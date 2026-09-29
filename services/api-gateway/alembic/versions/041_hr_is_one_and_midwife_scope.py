"""HR is one desk, and a midwife keeps the maternal room

Revision ID: 041_hr_is_one_and_midwife_scope
Revises: 040_hr_officer_settings
Create Date: 2026-09-29

Two corrections to the shipped matrix, both mirroring
``app.auth.permissions.ROLE_PERMISSIONS``. tests/test_permissions.py fails if
this frozen copy drifts from the code.

1. HR is one desk. Migration 040 took ``settings.manage`` away from ``hr`` and
   ``hr_officer`` on the reasoning that they keep records rather than run the
   facility. That read the ranks as a hierarchy the hospital never agreed to: an
   HR officer who can add an employee, assign them any role and reset their
   password, but who cannot correct the hospital's own phone number, is a
   distinction without a difference. All three ranks carry it again. A facility
   that wants to narrow one rank can say so with its own ``role_permissions``
   row, which is what the table is for.

2. A midwife keeps the maternal room. She was holding ``opd.view``,
   ``clinical.view``, ``ipd.view``, ``ipd.record``, ``emergency.view``,
   ``emergency.record`` and ``radiology.view`` while the navigation offers her
   no OPD, ward, emergency or imaging tab. A permission no tab can reach is how
   a role ends up with an API that answers a call its own sidebar would never
   make, so the seven are removed. She keeps the patient record, triage,
   Mother-and-Child, the laboratory and pharmacy lists she reads from inside
   that room, her clinic appointments and her referrals.

Only global rows (``facility_id IS NULL``) are touched, so a facility that has
granted itself more keeps that grant. Idempotent: re-running changes nothing.
"""

from alembic import op

revision = "041_hr_is_one_and_midwife_scope"
down_revision = "040_hr_officer_settings"
branch_labels = None
depends_on = None

_ROLE_PERMISSIONS_ADDITIONS: dict[str, tuple[str, ...]] = {
    "hr": ("settings.manage",),
    "hr_officer": ("settings.manage",),
}

_ROLE_PERMISSIONS_REVOKED: dict[str, tuple[str, ...]] = {
    "midwife": (
        "clinical.view",
        "opd.view",
        "ipd.view",
        "ipd.record",
        "emergency.view",
        "emergency.record",
        "radiology.view",
    ),
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
    # reject these statements under FORCE RLS. Lifting it for the statement is
    # what makes them work; the re-enable below puts the policy back.
    op.execute("ALTER TABLE role_permissions DISABLE ROW LEVEL SECURITY")
    op.execute(
        _INSERT_TEMPLATE.replace("__VALUES__", _values_sql(_ROLE_PERMISSIONS_ADDITIONS))
    )
    op.execute(
        _DELETE_TEMPLATE.replace("__VALUES__", _values_sql(_ROLE_PERMISSIONS_REVOKED))
    )
    op.execute("ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE role_permissions FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE role_permissions DISABLE ROW LEVEL SECURITY")
    op.execute(
        _INSERT_TEMPLATE.replace("__VALUES__", _values_sql(_ROLE_PERMISSIONS_REVOKED))
    )
    op.execute(
        _DELETE_TEMPLATE.replace("__VALUES__", _values_sql(_ROLE_PERMISSIONS_ADDITIONS))
    )
    op.execute("ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE role_permissions FORCE ROW LEVEL SECURITY")
