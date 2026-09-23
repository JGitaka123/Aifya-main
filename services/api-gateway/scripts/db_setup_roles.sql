-- ============================================================================
-- Aifya DB  Phase A  -  roles + database
-- Run as the postgres superuser, connected to the default 'postgres' DB:
--   psql -U postgres -h localhost -d postgres -f scripts\db_setup_roles.sql
-- Safe to re-run (idempotent).
-- ============================================================================

\set ON_ERROR_STOP 0

-- Restricted application role (no login)
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'aifya_app_role') THEN
    CREATE ROLE aifya_app_role NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
  END IF;
END
$$;

-- Application login user: create if missing, else reset password to match .env
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'aifya_user') THEN
    CREATE ROLE aifya_user LOGIN PASSWORD 'aifya_dev_password'
           NOSUPERUSER NOCREATEDB NOCREATEROLE;
  ELSE
    ALTER ROLE aifya_user WITH LOGIN PASSWORD 'aifya_dev_password';
  END IF;
END
$$;

GRANT aifya_app_role TO aifya_user;

-- Create the application database if it does not exist yet
SELECT 'CREATE DATABASE aifya OWNER aifya_user'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'aifya')\gexec