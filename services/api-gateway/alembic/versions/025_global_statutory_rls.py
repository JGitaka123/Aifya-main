"""Allow global statutory default rows to be seeded under tenant RLS.

Migration 008 gave every table with a nullable ``facility_id`` a
``facility_isolation`` policy whose USING clause admits shared rows
(``facility_id IS NULL``) but whose WITH CHECK clause does not. ``USING``
governs reads and ``WITH CHECK`` governs writes, so shared rows could be read
but never created.

That silently broke ``seed_payroll_defaults``: the national PAYE bands, NSSF
tiers, statutory rates and default leave types it seeds all carry
``facility_id = NULL``, so every insert was rejected by row-level security.
With no PAYE bands and no NSSF tiers the payroll engine computed PAYE and NSSF
as zero for every employee, and the P9 / PAYE / NSSF schedules reported zeros.

These four tables hold national rates that are identical for every facility,
so their WITH CHECK now mirrors USING. Facility-scoped rows stay confined to
their tenant, and the API never writes a NULL ``facility_id`` (both
``create_statutory_rate`` and ``create_leave_type`` force the caller's
facility), so this does not widen what a tenant can write.

Revision ID: 025_global_statutory_rls
Revises: 024_knowledge_chunk_embeddings
Create Date: 2026-09-10
"""

from alembic import op

revision = "025_global_statutory_rls"
down_revision = "024_knowledge_chunk_embeddings"
branch_labels = None
depends_on = None

# Tables whose rows may legitimately be facility-independent (national defaults).
_TABLES = ("paye_bands", "nssf_tiers", "statutory_rates", "leave_types")

_USING = (
    "facility_id IS NULL OR facility_id::text = "
    "current_setting('app.current_facility_id', true)"
)
_SCOPED = (
    "facility_id::text = current_setting('app.current_facility_id', true)"
)


def _rebuild(table: str, with_check: str) -> None:
    """Replace the facility_isolation policy on one table.

    @param table: Table name (never user input)
    @param with_check: WITH CHECK expression to install
    @returns None
    """
    op.execute(f"DROP POLICY IF EXISTS facility_isolation ON public.{table}")
    op.execute(
        f"CREATE POLICY facility_isolation ON public.{table} "
        f"USING ({_USING}) WITH CHECK ({with_check})"
    )


def upgrade() -> None:
    for table in _TABLES:
        _rebuild(table, _USING)


def downgrade() -> None:
    for table in _TABLES:
        _rebuild(table, _SCOPED)