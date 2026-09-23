-- ============================================================================
-- Aifya DB  Phase B  -  security baseline / hardening  (COMPLETE VERSION)
-- ----------------------------------------------------------------------------
-- WHAT THIS DOES
--   1. Creates (if missing) roles aifya_app_role / aifya_user and re-grants
--      aifya_user membership in aifya_app_role so RLS policies apply to the
--      login user the API actually connects with.
--   2. Enables pgcrypto / uuid-ossp (safe if already enabled).
--   3. Enforces least privilege on schema public (no PUBLIC usage/create).
--   4. Adds DB-level PII helpers encrypt_pii / decrypt_pii + facility
--      session-context helper set_facility_context().
--   5. Replaces the migration-008 policies on patients & encounters with
--      USING + WITH CHECK policies (so INSERT/UPDATE are constrained too)
--      and FORCEs RLS so even the table owner must honour facility context.
--   6. Creates an immutable audit_logs trail + SECURITY DEFINER trigger
--      function and attaches AFTER INSERT/UPDATE/DELETE triggers to
--      patients & encounters.
--   7. Prints a verification summary.
--
-- RUN ORDER (IMPORTANT)
--   a) services/api-gateway/scripts/db_setup_roles.sql   (as superuser, db=postgres)
--   b) alembic upgrade head                              (as aifya_user)
--   c) THIS FILE                                         (as superuser, db=aifya)
--
-- Example:
--   $env:PGPASSWORD = "YOUR_SUPERUSER_PASSWORD"
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost `
--       -d aifya -f scripts\db_security_baseline.sql
--
-- Safe to re-run (fully idempotent). Tables are guarded with to_regclass()
-- so this file never crashes if you run it before the migrations.
-- ============================================================================

\set ON_ERROR_STOP 1

-- ============================================================================
-- 1. EXTENSIONS
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 2. ROLE ARCHITECTURE (bootstrap is idempotent - duplicates Phase A safely)
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'aifya_app_role') THEN
        CREATE ROLE aifya_app_role NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'aifya_user') THEN
        CREATE ROLE aifya_user LOGIN PASSWORD 'aifya_dev_password'
               NOSUPERUSER NOCREATEDB NOCREATEROLE;
    ELSE
        -- Keep password in sync with services/api-gateway/.env
        ALTER ROLE aifya_user WITH LOGIN PASSWORD 'aifya_dev_password';
    END IF;
END
$$;

-- Membership is REQUIRED: policies below are FOR ALL TO aifya_app_role and
-- must also constrain aifya_user (the owner + the role the API logs in as).
GRANT aifya_app_role TO aifya_user;

-- ============================================================================
-- 3. LEAST-PRIVILEGE SCHEMA ACCESS
-- ============================================================================
-- Revoke everything from PUBLIC; database owner (aifya_user via
-- pg_database_owner) keeps CREATE for future alembic migrations.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO aifya_app_role;
GRANT USAGE ON SCHEMA public TO aifya_user;

-- Existing objects
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aifya_app_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO aifya_app_role;

-- Future objects created by the app login user (alembic)
ALTER DEFAULT PRIVILEGES FOR ROLE aifya_user IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aifya_app_role;
ALTER DEFAULT PRIVILEGES FOR ROLE aifya_user IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO aifya_app_role;

-- Future objects created by whichever superuser runs this script
ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aifya_app_role;
ALTER DEFAULT PRIVILEGES FOR ROLE CURRENT_USER IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO aifya_app_role;

-- ============================================================================
-- 4. ENCRYPTION AT REST FOR SENSITIVE PII  (DB-level helpers)
-- ============================================================================
-- Compatible with the two-argument call style used by
-- backfill_employee_encryption.py: encrypt_pii(data, key). When the key is
-- omitted it falls back to the session variable app.pii_secret.
CREATE OR REPLACE FUNCTION encrypt_pii(data TEXT, secret_key TEXT DEFAULT NULL)
RETURNS BYTEA
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  key TEXT := COALESCE(secret_key, current_setting('app.pii_secret', true));
BEGIN
  IF key IS NULL OR key = '' THEN
    RAISE EXCEPTION 'encrypt_pii: no secret key. Pass one or SET app.pii_secret';
  END IF;
  RETURN pgp_sym_encrypt(data, key, 'cipher-algo=aes256');
END;
$$;

CREATE OR REPLACE FUNCTION decrypt_pii(encrypted_data BYTEA, secret_key TEXT DEFAULT NULL)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  key TEXT := COALESCE(secret_key, current_setting('app.pii_secret', true));
BEGIN
  IF encrypted_data IS NULL THEN
    RETURN NULL;
  END IF;
  IF key IS NULL OR key = '' THEN
    RAISE EXCEPTION 'decrypt_pii: no secret key. Pass one or SET app.pii_secret';
  END IF;
  RETURN pgp_sym_decrypt(encrypted_data, key);
END;
$$;

-- Only the application role may execute these (defence in depth)
REVOKE ALL ON FUNCTION public.encrypt_pii(TEXT, TEXT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.decrypt_pii(BYTEA, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.encrypt_pii(TEXT, TEXT) TO aifya_app_role;
GRANT EXECUTE ON FUNCTION public.decrypt_pii(BYTEA, TEXT) TO aifya_app_role;

-- ============================================================================
-- 4b. FACILITY SESSION-CONTEXT HELPER
-- ============================================================================
-- The API middleware and the seed script call this (or set_config directly)
-- before any DML so the RLS policies below can filter rows per facility.
CREATE OR REPLACE FUNCTION set_facility_context(facility_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
  PERFORM set_config('app.current_facility_id', facility_id::text, false);
END;
$$;

REVOKE ALL ON FUNCTION public.set_facility_context(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.set_facility_context(UUID) TO aifya_app_role;
GRANT EXECUTE ON FUNCTION public.set_facility_context(UUID) TO aifya_user;

-- ============================================================================
-- 5. ROW-LEVEL SECURITY  (multi-facility isolation on patients & encounters)
-- ============================================================================
-- Migration 008 already ENABLE+FORCEs RLS and creates an unrestricted
-- `facility_isolation` policy on every facility_id table. Here we replace the
-- policy on the two clinical tables with a role-scoped policy that has both
-- USING (SELECT/UPDATE/DELETE filter) and WITH CHECK (INSERT/UPDATE guard),
-- and re-FORCE RLS so the table owner (aifya_user) is constrained as well.
DO $$
BEGIN
    IF to_regclass('public.patients') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.patients ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.patients FORCE ROW LEVEL SECURITY';
        EXECUTE 'DROP POLICY IF EXISTS facility_isolation ON public.patients';
        EXECUTE 'DROP POLICY IF EXISTS facility_isolation_patients ON public.patients';
        EXECUTE $pol$
            CREATE POLICY facility_isolation_patients ON public.patients
            FOR ALL TO aifya_app_role
            USING (facility_id = NULLIF(current_setting('app.current_facility_id', true), '')::uuid)
            WITH CHECK (facility_id = NULLIF(current_setting('app.current_facility_id', true), '')::uuid)
        $pol$;
    END IF;
END
$$;

DO $$
BEGIN
    IF to_regclass('public.encounters') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.encounters ENABLE ROW LEVEL SECURITY';
        EXECUTE 'ALTER TABLE public.encounters FORCE ROW LEVEL SECURITY';
        EXECUTE 'DROP POLICY IF EXISTS facility_isolation ON public.encounters';
        EXECUTE 'DROP POLICY IF EXISTS facility_isolation_encounters ON public.encounters';
        EXECUTE $pol$
            CREATE POLICY facility_isolation_encounters ON public.encounters
            FOR ALL TO aifya_app_role
            USING (facility_id = NULLIF(current_setting('app.current_facility_id', true), '')::uuid)
            WITH CHECK (facility_id = NULLIF(current_setting('app.current_facility_id', true), '')::uuid)
        $pol$;
    END IF;
END
$$;

-- ============================================================================
-- 6. IMMUTABLE HEALTH-DATA AUDIT TRAIL
-- ============================================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name  VARCHAR(64)  NOT NULL,
    operation   VARCHAR(10)  NOT NULL,
    record_id   UUID         NOT NULL,
    old_data    JSONB,
    new_data    JSONB,
    changed_by  VARCHAR(128) DEFAULT current_user,
    changed_at  TIMESTAMPTZ  DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_audit_logs_table_time ON audit_logs (table_name, changed_at);
CREATE INDEX IF NOT EXISTS ix_audit_logs_record     ON audit_logs (record_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_changed_at ON audit_logs (changed_at DESC);

-- The app role can append and read, but never alter/delete the trail.
REVOKE ALL ON audit_logs FROM aifya_app_role;
GRANT INSERT, SELECT ON audit_logs TO aifya_app_role;

-- Trigger function runs SECURITY DEFINER (owner = superuser that ran this
-- script) so it can always write to audit_logs. changed_by is recorded as the
-- real login role that fired the trigger (session_user), not the definer.
CREATE OR REPLACE FUNCTION audit_trigger_func()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        INSERT INTO audit_logs (table_name, operation, record_id, old_data, changed_by)
        VALUES (TG_TABLE_NAME, TG_OP, OLD.id, to_jsonb(OLD), session_user);
        RETURN OLD;
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO audit_logs (table_name, operation, record_id, old_data, new_data, changed_by)
        VALUES (TG_TABLE_NAME, TG_OP, NEW.id, to_jsonb(OLD), to_jsonb(NEW), session_user);
        RETURN NEW;
    ELSIF TG_OP = 'INSERT' THEN
        INSERT INTO audit_logs (table_name, operation, record_id, new_data, changed_by)
        VALUES (TG_TABLE_NAME, TG_OP, NEW.id, to_jsonb(NEW), session_user);
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION public.audit_trigger_func() FROM PUBLIC;

-- Attach triggers only where the underlying tables exist.
DO $$
BEGIN
    IF to_regclass('public.patients') IS NOT NULL THEN
        EXECUTE 'DROP TRIGGER IF EXISTS audit_patients ON public.patients';
        EXECUTE 'CREATE TRIGGER audit_patients
                 AFTER INSERT OR UPDATE OR DELETE ON public.patients
                 FOR EACH ROW EXECUTE FUNCTION public.audit_trigger_func()';
    END IF;
    IF to_regclass('public.encounters') IS NOT NULL THEN
        EXECUTE 'DROP TRIGGER IF EXISTS audit_encounters ON public.encounters';
        EXECUTE 'CREATE TRIGGER audit_encounters
                 AFTER INSERT OR UPDATE OR DELETE ON public.encounters
                 FOR EACH ROW EXECUTE FUNCTION public.audit_trigger_func()';
    END IF;
END
$$;

-- ============================================================================
-- 7. VERIFICATION  (run psql as superuser to see everything)
-- ============================================================================
SELECT rolname, rolcanlogin AS can_login, rolsuper AS is_superuser
FROM pg_roles
WHERE rolname LIKE 'aifya%'
ORDER BY 1;

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('patients', 'encounters', 'audit_logs')
ORDER BY 1;

SELECT schemaname, tablename, policyname, permissive, cmd, roles
FROM pg_policies
WHERE tablename IN ('patients', 'encounters')
ORDER BY tablename, policyname;

SELECT tgname, tgrelid::regclass AS on_table
FROM pg_trigger
WHERE NOT tgisinternal
  AND tgname IN ('audit_patients', 'audit_encounters')
ORDER BY tgrelid::regclass::text;

SELECT p.proname AS function_name
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
  AND p.proname IN ('encrypt_pii', 'decrypt_pii', 'set_facility_context', 'audit_trigger_func')
ORDER BY 1;