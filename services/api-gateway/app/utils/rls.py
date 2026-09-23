"""
PostgreSQL Row-Level Security helpers.
RLS is defense-in-depth for multi-tenancy — the application layer
already filters by facility_id, but RLS prevents accidental leaks.
"""

# SQL statements for setting up RLS on clinical tables.
# Run these as part of a migration or DB setup script.

RLS_TABLES = [
    "patients",
    "encounters",
    "clinical_notes",
    "diagnoses",
    "prescriptions",
    "vital_signs",
    "lab_orders",
    "lab_results",
    "clinical_trials",
    "trial_participants",
    "trial_participant_visits",
    "trial_adverse_events",
    "events",
    "staff",
    "departments",
]


def generate_rls_setup_sql() -> str:
    """
    Generate SQL to enable RLS on all clinical tables.
    Uses a session variable `app.current_facility_id` set per request.

    @returns SQL string for RLS setup
    """
    statements: list[str] = []

    for table in RLS_TABLES:
        statements.append(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        statements.append(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        statements.append(
            f"CREATE POLICY {table}_facility_isolation ON {table} "
            f"USING (facility_id::text = current_setting('app.current_facility_id', TRUE));"
        )

    return "\n".join(statements)


def generate_rls_teardown_sql() -> str:
    """
    Generate SQL to remove RLS from all clinical tables (for migration downgrade).

    @returns SQL string for RLS teardown
    """
    statements: list[str] = []

    for table in RLS_TABLES:
        statements.append(
            f"DROP POLICY IF EXISTS {table}_facility_isolation ON {table};"
        )
        statements.append(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")

    return "\n".join(statements)


SET_FACILITY_SQL = "SET app.current_facility_id = :facility_id;"
"""SQL to set the current facility for RLS filtering in a session."""
