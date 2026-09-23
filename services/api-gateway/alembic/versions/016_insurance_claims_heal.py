"""Self-heal missing insurance_claims validation columns.

Same baseline-stamp drift as migration 014: some environments were stamped
past migration 012 without its DDL ever running, so insurance_claims is missing
validation_decision / validation_result / validated_at even though Alembic
believes 012 is applied — the runtime `column insurance_claims.validation_decision
does not exist` errors. Re-add the columns idempotently (ADD COLUMN IF NOT
EXISTS), a no-op on a correctly-migrated database.

A single ALTER TABLE with three ADD COLUMN clauses is one command, so it is
safe under the asyncpg migration runner.

Revision ID: 016_insurance_claims_heal
Revises: 015_prescription_ack
Create Date: 2026-07-23
"""

from alembic import op

revision = "016_insurance_claims_heal"
down_revision = "015_prescription_ack"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE insurance_claims
            ADD COLUMN IF NOT EXISTS validation_decision VARCHAR(20),
            ADD COLUMN IF NOT EXISTS validation_result JSONB,
            ADD COLUMN IF NOT EXISTS validated_at TIMESTAMPTZ
        """
    )


def downgrade() -> None:
    # Non-destructive heal — the columns belong to migration 012; leave them.
    pass
