"""Queue management and patient calling.

Adds the four tables the queue engine needs:

* queue_service_points - the rooms and counters patients are called into.
* queue_tickets        - the waiting patient. A lightweight workflow object
                         that references the patient and, when the visit
                         already exists, the encounter.
* queue_events         - the immutable log of every transition. Events are a
                         different vocabulary from states, so a status column
                         can never be polluted by an event name.
* queue_announcements  - what the speaker said, and the hash of the text, so
                         a repeated call is not synthesised twice.

Ticket numbers are unique per facility per day. The unique constraint - not
the sequence the service computes - is what guarantees that, so a race simply
retries with the next number, and each new day starts again at 001.

Every table is facility-scoped, so each one gets the same FORCE ROW LEVEL
SECURITY policy as every other tenant table (migrations 008/018/022/030/031).

Safe to re-run: every step is guarded with IF NOT EXISTS / DROP POLICY IF
EXISTS / to_regclass.

Revision ID: 043_queue_core
Revises: 042_trial_schedule_rls
Create Date: 2026-10-05
"""

from alembic import op

revision = "043_queue_core"
down_revision = "042_trial_schedule_rls"
branch_labels = None
depends_on = None

_AUDIT_COLUMNS = """    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid,
    updated_by uuid,
    is_deleted boolean NOT NULL DEFAULT false,
    deleted_at timestamptz"""

_TABLES = (
    "queue_service_points",
    "queue_tickets",
    "queue_events",
    "queue_announcements",
)

_RLS_TEMPLATE = """
DO $$
BEGIN
    IF to_regclass('public.{table}') IS NULL THEN
        RETURN;
    END IF;
    EXECUTE 'ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY';
    EXECUTE 'ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY';
    DROP POLICY IF EXISTS facility_isolation ON public.{table};
    CREATE POLICY facility_isolation ON public.{table}
        USING (facility_id::text = current_setting('app.current_facility_id', true))
        WITH CHECK (facility_id::text = current_setting('app.current_facility_id', true));
END $$;
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS queue_service_points (
            id uuid PRIMARY KEY,
            facility_id uuid NOT NULL,
            department_id uuid REFERENCES departments(id),
            name varchar(120) NOT NULL,
            kind varchar(20) NOT NULL DEFAULT 'room',
            display_label varchar(120),
            is_active boolean NOT NULL DEFAULT true,
        {_AUDIT_COLUMNS}
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_service_points_facility_id "
        "ON queue_service_points (facility_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_service_points_facility_active "
        "ON queue_service_points (facility_id, is_active)"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS queue_tickets (
            id uuid PRIMARY KEY,
            facility_id uuid NOT NULL,
            patient_id uuid NOT NULL REFERENCES patients(id),
            encounter_id uuid REFERENCES encounters(id),
            department_id uuid REFERENCES departments(id),
            service_point_id uuid REFERENCES queue_service_points(id),
            ticket_number varchar(20) NOT NULL,
            issued_on date NOT NULL DEFAULT CURRENT_DATE,
            priority integer NOT NULL DEFAULT 0,
            triage_category varchar(30),
            status varchar(20) NOT NULL DEFAULT 'WAITING',
            issued_at timestamptz NOT NULL DEFAULT now(),
            called_at timestamptz,
            started_at timestamptz,
            completed_at timestamptz,
            called_by uuid,
            recall_count integer NOT NULL DEFAULT 0,
            notes text,
        idempotency_key varchar(255),
        {_AUDIT_COLUMNS}
        )
        """
    )
    # Re-runs against a database created before the column existed.
    op.execute(
        "ALTER TABLE queue_tickets ADD COLUMN IF NOT EXISTS idempotency_key varchar(255)"
    )
    op.execute(
        "ALTER TABLE queue_tickets ADD COLUMN IF NOT EXISTS issued_on date "
        "NOT NULL DEFAULT CURRENT_DATE"
    )
    # The number sequence restarts each day, so the day is part of the key.
    # An earlier draft keyed it per facility for all time, which made the first
    # ticket of every new day collide with yesterday's OPD-001.
    op.execute("DROP INDEX IF EXISTS uq_queue_tickets_facility_number")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_queue_tickets_facility_day_number "
        "ON queue_tickets (facility_id, issued_on, ticket_number)"
    )
    # NULL keys never collide, so only callers that send a retry key are deduped.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_queue_tickets_facility_idempotency "
        "ON queue_tickets (facility_id, idempotency_key)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_tickets_facility_id "
        "ON queue_tickets (facility_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_tickets_patient_id "
        "ON queue_tickets (patient_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_tickets_department_id "
        "ON queue_tickets (department_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_tickets_facility_status "
        "ON queue_tickets (facility_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_tickets_facility_department_status "
        "ON queue_tickets (facility_id, department_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_tickets_facility_issued "
        "ON queue_tickets (facility_id, issued_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_tickets_encounter "
        "ON queue_tickets (encounter_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_tickets_waiting_order "
        "ON queue_tickets (facility_id, status, priority DESC, issued_at ASC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS queue_events (
            id uuid PRIMARY KEY,
            facility_id uuid NOT NULL,
            ticket_id uuid NOT NULL REFERENCES queue_tickets(id),
            event_type varchar(40) NOT NULL,
            from_status varchar(20),
            to_status varchar(20),
            actor_id uuid,
            service_point_id uuid,
            detail jsonb,
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_events_facility_id "
        "ON queue_events (facility_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_events_facility_ticket "
        "ON queue_events (facility_id, ticket_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_events_facility_created "
        "ON queue_events (facility_id, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_events_facility_type_created "
        "ON queue_events (facility_id, event_type, created_at)"
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS queue_announcements (
            id uuid PRIMARY KEY,
            facility_id uuid NOT NULL,
            ticket_id uuid REFERENCES queue_tickets(id),
            queue_event_id uuid REFERENCES queue_events(id),
            text text NOT NULL,
            normalized_text text NOT NULL,
            language varchar(10) NOT NULL DEFAULT 'en',
            provider varchar(40),
            voice varchar(60),
            cache_key varchar(64) NOT NULL,
            storage_key varchar(255),
            content_type varchar(60),
            status varchar(20) NOT NULL DEFAULT 'pending',
            error text,
        {_AUDIT_COLUMNS}
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_announcements_facility_id "
        "ON queue_announcements (facility_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_announcements_facility_ticket "
        "ON queue_announcements (facility_id, ticket_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_queue_announcements_facility_cache "
        "ON queue_announcements (facility_id, cache_key)"
    )

    for table in _TABLES:
        op.execute(_RLS_TEMPLATE.format(table=table))


def downgrade() -> None:
    for table in (
        "queue_announcements",
        "queue_events",
        "queue_tickets",
        "queue_service_points",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
