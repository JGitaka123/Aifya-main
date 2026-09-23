"""Link emergency visits and referrals in both directions.

Adds the join columns needed for the Emergency <-> Referral workflow:

* emergency_visits.referral_id - the visit arrived because of this referral
* referrals.emergency_visit_id - the referral was raised from this ED visit
* referrals.receiving_facility_id - which facility a referral is addressed to

Safe to re-run: every step is guarded with IF NOT EXISTS / pg_constraint checks.

Revision ID: 021_emergency_referral_links
Revises: 020_fix_employee_sync_trigger
Create Date: 2026-09-10
"""

from alembic import op

revision = "021_emergency_referral_links"
down_revision = "020_fix_employee_sync_trigger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE emergency_visits ADD COLUMN IF NOT EXISTS referral_id uuid")
    op.execute("ALTER TABLE referrals ADD COLUMN IF NOT EXISTS emergency_visit_id uuid")
    op.execute(
        "ALTER TABLE referrals ADD COLUMN IF NOT EXISTS receiving_facility_id uuid"
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_emergency_visits_referral_id'
            ) THEN
                ALTER TABLE emergency_visits
                ADD CONSTRAINT fk_emergency_visits_referral_id
                FOREIGN KEY (referral_id) REFERENCES referrals (id)
                ON DELETE SET NULL;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_referrals_emergency_visit_id'
            ) THEN
                ALTER TABLE referrals
                ADD CONSTRAINT fk_referrals_emergency_visit_id
                FOREIGN KEY (emergency_visit_id) REFERENCES emergency_visits (id)
                ON DELETE SET NULL;
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_referrals_receiving_facility_id'
            ) THEN
                ALTER TABLE referrals
                ADD CONSTRAINT fk_referrals_receiving_facility_id
                FOREIGN KEY (receiving_facility_id) REFERENCES facilities (id)
                ON DELETE SET NULL;
            END IF;
        END
        $$;
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_referrals_receiving_facility "
        "ON referrals (receiving_facility_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_emergency_visits_referral "
        "ON emergency_visits (referral_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_emergency_visits_referral")
    op.execute("DROP INDEX IF EXISTS ix_referrals_receiving_facility")
    op.execute(
        "ALTER TABLE referrals DROP CONSTRAINT IF EXISTS fk_referrals_receiving_facility_id"
    )
    op.execute(
        "ALTER TABLE referrals DROP CONSTRAINT IF EXISTS fk_referrals_emergency_visit_id"
    )
    op.execute(
        "ALTER TABLE emergency_visits DROP CONSTRAINT IF EXISTS fk_emergency_visits_referral_id"
    )
    op.execute("ALTER TABLE referrals DROP COLUMN IF EXISTS receiving_facility_id")
    op.execute("ALTER TABLE referrals DROP COLUMN IF EXISTS emergency_visit_id")
    op.execute("ALTER TABLE emergency_visits DROP COLUMN IF EXISTS referral_id")