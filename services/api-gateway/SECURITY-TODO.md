# Security TODOs — Finance / HR-Payroll / Integrations

This file tracks security work that MUST be completed before the new
finance, HR/payroll, and integration modules go to production. The audit
that produced this list landed in 2026-05; revisit before any GA cut.

## Encryption at rest (HIGH)

- DONE (2026-09): `Employee.bank_account` is not plaintext - it is encrypted
  at the application layer and every row in the live database carries the
  `enc:v1:` envelope, as do `kra_pin`, `nssf_number` and `shif_number`.
  What remains is key custody: move `FIELD_ENCRYPTION_KEY` out of
  settings/.env into a KMS so rotation and access are auditable.
  - Option A: switch to `sqlalchemy_utils.EncryptedType(Text, secret_key=…,
    engine=AesGcmEngine, padding="oneandzeroes")` and source the key from
    Vault (NEVER from settings/env in cleartext).
  - Option B: encrypt at the application service layer with a dedicated
    KMS-backed envelope (AWS KMS / GCP KMS / Vault Transit). Store
    ciphertext + key version in two columns.
  - Whichever is chosen, the `payslip` PDF generator must read the
    plaintext only inside a single function and never log it. The PDF
    template currently shows `*** ENCRYPTED ***` for the account — keep
    that until decryption is wired.
- KRA PIN, NSSF #, SHIF # are PII/statutory IDs. Today they ride in
  `EmployeeResponse` (detail). The new `EmployeeListItem` schema hides
  them in list responses. Restrict the detail endpoint to
  `hr_admin/finance_admin/admin/facility_admin` plus the employee
  themselves (already enforced for the payslip endpoints).

## M-Pesa callback hardening (HIGH)

- Configure `MPESA_CALLBACK_IP_ALLOWLIST` in production to the published
  Safaricom production IP ranges (see `_DEFAULT_SAFARICOM_IPS` in
  `app/routers/mpesa.py`). Without it, only the edge LB / firewall is
  enforcing source IP.
- Daraja does not sign callbacks. Treat the callback as untrusted:
  - Always reconcile against the persisted `mpesa_stk_requests` row.
  - Idempotency on `mpesa_transaction_id` is now enforced for C2B.
  - Never auto-issue a refund based on callback alone — manual review.

## Help-bot rate limiting (MEDIUM)

- The router note in `app/routers/help_bot.py` flags this. Add a
  Redis-backed rate limiter (e.g. `slowapi`) with a 30 req/min/user
  bucket. The clinical/PHI guardrails block obvious misuse but a noisy
  user could still rack up vLLM costs.

## Patient identifiers in logs (MEDIUM)

- `app/routers/mpesa.py` previously logged the full C2B body (which
  includes MSISDN, a Kenya DPA-protected PII identifier). Logging is now
  trimmed to non-PII fields. Audit other modules for similar leaks before
  release.

## Audit trail completeness (MEDIUM)

The Finance audit log (`finance_audit_logs`) covers:
- post_transaction / post_compound_transaction
- reverse_transaction
- close_period / lock_period
- year_end_close
- manual_match_bank_statement (added)

Still TODO: emit audit-log rows for opening-balance approval, budget
approval, fixed-asset disposal, statutory-rate edits, and recurring-
template create / approve. Consider a central decorator on the service
layer so we can't forget.

Clinical audit is now covered at the database layer. Migration 026 adds an
append-only `audit_logs` trail with triggers on patients, encounters,
appointments, admissions, diagnoses, prescriptions, clinical_notes,
vital_signs, lab_orders, lab_results, patient_insurance, referrals,
emergency_visits and encounter_assignments. Each row records the acting
API user (published as `app.current_user_*`), the originating client
address, the changed columns and the full before/after row.

## Multi-tenant guards (CRITICAL — PARTIALLY ADDRESSED)

The 2026-05 audit closed several `facility_id` leaks across:
- `app/services/finance/periods.py` (year-end close join)
- `app/services/finance/reports.py` (every report query)
- `app/services/finance/reconciliation.py` (GL/DIT/OC)
- `app/services/finance/depreciation.py` (period lookup)
- `app/services/payroll/leave.py` (defence-in-depth on submit)
- `app/services/referral/note_generator.py` (patient-scoped lookups)

DONE (2026-09): the database enforces this itself now.
- Every facility-scoped table has Row-Level Security ENABLED and FORCED
  (104 tables) with a `facility_id =
  current_setting('app.current_facility_id')` policy carrying both USING
  and WITH CHECK. See migrations 008_enable_tenant_rls and
  018_tenant_rls_backfill.
- The API sets `app.current_facility_id` once per request from the JWT
  claim before any query runs, via `app/middleware/facility_context.py`.
- Verified on the live database: with no context set `patients` returns 0
  rows, and a facility sees only its own rows. This protects any future
  query that accidentally drops the WHERE clause.

## Payroll GL account-code drift (FIXED)

The payroll → GL integration previously hardcoded account codes (`5001`,
`1002`, `2034`, …) that did not match the seed-data chart of accounts
(`5000`, `1020`, `2200`, …). Posting any approved payroll run would have
failed with `FinanceError("Account codes not found")`. The codes in
`app/services/payroll/gl_integration.py` are now aligned with
`app/services/finance/seed_data.py:DEFAULT_ACCOUNTS`.

## Production deployment checklist

- [ ] Vault is the only source of M-Pesa, SHA, Africa's Talking secrets.
- [ ] `MPESA_CALLBACK_IP_ALLOWLIST` is set in the deployment manifest.
- [x] Postgres RLS policies created and tested (migrations 008/018, 104 tables).
- [x] `Employee.bank_account` encrypted at rest (`enc:v1:`); move the key to
      KMS custody before GA.
- [ ] `slowapi` rate-limit middleware enabled (default 60 rpm/user).
- [ ] OpenAPI / Swagger docs are off (`debug=False`).
- [ ] Disabled the SHA mock fallback (require real `SHA_API_URL`).
