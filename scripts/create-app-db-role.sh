#!/usr/bin/env bash
# Create a NON-superuser application role so tenant row-level security
# actually applies (audit finding H-3: the stock compose setup connects
# as a superuser, which bypasses FORCE ROW LEVEL SECURITY).
#
# Usage (on the server, once):
#   APP_DB_PASSWORD='strong-random-password' ./scripts/create-app-db-role.sh
#
# Then point DATABASE_URL at the new role and restart the API:
#   postgresql+asyncpg://aifya_app:<password>@postgres:5432/aifya
#
# Alembic migrations may keep using the owner role; only the runtime API
# connection needs to be non-superuser for RLS to bite.
set -euo pipefail

: "${APP_DB_PASSWORD:?set APP_DB_PASSWORD to a strong random password}"
POSTGRES_USER="${POSTGRES_USER:-aifya_user}"
POSTGRES_DB="${POSTGRES_DB:-aifya}"
APP_ROLE="${APP_ROLE:-aifya_app}"
COMPOSE="${COMPOSE:-docker compose}"

${COMPOSE} exec -T postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" \
  -v ON_ERROR_STOP=1 \
  -v role="${APP_ROLE}" \
  -v pw="${APP_DB_PASSWORD}" \
  -v db="${POSTGRES_DB}" <<'SQL'
-- Create or update the role (\gexec runs the generated statement).
SELECT format(
  'CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD %L',
  :'role', :'pw'
)
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'role')
\gexec

SELECT format(
  'ALTER ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD %L',
  :'role', :'pw'
)
WHERE EXISTS (SELECT FROM pg_roles WHERE rolname = :'role')
\gexec

SELECT format('GRANT CONNECT ON DATABASE %I TO %I', :'db', :'role') \gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'role') \gexec
SELECT format(
  'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO %I',
  :'role'
) \gexec
SELECT format(
  'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO %I', :'role'
) \gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I',
  :'role'
) \gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO %I',
  :'role'
) \gexec
SQL

echo "[db-role] role '${APP_ROLE}' ready."
echo "[db-role] Update DATABASE_URL to use ${APP_ROLE} and restart api-gateway,"
echo "[db-role] api-worker and api-beat. Verify RLS is active with:"
echo "  docker compose exec postgres psql -U ${APP_ROLE} -d ${POSTGRES_DB} -c 'SELECT count(*) FROM patients;'"
echo "  (should return 0 rows when app.current_facility_id is not set)"
