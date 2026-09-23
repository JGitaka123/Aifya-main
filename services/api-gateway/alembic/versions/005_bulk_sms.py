"""Bulk SMS campaigns + delivery log.

Revision ID: 005
Revises: 004
Create Date: 2026-05-07

Adds sms_campaigns and sms_delivery_log tables for bulk SMS sending.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "005"
down_revision = "004"
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
    """Create sms_campaigns and sms_delivery_log tables."""
    op.create_table(
        "sms_campaigns",
        *_audit_cols(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("recipient_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sent_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('draft','sending','completed','failed')",
            name="ck_sms_campaigns_status",
        ),
    )
    op.create_index(
        "ix_sms_campaigns_facility_status",
        "sms_campaigns",
        ["facility_id", "status"],
    )
    op.create_index(
        "ix_sms_campaigns_created_at",
        "sms_campaigns",
        ["facility_id", "created_at"],
    )

    op.create_table(
        "sms_delivery_log",
        *_audit_cols(),
        sa.Column(
            "campaign_id", UUID(as_uuid=True), sa.ForeignKey("sms_campaigns.id")
        ),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("provider_message_id", sa.String(100)),
        sa.Column("cost", sa.Numeric(8, 4), nullable=False, server_default="0"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("error_msg", sa.Text),
        sa.CheckConstraint(
            "status IN ('queued','sent','delivered','failed')",
            name="ck_sms_delivery_status",
        ),
    )
    op.create_index(
        "ix_sms_delivery_campaign",
        "sms_delivery_log",
        ["facility_id", "campaign_id"],
    )
    op.create_index(
        "ix_sms_delivery_status",
        "sms_delivery_log",
        ["facility_id", "status"],
    )
    op.create_index(
        "ix_sms_delivery_phone",
        "sms_delivery_log",
        ["facility_id", "phone_number"],
    )


def downgrade() -> None:
    """Drop bulk SMS tables."""
    op.drop_index("ix_sms_delivery_phone", table_name="sms_delivery_log")
    op.drop_index("ix_sms_delivery_status", table_name="sms_delivery_log")
    op.drop_index("ix_sms_delivery_campaign", table_name="sms_delivery_log")
    op.drop_table("sms_delivery_log")
    op.drop_index("ix_sms_campaigns_created_at", table_name="sms_campaigns")
    op.drop_index("ix_sms_campaigns_facility_status", table_name="sms_campaigns")
    op.drop_table("sms_campaigns")
