"""Admission orders - the bridge between consultation and IPD.

A doctor clicking "admit" used to create an inpatient immediately. That is
wrong: the clinical decision to admit and the act of admitting are different
events, made by different people, and a bed may not even be free. This
migration adds the admission_orders table, which records the *request* -
reason, diagnosis, admission type, priority, requesting ward and doctor -
while admissions continues to mean "this patient is an inpatient in this bed".

An order moves pending -> accepted | bed_pending -> admitted, or leaves the
queue as declined / cancelled. Only the admit step writes an admissions row,
and it links back through admission_orders.admission_id.

The table is facility-scoped, so it gets the same FORCE ROW LEVEL SECURITY
policy as every other tenant table (migrations 008/018/022/030).

Safe to re-run: every step is guarded with IF NOT EXISTS / DROP POLICY IF
EXISTS.

Revision ID: 031_admission_orders
Revises: 030_opd_routing_and_tests
Create Date: 2026-09-27
"""

from alembic import op

revision = "031_admission_orders"
down_revision = "030_opd_routing_and_tests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS admission_orders (
            id uuid PRIMARY KEY,
            order_number varchar(30) NOT NULL,
            encounter_id uuid NOT NULL REFERENCES encounters(id),
            patient_id uuid NOT NULL REFERENCES patients(id),
            ordered_by uuid,
            attending_doctor_id uuid REFERENCES staff(id),
            reason text NOT NULL,
            primary_diagnosis varchar(500),
            admission_type varchar(20) NOT NULL DEFAULT 'elective',
            priority varchar(20) NOT NULL DEFAULT 'routine',
            department_id uuid REFERENCES departments(id),
            requested_ward_id uuid REFERENCES wards(id),
            clinical_notes text,
            requested_at timestamptz,
            status varchar(20) NOT NULL DEFAULT 'pending',
            decided_by uuid,
            decided_at timestamptz,
            decision_notes text,
            admission_id uuid REFERENCES admissions(id),
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
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_admission_orders_order_number "
        "ON admission_orders (facility_id, order_number)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_admission_orders_facility_status "
        "ON admission_orders (facility_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_admission_orders_facility_patient "
        "ON admission_orders (facility_id, patient_id)"
    )
    # The encounter page asks "is there already an open request for this visit?"
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_admission_orders_encounter "
        "ON admission_orders (encounter_id)"
    )

    op.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE public.admission_orders ENABLE ROW LEVEL SECURITY;
            ALTER TABLE public.admission_orders FORCE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS facility_isolation
                ON public.admission_orders;
            CREATE POLICY facility_isolation ON public.admission_orders
                USING (facility_id::text = current_setting('app.current_facility_id', true))
                WITH CHECK (facility_id::text = current_setting('app.current_facility_id', true));
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS admission_orders")
