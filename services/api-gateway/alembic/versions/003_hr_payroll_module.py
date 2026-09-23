"""HR/Payroll Module v1.0 — Kenya-compliant payroll engine.

Revision ID: 003
Revises: 002
Create Date: 2026-05-07

Adds payroll-grade tables (employees, salaries, payroll runs, statutory
configuration, leave, deductions, disciplinary, training, performance,
exit). The pre-existing `staff` and `staff_profiles` tables remain in place
for the general staff directory; payroll uses the new `employees` table.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def _audit_cols() -> list[sa.Column]:
    """Audit columns shared across multi-tenant tables."""
    return [
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_by", UUID(as_uuid=True)),
        sa.Column("updated_by", UUID(as_uuid=True)),
        sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    ]


def upgrade() -> None:
    """Create HR/Payroll tables."""

    # ── employees ────────────────────────────────────────────────────────────
    op.create_table(
        "employees",
        *_audit_cols(),
        sa.Column("staff_id", sa.String(50), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("id_number", sa.String(20)),
        sa.Column("kra_pin", sa.String(20)),
        sa.Column("nssf_number", sa.String(20)),
        sa.Column("shif_number", sa.String(20)),
        sa.Column("department_id", UUID(as_uuid=True)),
        sa.Column("job_title", sa.String(200)),
        sa.Column(
            "employment_type",
            sa.String(20),
            nullable=False,
            server_default="permanent",
        ),
        sa.Column("hire_date", sa.Date, nullable=False),
        sa.Column("termination_date", sa.Date),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("bank_name", sa.String(100)),
        sa.Column("bank_branch", sa.String(100)),
        # bank_account is encrypted-at-rest at app layer (TEXT to allow ciphertext)
        sa.Column("bank_account", sa.Text),
        sa.Column(
            "disability_exemption",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
        sa.Column("phone", sa.String(20)),
        sa.Column("email", sa.String(255)),
        sa.Column("notes", sa.Text),
        sa.UniqueConstraint(
            "facility_id", "staff_id", name="uq_employees_facility_staffid"
        ),
    )
    op.create_index("ix_employees_facility_active", "employees", ["facility_id", "is_active"])
    op.create_index("ix_employees_department", "employees", ["facility_id", "department_id"])
    op.create_index("ix_employees_hire_date", "employees", ["facility_id", "hire_date"])

    # ── employee_salaries ────────────────────────────────────────────────────
    op.create_table(
        "employee_salaries",
        *_audit_cols(),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id"),
            nullable=False,
        ),
        sa.Column("basic_salary", sa.Numeric(12, 2), nullable=False),
        sa.Column("house_allowance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("transport_allowance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("other_allowances", JSONB, nullable=False, server_default="{}"),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date),
        sa.Column("approved_by", UUID(as_uuid=True)),
        sa.Column("notes", sa.Text),
    )
    op.create_index(
        "ix_employee_salaries_emp_period",
        "employee_salaries",
        ["facility_id", "employee_id", "effective_from"],
    )

    # ── payroll_runs ─────────────────────────────────────────────────────────
    op.create_table(
        "payroll_runs",
        *_audit_cols(),
        sa.Column("period_id", UUID(as_uuid=True)),  # FK to accounting_periods if Finance available
        sa.Column("month", sa.Integer, nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column(
            "run_date",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("approved_by", UUID(as_uuid=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("gl_transaction_id", UUID(as_uuid=True)),
        sa.Column("total_gross", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_paye", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_nssf", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_shif", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_hl", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_net", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_employer_nssf", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("total_employer_hl", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text),
        sa.CheckConstraint("month BETWEEN 1 AND 12", name="ck_payroll_runs_month"),
    )
    op.create_index(
        "ix_payroll_runs_period",
        "payroll_runs",
        ["facility_id", "year", "month"],
    )
    op.create_index(
        "ix_payroll_runs_status",
        "payroll_runs",
        ["facility_id", "status"],
    )
    # Only one approved/posted/locked run per period
    op.execute(
        """
        CREATE UNIQUE INDEX uq_payroll_runs_period_active
        ON payroll_runs (facility_id, year, month)
        WHERE status IN ('approved','posted','locked') AND is_deleted = false
        """
    )

    # ── payroll_line_items ───────────────────────────────────────────────────
    op.create_table(
        "payroll_line_items",
        *_audit_cols(),
        sa.Column(
            "payroll_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("payroll_runs.id"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id"),
            nullable=False,
        ),
        sa.Column("basic_salary", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("house_allowance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("transport_allowance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("other_allowances", JSONB, nullable=False, server_default="{}"),
        sa.Column("gross_salary", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("nssf_employee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("shif", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("housing_levy", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("taxable_pay", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("paye_gross", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("personal_relief", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("insurance_relief", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("paye", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("other_deductions", JSONB, nullable=False, server_default="{}"),
        sa.Column("total_deductions", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("net_salary", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("employer_nssf", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("employer_housing_levy", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text),
    )
    op.create_index(
        "ix_payroll_line_items_run",
        "payroll_line_items",
        ["facility_id", "payroll_run_id"],
    )
    op.create_index(
        "ix_payroll_line_items_employee",
        "payroll_line_items",
        ["facility_id", "employee_id"],
    )

    # ── statutory_rates ──────────────────────────────────────────────────────
    op.create_table(
        "statutory_rates",
        *_audit_cols(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("rate", sa.Numeric(8, 6)),
        sa.Column("fixed_amount", sa.Numeric(12, 2)),
        sa.Column("fixed_cap", sa.Numeric(12, 2)),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date),
        sa.Column("approved_by", UUID(as_uuid=True)),
        sa.Column("notes", sa.Text),
    )
    # facility_id may be NULL for global defaults — drop the NOT NULL added by _audit_cols
    op.alter_column("statutory_rates", "facility_id", nullable=True)
    op.create_index(
        "ix_statutory_rates_lookup",
        "statutory_rates",
        ["category", "effective_from"],
    )

    # ── paye_bands ───────────────────────────────────────────────────────────
    op.create_table(
        "paye_bands",
        *_audit_cols(),
        sa.Column("lower_limit", sa.Numeric(12, 2), nullable=False),
        sa.Column("upper_limit", sa.Numeric(12, 2)),
        sa.Column("rate", sa.Numeric(5, 4), nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date),
    )
    op.alter_column("paye_bands", "facility_id", nullable=True)
    op.create_index(
        "ix_paye_bands_effective",
        "paye_bands",
        ["effective_from", "lower_limit"],
    )

    # ── nssf_tiers ───────────────────────────────────────────────────────────
    op.create_table(
        "nssf_tiers",
        *_audit_cols(),
        sa.Column("tier", sa.String(5), nullable=False),
        sa.Column("lower_limit", sa.Numeric(12, 2), nullable=False),
        sa.Column("upper_limit", sa.Numeric(12, 2), nullable=False),
        sa.Column("employee_rate", sa.Numeric(5, 4), nullable=False),
        sa.Column("employer_rate", sa.Numeric(5, 4), nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("effective_to", sa.Date),
    )
    op.alter_column("nssf_tiers", "facility_id", nullable=True)
    op.create_index(
        "ix_nssf_tiers_effective",
        "nssf_tiers",
        ["effective_from", "tier"],
    )

    # ── leave_types ──────────────────────────────────────────────────────────
    op.create_table(
        "leave_types",
        *_audit_cols(),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("days_entitlement", sa.Integer, nullable=False, server_default="0"),
        sa.Column("paid", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("partial_pay", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("carries_over", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("max_carryover", sa.Integer),
        sa.Column("notes", sa.Text),
    )
    op.alter_column("leave_types", "facility_id", nullable=True)
    op.create_index("ix_leave_types_name", "leave_types", ["facility_id", "name"])

    # ── payroll_leave_requests (separate from existing hr.leave_requests) ────
    op.create_table(
        "payroll_leave_requests",
        *_audit_cols(),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id"),
            nullable=False,
        ),
        sa.Column(
            "leave_type_id",
            UUID(as_uuid=True),
            sa.ForeignKey("leave_types.id"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("days_requested", sa.Integer, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("approved_by", UUID(as_uuid=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text),
        sa.Column(
            "payroll_deduction",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column("payroll_period_id", UUID(as_uuid=True)),
    )
    op.create_index(
        "ix_payroll_leave_emp_status",
        "payroll_leave_requests",
        ["facility_id", "employee_id", "status"],
    )
    op.create_index(
        "ix_payroll_leave_dates",
        "payroll_leave_requests",
        ["facility_id", "start_date", "end_date"],
    )

    # ── employee_deductions ─────────────────────────────────────────────────
    op.create_table(
        "employee_deductions",
        *_audit_cols(),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notes", sa.Text),
    )
    op.create_index(
        "ix_employee_deductions_emp",
        "employee_deductions",
        ["facility_id", "employee_id", "is_active"],
    )

    # ── disciplinary_cases ──────────────────────────────────────────────────
    op.create_table(
        "disciplinary_cases",
        *_audit_cols(),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id"),
            nullable=False,
        ),
        sa.Column("allegation", sa.Text, nullable=False),
        sa.Column("investigation_notes", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("outcome", sa.String(30)),
        sa.Column("hearing_date", sa.Date),
        sa.Column("approved_by", UUID(as_uuid=True)),
    )
    op.create_index(
        "ix_disciplinary_emp",
        "disciplinary_cases",
        ["facility_id", "employee_id"],
    )

    # ── grievance_cases ─────────────────────────────────────────────────────
    op.create_table(
        "grievance_cases",
        *_audit_cols(),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id"),
            nullable=False,
        ),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("resolution", sa.Text),
        sa.Column("assigned_to", UUID(as_uuid=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_grievance_emp",
        "grievance_cases",
        ["facility_id", "employee_id", "status"],
    )

    # ── training_programs ───────────────────────────────────────────────────
    op.create_table(
        "training_programs",
        *_audit_cols(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("internal", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("cpd_hours", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
    )
    op.create_index("ix_training_programs_facility", "training_programs", ["facility_id"])

    # ── training_attendance ─────────────────────────────────────────────────
    op.create_table(
        "training_attendance",
        *_audit_cols(),
        sa.Column(
            "training_id",
            UUID(as_uuid=True),
            sa.ForeignKey("training_programs.id"),
            nullable=False,
        ),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="nominated"),
        sa.Column("score", sa.Numeric(5, 2)),
        sa.Column("certificate_url", sa.String(500)),
        sa.Column("completion_date", sa.Date),
    )
    op.create_index(
        "ix_training_attendance_emp",
        "training_attendance",
        ["facility_id", "employee_id"],
    )

    # ── performance_reviews ─────────────────────────────────────────────────
    op.create_table(
        "performance_reviews",
        *_audit_cols(),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id"),
            nullable=False,
        ),
        sa.Column("period_label", sa.String(50), nullable=False),
        sa.Column("self_assessment", JSONB),
        sa.Column("manager_review", JSONB),
        sa.Column("overall_score", sa.Numeric(5, 2)),
        sa.Column("reviewed_by", UUID(as_uuid=True)),
        sa.Column("calibrated_by", UUID(as_uuid=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
    )
    op.create_index(
        "ix_perf_reviews_emp",
        "performance_reviews",
        ["facility_id", "employee_id", "period_label"],
    )

    # ── exit_checklists ─────────────────────────────────────────────────────
    op.create_table(
        "exit_checklists",
        *_audit_cols(),
        sa.Column(
            "employee_id",
            UUID(as_uuid=True),
            sa.ForeignKey("employees.id"),
            nullable=False,
        ),
        sa.Column("last_day", sa.Date, nullable=False),
        sa.Column("notice_pay", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("gratuity", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("leave_encashment", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("final_pay", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("checklist_status", JSONB, nullable=False, server_default="{}"),
        sa.Column("processed_by", UUID(as_uuid=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="in_progress"),
    )
    op.create_index(
        "ix_exit_checklists_emp",
        "exit_checklists",
        ["facility_id", "employee_id"],
    )


def downgrade() -> None:
    """Drop HR/Payroll tables."""
    op.drop_index("ix_exit_checklists_emp", table_name="exit_checklists")
    op.drop_table("exit_checklists")
    op.drop_index("ix_perf_reviews_emp", table_name="performance_reviews")
    op.drop_table("performance_reviews")
    op.drop_index("ix_training_attendance_emp", table_name="training_attendance")
    op.drop_table("training_attendance")
    op.drop_index("ix_training_programs_facility", table_name="training_programs")
    op.drop_table("training_programs")
    op.drop_index("ix_grievance_emp", table_name="grievance_cases")
    op.drop_table("grievance_cases")
    op.drop_index("ix_disciplinary_emp", table_name="disciplinary_cases")
    op.drop_table("disciplinary_cases")
    op.drop_index("ix_employee_deductions_emp", table_name="employee_deductions")
    op.drop_table("employee_deductions")
    op.drop_index("ix_payroll_leave_dates", table_name="payroll_leave_requests")
    op.drop_index("ix_payroll_leave_emp_status", table_name="payroll_leave_requests")
    op.drop_table("payroll_leave_requests")
    op.drop_index("ix_leave_types_name", table_name="leave_types")
    op.drop_table("leave_types")
    op.drop_index("ix_nssf_tiers_effective", table_name="nssf_tiers")
    op.drop_table("nssf_tiers")
    op.drop_index("ix_paye_bands_effective", table_name="paye_bands")
    op.drop_table("paye_bands")
    op.drop_index("ix_statutory_rates_lookup", table_name="statutory_rates")
    op.drop_table("statutory_rates")
    op.drop_index("ix_payroll_line_items_employee", table_name="payroll_line_items")
    op.drop_index("ix_payroll_line_items_run", table_name="payroll_line_items")
    op.drop_table("payroll_line_items")
    op.execute("DROP INDEX IF EXISTS uq_payroll_runs_period_active")
    op.drop_index("ix_payroll_runs_status", table_name="payroll_runs")
    op.drop_index("ix_payroll_runs_period", table_name="payroll_runs")
    op.drop_table("payroll_runs")
    op.drop_index("ix_employee_salaries_emp_period", table_name="employee_salaries")
    op.drop_table("employee_salaries")
    op.drop_index("ix_employees_hire_date", table_name="employees")
    op.drop_index("ix_employees_department", table_name="employees")
    op.drop_index("ix_employees_facility_active", table_name="employees")
    op.drop_table("employees")
