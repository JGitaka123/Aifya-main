"""Isolate the trial visit schedule by its parent trial.

``trial_visit_schedule`` is the one tenant-owned table in the schema with
neither a ``facility_id`` of its own nor row level security. Every other child
table carries its own ``facility_id``; this one hangs off ``clinical_trials``
and was expected to be covered by the parent.

It is not. Row level security does not reach through a foreign key, so a
facility signed in to its own tenant could read, rewrite and delete every
other hospital's protocol visit schedule. The parent trial stayed invisible
while its schedule rows were not, which is why the deployment check's child
table test caught it and the parent-only tests did not.

The policy below derives the tenant from the parent trial instead of adding a
column: it needs no backfill, no change to the ORM model and no change to
``ClinicalTrialService``, which already reads and writes this table from a
tenant-scoped session. The ``EXISTS`` subquery reads ``clinical_trials``, whose
own policy is a plain column comparison, so the two do not recurse.

Revision ID: 042_trial_schedule_rls
Revises: 041_hr_is_one_and_midwife_scope
Create Date: 2026-09-30
"""

from alembic import op

revision = "042_trial_schedule_rls"
down_revision = "041_hr_is_one_and_midwife_scope"
branch_labels = None
depends_on = None

#: Tenant must match the parent trial, for reads and for writes alike.
_POLICY = """
    EXISTS (
        SELECT 1 FROM public.clinical_trials trial
        WHERE trial.id = trial_visit_schedule.trial_id
          AND trial.facility_id::text
              = NULLIF(current_setting('app.current_facility_id', true), '')
    )
"""


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF to_regclass('public.trial_visit_schedule') IS NULL THEN
                RETURN;
            END IF;

            EXECUTE 'ALTER TABLE public.trial_visit_schedule ENABLE ROW LEVEL SECURITY';
            EXECUTE 'ALTER TABLE public.trial_visit_schedule FORCE ROW LEVEL SECURITY';

            EXECUTE 'DROP POLICY IF EXISTS trial_visit_schedule_isolation ON public.trial_visit_schedule';
            EXECUTE $pol$
                CREATE POLICY trial_visit_schedule_isolation
                ON public.trial_visit_schedule
                FOR ALL
                USING ({_POLICY})
                WITH CHECK ({_POLICY})
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
            IF to_regclass('public.trial_visit_schedule') IS NULL THEN
                RETURN;
            END IF;
            EXECUTE 'DROP POLICY IF EXISTS trial_visit_schedule_isolation ON public.trial_visit_schedule';
            EXECUTE 'ALTER TABLE public.trial_visit_schedule NO FORCE ROW LEVEL SECURITY';
            EXECUTE 'ALTER TABLE public.trial_visit_schedule DISABLE ROW LEVEL SECURITY';
        END
        $$;
        """
    )