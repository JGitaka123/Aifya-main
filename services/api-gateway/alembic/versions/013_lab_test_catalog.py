"""Lab test catalog (D6) — managed orderable tests with prices.

Revision ID: 013_lab_test_catalog
Revises: 009_license_active_idx
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "013_lab_test_catalog"
down_revision = "009_license_active_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lab_test_catalog",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("test_code", sa.String(50), nullable=False),
        sa.Column("test_name", sa.String(200), nullable=False),
        sa.Column("specimen_type", sa.String(50)),
        sa.Column("loinc_code", sa.String(20)),
        sa.Column("panel_name", sa.String(100)),
        sa.Column("price_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reference_range", sa.String(200)),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", UUID(as_uuid=True)),
        sa.Column("updated_by", UUID(as_uuid=True)),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_lab_catalog_facility_code",
        "lab_test_catalog",
        ["facility_id", "test_code"],
    )
    op.create_index(
        "ix_lab_catalog_facility_active",
        "lab_test_catalog",
        ["facility_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_lab_catalog_facility_active", table_name="lab_test_catalog")
    op.drop_index("ix_lab_catalog_facility_code", table_name="lab_test_catalog")
    op.drop_table("lab_test_catalog")
