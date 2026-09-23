"""Store knowledge chunk embeddings in PostgreSQL.

Adds ``knowledge_chunks.embedding`` so vector search can run against the
database Aifya already has, with no Qdrant server, no Docker and no extra
Python wheel. Query embeddings are L2-normalised, so a plain dot product is
the cosine similarity and can be computed with ``unnest ... WITH ORDINALITY``.

``VECTOR_BACKEND=postgres`` selects this backend; ``qdrant`` still works and
keeps using the external vector store.

Safe to re-run: guarded with IF NOT EXISTS.

Revision ID: 024_knowledge_chunk_embeddings
Revises: 023_knowledge_tables
Create Date: 2026-09-10
"""

from alembic import op

revision = "024_knowledge_chunk_embeddings"
down_revision = "023_knowledge_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE knowledge_chunks "
        "ADD COLUMN IF NOT EXISTS embedding real[]"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS embedding"
    )