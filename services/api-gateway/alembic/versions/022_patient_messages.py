"""Patient communication tables — durable message log and consent record.

Adds the two tables the Communication Hub needs so sending a message actually
records it:

* patient_messages           — outbound SMS / WhatsApp / email delivery log
* communication_preferences  — per-patient consent + opt-out (Kenya DPA)

Both are facility-scoped, so the same FORCE ROW LEVEL SECURITY policy that
migration 008/018 applies everywhere else is applied here too. Without it the
tables would be the only tenant data readable across facilities.

Safe to re-run: every step is guarded with IF NOT EXISTS / DROP POLICY IF EXISTS.

Revision ID: 022_patient_messages
Revises: 021_emergency_referral_links
Create Date: 2026-09-10
"""

from alembic import op

revision = "022_patient_messages"
down_revision = "021_emergency_referral_links"
branch_labels = None
depends_on = None

_AUDIT_COLUMNS = """
    facility_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    created_by uuid,
    updated_by uuid,
    is_deleted boolean NOT NULL DEFAULT false,
    deleted_at timestamptz
"""


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS patient_messages (
            id uuid PRIMARY KEY,
            patient_id uuid NOT NULL,
            channel varchar(20) NOT NULL,
            category varchar(40) NOT NULL,
            recipient_phone varchar(20) NOT NULL DEFAULT '',
            recipient_email varchar(255),
            subject varchar(200),
            template_id uuid,
            template_params jsonb,
            body text NOT NULL,
            status varchar(20) NOT NULL DEFAULT 'queued',
            retry_count integer NOT NULL DEFAULT 0,
            scheduled_at timestamptz,
            sent_at timestamptz,
            delivered_at timestamptz,
            read_at timestamptz,
            error_message text,
            provider_message_id varchar(120),
            {_AUDIT_COLUMNS}
        )
        """
    )

    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS communication_preferences (
            id uuid PRIMARY KEY,
            patient_id uuid NOT NULL,
            preferred_channel varchar(20) NOT NULL DEFAULT 'sms',
            opt_out_categories jsonb DEFAULT '[]'::jsonb,
            consent_given boolean NOT NULL DEFAULT false,
            consent_date timestamptz,
            preferred_language varchar(5) NOT NULL DEFAULT 'en',
            {_AUDIT_COLUMNS},
            CONSTRAINT uq_communication_preferences_patient
                UNIQUE (facility_id, patient_id)
        )
        """
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_patient_messages_facility_created "
        "ON patient_messages (facility_id, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_patient_messages_patient "
        "ON patient_messages (facility_id, patient_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_patient_messages_status "
        "ON patient_messages (facility_id, status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_communication_preferences_facility "
        "ON communication_preferences (facility_id)"
    )

    # Tenant isolation, matching migrations 008 and 018.
    op.execute(
        """
        DO $$
        DECLARE
            target text;
        BEGIN
            FOREACH target IN ARRAY ARRAY[
                'patient_messages',
                'communication_preferences'
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
    op.execute("DROP TABLE IF EXISTS communication_preferences")
    op.execute("DROP TABLE IF EXISTS patient_messages")