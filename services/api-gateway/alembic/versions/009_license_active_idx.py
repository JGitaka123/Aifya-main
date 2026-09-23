"""Allow multiple inactive facility licenses

Revision ID: 009_license_active_idx
Revises: 008_enable_tenant_rls
Create Date: 2026-07-12
"""

import sqlalchemy as sa
from alembic import op

revision = "009_license_active_idx"
# Linearized after the claim-validation migration when main + the audit
# branch merged (both originally branched from 008_enable_tenant_rls).
down_revision = "012_claim_validation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE facility_licenses
        DROP CONSTRAINT IF EXISTS uq_facility_licenses_active;
        """
    )
    op.create_index(
        "uq_facility_licenses_active",
        "facility_licenses",
        ["facility_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_facility_licenses_active", table_name="facility_licenses")
    op.create_unique_constraint(
        "uq_facility_licenses_active",
        "facility_licenses",
        ["facility_id", "is_active"],
    )
