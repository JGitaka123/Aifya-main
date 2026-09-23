#!/usr/bin/env bash
set -euo pipefail

# ClaimFlow Tenant & Admin Onboarding Utility
# This script creates a new tenant, a facility, and a bootstrap administrator.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker/docker-compose.prod.yml"
ENV_FILE="${REPO_ROOT}/docker/.env"

log() {
  printf "[onboard] %s\n" "$*"
}

fail() {
  printf "[onboard] ERROR: %s\n" "$*" >&2
  exit 1
}

usage() {
  cat <<EOF
Usage: bash scripts/onboard-tenant.sh [options]

Options:
  --tenant-name <name>       Name of the organization/hospital
  --tenant-slug <slug>       URL-friendly slug (e.g., 'city-hospital')
  --facility-name <name>     Full name of the facility
  --facility-code <id>       SHA/National ID for the facility
  --admin-email <email>      Email for the new administrator
  --admin-password <pass>    Temporary password for the administrator
  --tier <level>             Facility tier (e.g., LEVEL_4)
  --county <name>            County location
  -h, --help                 Show this help
EOF
}

# Parse arguments
TENANT_NAME=""
TENANT_SLUG=""
FACILITY_NAME=""
FACILITY_CODE=""
ADMIN_EMAIL=""
ADMIN_PASSWORD=""
TIER="LEVEL_4"
COUNTY="UNKNOWN"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --tenant-name) TENANT_NAME="$2"; shift 2 ;;
    --tenant-slug) TENANT_SLUG="$2"; shift 2 ;;
    --facility-name) FACILITY_NAME="$2"; shift 2 ;;
    --facility-code) FACILITY_CODE="$2"; shift 2 ;;
    --admin-email) ADMIN_EMAIL="$2"; shift 2 ;;
    --admin-password) ADMIN_PASSWORD="$2"; shift 2 ;;
    --tier) TIER="$2"; shift 2 ;;
    --county) COUNTY="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown argument: $1" ;;
  esac
done

[[ -n "${TENANT_NAME}" ]] || fail "--tenant-name is required"
[[ -n "${TENANT_SLUG}" ]] || fail "--tenant-slug is required"
[[ -n "${FACILITY_NAME}" ]] || fail "--facility-name is required"
[[ -n "${FACILITY_CODE}" ]] || fail "--facility-code is required"
[[ -n "${ADMIN_EMAIL}" ]] || fail "--admin-email is required"
[[ -n "${ADMIN_PASSWORD}" ]] || fail "--admin-password is required"

[ -f "${ENV_FILE}" ] || fail "Missing ${ENV_FILE}. Run scripts/setup.sh first."

# Load environment
set -a
source "${ENV_FILE}"
set +a

# Helper to execute SQL in production postgres
exec_sql() {
  docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U claimflow -d claimflow -c "$1"
}

log "Onboarding tenant: ${TENANT_NAME}..."

# We call the logic similar to setup.sh but for a specific new tenant
# We escape single quotes for SQL
SQL_TENANT_NAME="${TENANT_NAME//\'/\'\'}"
SQL_TENANT_SLUG="${TENANT_SLUG//\'/\'\'}"
SQL_FACILITY_NAME="${FACILITY_NAME//\'/\'\'}"
SQL_FACILITY_ID="${FACILITY_CODE//\'/\'\'}"
SQL_ADMIN_EMAIL="${ADMIN_EMAIL//\'/\'\'}"
SQL_ADMIN_PASS="${ADMIN_PASSWORD//\'/\'\'}"
SQL_TIER="${TIER//\'/\'\'}"
SQL_COUNTY="${COUNTY//\'/\'\'}"

exec_sql "
WITH new_tenant AS (
  INSERT INTO tenants (name, slug)
  VALUES ('${SQL_TENANT_NAME}', '${SQL_TENANT_SLUG}')
  ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name
  RETURNING id
),
new_facility AS (
  INSERT INTO facilities (tenant_id, name, sha_facility_code, tier_level, county, status)
  SELECT id, '${SQL_FACILITY_NAME}', '${SQL_FACILITY_ID}', '${SQL_TIER}', '${SQL_COUNTY}', 'ACTIVE'
  FROM new_tenant
  ON CONFLICT (tenant_id, sha_facility_code) DO UPDATE SET name = EXCLUDED.name
  RETURNING id, tenant_id
)
INSERT INTO users (tenant_id, facility_id, email, display_name, password_hash, role, must_change_password)
SELECT 
  tenant_id, 
  id, 
  lower('${SQL_ADMIN_EMAIL}'), 
  'Administrator', 
  crypt('${SQL_ADMIN_PASS}', gen_salt('bf', 12)), 
  'admin', 
  true
FROM new_facility
ON CONFLICT (tenant_id, email) DO UPDATE SET password_hash = EXCLUDED.password_hash;
"

# Setup license
exec_sql "
INSERT INTO license_state (facility_id, tier, license_token, expires_at)
SELECT f.id, '${SQL_TIER}', 'trial-' || encode(gen_random_bytes(16), 'hex'), now() + INTERVAL '30 days'
FROM facilities f
JOIN tenants t ON t.id = f.tenant_id
WHERE t.slug = '${SQL_TENANT_SLUG}' AND f.sha_facility_code = '${SQL_FACILITY_ID}'
ON CONFLICT (facility_id) DO NOTHING;
"

log "✅ Onboarding complete for ${TENANT_NAME}."
log "Admin user ${ADMIN_EMAIL} can now log in at your web URL."
