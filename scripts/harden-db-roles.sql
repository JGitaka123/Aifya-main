-- Tighten the database roles behind tenant isolation.
--
-- Verified against the workstation database on 2026-09-27:
--   * 123 tables in `public`; 107 carry ENABLE + FORCE ROW LEVEL SECURITY.
--   * The runtime login `aifya_user` OWNS 112 of them.
--   * `aifya_app_role` - the NOLOGIN group meant to carry the application's
--     grants - holds NO privileges on any table, and `aifya_user` is its only
--     member. It currently grants nothing and only looks like a restriction.
--
-- Why that matters: a table owner bypasses row-level security unless FORCE is
-- set, and can switch it off with a single ALTER. Isolation therefore rests on
-- every future table being created with FORCE by hand, and the credential the
-- API serves traffic with can also DROP tables.
--
-- Take a backup first, then run PART A as a superuser:
--
--   psql -U postgres -d "AIFYA-MAIN" -v app_password='<strong-random>' \
--        -f scripts/harden-db-roles.sql
--
-- PART A is additive and safe to run now. PART B changes ownership: run it in
-- a maintenance window, and afterwards run Alembic as `aifya_owner` so future
-- migrations create their tables under the right name.
--
-- PART B has one hard prerequisite: point the API's DATABASE_URL at the new
-- `aifya_app` login and confirm it serves traffic BEFORE running it. Ownership
-- is what gives `aifya_user` its access today, so the moment ownership moves
-- that login can no longer read a row. Switching afterwards is an outage.

\set ON_ERROR_STOP on

-- ===========================================================================
-- PART A - a runtime login that can only read and write rows
-- ===========================================================================

-- A.1 The restricted login. NOBYPASSRLS is the point of this whole exercise.
SELECT format(
  'CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT '
  'NOBYPASSRLS PASSWORD %L',
  'aifya_app', :'app_password'
)
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aifya_app')
\gexec

SELECT format(
  'ALTER ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT '
  'NOBYPASSRLS PASSWORD %L',
  'aifya_app', :'app_password'
)
\gexec

-- A.2 Reach the schema, but never its structure.
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), 'aifya_app') \gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', 'aifya_app') \gexec
SELECT format('REVOKE CREATE ON SCHEMA public FROM %I', 'aifya_app') \gexec

-- A.3 Rows, not DDL: SELECT/INSERT/UPDATE/DELETE and nothing else. No TRUNCATE,
--     no REFERENCES, no TRIGGER, and no ownership.
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO aifya_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO aifya_app;

-- A.4 Same rights for anything a future migration creates.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO aifya_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO aifya_app;

-- A.5 Prove isolation before pointing the API at it. Both must return 0 with no
--     app.current_facility_id set, and the right count once it is set.
--   psql -U aifya_app -d "AIFYA-MAIN" -c 'SELECT count(*) FROM patients;'
--   psql -U aifya_app -d "AIFYA-MAIN" -c \
--     "SELECT set_config('app.current_facility_id','<facility-uuid>',false); SELECT count(*) FROM patients;"

-- ===========================================================================
-- PART B - stop the runtime login from owning the schema  (maintenance window)
-- ===========================================================================
-- Run this only after A.5 passed. Move the objects first, then the database,
-- so there is never a moment where the API's role owns nothing it can reach.

-- B.1 An owner role that never serves traffic.
SELECT format('CREATE ROLE %I NOLOGIN', 'aifya_owner')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'aifya_owner')
\gexec

-- B.2 Hand over every object in the schema.
DO $$
DECLARE obj record;
BEGIN
  FOR obj IN
    SELECT tablename AS name, 'TABLE' AS kind FROM pg_tables WHERE schemaname = 'public'
    UNION ALL
    SELECT sequence_name, 'SEQUENCE' FROM information_schema.sequences WHERE sequence_schema = 'public'
    UNION ALL
    SELECT viewname, 'VIEW' FROM pg_views WHERE schemaname = 'public'
  LOOP
    EXECUTE format('ALTER %s public.%I OWNER TO aifya_owner', obj.kind, obj.name);
  END LOOP;
END $$;

SELECT format('ALTER SCHEMA public OWNER TO %I', 'aifya_owner') \gexec
SELECT format('ALTER DATABASE %I OWNER TO %I', current_database(), 'aifya_owner') \gexec

-- B.3 Lock out the old login and drop the dead group. By this point the API is
--     already running as `aifya_app` (PART A) - see the prerequisite above.
--     `aifya_app_role` never granted anything, so it only looked like a
--     restriction; remove it rather than leave it pretending.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM aifya_app_role;
DROP ROLE IF EXISTS aifya_app_role;
ALTER ROLE aifya_user NOLOGIN;

-- B.4 Sanity checks, both of which must hold before the window is closed.
--   psql -U aifya_app -d "AIFYA-MAIN" -c \
--     "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tableowner='aifya_app';"
--   -- expect 0: the runtime login owns nothing
--   psql -U aifya_app -d "AIFYA-MAIN" -c 'SELECT count(*) FROM patients;'
--   -- expect 0: RLS is doing the isolating now, not ownership