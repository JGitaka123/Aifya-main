"""Login throttling columns on auth_accounts.

Adds the two columns the internal sign-in path needs to slow a password
guessing attack: ``failed_login_attempts`` counts consecutive wrong passwords
and ``locked_until`` marks the cooling-off period once the limit is reached.
Both are cleared by a successful sign-in.

The pair lives on the account row rather than in memory so the limit survives
a restart and applies across every API worker.

Safe to re-run: every step is guarded with IF NOT EXISTS.

Revision ID: 045_login_lockout
Revises: 044_staff_work_status
Create Date: 2026-10-07
"""

from alembic import op

revision = "045_login_lockout"
down_revision = "044_staff_work_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE auth_accounts ADD COLUMN IF NOT EXISTS "
        "failed_login_attempts integer NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE auth_accounts ADD COLUMN IF NOT EXISTS "
        "locked_until timestamptz"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE auth_accounts DROP COLUMN IF EXISTS locked_until")
    op.execute(
        "ALTER TABLE auth_accounts DROP COLUMN IF EXISTS failed_login_attempts"
    )
