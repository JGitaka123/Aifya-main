"""Re-run the 033 and 035 backfills with the tenant context set.

Migrations 033 (triaged_at) and 035 (completed_at) each ended with an UPDATE
that had to read the very rows it was stamping. Both ran with no tenant in the
session, and encounters / vital_signs are FORCE row level security, so the
facility_isolation policy matched nothing and each UPDATE silently changed zero
rows. Two facts went missing as a result:

    triaged_at    a visit that already held vitals kept a NULL triaged_at, so
                  the consultation room never queued it for a doctor
    completed_at  a closed visit kept a NULL completed_at, so the record could
                  not say when the department finished with the patient

The fix is to walk the facilities and publish app.current_facility_id - the
same setting the API itself sets - before each pass, so the policies expose
that facility's rows for the duration of the update.

Safe to re-run: both statements only touch rows that are still NULL, so a
facility that was already correct is left alone.

Revision ID: 036_rls_aware_backfills
Revises: 035_encounter_outcome
Create Date: 2026-09-28
"""

from alembic import op

revision = "036_rls_aware_backfills"
down_revision = "035_encounter_outcome"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            facility_record record;
        BEGIN
            FOR facility_record IN SELECT id FROM facilities LOOP
                PERFORM set_config(
                    'app.current_facility_id', facility_record.id::text, true
                );

                -- 033: a visit that already holds vitals was, in fact, triaged.
                UPDATE encounters AS e
                   SET triaged_at = v.first_recorded_at,
                       nurse_id = v.first_recorded_by,
                       updated_at = now()
                  FROM (
                        SELECT encounter_id,
                               min(recorded_at) AS first_recorded_at,
                               (array_agg(recorded_by ORDER BY recorded_at))[1]
                                   AS first_recorded_by
                          FROM vital_signs
                         WHERE is_deleted = false
                         GROUP BY encounter_id
                       ) AS v
                 WHERE e.id = v.encounter_id
                   AND e.triaged_at IS NULL;

                -- 035: a closed visit was completed at the last time it was
                -- touched, which is the best evidence the old rows carry.
                UPDATE encounters
                   SET completed_at = updated_at
                 WHERE status = 'completed'
                   AND completed_at IS NULL;
            END LOOP;

            PERFORM set_config('app.current_facility_id', '', true);
        END $$;
        """
    )


def downgrade() -> None:
    # Deliberately a no-op. The backfill wrote facts the rows already implied
    # (vitals imply triage, a closed status implies completion); clearing them
    # again would only restore the wrong NULLs.
    pass