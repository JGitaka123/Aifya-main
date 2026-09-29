"""Stop HR officers from rewriting the facility's own settings

Revision ID: 040_hr_officer_settings
Revises: 039_role_tab_alignment
Create Date: 2026-09-29

Migration 039 gave ``settings.manage`` to ``hr`` and ``hr_officer`` so the
Setting and Integrations destinations would answer. That was too much: those
pages rewrite the hospital's own profile and the integration credentials behind
it, and the endpoint that saves them already refuses anyone but an
administrator or ``hr_admin`` (``PATCH /api/v1/facility``).

This removes the global grant from the two HR ranks that keep records rather
than run the facility. ``hr_admin`` keeps it, so the Human Resource desk can
still be handed the settings page.

It removes rows, never adds them, and only the platform-wide rows - a facility
that granted ``settings.manage`` to its own HR officers keeps that grant, which
is exactly the point of a per-facility override.

Idempotent: re-running it changes nothing.
"""

from alembic import op

revision = "040_hr_officer_settings"
down_revision = "039_role_tab_alignment"
branch_labels = None
depends_on = None

#: Roles that must not carry ``settings.manage`` by default, mirroring
#: ``app.auth.permissions.ROLE_PERMISSIONS``. tests/test_permissions.py fails if
#: this frozen copy drifts from the code.
_ROLE_PERMISSIONS_REVOKED: dict[str, tuple[str, ...]] = {
    "hr": ("settings.manage",),
    "hr_officer": ("settings.manage",),
}

_REVOKE_TEMPLATE = """
DELETE FROM role_permissions
 WHERE facility_id IS NULL
   AND (role, permission) IN (VALUES
__VALUES__
       )
"""

_RESTORE_TEMPLATE = """
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
    # reject the DELETE under FORCE RLS. Lifting it for the statement is what
    # makes it work; the re-enable below puts the policy back.
    op.execute("ALTER TABLE role_permissions DISABLE ROW LEVEL SECURITY")
    op.execute(_REVOKE_TEMPLATE.replace("__VALUES__", _values_sql(_ROLE_PERMISSIONS_REVOKED)))
    op.execute("ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE role_permissions FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE role_permissions DISABLE ROW LEVEL SECURITY")
    op.execute(_RESTORE_TEMPLATE.replace("__VALUES__", _values_sql(_ROLE_PERMISSIONS_REVOKED)))
    op.execute("ALTER TABLE role_permissions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE role_permissions FORCE ROW LEVEL SECURITY")