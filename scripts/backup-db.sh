#!/usr/bin/env bash
# Nightly PostgreSQL backup for the Aifya stack (docker compose deployment).
#
# Usage:  ./scripts/backup-db.sh [backup_dir]
# Cron:   15 2 * * * cd /root/Aifya && ./scripts/backup-db.sh >> /var/log/aifya-backup.log 2>&1
#
# Keeps the last $RETAIN_DAYS daily dumps. Restore with scripts/restore-db.sh.
set -euo pipefail

BACKUP_DIR="${1:-/var/backups/aifya}"
RETAIN_DAYS="${RETAIN_DAYS:-14}"
POSTGRES_USER="${POSTGRES_USER:-aifya_user}"
POSTGRES_DB="${POSTGRES_DB:-aifya}"
COMPOSE="${COMPOSE:-docker compose}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${BACKUP_DIR}/aifya-${STAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"

echo "[backup] dumping ${POSTGRES_DB} to ${OUT}"
${COMPOSE} exec -T postgres pg_dump -U "${POSTGRES_USER}" --no-owner "${POSTGRES_DB}" \
  | gzip > "${OUT}.partial"
mv "${OUT}.partial" "${OUT}"

# Integrity check: a dump that gunzips clean and ends with the pg_dump
# footer is structurally complete.
if ! gunzip -t "${OUT}"; then
  echo "[backup] ERROR: ${OUT} failed gzip integrity check" >&2
  exit 1
fi
if ! gunzip -c "${OUT}" | tail -5 | grep -q "PostgreSQL database dump complete"; then
  echo "[backup] ERROR: ${OUT} is truncated (no pg_dump footer)" >&2
  exit 1
fi

SIZE="$(du -h "${OUT}" | cut -f1)"
echo "[backup] OK ${OUT} (${SIZE})"

echo "[backup] pruning dumps older than ${RETAIN_DAYS} days"
find "${BACKUP_DIR}" -name 'aifya-*.sql.gz' -mtime "+${RETAIN_DAYS}" -delete

echo "[backup] done"
