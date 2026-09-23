#!/usr/bin/env bash
set -euo pipefail

# ClaimFlow Reset and Seed Real Documents Script
# This script clears all existing data and seeds the system with real documents for testing.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker/docker-compose.yml"
ENV_FILE="${REPO_ROOT}/docker/.env"
SAMPLE_PDF="${REPO_ROOT}/reference-data/SHA_claim_form_Jordan_Hospital.pdf"

log() {
  printf "[reset-seed] %s\n" "$*"
}

fail() {
  printf "[reset-seed] ERROR: %s\n" "$*" >&2
  exit 1
}

compose_exec_psql() {
  local sql="$1"
  docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U claimflow -d claimflow -c "${sql}"
}

[ -f "${SAMPLE_PDF}" ] || fail "Sample PDF not found at ${SAMPLE_PDF}"
[ -f "${ENV_FILE}" ] || fail "Docker env file not found at ${ENV_FILE}"

log "Clearing all transactional data..."
compose_exec_psql "
  UPDATE claims SET last_audit_session_id = NULL;
  DELETE FROM rule_results;
  DELETE FROM audit_sessions;
  DELETE FROM extracted_fields;
  DELETE FROM ocr_text;
  DELETE FROM document_pages;
  DELETE FROM documents;
  DELETE FROM claim_lines;
  DELETE FROM claims;
"

log "Creating 5 new claims for comprehensive testing..."
compose_exec_psql "
  WITH context AS (
    SELECT
      t.id AS tenant_id,
      f.id AS facility_id,
      u.id AS user_id
    FROM tenants t
    JOIN facilities f ON f.tenant_id = t.id
    JOIN users u ON u.tenant_id = t.id
    WHERE u.role = 'super_admin'
    LIMIT 1
  )
  INSERT INTO claims (
    tenant_id,
    facility_id,
    patient_sha_id,
    patient_name_enc,
    hmis_ref,
    claim_type,
    visit_type,
    admission_date,
    status,
    created_by
  )
  SELECT
    c.tenant_id,
    c.facility_id,
    format('TEST-SHA-%04s', gs),
    format('Real Data Test %s', gs),
    format('RD-TEST-%04s', gs),
    (ARRAY['OUTPATIENT','INPATIENT','MATERNITY','SURGICAL','EMERGENCY'])[((gs - 1) % 5) + 1]::claim_type,
    CASE WHEN gs % 2 = 0 THEN 'IP'::visit_type ELSE 'OP'::visit_type END,
    CURRENT_DATE - (gs || ' days')::interval,
    'DOCUMENTS_UPLOADED'::claim_status,
    c.user_id
  FROM context c
  CROSS JOIN generate_series(1, 5) AS gs;
"

log "Seeding real documents and injecting files into storage volume..."
# List new claims
claim_ids=$(docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T postgres \
  psql -U claimflow -d claimflow -tAc "SELECT id FROM claims WHERE hmis_ref LIKE 'RD-TEST-%' ORDER BY id;")

for claim_id in ${claim_ids}; do
  storage_path="uploads/${claim_id}/claim.pdf"
  log "Setting up document for claim ${claim_id}..."
  
  # Create directory in container
  docker exec claimflow-ml-1 mkdir -p "/data/uploads/${claim_id}"
  # Copy file to container
  docker cp "${SAMPLE_PDF}" "claimflow-ml-1:/data/${storage_path}"
  # Fix permissions
  docker exec -u root claimflow-ml-1 chown -R 1000:1000 "/data/uploads/${claim_id}"

  # Insert document record
  compose_exec_psql "
    INSERT INTO documents (
      claim_id,
      doc_type,
      processing_route,
      mime_type,
      original_filename,
      page_count,
      file_size_bytes,
      storage_path,
      sha256,
      processing_status,
      uploaded_by
    )
    SELECT
      '${claim_id}'::uuid,
      'SHA_CLAIM_FORM_OP'::doc_type,
      'FULL_OCR_EXTRACT'::doc_processing_route,
      'application/pdf',
      'SHA_claim_form_Jordan_Hospital.pdf',
      3,
      $(stat -c%s "${SAMPLE_PDF}"),
      '${storage_path}',
      '$(sha256sum "${SAMPLE_PDF}" | awk '{print $1}')',
      'PENDING'::doc_processing_status,
      id FROM users WHERE role = 'super_admin' LIMIT 1;
  "
done

log "Reset and seeding complete! 5 new claims are ready for audit in the UI."
