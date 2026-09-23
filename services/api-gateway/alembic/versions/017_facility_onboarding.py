"""Facility onboarding status for gated sign-up.

Adds onboarding_status (pending/approved/rejected) and admin_email to
facilities. Existing facilities default to 'approved' so nothing changes for
them; new self-service sign-ups start 'pending' until a super-admin approves.

Idempotent (ADD COLUMN IF NOT EXISTS) and single-statement per execute for the
asyncpg migration runner.

Revision ID: 017_facility_onboarding
Revises: 016_insurance_claims_heal
Create Date: 2026-07-26
"""

from alembic import op

revision = "017_facility_onboarding"
down_revision = "016_insurance_claims_heal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE facilities "
        "ADD COLUMN IF NOT EXISTS onboarding_status VARCHAR(20) "
        "NOT NULL DEFAULT 'approved'"
    )
    op.execute(
        "ALTER TABLE facilities ADD COLUMN IF NOT EXISTS admin_email VARCHAR(255)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE facilities DROP COLUMN IF EXISTS admin_email")
    op.execute("ALTER TABLE facilities DROP COLUMN IF EXISTS onboarding_status")
