"""Platform-level login store for internal (Aifya-hosted) authentication.

When AUTH_PROVIDER=internal the branded login/registration forms verify
credentials stored here instead of in Keycloak. The table is intentionally
NOT facility-scoped/RLS-protected: it is the platform-level identity lookup
that maps a unique email to its staff + facility, mirroring the role the
Keycloak user store used to play. It holds no clinical data.

Revision ID: 019_internal_auth_accounts
Revises: 018_tenant_rls_backfill
Create Date: 2026-09-08
"""

from alembic import op

revision = "019_internal_auth_accounts"
down_revision = "018_tenant_rls_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS auth_accounts ("
        "id UUID PRIMARY KEY, "
        "staff_id UUID NOT NULL UNIQUE REFERENCES staff(id) ON DELETE CASCADE, "
        "facility_id UUID NOT NULL REFERENCES facilities(id) ON DELETE CASCADE, "
        "email VARCHAR(255) NOT NULL, "
        "password_hash VARCHAR(255) NOT NULL, "
        "is_active BOOLEAN NOT NULL DEFAULT TRUE, "
        "created_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ")"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_auth_accounts_email_lower "
        "ON auth_accounts (lower(email))"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_auth_accounts_facility_id "
        "ON auth_accounts (facility_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS auth_accounts")
