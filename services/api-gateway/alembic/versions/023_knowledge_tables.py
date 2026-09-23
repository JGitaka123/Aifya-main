"""Knowledge RAG tables â€” document metadata and extracted text chunks.

The Knowledge tab ("Institutional Knowledge") uploads documents to MinIO,
extracts and embeds their text, and records the metadata here. Until now
these two tables existed only as SQLAlchemy models inside
``services/ai-service/knowledge`` with no migration anywhere in the repo,
so the upload endpoint failed with a 502/500 as soon as the service was
reachable.

* knowledge_documents â€” uploaded document metadata + ingest status
* knowledge_chunks    â€” text chunks extracted from each document

Both are facility-scoped, so the same FORCE ROW LEVEL SECURITY policy that
migrations 008/018/022 apply everywhere else is applied here too.

Safe to re-run: every step is guarded with IF NOT EXISTS / DROP POLICY IF EXISTS.

Revision ID: 023_knowledge_tables
Revises: 022_patient_messages
Create Date: 2026-09-10
"""

from alembic import op

revision = "023_knowledge_tables"
down_revision = "022_patient_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_documents (
            id uuid PRIMARY KEY,
            facility_id uuid NOT NULL,
            title varchar(500) NOT NULL,
            category varchar(50) NOT NULL,
            status varchar(30) NOT NULL DEFAULT 'uploading',
            description text,
            department varchar(100),
            tags varchar[] NOT NULL DEFAULT '{}',
            access_scope varchar(30) NOT NULL DEFAULT 'facility',
            file_name varchar(500) NOT NULL,
            file_size_bytes integer NOT NULL,
            mime_type varchar(100) NOT NULL,
            minio_object_key varchar(1000) NOT NULL,
            chunk_count integer NOT NULL DEFAULT 0,
            page_count integer NOT NULL DEFAULT 0,
            version_label varchar(50),
            effective_date timestamptz,
            expiry_date timestamptz,
            celery_task_id varchar(255),
            error_message text,
            processing_metadata jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            created_by uuid,
            updated_by uuid,
            uploaded_by_name varchar(200),
            is_deleted boolean NOT NULL DEFAULT false,
            deleted_at timestamptz
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id uuid PRIMARY KEY,
            document_id uuid NOT NULL,
            facility_id uuid NOT NULL,
            chunk_index integer NOT NULL,
            "text" text NOT NULL,
            page_number integer,
            section_title varchar(500),
            token_count integer NOT NULL DEFAULT 0,
            qdrant_point_id varchar(255),
            created_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )

    index_statements = (
        "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_facility_id "
        "ON knowledge_documents (facility_id)",
        "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_category "
        "ON knowledge_documents (category)",
        "CREATE INDEX IF NOT EXISTS ix_kdocs_facility_category "
        "ON knowledge_documents (facility_id, category)",
        "CREATE INDEX IF NOT EXISTS ix_kdocs_facility_status "
        "ON knowledge_documents (facility_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_kdocs_facility_department "
        "ON knowledge_documents (facility_id, department)",
        "CREATE INDEX IF NOT EXISTS ix_kdocs_facility_created "
        "ON knowledge_documents (facility_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_document_id "
        "ON knowledge_chunks (document_id)",
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_facility_id "
        "ON knowledge_chunks (facility_id)",
        "CREATE INDEX IF NOT EXISTS ix_kchunks_document "
        "ON knowledge_chunks (document_id)",
        "CREATE INDEX IF NOT EXISTS ix_kchunks_facility "
        "ON knowledge_chunks (facility_id)",
    )
    for statement in index_statements:
        op.execute(statement)

    # Tenant isolation, matching migrations 008, 018 and 022.
    op.execute(
        """
        DO $$
        DECLARE
            target text;
        BEGIN
            FOREACH target IN ARRAY ARRAY[
                'knowledge_documents',
                'knowledge_chunks'
            ]
            LOOP
                EXECUTE format(
                    'ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', target
                );
                EXECUTE format(
                    'ALTER TABLE public.%I FORCE ROW LEVEL SECURITY', target
                );
                EXECUTE format(
                    'DROP POLICY IF EXISTS facility_isolation ON public.%I',
                    target
                );
                EXECUTE format(
                    'CREATE POLICY facility_isolation ON public.%I '
                    || 'USING (facility_id::text = '
                    || 'current_setting(''app.current_facility_id'', true)) '
                    || 'WITH CHECK (facility_id::text = '
                    || 'current_setting(''app.current_facility_id'', true))',
                    target
                );
            END LOOP;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS knowledge_chunks")
    op.execute("DROP TABLE IF EXISTS knowledge_documents")