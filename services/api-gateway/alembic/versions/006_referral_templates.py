"""Referral templates.

Revision ID: 006
Revises: 005
Create Date: 2026-05-07

Adds referral_templates for facility-managed standardized referral
note prefills by specialty.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "006"
down_revision = "005"
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
    """Create referral_templates table."""
    op.create_table(
        "referral_templates",
        *_audit_cols(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("specialty", sa.String(100), nullable=False),
        sa.Column("template_text", sa.Text, nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
    )
    op.create_index(
        "ix_referral_templates_specialty",
        "referral_templates",
        ["facility_id", "specialty"],
    )


def downgrade() -> None:
    """Drop referral_templates table."""
    op.drop_index("ix_referral_templates_specialty", table_name="referral_templates")
    op.drop_table("referral_templates")
