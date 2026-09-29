"""Consultation-room hand-off and general testing.

Two things the consultation room was missing:

* A clinician could not send a patient on to another unit. Reception routed
  the patient once, at registration, and ``encounters.department_id`` was
  never written again, so a patient the doctor asked to see Dental or
  Physiotherapy never appeared in that unit's queue. An internal ``referral``
  already models "who sent this patient where and why", but nothing indexed
  the referrals by encounter, so an encounter's routing trail could not be
  read back cheaply.
* HIV, malaria RDT, urinalysis and pregnancy tests are done at the bedside,
  not in the laboratory. There was nowhere to record them, so they ended up in
  free-text notes. ``point_of_care_tests`` gives them a row on the encounter.

The new table is facility-scoped, so it gets the same FORCE ROW LEVEL SECURITY
policy as every other tenant table (migrations 008/018/022).

Safe to re-run: every step is guarded with IF NOT EXISTS / DROP POLICY IF
EXISTS.

Revision ID: 030_opd_routing_and_tests
Revises: 029_role_permissions
Create Date: 2026-09-27
"""

from alembic import op

revision = "030_opd_routing_and_tests"
down_revision = "029_role_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS point_of_care_tests (
            id uuid PRIMARY KEY,
            encounter_id uuid NOT NULL,
            patient_id uuid NOT NULL,
            performed_by uuid NOT NULL,
            performed_at timestamptz NOT NULL DEFAULT now(),
            test_code varchar(50) NOT NULL,
            test_name varchar(200) NOT NULL,
            category varchar(30) NOT NULL DEFAULT 'screening',
            specimen_type varchar(50),
            result_value varchar(200),
            result_numeric double precision,
            result_unit varchar(50),
            interpretation varchar(20),
            is_abnormal boolean NOT NULL DEFAULT false,
            notes text,
            fhir_id varchar(100),
            facility_id uuid NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            created_by uuid,
            updated_by uuid,
            is_deleted boolean NOT NULL DEFAULT false,
            deleted_at timestamptz
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_poc_tests_encounter "
        "ON point_of_care_tests (facility_id, encounter_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_poc_tests_patient "
        "ON point_of_care_tests (facility_id, patient_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_poc_tests_code "
        "ON point_of_care_tests (facility_id, test_code)"
    )

    # An encounter's routing trail is read by encounter, newest first.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_referrals_encounter "
        "ON referrals (facility_id, encounter_id)"
    )

    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE public.point_of_care_tests ENABLE ROW LEVEL SECURITY;
            ALTER TABLE public.point_of_care_tests FORCE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS facility_isolation
                ON public.point_of_care_tests;
            CREATE POLICY facility_isolation ON public.point_of_care_tests
                USING (facility_id::text = current_setting('app.current_facility_id', true))
                WITH CHECK (facility_id::text = current_setting('app.current_facility_id', true));
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_referrals_encounter")
    op.execute("DROP TABLE IF EXISTS point_of_care_tests")