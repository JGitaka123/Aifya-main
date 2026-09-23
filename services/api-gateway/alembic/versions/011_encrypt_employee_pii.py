"""Encrypt sensitive employee PII at rest (id_number, kra_pin, bank_account).

Widens id_number/kra_pin to hold Fernet ciphertext and lazily backfills:
existing plaintext rows keep working (the app decrypts values without the
enc: prefix as-is) and are re-encrypted on next save. Run the one-off
backfill in scripts/backfill_employee_encryption.py to encrypt eagerly.

Revision ID: 011_encrypt_employee_pii
Revises: 010_pharmacy_batches
Create Date: 2026-07-20
"""

import sqlalchemy as sa
from alembic import op

revision = "011_encrypt_employee_pii"
down_revision = "010_pharmacy_batches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ciphertext is far longer than the plaintext; widen the columns.
    op.alter_column(
        "employees", "id_number",
        existing_type=sa.String(length=20),
        type_=sa.String(length=188),
        existing_nullable=True,
    )
    op.alter_column(
        "employees", "kra_pin",
        existing_type=sa.String(length=20),
        type_=sa.String(length=188),
        existing_nullable=True,
    )
    # bank_account is already TEXT — no column change needed.


def downgrade() -> None:
    # Narrowing would truncate ciphertext; only safe once values are
    # decrypted back to plaintext. Left as a widen-only, non-reversible
    # column size change (data is preserved).
    op.alter_column(
        "employees", "kra_pin",
        existing_type=sa.String(length=188),
        type_=sa.String(length=20),
        existing_nullable=True,
    )
    op.alter_column(
        "employees", "id_number",
        existing_type=sa.String(length=188),
        type_=sa.String(length=20),
        existing_nullable=True,
    )
