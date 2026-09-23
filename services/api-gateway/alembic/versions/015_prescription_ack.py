"""Prescription safety-alert acknowledgement (Tier 4).

Records the clinician's acknowledgement of non-blocking (WARN) CDS alerts
raised at prescription save time, so an interacting-pair / dose-range warning
that the prescriber chose to proceed through is captured in the record.

Revision ID: 015_prescription_ack
Revises: 014_pharmacy_stock_nonneg
Create Date: 2026-07-23
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "015_prescription_ack"
down_revision = "014_pharmacy_stock_nonneg"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "prescriptions",
        sa.Column("acknowledged_alerts", JSONB(), nullable=True),
    )
    op.add_column(
        "prescriptions",
        sa.Column("override_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("prescriptions", "override_reason")
    op.drop_column("prescriptions", "acknowledged_alerts")
