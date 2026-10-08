"""Staff work availability - who can take a patient right now.

Adds ``staff.work_status``, the availability the consultation room assigns on.
It is deliberately separate from ``staff.is_active``: an active account can
still be off duty, on leave, in surgery or already holding a consultation, and
the routing picker must offer only clinicians who can actually see the patient.

Values are ``available``, ``busy``, ``on_leave``, ``off_duty`` and
``unavailable``. The default keeps every existing staff member exactly as
assignable as they were before this migration.

Safe to re-run: every step is guarded with IF NOT EXISTS.

Revision ID: 044_staff_work_status
Revises: 043_queue_core
Create Date: 2026-10-06
"""

from alembic import op

revision = "044_staff_work_status"
down_revision = "043_queue_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE staff ADD COLUMN IF NOT EXISTS work_status "
        "varchar(20) NOT NULL DEFAULT 'available'"
    )
    # The routing picker looks staff up by unit and availability.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_staff_facility_department_status "
        "ON staff (facility_id, department_id, work_status)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_staff_facility_department_status")
    op.execute("ALTER TABLE staff DROP COLUMN IF EXISTS work_status")
