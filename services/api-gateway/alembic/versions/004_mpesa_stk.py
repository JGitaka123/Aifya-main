"""M-Pesa STK Push tracking + Bulk SMS + Referral Templates.

Revision ID: 004
Revises: 003
Create Date: 2026-05-07

Adds the mpesa_stk_requests table for tracking M-Pesa STK Push payments
through their full lifecycle (initiation → callback → reconciliation).
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "004"
down_revision = "003"
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
    """Create mpesa_stk_requests table."""
    op.create_table(
        "mpesa_stk_requests",
        *_audit_cols(),
        sa.Column("invoice_id", UUID(as_uuid=True), sa.ForeignKey("invoices.id")),
        sa.Column("patient_id", UUID(as_uuid=True)),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reference", sa.String(100), nullable=False),
        sa.Column("description", sa.String(200), nullable=False, server_default=""),
        sa.Column("checkout_request_id", sa.String(100), nullable=False),
        sa.Column("merchant_request_id", sa.String(100), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("result_code", sa.Integer),
        sa.Column("result_desc", sa.Text),
        sa.Column("mpesa_receipt_number", sa.String(50)),
        sa.Column("transaction_date", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "checkout_request_id", name="uq_mpesa_stk_checkout_request_id"
        ),
        sa.CheckConstraint(
            "status IN ('pending','success','failed','timeout')",
            name="ck_mpesa_stk_status",
        ),
    )
    op.create_index(
        "ix_mpesa_stk_facility_status",
        "mpesa_stk_requests",
        ["facility_id", "status"],
    )
    op.create_index(
        "ix_mpesa_stk_invoice",
        "mpesa_stk_requests",
        ["facility_id", "invoice_id"],
    )
    op.create_index(
        "ix_mpesa_stk_created_at",
        "mpesa_stk_requests",
        ["facility_id", "created_at"],
    )


def downgrade() -> None:
    """Drop mpesa_stk_requests table."""
    op.drop_index("ix_mpesa_stk_created_at", table_name="mpesa_stk_requests")
    op.drop_index("ix_mpesa_stk_invoice", table_name="mpesa_stk_requests")
    op.drop_index("ix_mpesa_stk_facility_status", table_name="mpesa_stk_requests")
    op.drop_table("mpesa_stk_requests")
