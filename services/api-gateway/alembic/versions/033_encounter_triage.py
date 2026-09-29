"""Encounter triage provenance - who took the vitals, and when.

The nurse is the first clinician most patients see, but the visit itself
recorded nothing about that step. vital_signs knew who measured what; the
encounter still looked untouched, so the OPD board could not tell a patient
who had been triaged from one who had not, and the consultation room had no
timestamp behind the queue it was working.

triaged_at is stamped with the first recording and nurse_id keeps the person
who took it. Both are additive: a visit that was never triaged keeps NULL and
nothing about it changes.

Safe to re-run: every step is guarded with IF NOT EXISTS.

Revision ID: 033_encounter_triage
Revises: 032_vitals_reports
Create Date: 2026-09-27
"""

from alembic import op

revision = "033_encounter_triage"
down_revision = "032_vitals_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE encounters ADD COLUMN IF NOT EXISTS triaged_at "
        "timestamp with time zone"
    )
    # The OPD board asks "who is still waiting untriaged?" per facility.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_encounters_facility_triaged "
        "ON encounters (facility_id, triaged_at)"
    )
    # Visits that already hold vitals were, in fact, triaged. Stamp them from
    # the earliest recording so the board is not wrong about yesterday.
    op.execute(
        """
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
           AND e.triaged_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_encounters_facility_triaged")
    op.execute("ALTER TABLE encounters DROP COLUMN IF EXISTS triaged_at")