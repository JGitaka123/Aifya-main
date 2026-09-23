"""Allow NULL received_by on payments for machine-recorded M-Pesa payments.

M-Pesa STK/C2B callback payments are recorded by the system, not by a staff
member, so received_by must be nullable for those rows.

Revision ID: 009_payment_received_by_nullable
Revises: 008_enable_tenant_rls
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op

revision = "009_payment_received_by_nullable"
down_revision = "008_enable_tenant_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "payments",
        "received_by",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=True,
    )


def downgrade() -> None:
    # Backfill machine-recorded rows with the nil UUID so NOT NULL can be
    # restored without data loss.
    op.execute(
        "UPDATE payments SET received_by = '00000000-0000-0000-0000-000000000000' "
        "WHERE received_by IS NULL"
    )
    op.alter_column(
        "payments",
        "received_by",
        existing_type=sa.dialects.postgresql.UUID(as_uuid=True),
        nullable=False,
    )
