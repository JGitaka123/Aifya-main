"""Batch-level pharmacy stock for FEFO dispensing.

Each stock receipt becomes a batch (lot) with its own expiry;
dispensing consumes earliest-expiry-first. Existing per-item stock is
backfilled into one opening batch per item so totals are preserved.

Revision ID: 010_pharmacy_batches
Revises: 009_payment_received_by_nullable
Create Date: 2026-07-07
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "010_pharmacy_batches"
down_revision = "009_payment_received_by_nullable"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pharmacy_batches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "pharmacy_item_id",
            UUID(as_uuid=True),
            sa.ForeignKey("pharmacy_items.id"),
            nullable=False,
        ),
        sa.Column("batch_number", sa.String(50)),
        sa.Column("expiry_date", sa.Date()),
        sa.Column("quantity_received", sa.Integer(), nullable=False),
        sa.Column("quantity_remaining", sa.Integer(), nullable=False),
        sa.Column("unit_cost_cents", sa.Integer()),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("reference_number", sa.String(100)),
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
        "ix_pharmacy_batches_item",
        "pharmacy_batches",
        ["facility_id", "pharmacy_item_id"],
    )
    op.create_index(
        "ix_pharmacy_batches_expiry",
        "pharmacy_batches",
        ["facility_id", "expiry_date"],
    )

    # Backfill: one opening batch per item carrying the current stock and
    # the item's legacy batch/expiry values.
    op.execute(
        """
        INSERT INTO pharmacy_batches (
            id, facility_id, pharmacy_item_id, batch_number, expiry_date,
            quantity_received, quantity_remaining, unit_cost_cents,
            received_at, created_at, updated_at, created_by, updated_by,
            is_deleted
        )
        SELECT
            gen_random_uuid(), facility_id, id, batch_number, expiry_date,
            current_quantity, current_quantity, buying_price_cents,
            now(), now(), now(), created_by, updated_by, FALSE
        FROM pharmacy_items
        WHERE current_quantity > 0 AND is_deleted = FALSE
        """
    )

    # Tenant RLS parity with migration 008 for the new table.
    op.execute("ALTER TABLE pharmacy_batches ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE pharmacy_batches FORCE ROW LEVEL SECURITY;")
    op.execute("DROP POLICY IF EXISTS pharmacy_batches_facility_isolation ON pharmacy_batches;")
    op.execute(
        """
        CREATE POLICY pharmacy_batches_facility_isolation ON pharmacy_batches
            USING (facility_id::text = current_setting('app.current_facility_id', TRUE));
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP POLICY IF EXISTS pharmacy_batches_facility_isolation ON pharmacy_batches"
    )
    op.drop_index("ix_pharmacy_batches_expiry", table_name="pharmacy_batches")
    op.drop_index("ix_pharmacy_batches_item", table_name="pharmacy_batches")
    op.drop_table("pharmacy_batches")
