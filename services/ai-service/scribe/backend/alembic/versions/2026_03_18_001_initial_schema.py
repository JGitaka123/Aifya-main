"""Initial schema - baseline from aifya_schema.sql

Revision ID: 001
Revises: None
Create Date: 2026-03-18

This migration represents the baseline schema. If you're starting fresh,
run the database/aifya_schema.sql file first, then stamp this revision:
    alembic stamp 001
"""
from typing import Sequence, Union

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This is a baseline migration.
    # The initial schema is defined in database/aifya_schema.sql
    # Run that SQL file manually for fresh deployments, then:
    #   alembic stamp 001
    #
    # For subsequent migrations, add new revision files.
    op.execute("""
        CREATE TABLE IF NOT EXISTS alembic_version_tracking (
            id SERIAL PRIMARY KEY,
            migration_id VARCHAR(32) NOT NULL,
            applied_at TIMESTAMPTZ DEFAULT NOW(),
            description TEXT
        );
        INSERT INTO alembic_version_tracking (migration_id, description)
        VALUES ('001', 'Baseline schema from aifya_schema.sql');
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alembic_version_tracking;")
