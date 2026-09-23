#!/usr/bin/env bash
# Restore a PostgreSQL dump produced by scripts/backup-db.sh into the
# Aifya docker compose stack.
#
# Usage: ./scripts/restore-db.sh /var/backups/aifya/aifya-YYYYMMDD-HHMMSS.sql.gz
#
# DESTRUCTIVE: drops and recreates the target database. The script asks
# for confirmation unless FORCE=1 is set. Stop the API first so no
# connections hold the database open.
set -euo pipefail

DUMP="${1:?usage: restore-db.sh <dump.sql.gz>}"
POSTGRES_USER="${POSTGRES_USER:-aifya_user}"
POSTGRES_DB="${POSTGRES_DB:-aifya}"
COMPOSE="${COMPOSE:-docker compose}"

[ -f "${DUMP}" ] || { echo "[restore] ERROR: ${DUMP} not found" >&2; exit 1; }
gunzip -t "${DUMP}" || { echo "[restore] ERROR: dump fails integrity check" >&2; exit 1; }

if [ "${FORCE:-0}" != "1" ]; then
  echo "This will DROP and recreate database '${POSTGRES_DB}' from:"
  echo "  ${DUMP}"
  read -r -p "Type 'restore' to continue: " answer
  [ "${answer}" = "restore" ] || { echo "[restore] aborted"; exit 1; }
fi

echo "[restore] stopping api services"
${COMPOSE} stop api-gateway api-worker api-beat || true

echo "[restore] recreating database ${POSTGRES_DB}"
${COMPOSE} exec -T postgres psql -U "${POSTGRES_USER}" -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT pg_terminate_backend(pid) FROM pg_stat_activity
  WHERE datname = '${POSTGRES_DB}' AND pid <> pg_backend_pid();
DROP DATABASE IF EXISTS ${POSTGRES_DB};
CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};
SQL

echo "[restore] loading dump"
gunzip -c "${DUMP}" | ${COMPOSE} exec -T postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -v ON_ERROR_STOP=1 -q

echo "[restore] verifying"
${COMPOSE} exec -T postgres psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -tAc \
  "SELECT 'tables: ' || count(*) FROM information_schema.tables WHERE table_schema='public';"

echo "[restore] restarting api services"
${COMPOSE} start api-gateway api-worker api-beat || ${COMPOSE} up -d api-gateway

echo "[restore] done — verify the app before resuming clinical use"
