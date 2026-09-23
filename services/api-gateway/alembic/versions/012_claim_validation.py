"""Store ClaimFlow validation results on insurance claims.

Revision ID: 012_claim_validation
Revises: 011_encrypt_employee_pii
Create Date: 2026-07-20
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "012_claim_validation"
down_revision = "011_encrypt_employee_pii"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "insurance_claims",
        sa.Column("validation_decision", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "insurance_claims",
        sa.Column("validation_result", JSONB(), nullable=True),
    )
    op.add_column(
        "insurance_claims",
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("insurance_claims", "validated_at")
    op.drop_column("insurance_claims", "validation_result")
    op.drop_column("insurance_claims", "validation_decision")
