"""Let the receiving facility see and act on referrals addressed to it.

Migration 021 added ``referrals.receiving_facility_id`` to record which
facility a referral is addressed to, and ``ReferralService`` already filters
with ``facility_id = :facility OR receiving_facility_id = :facility``.

The generic ``facility_isolation`` policy only matches ``facility_id``, so a
referral addressed to another hospital was invisible to that hospital: the
receiving facility's incoming list and summary came back empty even though
the referral had been sent.

Postgres permissive policies are OR-ed, so the two policies below only widen
access to the single facility named in ``receiving_facility_id``. INSERT and
DELETE remain restricted to the owning facility by ``facility_isolation``, so
a receiving facility cannot create or remove another facility's referral.

Revision ID: 027_referral_receiving_rls
Revises: 026_clinical_access_audit
Create Date: 2026-09-24
"""

from alembic import op

revision = "027_referral_receiving_rls"
down_revision = "026_clinical_access_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regclass('public.referrals') IS NULL THEN
                RETURN;
            END IF;

            EXECUTE 'ALTER TABLE public.referrals ENABLE ROW LEVEL SECURITY';
            EXECUTE 'ALTER TABLE public.referrals FORCE ROW LEVEL SECURITY';

            EXECUTE 'DROP POLICY IF EXISTS referrals_receiving_facility_read ON public.referrals';
            EXECUTE $pol$
                CREATE POLICY referrals_receiving_facility_read ON public.referrals
                FOR SELECT
                USING (
                    receiving_facility_id::text
                    = NULLIF(current_setting('app.current_facility_id', true), '')
                )
            $pol$;

            EXECUTE 'DROP POLICY IF EXISTS referrals_receiving_facility_update ON public.referrals';
            EXECUTE $pol$
                CREATE POLICY referrals_receiving_facility_update ON public.referrals
                FOR UPDATE
                USING (
                    receiving_facility_id::text
                    = NULLIF(current_setting('app.current_facility_id', true), '')
                )
                WITH CHECK (
                    receiving_facility_id::text
                    = NULLIF(current_setting('app.current_facility_id', true), '')
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
            IF to_regclass('public.referrals') IS NULL THEN
                RETURN;
            END IF;
            EXECUTE 'DROP POLICY IF EXISTS referrals_receiving_facility_read ON public.referrals';
            EXECUTE 'DROP POLICY IF EXISTS referrals_receiving_facility_update ON public.referrals';
        END
        $$;
        """
    )