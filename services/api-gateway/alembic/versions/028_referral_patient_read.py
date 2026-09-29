"""Let the receiving facility identify the patient on a referral sent to it.

Migration 027 let a facility read the referrals addressed to it. The referral
list also joins ``patients`` to show who the patient is, but ``patients``
carries only ``facility_isolation``, so the referring facility's patient row
stayed invisible to the receiving facility and the join dropped every incoming
row: the tab stayed empty even though the referral itself was now readable.

The policy below opens the patient record - read only - while a live referral
addressed to the current facility exists for that patient. That is the minimum
needed to identify the person being handed over, and access closes again once
the referral is deleted. Writes remain restricted by ``facility_isolation``.

Revision ID: 028_referral_patient_read
Revises: 027_referral_receiving_rls
Create Date: 2026-09-24
"""

from alembic import op

revision = "028_referral_patient_read"
down_revision = "027_referral_receiving_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.patients') IS NULL
               OR to_regclass('public.referrals') IS NULL THEN
                RETURN;
            END IF;

            EXECUTE 'DROP POLICY IF EXISTS patients_referred_in_read ON public.patients';
            EXECUTE $pol$
                CREATE POLICY patients_referred_in_read ON public.patients
                FOR SELECT
                USING (
                    EXISTS (
                        SELECT 1
                        FROM public.referrals r
                        WHERE r.patient_id = public.patients.id
                          AND r.is_deleted = false
                          AND r.receiving_facility_id::text
                              = NULLIF(current_setting('app.current_facility_id', true), '')
                    )
                )
            $pol$;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.patients') IS NULL THEN
                RETURN;
            END IF;
            EXECUTE 'DROP POLICY IF EXISTS patients_referred_in_read ON public.patients';
        END
        $$;
        """
    )