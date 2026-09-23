"""No-negative-stock guard + pharmacy_batches self-heal (Tier 3 inventory guard).

Adds CHECK constraints enforcing pharmacy_items.current_quantity >= 0 and
pharmacy_batches.quantity_remaining >= 0, as defense-in-depth behind the
application-level guards.

Self-heal: some environments were baseline-stamped past migration 010 without
its DDL ever running, so `pharmacy_batches` can be missing even though Alembic
believes 010 is applied. This migration recreates the table (and its opening
batches) when absent, so the constraint can attach and the app's stock queries
work again. It is fully idempotent — every step is guarded — so it is a no-op
on a correctly-migrated database.

Each statement is issued in its own op.execute(): the production migration
runner uses asyncpg, which prepares every statement and rejects multiple
commands in a single execute ("cannot insert multiple commands into a prepared
statement").

Constraints are added NOT VALID: they enforce every new/updated row immediately
while skipping a validating scan of legacy data, so a pre-existing out-of-range
value cannot fail the deploy.

Revision ID: 014_pharmacy_stock_nonneg
Revises: 013_lab_test_catalog
Create Date: 2026-07-23
"""

from alembic import op

revision = "014_pharmacy_stock_nonneg"
down_revision = "013_lab_test_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Recreate pharmacy_batches if a prior baseline stamp skipped migration 010.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pharmacy_batches (
            id UUID PRIMARY KEY,
            facility_id UUID NOT NULL,
            pharmacy_item_id UUID NOT NULL REFERENCES pharmacy_items(id),
            batch_number VARCHAR(50),
            expiry_date DATE,
            quantity_received INTEGER NOT NULL,
            quantity_remaining INTEGER NOT NULL,
            unit_cost_cents INTEGER,
            received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            reference_number VARCHAR(100),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_by UUID,
            updated_by UUID,
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_pharmacy_batches_item "
        "ON pharmacy_batches (facility_id, pharmacy_item_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_pharmacy_batches_expiry "
        "ON pharmacy_batches (facility_id, expiry_date)"
    )

    # 2. Tenant RLS parity (idempotent) — one statement per execute (asyncpg).
    op.execute("ALTER TABLE pharmacy_batches ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE pharmacy_batches FORCE ROW LEVEL SECURITY")
    op.execute(
        "DROP POLICY IF EXISTS pharmacy_batches_facility_isolation ON pharmacy_batches"
    )
    op.execute(
        """
        CREATE POLICY pharmacy_batches_facility_isolation ON pharmacy_batches
            USING (facility_id::text = current_setting('app.current_facility_id', TRUE))
        """
    )

    # 3. Backfill one opening batch per stocked item — only if the table was
    #    just created (still empty), so this never double-inserts.
    op.execute(
        """
        INSERT INTO pharmacy_batches (
            id, facility_id, pharmacy_item_id, batch_number, expiry_date,
            quantity_received, quantity_remaining, unit_cost_cents,
            received_at, created_at, updated_at, created_by, updated_by, is_deleted
        )
        SELECT
            gen_random_uuid(), facility_id, id, batch_number, expiry_date,
            current_quantity, current_quantity, buying_price_cents,
            now(), now(), now(), created_by, updated_by, FALSE
        FROM pharmacy_items
        WHERE current_quantity > 0 AND is_deleted = FALSE
          AND NOT EXISTS (SELECT 1 FROM pharmacy_batches)
        """
    )

    # 4. No-negative-stock CHECK constraints (idempotent, NOT VALID for safety).
    #    Each guarded add is a single DO block (one command).
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_pharmacy_items_qty_nonneg'
          ) THEN
            ALTER TABLE pharmacy_items
              ADD CONSTRAINT ck_pharmacy_items_qty_nonneg
              CHECK (current_quantity >= 0) NOT VALID;
          END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_pharmacy_batches_qty_nonneg'
          ) THEN
            ALTER TABLE pharmacy_batches
              ADD CONSTRAINT ck_pharmacy_batches_qty_nonneg
              CHECK (quantity_remaining >= 0) NOT VALID;
          END IF;
        END $$
        """
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE pharmacy_batches DROP CONSTRAINT IF EXISTS ck_pharmacy_batches_qty_nonneg"
    )
    op.execute(
        "ALTER TABLE pharmacy_items DROP CONSTRAINT IF EXISTS ck_pharmacy_items_qty_nonneg"
    )
