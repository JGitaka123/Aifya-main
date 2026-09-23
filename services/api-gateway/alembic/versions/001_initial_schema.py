"""Initial schema — all 66 tables for Aifya HMIS.

Revision ID: 001
Revises: None
Create Date: 2026-04-12

Tables created in FK-dependency order:
  Layer 0: facilities, events, facility_licenses, usage_telemetry, app_updates, facility_update_status
  Layer 1: departments, patients, report_templates, pharmacy_items, suppliers, insurance_schemes, operating_theatres
  Layer 2: staff, wards, shifts, inventory_items
  Layer 3: encounters, doctor_schedules, staff_profiles, dental_charts, clinical_trials, beds
  Layer 4: clinical_notes, diagnoses, prescriptions, vital_signs, lab_orders, imaging_orders,
           invoices, anc_profiles, emergency_visits, referrals, dental_visits, dental_treatment_plans,
           appointments, admissions, surgical_cases, patient_insurance, trial_participants,
           trial_visit_schedule, shift_assignments, leave_requests, attendance, generated_reports,
           purchase_orders
  Layer 5: lab_results, imaging_results, invoice_items, payments, dispensings, nursing_notes,
           anc_visits, delivery_records, insurance_claims, pre_authorizations,
           trial_participant_visits, trial_adverse_events, trial_ai_screening,
           purchase_order_items, inventory_transactions
  Layer 6: stock_transactions, child_records
  Layer 7: immunizations
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables."""

    # ── Layer 0 ──────────────────────────────────────────────────────────────

    op.create_table(
        "facilities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), unique=True, nullable=False),
        sa.Column("facility_type", sa.String(50), nullable=False),
        sa.Column("keph_level", sa.String(10)),
        sa.Column("mfl_code", sa.String(20), unique=True),
        sa.Column("county", sa.String(100)),
        sa.Column("sub_county", sa.String(100)),
        sa.Column("ward", sa.String(100)),
        sa.Column("physical_address", sa.Text),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("phone", sa.String(20)),
        sa.Column("email", sa.String(255)),
        sa.Column("website", sa.String(500)),
        sa.Column("logo_url", sa.String(500)),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Africa/Nairobi"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("settings", JSONB),
        sa.Column("dhis2_org_unit_id", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )

    op.create_table(
        "events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("stream_type", sa.String(100), nullable=False, index=True),
        sa.Column("stream_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("event_data", JSONB, nullable=False),
        sa.Column("metadata", JSONB),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True)),
        sa.Column("idempotency_key", sa.String(255), unique=True),
    )

    op.create_table(
        "facility_licenses",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", UUID(as_uuid=True), nullable=False),
        sa.Column("license_key", sa.String(64), nullable=False),
        sa.Column("tier", sa.String(30), nullable=False, server_default="community"),
        sa.Column("max_users", sa.Integer, nullable=False, server_default="5"),
        sa.Column("max_patients", sa.Integer, nullable=False, server_default="500"),
        sa.Column("max_facilities", sa.Integer, nullable=False, server_default="1"),
        sa.Column("enabled_modules", JSONB, nullable=False),
        sa.Column("feature_flags", JSONB, nullable=False, server_default="{}"),
        sa.Column("billing_cycle", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("price_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False, server_default="KES"),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("grace_period_days", sa.Integer, nullable=False, server_default="30"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_interval_hours", sa.Integer, nullable=False, server_default="24"),
        sa.Column("issued_by", sa.String(255)),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("facility_id", "is_active", name="uq_facility_licenses_active"),
    )
    op.create_index("ix_facility_licenses_key", "facility_licenses", ["license_key"], unique=True)
    op.create_index("ix_facility_licenses_facility", "facility_licenses", ["facility_id"])
    op.create_index("ix_facility_licenses_expires", "facility_licenses", ["expires_at"])

    op.create_table(
        "usage_telemetry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", UUID(as_uuid=True), nullable=False),
        sa.Column("recorded_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_users", sa.Integer, server_default="0"),
        sa.Column("total_patients", sa.Integer, server_default="0"),
        sa.Column("encounters_today", sa.Integer, server_default="0"),
        sa.Column("prescriptions_today", sa.Integer, server_default="0"),
        sa.Column("lab_orders_today", sa.Integer, server_default="0"),
        sa.Column("admissions_today", sa.Integer, server_default="0"),
        sa.Column("billing_total_cents", sa.Integer, server_default="0"),
        sa.Column("ai_requests_today", sa.Integer, server_default="0"),
        sa.Column("modules_used", JSONB, nullable=False, server_default="[]"),
        sa.Column("api_latency_p95_ms", sa.Integer),
        sa.Column("error_count", sa.Integer, server_default="0"),
        sa.Column("offline_sync_queue_size", sa.Integer, server_default="0"),
        sa.Column("app_version", sa.String(30)),
        sa.Column("db_version", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_usage_telemetry_facility_date", "usage_telemetry", ["facility_id", "recorded_date"])
    op.create_index("ix_usage_telemetry_date", "usage_telemetry", ["recorded_date"])

    op.create_table(
        "app_updates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="stable"),
        sa.Column("min_tier", sa.String(30), nullable=False, server_default="community"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("changelog", sa.Text, nullable=False),
        sa.Column("changelog_sw", sa.Text),
        sa.Column("is_critical", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_mandatory", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("download_url", sa.String(500)),
        sa.Column("docker_tag", sa.String(200)),
        sa.Column("db_migration_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("min_version", sa.String(30)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("version", name="uq_app_updates_version"),
    )
    op.create_index("ix_app_updates_published", "app_updates", ["published_at"])

    op.create_table(
        "facility_update_status",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", UUID(as_uuid=True), nullable=False),
        sa.Column("current_version", sa.String(30), nullable=False),
        sa.Column("last_update_check", sa.DateTime(timezone=True)),
        sa.Column("last_updated_at", sa.DateTime(timezone=True)),
        sa.Column("update_channel", sa.String(20), nullable=False, server_default="stable"),
        sa.Column("auto_update", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("facility_id", name="uq_facility_update_status_facility"),
    )

    # ── Layer 1 ──────────────────────────────────────────────────────────────
    # Helper: AuditMixin columns reused across most tables
    def _audit_cols():
        return [
            sa.Column("id", UUID(as_uuid=True), primary_key=True),
            sa.Column("facility_id", UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", UUID(as_uuid=True)),
            sa.Column("updated_by", UUID(as_uuid=True)),
            sa.Column("is_deleted", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("deleted_at", sa.DateTime(timezone=True)),
        ]

    op.create_table(
        "departments",
        *_audit_cols(),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500)),
        sa.Column("department_type", sa.String(50), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("head_of_department_id", UUID(as_uuid=True)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_index("ix_departments_facility_code", "departments", ["facility_id", "code"], unique=True)

    op.create_table(
        "patients",
        *_audit_cols(),
        sa.Column("mrn", sa.String(50), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("middle_name", sa.String(100)),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=False),
        sa.Column("gender", sa.String(20), nullable=False),
        sa.Column("national_id", sa.String(50)),
        sa.Column("passport_number", sa.String(50)),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("alternate_phone", sa.String(20)),
        sa.Column("email", sa.String(255)),
        sa.Column("county", sa.String(100)),
        sa.Column("sub_county", sa.String(100)),
        sa.Column("ward", sa.String(100)),
        sa.Column("village", sa.String(200)),
        sa.Column("postal_address", sa.String(200)),
        sa.Column("occupation", sa.String(100)),
        sa.Column("marital_status", sa.String(20)),
        sa.Column("next_of_kin_name", sa.String(200)),
        sa.Column("next_of_kin_phone", sa.String(20)),
        sa.Column("next_of_kin_relationship", sa.String(50)),
        sa.Column("insurance_provider", sa.String(100)),
        sa.Column("insurance_member_number", sa.String(100)),
        sa.Column("sha_number", sa.String(50)),
        sa.Column("blood_group", sa.String(10)),
        sa.Column("allergies", JSONB),
        sa.Column("chronic_conditions", JSONB),
        sa.Column("photo_url", sa.String(500)),
        sa.Column("fhir_id", sa.String(100)),
    )
    op.create_index("ix_patients_facility_national_id", "patients", ["facility_id", "national_id"])
    op.create_index("ix_patients_facility_phone", "patients", ["facility_id", "phone_number"])
    op.create_index("ix_patients_facility_name", "patients", ["facility_id", "first_name", "last_name"])
    op.create_index("ix_patients_mrn", "patients", ["facility_id", "mrn"], unique=True)

    op.create_table(
        "report_templates",
        *_audit_cols(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.Text),
        sa.Column("category", sa.String(30), nullable=False, server_default="operational"),
        sa.Column("department", sa.String(50)),
        sa.Column("report_type", sa.String(20), nullable=False, server_default="tabular"),
        sa.Column("parameters_schema", JSONB),
        sa.Column("query_config", JSONB),
        sa.Column("columns_config", JSONB),
        sa.Column("is_scheduled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("schedule_cron", sa.String(50)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("moh_form_number", sa.String(20)),
        sa.Column("reporting_period", sa.String(20)),
    )

    op.create_table(
        "pharmacy_items",
        *_audit_cols(),
        sa.Column("drug_code", sa.String(50), nullable=False),
        sa.Column("drug_name", sa.String(300), nullable=False),
        sa.Column("generic_name", sa.String(300)),
        sa.Column("atc_code", sa.String(20)),
        sa.Column("is_keml", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("dosage_form", sa.String(50)),
        sa.Column("strength", sa.String(50)),
        sa.Column("batch_number", sa.String(50)),
        sa.Column("current_quantity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unit_of_measure", sa.String(30), nullable=False, server_default="tablet"),
        sa.Column("reorder_level", sa.Integer, nullable=False, server_default="10"),
        sa.Column("max_stock_level", sa.Integer),
        sa.Column("buying_price_cents", sa.Integer),
        sa.Column("selling_price_cents", sa.Integer),
        sa.Column("expiry_date", sa.Date),
        sa.Column("manufacturer", sa.String(200)),
        sa.Column("supplier", sa.String(200)),
        sa.Column("storage_conditions", sa.String(100)),
        sa.Column("shelf_location", sa.String(50)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_index("ix_pharmacy_items_facility_drug", "pharmacy_items", ["facility_id", "drug_code"])
    op.create_index("ix_pharmacy_items_facility_name", "pharmacy_items", ["facility_id", "drug_name"])
    op.create_index("ix_pharmacy_items_expiry", "pharmacy_items", ["facility_id", "expiry_date"])

    op.create_table(
        "suppliers",
        *_audit_cols(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("supplier_code", sa.String(50)),
        sa.Column("contact_person", sa.String(200)),
        sa.Column("phone", sa.String(30)),
        sa.Column("email", sa.String(200)),
        sa.Column("address", sa.Text),
        sa.Column("kra_pin", sa.String(20)),
        sa.Column("payment_terms", sa.String(100)),
        sa.Column("category", sa.String(50)),
        sa.Column("rating", sa.Integer),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_suppliers_facility", "suppliers", ["facility_id"])

    op.create_table(
        "insurance_schemes",
        *_audit_cols(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("scheme_code", sa.String(50), nullable=False),
        sa.Column("scheme_type", sa.String(30), nullable=False, server_default="sha"),
        sa.Column("contact_person", sa.String(200)),
        sa.Column("phone", sa.String(30)),
        sa.Column("email", sa.String(200)),
        sa.Column("address", sa.Text),
        sa.Column("contract_start", sa.DateTime(timezone=True)),
        sa.Column("contract_end", sa.DateTime(timezone=True)),
        sa.Column("coverage_details", JSONB),
        sa.Column("rebate_percentage", sa.Integer),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_insurance_schemes_facility", "insurance_schemes", ["facility_id"])
    op.create_index("ix_insurance_schemes_facility_type", "insurance_schemes", ["facility_id", "scheme_type"])

    op.create_table(
        "operating_theatres",
        *_audit_cols(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("theatre_type", sa.String(30), nullable=False, server_default="general"),
        sa.Column("status", sa.String(20), nullable=False, server_default="available"),
        sa.Column("floor", sa.String(20)),
        sa.Column("equipment", JSONB),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_operating_theatres_facility", "operating_theatres", ["facility_id"])

    # ── Layer 2 ──────────────────────────────────────────────────────────────

    op.create_table(
        "staff",
        *_audit_cols(),
        sa.Column("keycloak_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("employee_number", sa.String(50), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("middle_name", sa.String(100)),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("title", sa.String(50)),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("specialization", sa.String(100)),
        sa.Column("license_number", sa.String(50)),
        sa.Column("license_body", sa.String(100)),
        sa.Column("department_id", UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("primary_department_id", UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("phone", sa.String(20)),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("permissions", JSONB),
        sa.Column("signature_url", sa.String(500)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_index("ix_staff_facility_keycloak", "staff", ["facility_id", "keycloak_user_id"], unique=True)
    op.create_index("ix_staff_facility_employee_number", "staff", ["facility_id", "employee_number"], unique=True)

    op.create_table(
        "wards",
        *_audit_cols(),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("ward_type", sa.String(30), nullable=False),
        sa.Column("department_id", UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("floor", sa.String(20)),
        sa.Column("total_beds", sa.Integer, nullable=False, server_default="0"),
        sa.Column("gender_restriction", sa.String(10)),
        sa.Column("charge_per_day_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_wards_facility_name", "wards", ["facility_id", "name"], unique=True)

    op.create_table(
        "shifts",
        *_audit_cols(),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("duration_hours", sa.Integer, nullable=False),
        sa.Column("is_night_shift", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("department_id", UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_shifts_facility_code", "shifts", ["facility_id", "code"], unique=True)

    op.create_table(
        "inventory_items",
        *_audit_cols(),
        sa.Column("item_code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("sub_category", sa.String(100)),
        sa.Column("unit_of_measure", sa.String(30), nullable=False),
        sa.Column("unit_cost", sa.Integer, nullable=False, server_default="0"),
        sa.Column("current_stock", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reorder_level", sa.Integer, nullable=False, server_default="10"),
        sa.Column("reorder_quantity", sa.Integer, nullable=False, server_default="50"),
        sa.Column("max_stock", sa.Integer),
        sa.Column("store_location", sa.String(100)),
        sa.Column("department_id", UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("specifications", JSONB),
    )
    op.create_index("ix_inventory_items_category", "inventory_items", ["facility_id", "category"])
    op.create_index("ix_inventory_items_code", "inventory_items", ["facility_id", "item_code"], unique=True)

    # ── Layer 3 ──────────────────────────────────────────────────────────────

    op.create_table(
        "encounters",
        *_audit_cols(),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("encounter_type", sa.String(30), nullable=False),
        sa.Column("encounter_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("department_id", UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("attending_doctor_id", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("nurse_id", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("queue_number", sa.Integer),
        sa.Column("triage_category", sa.String(20)),
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="waiting"),
        sa.Column("chief_complaint", sa.Text),
        sa.Column("disposition", sa.String(30)),
        sa.Column("bed_id", UUID(as_uuid=True)),
        sa.Column("admission_date", sa.DateTime(timezone=True)),
        sa.Column("discharge_date", sa.DateTime(timezone=True)),
        sa.Column("discharge_summary", sa.Text),
        sa.Column("billing_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("scribe_session_id", UUID(as_uuid=True)),
        sa.Column("trial_participant_id", UUID(as_uuid=True)),
        sa.Column("fhir_id", sa.String(100)),
    )
    op.create_index("ix_encounters_facility_patient", "encounters", ["facility_id", "patient_id"])
    op.create_index("ix_encounters_facility_status", "encounters", ["facility_id", "status"])
    op.create_index("ix_encounters_facility_date", "encounters", ["facility_id", "encounter_date"])

    op.create_table(
        "doctor_schedules",
        *_audit_cols(),
        sa.Column("doctor_id", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("department_id", UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("day_of_week", sa.Integer, nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("slot_duration_minutes", sa.Integer, nullable=False, server_default="15"),
        sa.Column("max_patients", sa.Integer),
        sa.Column("room", sa.String(50)),
        sa.Column("consultation_type", sa.String(30), nullable=False, server_default="general"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("effective_from", sa.Date),
        sa.Column("effective_until", sa.Date),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_doctor_schedules_doctor", "doctor_schedules", ["facility_id", "doctor_id"])

    op.create_table(
        "staff_profiles",
        *_audit_cols(),
        sa.Column("staff_id", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("date_of_birth", sa.Date),
        sa.Column("gender", sa.String(10)),
        sa.Column("national_id", sa.String(20)),
        sa.Column("kra_pin", sa.String(20)),
        sa.Column("nhif_number", sa.String(20)),
        sa.Column("nssf_number", sa.String(20)),
        sa.Column("address", sa.Text),
        sa.Column("county", sa.String(50)),
        sa.Column("sub_county", sa.String(50)),
        sa.Column("emergency_contact_name", sa.String(200)),
        sa.Column("emergency_contact_phone", sa.String(20)),
        sa.Column("emergency_contact_relationship", sa.String(50)),
        sa.Column("employment_type", sa.String(20), nullable=False, server_default="permanent"),
        sa.Column("employment_date", sa.Date),
        sa.Column("contract_end_date", sa.Date),
        sa.Column("probation_end_date", sa.Date),
        sa.Column("basic_salary", sa.Integer),
        sa.Column("allowances", JSONB),
        sa.Column("qualifications", JSONB),
        sa.Column("certifications", JSONB),
        sa.Column("annual_leave_balance", sa.Integer, nullable=False, server_default="21"),
        sa.Column("sick_leave_balance", sa.Integer, nullable=False, server_default="30"),
        sa.Column("maternity_leave_balance", sa.Integer, nullable=False, server_default="90"),
        sa.Column("paternity_leave_balance", sa.Integer, nullable=False, server_default="14"),
        sa.Column("photo_url", sa.String(500)),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_staff_profiles_staff", "staff_profiles", ["facility_id", "staff_id"], unique=True)

    op.create_table(
        "dental_charts",
        *_audit_cols(),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("teeth", JSONB, nullable=False, server_default="{}"),
        sa.Column("periodontal_status", sa.Text),
        sa.Column("occlusion_notes", sa.Text),
        sa.Column("last_xray_date", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_dental_charts_facility", "dental_charts", ["facility_id"])
    op.create_index("ix_dental_charts_patient", "dental_charts", ["facility_id", "patient_id"], unique=True)

    op.create_table(
        "clinical_trials",
        *_audit_cols(),
        sa.Column("trial_code", sa.String(50), unique=True, nullable=False),
        sa.Column("nct_number", sa.String(20)),
        sa.Column("pactr_number", sa.String(20)),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("short_title", sa.String(200)),
        sa.Column("phase", sa.String(20)),
        sa.Column("study_type", sa.String(30), nullable=False),
        sa.Column("therapeutic_area", sa.String(100)),
        sa.Column("sponsor", sa.String(200), nullable=False),
        sa.Column("principal_investigator_id", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("co_investigators", JSONB),
        sa.Column("irb_approval_number", sa.String(50)),
        sa.Column("irb_approval_date", sa.Date),
        sa.Column("irb_expiry_date", sa.Date),
        sa.Column("ethics_committee", sa.String(200)),
        sa.Column("nacosti_permit", sa.String(50)),
        sa.Column("protocol_version", sa.String(20), nullable=False),
        sa.Column("protocol_date", sa.Date, nullable=False),
        sa.Column("protocol_document_url", sa.String(500)),
        sa.Column("amendments", JSONB),
        sa.Column("inclusion_criteria", JSONB, nullable=False),
        sa.Column("exclusion_criteria", JSONB, nullable=False),
        sa.Column("target_enrollment", sa.Integer),
        sa.Column("redcap_project_id", sa.Integer),
        sa.Column("redcap_api_url", sa.String(500)),
        sa.Column("redcap_api_token_vault_key", sa.String(100)),
        sa.Column("redcap_field_mapping", JSONB),
        sa.Column("redcap_sync_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("redcap_sync_mode", sa.String(20), nullable=False, server_default="bidirectional"),
        sa.Column("status", sa.String(20), nullable=False, server_default="setup"),
        sa.Column("start_date", sa.Date),
        sa.Column("end_date", sa.Date),
    )
    op.create_index("ix_trials_facility_status", "clinical_trials", ["facility_id", "status"])

    op.create_table(
        "beds",
        *_audit_cols(),
        sa.Column("ward_id", UUID(as_uuid=True), sa.ForeignKey("wards.id"), nullable=False),
        sa.Column("bed_number", sa.String(20), nullable=False),
        sa.Column("bed_type", sa.String(20), nullable=False, server_default="standard"),
        sa.Column("status", sa.String(20), nullable=False, server_default="available"),
        sa.Column("current_patient_id", UUID(as_uuid=True)),
        sa.Column("current_admission_id", UUID(as_uuid=True)),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_beds_ward", "beds", ["facility_id", "ward_id"])
    op.create_index("ix_beds_facility_number", "beds", ["facility_id", "ward_id", "bed_number"], unique=True)
    op.create_index("ix_beds_status", "beds", ["facility_id", "status"])

    # ── Layer 4 ──────────────────────────────────────────────────────────────

    op.create_table(
        "clinical_notes",
        *_audit_cols(),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("note_type", sa.String(30), nullable=False),
        sa.Column("subjective", sa.Text),
        sa.Column("objective", sa.Text),
        sa.Column("assessment", sa.Text),
        sa.Column("plan", sa.Text),
        sa.Column("content", sa.Text),
        sa.Column("is_ai_generated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ai_model_version", sa.String(50)),
        sa.Column("clinician_approved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("clinician_approved_at", sa.DateTime(timezone=True)),
        sa.Column("clinician_approved_by", UUID(as_uuid=True)),
        sa.Column("is_addendum", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("parent_note_id", UUID(as_uuid=True), sa.ForeignKey("clinical_notes.id")),
    )
    op.create_index("ix_clinical_notes_encounter", "clinical_notes", ["facility_id", "encounter_id"])

    op.create_table(
        "diagnoses",
        *_audit_cols(),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("diagnosed_by", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("icd10_code", sa.String(20), nullable=False),
        sa.Column("icd10_description", sa.String(500), nullable=False),
        sa.Column("diagnosis_type", sa.String(20), nullable=False),
        sa.Column("clinical_status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("onset_date", sa.Date),
        sa.Column("resolved_date", sa.Date),
        sa.Column("notes", sa.Text),
        sa.Column("certainty", sa.String(20), nullable=False, server_default="confirmed"),
        sa.Column("is_chronic", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("fhir_id", sa.String(100)),
    )
    op.create_index("ix_diagnoses_encounter", "diagnoses", ["facility_id", "encounter_id"])
    op.create_index("ix_diagnoses_patient", "diagnoses", ["facility_id", "patient_id"])
    op.create_index("ix_diagnoses_icd10", "diagnoses", ["icd10_code"])

    op.create_table(
        "prescriptions",
        *_audit_cols(),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("prescriber_id", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("drug_name", sa.String(300), nullable=False),
        sa.Column("drug_code", sa.String(50)),
        sa.Column("generic_name", sa.String(300)),
        sa.Column("is_keml", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("atc_code", sa.String(20)),
        sa.Column("dosage", sa.String(100), nullable=False),
        sa.Column("dosage_value", sa.Float),
        sa.Column("dosage_unit", sa.String(20)),
        sa.Column("route", sa.String(30), nullable=False),
        sa.Column("frequency", sa.String(50), nullable=False),
        sa.Column("duration_days", sa.Integer),
        sa.Column("quantity", sa.Integer),
        sa.Column("instructions", sa.Text),
        sa.Column("interaction_checked", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("interactions", JSONB),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("dispensed_by", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("dispensed_at", sa.DateTime(timezone=True)),
        sa.Column("dispensed_quantity", sa.Integer),
        sa.Column("substitution_drug", sa.String(300)),
        sa.Column("refills_allowed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("refills_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unit_cost_cents", sa.Integer),
        sa.Column("total_cost_cents", sa.Integer),
        sa.Column("fhir_id", sa.String(100)),
    )
    op.create_index("ix_prescriptions_encounter", "prescriptions", ["facility_id", "encounter_id"])
    op.create_index("ix_prescriptions_patient", "prescriptions", ["facility_id", "patient_id"])
    op.create_index("ix_prescriptions_status", "prescriptions", ["facility_id", "status"])

    op.create_table(
        "vital_signs",
        *_audit_cols(),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("recorded_by", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("systolic_bp", sa.Integer),
        sa.Column("diastolic_bp", sa.Integer),
        sa.Column("heart_rate", sa.Integer),
        sa.Column("temperature", sa.Float),
        sa.Column("temperature_site", sa.String(20)),
        sa.Column("respiratory_rate", sa.Integer),
        sa.Column("oxygen_saturation", sa.Float),
        sa.Column("on_supplemental_o2", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("o2_flow_rate", sa.Float),
        sa.Column("weight_kg", sa.Float),
        sa.Column("height_cm", sa.Float),
        sa.Column("bmi", sa.Float),
        sa.Column("head_circumference_cm", sa.Float),
        sa.Column("muac_cm", sa.Float),
        sa.Column("pain_score", sa.Integer),
        sa.Column("blood_glucose", sa.Float),
        sa.Column("glucose_timing", sa.String(20)),
        sa.Column("gcs_eye", sa.Integer),
        sa.Column("gcs_verbal", sa.Integer),
        sa.Column("gcs_motor", sa.Integer),
        sa.Column("is_critical", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("critical_alerts", sa.String(500)),
        sa.Column("fhir_id", sa.String(100)),
    )
    op.create_index("ix_vitals_encounter", "vital_signs", ["facility_id", "encounter_id"])
    op.create_index("ix_vitals_patient", "vital_signs", ["facility_id", "patient_id"])
    op.create_index("ix_vitals_recorded_at", "vital_signs", ["facility_id", "recorded_at"])

    op.create_table(
        "lab_orders",
        *_audit_cols(),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("ordered_by", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("order_number", sa.String(50), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="routine"),
        sa.Column("status", sa.String(20), nullable=False, server_default="ordered"),
        sa.Column("specimen_type", sa.String(50)),
        sa.Column("specimen_collected_at", sa.DateTime(timezone=True)),
        sa.Column("specimen_collected_by", UUID(as_uuid=True)),
        sa.Column("specimen_id", sa.String(50)),
        sa.Column("clinical_info", sa.Text),
        sa.Column("fasting", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("total_cost_cents", sa.Integer),
        sa.Column("fhir_id", sa.String(100)),
    )
    op.create_index("ix_lab_orders_encounter", "lab_orders", ["facility_id", "encounter_id"])
    op.create_index("ix_lab_orders_patient", "lab_orders", ["facility_id", "patient_id"])
    op.create_index("ix_lab_orders_status", "lab_orders", ["facility_id", "status"])

    op.create_table(
        "imaging_orders",
        *_audit_cols(),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("ordered_by", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("order_number", sa.String(50), nullable=False),
        sa.Column("accession_number", sa.String(50)),
        sa.Column("modality", sa.String(20), nullable=False),
        sa.Column("body_part", sa.String(100), nullable=False),
        sa.Column("laterality", sa.String(20)),
        sa.Column("views_requested", sa.String(200)),
        sa.Column("study_description", sa.String(300), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False, server_default="routine"),
        sa.Column("clinical_indication", sa.Text),
        sa.Column("clinical_history", sa.Text),
        sa.Column("contrast_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("contrast_type", sa.String(100)),
        sa.Column("pregnancy_status", sa.String(20)),
        sa.Column("allergies_noted", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="ordered"),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("room", sa.String(50)),
        sa.Column("performed_by", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("performed_at", sa.DateTime(timezone=True)),
        sa.Column("total_cost_cents", sa.Integer),
        sa.Column("fhir_id", sa.String(100)),
    )
    op.create_index("ix_imaging_orders_encounter", "imaging_orders", ["facility_id", "encounter_id"])
    op.create_index("ix_imaging_orders_patient", "imaging_orders", ["facility_id", "patient_id"])
    op.create_index("ix_imaging_orders_status", "imaging_orders", ["facility_id", "status"])
    op.create_index("ix_imaging_orders_modality", "imaging_orders", ["facility_id", "modality"])

    op.create_table(
        "invoices",
        *_audit_cols(),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("invoice_number", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("payment_method", sa.String(20)),
        sa.Column("insurance_provider", sa.String(100)),
        sa.Column("insurance_member_no", sa.String(50)),
        sa.Column("sha_claim_ref", sa.String(100)),
        sa.Column("subtotal_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("discount_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tax_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("paid_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("balance_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.Text),
        sa.Column("finalized_at", sa.DateTime(timezone=True)),
        sa.Column("finalized_by", UUID(as_uuid=True)),
    )
    op.create_index("ix_invoices_facility_patient", "invoices", ["facility_id", "patient_id"])
    op.create_index("ix_invoices_facility_status", "invoices", ["facility_id", "status"])
    op.create_index("ix_invoices_number", "invoices", ["facility_id", "invoice_number"], unique=True)

    op.create_table(
        "anc_profiles",
        *_audit_cols(),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id")),
        sa.Column("anc_number", sa.String(50), nullable=False),
        sa.Column("gravida", sa.Integer, nullable=False),
        sa.Column("parity", sa.Integer, nullable=False),
        sa.Column("living_children", sa.Integer, nullable=False, server_default="0"),
        sa.Column("lmp_date", sa.Date),
        sa.Column("expected_delivery_date", sa.Date),
        sa.Column("first_visit_date", sa.Date),
        sa.Column("gestation_at_first_visit", sa.Integer),
        sa.Column("risk_level", sa.String(20), nullable=False, server_default="low"),
        sa.Column("risk_factors", JSONB),
        sa.Column("blood_group", sa.String(10)),
        sa.Column("hiv_status", sa.String(20)),
        sa.Column("hiv_test_date", sa.Date),
        sa.Column("on_art", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("vdrl_status", sa.String(20)),
        sa.Column("hepatitis_b", sa.String(20)),
        sa.Column("rhesus", sa.String(10)),
        sa.Column("pmtct_enrolled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("partner_hiv_status", sa.String(20)),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("pregnancy_outcome", sa.String(20)),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_anc_profiles_patient", "anc_profiles", ["facility_id", "patient_id"])
    op.create_index("ix_anc_profiles_status", "anc_profiles", ["facility_id", "status"])
    op.create_index("ix_anc_profiles_edd", "anc_profiles", ["facility_id", "expected_delivery_date"])

    op.create_table(
        "emergency_visits",
        *_audit_cols(),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id")),
        sa.Column("visit_number", sa.String(50), nullable=False),
        sa.Column("arrival_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("arrival_mode", sa.String(20), nullable=False, server_default="walk_in"),
        sa.Column("brought_by", sa.String(200)),
        sa.Column("chief_complaint", sa.Text, nullable=False),
        sa.Column("triage_category", sa.String(20), nullable=False, server_default="standard"),
        sa.Column("triage_color", sa.String(10), nullable=False, server_default="yellow"),
        sa.Column("triage_score", sa.Integer),
        sa.Column("triage_time", sa.DateTime(timezone=True)),
        sa.Column("triaged_by", UUID(as_uuid=True)),
        sa.Column("triage_vitals", JSONB),
        sa.Column("assigned_doctor_id", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("treatment_area", sa.String(30)),
        sa.Column("treatment_started_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="arrived"),
        sa.Column("disposition", sa.String(20)),
        sa.Column("disposition_time", sa.DateTime(timezone=True)),
        sa.Column("disposition_notes", sa.Text),
        sa.Column("admitted_to_ward_id", UUID(as_uuid=True)),
        sa.Column("is_trauma", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_resuscitation", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("allergies_noted", sa.Text),
        sa.Column("interventions", JSONB),
        sa.Column("notes", sa.Text),
        sa.UniqueConstraint("facility_id", "visit_number", name="uq_emergency_visits_visit_number"),
    )
    op.create_index("ix_emergency_visits_date", "emergency_visits", ["facility_id", "arrival_time"])
    op.create_index("ix_emergency_visits_status", "emergency_visits", ["facility_id", "status"])

    op.create_table(
        "referrals",
        *_audit_cols(),
        sa.Column("referral_number", sa.String(50), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id")),
        sa.Column("referral_type", sa.String(20), nullable=False, server_default="internal"),
        sa.Column("direction", sa.String(20), nullable=False, server_default="outgoing"),
        sa.Column("referring_doctor_id", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("referring_department_id", UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("referring_facility_name", sa.String(200)),
        sa.Column("receiving_doctor_id", UUID(as_uuid=True)),
        sa.Column("receiving_department_id", UUID(as_uuid=True)),
        sa.Column("receiving_facility_name", sa.String(200)),
        sa.Column("receiving_facility_mfl", sa.String(20)),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("clinical_notes", sa.Text),
        sa.Column("diagnosis", sa.String(500)),
        sa.Column("urgency", sa.String(20), nullable=False, server_default="routine"),
        sa.Column("referral_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("response_date", sa.DateTime(timezone=True)),
        sa.Column("response_notes", sa.Text),
        sa.Column("feedback", sa.Text),
        sa.Column("attachments", JSONB),
        sa.Column("notes", sa.Text),
        sa.UniqueConstraint("facility_id", "referral_number", name="uq_referrals_referral_number"),
    )
    op.create_index("ix_referrals_status", "referrals", ["facility_id", "status"])
    op.create_index("ix_referrals_patient", "referrals", ["facility_id", "patient_id"])
    op.create_index("ix_referrals_date", "referrals", ["facility_id", "referral_date"])
    op.create_index("ix_referrals_type", "referrals", ["facility_id", "referral_type"])

    op.create_table(
        "dental_visits",
        *_audit_cols(),
        sa.Column("visit_number", sa.String(50), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id")),
        sa.Column("dentist_id", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("visit_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("chief_complaint", sa.Text),
        sa.Column("examination_findings", sa.Text),
        sa.Column("procedures", JSONB),
        sa.Column("diagnosis", sa.String(500)),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_dental_visits_date", "dental_visits", ["facility_id", "visit_date"])
    op.create_index("ix_dental_visits_patient", "dental_visits", ["facility_id", "patient_id"])
    op.create_index("ix_dental_visits_status", "dental_visits", ["facility_id", "status"])

    op.create_table(
        "dental_treatment_plans",
        *_audit_cols(),
        sa.Column("plan_number", sa.String(50), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("dentist_id", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("diagnosis", sa.Text),
        sa.Column("plan_items", JSONB, nullable=False, server_default="[]"),
        sa.Column("total_estimated_cost", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_dental_treatment_plans_patient", "dental_treatment_plans", ["facility_id", "patient_id"])
    op.create_index("ix_dental_treatment_plans_status", "dental_treatment_plans", ["facility_id", "status"])

    op.create_table(
        "appointments",
        *_audit_cols(),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("doctor_id", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("department_id", UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("schedule_id", UUID(as_uuid=True), sa.ForeignKey("doctor_schedules.id")),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id")),
        sa.Column("appointment_number", sa.String(50), nullable=False),
        sa.Column("appointment_date", sa.Date, nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=False, server_default="15"),
        sa.Column("appointment_type", sa.String(30), nullable=False, server_default="consultation"),
        sa.Column("visit_reason", sa.Text),
        sa.Column("priority", sa.String(20), nullable=False, server_default="routine"),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("checked_in_at", sa.DateTime(timezone=True)),
        sa.Column("checked_in_by", UUID(as_uuid=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_by", UUID(as_uuid=True)),
        sa.Column("cancellation_reason", sa.Text),
        sa.Column("reminder_sent", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("reminder_sent_at", sa.DateTime(timezone=True)),
        sa.Column("is_recurring", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("recurrence_parent_id", UUID(as_uuid=True), sa.ForeignKey("appointments.id")),
        sa.Column("room", sa.String(50)),
        sa.Column("notes", sa.Text),
        sa.Column("internal_notes", sa.Text),
        sa.Column("booked_by", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.UniqueConstraint("facility_id", "appointment_number", name="uq_appointments_appointment_number"),
    )
    op.create_index("ix_appointments_patient", "appointments", ["facility_id", "patient_id"])
    op.create_index("ix_appointments_doctor", "appointments", ["facility_id", "doctor_id"])
    op.create_index("ix_appointments_date", "appointments", ["facility_id", "appointment_date"])
    op.create_index("ix_appointments_status", "appointments", ["facility_id", "status"])

    op.create_table(
        "admissions",
        *_audit_cols(),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("ward_id", UUID(as_uuid=True), sa.ForeignKey("wards.id"), nullable=False),
        sa.Column("bed_id", UUID(as_uuid=True), sa.ForeignKey("beds.id"), nullable=False),
        sa.Column("admission_number", sa.String(30), nullable=False),
        sa.Column("attending_doctor_id", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("primary_nurse_id", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("status", sa.String(20), nullable=False, server_default="admitted"),
        sa.Column("admission_reason", sa.Text),
        sa.Column("admission_diagnosis", sa.String(500)),
        sa.Column("admitted_from", sa.String(30)),
        sa.Column("accommodation_type", sa.String(30)),
        sa.Column("admitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("discharged_at", sa.DateTime(timezone=True)),
        sa.Column("discharged_by", UUID(as_uuid=True)),
        sa.Column("discharge_type", sa.String(30)),
        sa.Column("discharge_diagnosis", sa.String(500)),
        sa.Column("discharge_summary", sa.Text),
        sa.Column("follow_up_plan", sa.Text),
        sa.Column("discharge_medications", sa.Text),
        sa.Column("length_of_stay_days", sa.Integer),
        sa.UniqueConstraint("facility_id", "admission_number", name="uq_admissions_admission_number"),
    )
    op.create_index("ix_admissions_facility_patient", "admissions", ["facility_id", "patient_id"])
    op.create_index("ix_admissions_facility_status", "admissions", ["facility_id", "status"])
    op.create_index("ix_admissions_encounter", "admissions", ["encounter_id"])

    op.create_table(
        "surgical_cases",
        *_audit_cols(),
        sa.Column("case_number", sa.String(50), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id")),
        sa.Column("theatre_id", UUID(as_uuid=True), sa.ForeignKey("operating_theatres.id")),
        sa.Column("scheduled_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estimated_duration_min", sa.Integer, nullable=False, server_default="60"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="elective"),
        sa.Column("procedure_name", sa.String(500), nullable=False),
        sa.Column("procedure_code", sa.String(20)),
        sa.Column("laterality", sa.String(10)),
        sa.Column("diagnosis", sa.Text),
        sa.Column("anaesthesia_type", sa.String(30)),
        sa.Column("anaesthetist_id", UUID(as_uuid=True)),
        sa.Column("lead_surgeon_id", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("assistant_surgeon_id", UUID(as_uuid=True)),
        sa.Column("scrub_nurse_id", UUID(as_uuid=True)),
        sa.Column("circulating_nurse_id", UUID(as_uuid=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("preop_start", sa.DateTime(timezone=True)),
        sa.Column("surgery_start", sa.DateTime(timezone=True)),
        sa.Column("surgery_end", sa.DateTime(timezone=True)),
        sa.Column("recovery_start", sa.DateTime(timezone=True)),
        sa.Column("recovery_end", sa.DateTime(timezone=True)),
        sa.Column("operative_findings", sa.Text),
        sa.Column("operative_notes", sa.Text),
        sa.Column("specimens", JSONB),
        sa.Column("implants", JSONB),
        sa.Column("complications", sa.Text),
        sa.Column("blood_loss_ml", sa.Integer),
        sa.Column("postop_instructions", sa.Text),
        sa.Column("preop_checklist", JSONB),
        sa.Column("timeout_checklist", JSONB),
        sa.Column("signout_checklist", JSONB),
        sa.Column("cancellation_reason", sa.Text),
        sa.Column("notes", sa.Text),
        sa.UniqueConstraint("facility_id", "case_number", name="uq_surgical_cases_case_number"),
    )
    op.create_index("ix_surgical_cases_date", "surgical_cases", ["facility_id", "scheduled_date"])
    op.create_index("ix_surgical_cases_status", "surgical_cases", ["facility_id", "status"])
    op.create_index("ix_surgical_cases_patient", "surgical_cases", ["facility_id", "patient_id"])

    op.create_table(
        "patient_insurance",
        *_audit_cols(),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("scheme_id", UUID(as_uuid=True), sa.ForeignKey("insurance_schemes.id"), nullable=False),
        sa.Column("member_number", sa.String(50), nullable=False),
        sa.Column("principal_name", sa.String(200)),
        sa.Column("relationship", sa.String(30)),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_to", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )
    op.create_index("ix_patient_insurance_patient", "patient_insurance", ["facility_id", "patient_id"])
    op.create_index("ix_patient_insurance_facility_status", "patient_insurance", ["facility_id", "is_active"])

    op.create_table(
        "trial_participants",
        *_audit_cols(),
        sa.Column("trial_id", UUID(as_uuid=True), sa.ForeignKey("clinical_trials.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("participant_number", sa.String(30), nullable=False),
        sa.Column("randomization_arm", sa.String(50)),
        sa.Column("randomization_date", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="screened"),
        sa.Column("screening_date", sa.DateTime(timezone=True)),
        sa.Column("screened_by", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("screen_fail_reason", sa.Text),
        sa.Column("eligibility_check", JSONB),
        sa.Column("ai_eligibility_score", sa.Float),
        sa.Column("consent_version", sa.String(20)),
        sa.Column("consent_date", sa.DateTime(timezone=True)),
        sa.Column("consent_document_url", sa.String(500)),
        sa.Column("consent_witness", sa.String(200)),
        sa.Column("consent_withdrawn", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("consent_withdrawn_date", sa.DateTime(timezone=True)),
        sa.Column("consent_withdrawn_reason", sa.Text),
        sa.Column("enrollment_date", sa.DateTime(timezone=True)),
        sa.Column("enrolled_by", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("completion_date", sa.DateTime(timezone=True)),
        sa.Column("completion_status", sa.String(30)),
        sa.Column("withdrawal_reason", sa.Text),
        sa.Column("redcap_record_id", sa.String(50)),
        sa.Column("last_redcap_sync", sa.DateTime(timezone=True)),
        sa.Column("redcap_sync_status", sa.String(20), nullable=False, server_default="pending"),
        sa.UniqueConstraint("trial_id", "patient_id", name="uq_trial_patient"),
        sa.UniqueConstraint("trial_id", "participant_number", name="uq_trial_participant_number"),
    )
    op.create_index("ix_trial_participants_patient", "trial_participants", ["facility_id", "patient_id"])
    op.create_index("ix_trial_participants_trial", "trial_participants", ["trial_id", "status"])

    op.create_table(
        "trial_visit_schedule",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("trial_id", UUID(as_uuid=True), sa.ForeignKey("clinical_trials.id"), nullable=False),
        sa.Column("visit_code", sa.String(20), nullable=False),
        sa.Column("visit_name", sa.String(100), nullable=False),
        sa.Column("day_from_enrollment", sa.Integer, nullable=False),
        sa.Column("window_before_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("window_after_days", sa.Integer, nullable=False, server_default="0"),
        sa.Column("required_assessments", JSONB, nullable=False, server_default="[]"),
        sa.Column("is_mandatory", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "shift_assignments",
        *_audit_cols(),
        sa.Column("staff_id", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("shift_id", UUID(as_uuid=True), sa.ForeignKey("shifts.id"), nullable=False),
        sa.Column("department_id", UUID(as_uuid=True), sa.ForeignKey("departments.id")),
        sa.Column("assignment_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="assigned"),
        sa.Column("swapped_with_id", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("swap_reason", sa.Text),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_shift_assignments_date", "shift_assignments", ["facility_id", "assignment_date"])
    op.create_index("ix_shift_assignments_staff", "shift_assignments", ["facility_id", "staff_id"])

    op.create_table(
        "leave_requests",
        *_audit_cols(),
        sa.Column("staff_id", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("leave_type", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("days_requested", sa.Integer, nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("approved_by", UUID(as_uuid=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("handover_to", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("handover_notes", sa.Text),
        sa.Column("attachment_keys", JSONB),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_leave_requests_staff", "leave_requests", ["facility_id", "staff_id"])
    op.create_index("ix_leave_requests_status", "leave_requests", ["facility_id", "status"])

    op.create_table(
        "attendance",
        *_audit_cols(),
        sa.Column("staff_id", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("shift_id", UUID(as_uuid=True), sa.ForeignKey("shifts.id")),
        sa.Column("attendance_date", sa.Date, nullable=False),
        sa.Column("clock_in", sa.DateTime(timezone=True)),
        sa.Column("clock_out", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="present"),
        sa.Column("overtime_minutes", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_attendance_staff_date", "attendance", ["facility_id", "staff_id", "attendance_date"])

    op.create_table(
        "generated_reports",
        *_audit_cols(),
        sa.Column("template_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("report_number", sa.String(50), nullable=False),
        sa.Column("parameters", JSONB),
        sa.Column("date_from", sa.Date, nullable=False),
        sa.Column("date_to", sa.Date, nullable=False),
        sa.Column("result_data", JSONB),
        sa.Column("summary_data", JSONB),
        sa.Column("row_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="generating"),
        sa.Column("format", sa.String(10), nullable=False, server_default="json"),
        sa.Column("file_key", sa.String(500)),
        sa.Column("generated_by", UUID(as_uuid=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "purchase_orders",
        *_audit_cols(),
        sa.Column("po_number", sa.String(50), nullable=False),
        sa.Column("supplier_id", UUID(as_uuid=True), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("order_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expected_delivery", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("subtotal", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tax_amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("approved_by", UUID(as_uuid=True)),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("delivery_address", sa.Text),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_purchase_orders_status", "purchase_orders", ["facility_id", "status"])
    op.create_index("ix_purchase_orders_supplier", "purchase_orders", ["facility_id", "supplier_id"])

    # ── Layer 5 ──────────────────────────────────────────────────────────────

    op.create_table(
        "lab_results",
        *_audit_cols(),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("lab_orders.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("performed_by", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("verified_by", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("test_code", sa.String(50), nullable=False),
        sa.Column("test_name", sa.String(200), nullable=False),
        sa.Column("loinc_code", sa.String(20)),
        sa.Column("panel_name", sa.String(100)),
        sa.Column("result_value", sa.String(200)),
        sa.Column("result_numeric", sa.Float),
        sa.Column("result_unit", sa.String(50)),
        sa.Column("reference_range", sa.String(100)),
        sa.Column("interpretation", sa.String(20)),
        sa.Column("is_critical", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_abnormal", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("critical_notified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("critical_notified_to", UUID(as_uuid=True)),
        sa.Column("critical_notified_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("resulted_at", sa.DateTime(timezone=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
        sa.Column("method", sa.String(100)),
        sa.Column("fhir_id", sa.String(100)),
    )
    op.create_index("ix_lab_results_order", "lab_results", ["facility_id", "order_id"])
    op.create_index("ix_lab_results_test_code", "lab_results", ["test_code"])

    op.create_table(
        "imaging_results",
        *_audit_cols(),
        sa.Column("order_id", UUID(as_uuid=True), sa.ForeignKey("imaging_orders.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("reported_by", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("verified_by", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("findings", sa.Text),
        sa.Column("impression", sa.Text),
        sa.Column("recommendations", sa.Text),
        sa.Column("technique", sa.Text),
        sa.Column("comparison", sa.Text),
        sa.Column("urgency", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("is_critical", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("critical_notified", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("critical_notified_to", UUID(as_uuid=True)),
        sa.Column("critical_notified_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("reported_at", sa.DateTime(timezone=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("image_keys", JSONB),
        sa.Column("dicom_study_uid", sa.String(200)),
        sa.Column("dicom_series_count", sa.Integer),
        sa.Column("dicom_instance_count", sa.Integer),
        sa.Column("notes", sa.Text),
        sa.Column("fhir_id", sa.String(100)),
    )
    op.create_index("ix_imaging_results_order", "imaging_results", ["facility_id", "order_id"])
    op.create_index("ix_imaging_results_status", "imaging_results", ["facility_id", "status"])

    op.create_table(
        "invoice_items",
        *_audit_cols(),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("item_type", sa.String(30), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("unit_price_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("discount_cents", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reference_id", UUID(as_uuid=True)),
        sa.Column("reference_type", sa.String(30)),
    )
    op.create_index("ix_invoice_items_invoice", "invoice_items", ["invoice_id"])

    op.create_table(
        "payments",
        *_audit_cols(),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("payment_method", sa.String(20), nullable=False),
        sa.Column("reference_number", sa.String(100)),
        sa.Column("mpesa_transaction_id", sa.String(50)),
        sa.Column("received_by", UUID(as_uuid=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_payments_invoice", "payments", ["invoice_id"])
    op.create_index("ix_payments_facility_date", "payments", ["facility_id", "paid_at"])

    op.create_table(
        "dispensings",
        *_audit_cols(),
        sa.Column("prescription_id", UUID(as_uuid=True), sa.ForeignKey("prescriptions.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("pharmacy_item_id", UUID(as_uuid=True), sa.ForeignKey("pharmacy_items.id")),
        sa.Column("dispensed_by", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("drug_name", sa.String(300), nullable=False),
        sa.Column("quantity_requested", sa.Integer, nullable=False),
        sa.Column("quantity_dispensed", sa.Integer, nullable=False),
        sa.Column("substitution_drug", sa.String(300)),
        sa.Column("substitution_reason", sa.Text),
        sa.Column("dosage_instructions", sa.Text),
        sa.Column("counseling_done", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("counseling_notes", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="dispensed"),
        sa.Column("unit_price_cents", sa.Integer),
        sa.Column("total_price_cents", sa.Integer),
        sa.Column("payment_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("payment_method", sa.String(20)),
        sa.Column("dispensed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_dispensings_prescription", "dispensings", ["facility_id", "prescription_id"])
    op.create_index("ix_dispensings_patient", "dispensings", ["facility_id", "patient_id"])
    op.create_index("ix_dispensings_status", "dispensings", ["facility_id", "status"])

    op.create_table(
        "nursing_notes",
        *_audit_cols(),
        sa.Column("admission_id", UUID(as_uuid=True), sa.ForeignKey("admissions.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("note_type", sa.String(30), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("shift", sa.String(10)),
        sa.Column("severity", sa.String(10)),
    )
    op.create_index("ix_nursing_notes_admission", "nursing_notes", ["facility_id", "admission_id"])

    op.create_table(
        "anc_visits",
        *_audit_cols(),
        sa.Column("anc_profile_id", UUID(as_uuid=True), sa.ForeignKey("anc_profiles.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id")),
        sa.Column("provider_id", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("visit_number", sa.Integer, nullable=False),
        sa.Column("visit_date", sa.Date, nullable=False),
        sa.Column("gestation_weeks", sa.Integer),
        sa.Column("weight_kg", sa.Float),
        sa.Column("bp_systolic", sa.Integer),
        sa.Column("bp_diastolic", sa.Integer),
        sa.Column("pulse_rate", sa.Integer),
        sa.Column("temperature", sa.Float),
        sa.Column("urine_protein", sa.String(20)),
        sa.Column("urine_glucose", sa.String(20)),
        sa.Column("fundal_height_cm", sa.Float),
        sa.Column("fetal_heart_rate", sa.Integer),
        sa.Column("fetal_presentation", sa.String(30)),
        sa.Column("fetal_movement", sa.String(20)),
        sa.Column("oedema", sa.String(20)),
        sa.Column("hb_level", sa.Float),
        sa.Column("iron_folate_given", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("tetanus_dose", sa.String(20)),
        sa.Column("ipt_malaria_dose", sa.String(20)),
        sa.Column("deworming_given", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("llins_given", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("birth_plan_discussed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("danger_signs_counselled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("breastfeeding_counselled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("next_visit_date", sa.Date),
        sa.Column("clinical_notes", sa.Text),
        sa.Column("complications", sa.Text),
        sa.Column("referred", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("referral_reason", sa.Text),
    )
    op.create_index("ix_anc_visits_profile", "anc_visits", ["facility_id", "anc_profile_id"])

    op.create_table(
        "delivery_records",
        *_audit_cols(),
        sa.Column("anc_profile_id", UUID(as_uuid=True), sa.ForeignKey("anc_profiles.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id")),
        sa.Column("delivered_by", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("delivery_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("gestation_weeks", sa.Integer),
        sa.Column("mode_of_delivery", sa.String(30), nullable=False),
        sa.Column("duration_of_labour_hours", sa.Float),
        sa.Column("place_of_delivery", sa.String(30), nullable=False, server_default="facility"),
        sa.Column("maternal_outcome", sa.String(20), nullable=False, server_default="alive"),
        sa.Column("maternal_complications", sa.Text),
        sa.Column("blood_loss_ml", sa.Integer),
        sa.Column("episiotomy", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("tears", sa.String(20)),
        sa.Column("baby_outcome", sa.String(20), nullable=False),
        sa.Column("baby_sex", sa.String(10)),
        sa.Column("birth_weight_grams", sa.Integer),
        sa.Column("apgar_1min", sa.Integer),
        sa.Column("apgar_5min", sa.Integer),
        sa.Column("apgar_10min", sa.Integer),
        sa.Column("resuscitation_needed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("skin_to_skin", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("breastfed_within_1hr", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("vitamin_k_given", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("eye_prophylaxis", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("bcg_given", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("opv_0_given", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("arv_prophylaxis_baby", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_delivery_records_profile", "delivery_records", ["facility_id", "anc_profile_id"])
    op.create_index("ix_delivery_records_patient", "delivery_records", ["facility_id", "patient_id"])

    op.create_table(
        "insurance_claims",
        *_audit_cols(),
        sa.Column("claim_number", sa.String(50), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("scheme_id", UUID(as_uuid=True), sa.ForeignKey("insurance_schemes.id"), nullable=False),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id")),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id")),
        sa.Column("member_number", sa.String(50), nullable=False),
        sa.Column("claim_amount", sa.Integer, nullable=False),
        sa.Column("approved_amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("paid_amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("claim_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("submitted_date", sa.DateTime(timezone=True)),
        sa.Column("processed_date", sa.DateTime(timezone=True)),
        sa.Column("paid_date", sa.DateTime(timezone=True)),
        sa.Column("claim_items", JSONB),
        sa.Column("diagnosis_codes", JSONB),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("sha_reference", sa.String(50)),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_insurance_claims_status", "insurance_claims", ["facility_id", "status"])
    op.create_index("ix_insurance_claims_scheme", "insurance_claims", ["facility_id", "scheme_id"])
    op.create_index("ix_insurance_claims_patient", "insurance_claims", ["facility_id", "patient_id"])

    op.create_table(
        "pre_authorizations",
        *_audit_cols(),
        sa.Column("auth_number", sa.String(50), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("scheme_id", UUID(as_uuid=True), sa.ForeignKey("insurance_schemes.id"), nullable=False),
        sa.Column("member_number", sa.String(50), nullable=False),
        sa.Column("service_description", sa.Text, nullable=False),
        sa.Column("estimated_cost", sa.Integer, nullable=False),
        sa.Column("approved_amount", sa.Integer, nullable=False, server_default="0"),
        sa.Column("diagnosis", sa.String(500)),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("request_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("response_date", sa.DateTime(timezone=True)),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_pre_auth_status", "pre_authorizations", ["facility_id", "status"])

    op.create_table(
        "trial_participant_visits",
        *_audit_cols(),
        sa.Column("participant_id", UUID(as_uuid=True), sa.ForeignKey("trial_participants.id"), nullable=False),
        sa.Column("schedule_id", UUID(as_uuid=True), sa.ForeignKey("trial_visit_schedule.id"), nullable=False),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id")),
        sa.Column("scheduled_date", sa.Date, nullable=False),
        sa.Column("actual_date", sa.Date),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"),
        sa.Column("assessments_completed", JSONB),
        sa.Column("protocol_deviations", JSONB),
        sa.Column("ai_window_alert", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ai_missing_assessments", JSONB),
        sa.Column("redcap_synced", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("redcap_sync_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_tpv_participant", "trial_participant_visits", ["participant_id", "status"])

    op.create_table(
        "trial_adverse_events",
        *_audit_cols(),
        sa.Column("participant_id", UUID(as_uuid=True), sa.ForeignKey("trial_participants.id"), nullable=False),
        sa.Column("trial_id", UUID(as_uuid=True), sa.ForeignKey("clinical_trials.id"), nullable=False),
        sa.Column("ae_term", sa.Text, nullable=False),
        sa.Column("meddra_code", sa.String(20)),
        sa.Column("meddra_pt", sa.String(200)),
        sa.Column("meddra_soc", sa.String(200)),
        sa.Column("ctcae_grade", sa.SmallInteger),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("is_serious", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("seriousness_criteria", JSONB),
        sa.Column("relatedness", sa.String(30)),
        sa.Column("onset_date", sa.Date, nullable=False),
        sa.Column("resolution_date", sa.Date),
        sa.Column("outcome", sa.String(30)),
        sa.Column("action_taken", sa.String(30)),
        sa.Column("reported_by", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("reported_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("sae_aware_date", sa.DateTime(timezone=True)),
        sa.Column("sae_reported_to_sponsor", sa.DateTime(timezone=True)),
        sa.Column("sae_reported_to_irb", sa.DateTime(timezone=True)),
        sa.Column("sae_report_document_url", sa.String(500)),
        sa.Column("redcap_synced", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_index("ix_tae_participant", "trial_adverse_events", ["participant_id"])
    op.create_index("ix_tae_trial_serious", "trial_adverse_events", ["trial_id", "is_serious"])

    op.create_table(
        "trial_ai_screening",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("facility_id", UUID(as_uuid=True), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("trial_id", UUID(as_uuid=True), sa.ForeignKey("clinical_trials.id"), nullable=False),
        sa.Column("encounter_id", UUID(as_uuid=True), sa.ForeignKey("encounters.id")),
        sa.Column("eligibility_score", sa.Float, nullable=False),
        sa.Column("criteria_met", JSONB, nullable=False),
        sa.Column("criteria_not_met", JSONB),
        sa.Column("criteria_unknown", JSONB),
        sa.Column("ai_reasoning", sa.Text),
        sa.Column("model_version", sa.String(50)),
        sa.Column("investigator_reviewed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("investigator_id", UUID(as_uuid=True), sa.ForeignKey("staff.id")),
        sa.Column("investigator_decision", sa.String(20)),
        sa.Column("review_notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_screening_patient_trial", "trial_ai_screening", ["patient_id", "trial_id"])
    op.create_index("ix_screening_facility", "trial_ai_screening", ["facility_id"])

    op.create_table(
        "purchase_order_items",
        *_audit_cols(),
        sa.Column("purchase_order_id", UUID(as_uuid=True), sa.ForeignKey("purchase_orders.id"), nullable=False),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("inventory_items.id"), nullable=False),
        sa.Column("quantity_ordered", sa.Integer, nullable=False),
        sa.Column("quantity_received", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Integer, nullable=False),
        sa.Column("total_cost", sa.Integer, nullable=False),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_po_items_order", "purchase_order_items", ["purchase_order_id"])

    op.create_table(
        "inventory_transactions",
        *_audit_cols(),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("inventory_items.id"), nullable=False),
        sa.Column("transaction_type", sa.String(30), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("balance_after", sa.Integer, nullable=False),
        sa.Column("unit_cost", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Integer, nullable=False, server_default="0"),
        sa.Column("transaction_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reference_number", sa.String(50)),
        sa.Column("department_id", UUID(as_uuid=True)),
        sa.Column("issued_to", sa.String(200)),
        sa.Column("reason", sa.Text),
        sa.Column("batch_number", sa.String(50)),
        sa.Column("expiry_date", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_inventory_transactions_item", "inventory_transactions", ["facility_id", "item_id"])
    op.create_index("ix_inventory_transactions_date", "inventory_transactions", ["facility_id", "transaction_date"])

    # ── Layer 6 ──────────────────────────────────────────────────────────────

    op.create_table(
        "stock_transactions",
        *_audit_cols(),
        sa.Column("pharmacy_item_id", UUID(as_uuid=True), sa.ForeignKey("pharmacy_items.id"), nullable=False),
        sa.Column("dispensing_id", UUID(as_uuid=True), sa.ForeignKey("dispensings.id")),
        sa.Column("transaction_type", sa.String(20), nullable=False),
        sa.Column("quantity_change", sa.Integer, nullable=False),
        sa.Column("quantity_before", sa.Integer, nullable=False),
        sa.Column("quantity_after", sa.Integer, nullable=False),
        sa.Column("reference_number", sa.String(100)),
        sa.Column("reason", sa.Text),
        sa.Column("unit_cost_cents", sa.Integer),
        sa.Column("batch_number", sa.String(50)),
        sa.Column("expiry_date", sa.Date),
    )
    op.create_index("ix_stock_transactions_item", "stock_transactions", ["facility_id", "pharmacy_item_id"])
    op.create_index("ix_stock_transactions_type", "stock_transactions", ["facility_id", "transaction_type"])

    op.create_table(
        "child_records",
        *_audit_cols(),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("mother_patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id")),
        sa.Column("delivery_record_id", UUID(as_uuid=True), sa.ForeignKey("delivery_records.id")),
        sa.Column("child_number", sa.String(50), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=False),
        sa.Column("birth_weight_grams", sa.Integer),
        sa.Column("sex", sa.String(10), nullable=False),
        sa.Column("place_of_birth", sa.String(30)),
        sa.Column("birth_notification_number", sa.String(50)),
        sa.Column("hiv_exposed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("pcr_test_date", sa.Date),
        sa.Column("pcr_result", sa.String(20)),
        sa.Column("feeding_method", sa.String(30)),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_child_records_patient", "child_records", ["facility_id", "patient_id"])
    op.create_index("ix_child_records_mother", "child_records", ["facility_id", "mother_patient_id"])

    # ── Layer 7 ──────────────────────────────────────────────────────────────

    op.create_table(
        "immunizations",
        *_audit_cols(),
        sa.Column("child_record_id", UUID(as_uuid=True), sa.ForeignKey("child_records.id"), nullable=False),
        sa.Column("patient_id", UUID(as_uuid=True), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("administered_by", UUID(as_uuid=True), sa.ForeignKey("staff.id"), nullable=False),
        sa.Column("vaccine_code", sa.String(30), nullable=False),
        sa.Column("vaccine_name", sa.String(100), nullable=False),
        sa.Column("dose_number", sa.Integer, nullable=False),
        sa.Column("date_given", sa.Date, nullable=False),
        sa.Column("age_at_dose_weeks", sa.Integer),
        sa.Column("batch_number", sa.String(50)),
        sa.Column("site", sa.String(50)),
        sa.Column("route", sa.String(20)),
        sa.Column("scheduled_date", sa.Date),
        sa.Column("is_overdue", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("adverse_event", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("adverse_event_description", sa.Text),
        sa.Column("notes", sa.Text),
    )
    op.create_index("ix_immunizations_child", "immunizations", ["facility_id", "child_record_id"])
    op.create_index("ix_immunizations_vaccine", "immunizations", ["facility_id", "vaccine_code"])


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    tables = [
        "immunizations",
        "child_records",
        "stock_transactions",
        "inventory_transactions",
        "purchase_order_items",
        "trial_ai_screening",
        "trial_adverse_events",
        "trial_participant_visits",
        "pre_authorizations",
        "insurance_claims",
        "delivery_records",
        "anc_visits",
        "nursing_notes",
        "dispensings",
        "payments",
        "invoice_items",
        "imaging_results",
        "lab_results",
        "purchase_orders",
        "generated_reports",
        "attendance",
        "leave_requests",
        "shift_assignments",
        "trial_visit_schedule",
        "trial_participants",
        "patient_insurance",
        "surgical_cases",
        "admissions",
        "appointments",
        "dental_treatment_plans",
        "dental_visits",
        "referrals",
        "emergency_visits",
        "anc_profiles",
        "invoices",
        "imaging_orders",
        "lab_orders",
        "vital_signs",
        "prescriptions",
        "diagnoses",
        "clinical_notes",
        "beds",
        "clinical_trials",
        "dental_charts",
        "staff_profiles",
        "doctor_schedules",
        "encounters",
        "inventory_items",
        "shifts",
        "wards",
        "staff",
        "operating_theatres",
        "insurance_schemes",
        "suppliers",
        "pharmacy_items",
        "report_templates",
        "patients",
        "departments",
        "facility_update_status",
        "app_updates",
        "usage_telemetry",
        "facility_licenses",
        "events",
        "facilities",
    ]
    for table in tables:
        op.drop_table(table)
