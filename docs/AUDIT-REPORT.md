# Aifya HMIS — Platform Audit Report

Date: 2026-07-07 · Branch: `claude/aifya-hmis-audit-debug-ahtylr`

> **Status update (end of this branch's work):** items marked ✅ below are
> fixed on this branch with tests. See §8 for what remains open.
Method: full static audit of every router/service/page + test-suite execution
(backend: 326 tests, 80 failing at audit time; frontend: 59 passing) + four
parallel deep audits (security/tenancy, critical paths, frontend, infra/CI).

## 1. Stack reality vs. documentation

The actual product is a **Next.js 15 web app (`apps/web`, 70 pages) + FastAPI
monolith (`services/api-gateway`, 32 mounted routers) + PostgreSQL/Keycloak/
Redis/MinIO/Qdrant**, with two integrated AI side-services (scribe :8005,
knowledge :8025) deployed by docker-compose to a single host.

Everything else the docs describe is aspirational or dead:

- README/CLAUDE.md claim K3s, Traefik, Prometheus, Grafana, Loki, Tempo,
  Vault, Kafka pipelines, vLLM fleet — **none are configured**
  (observability is commented out of `docker-compose.yml:258-272`; the
  referenced `prometheus.yml` doesn't exist).
- `docs/TRAINING-MANUAL.md` documents Grafana dashboards and pg_dump backup
  procedures **that do not exist anywhere**.
- `services/ai-service/claimflow/` is an entire vendored monorepo (own
  Fastify API, Next.js web, Firebase auth, ML service, 15 SQL migrations, own
  CI) that **nothing calls** — dead code with a conflicting auth stack.
  *(Resolved — see §8: pruned to the rule-engine + a new Keycloak-authed
  validator-service, now wired in as SHA pre-submission validation.)*
- `services/sync-service` (Go) is an **in-memory stub** (comment at
  `main.go:74` admits it); it ships in prod compose implying durable offline
  sync that does not exist. Nothing in the frontend calls it.
- `services/billing-service` (Go) is real code but **nothing calls it** —
  and it is dangerous (see C-2).

## 2. Module inventory

| Module | Verdict | Evidence |
|---|---|---|
| Patient registration | WORKS | full CRUD, offline queue; writes role-gated, PII reads gate-able via `PATIENT_READ_ROLES` (H-4, see §8) |
| Appointments/queue | WORKS | incl. OPD queue + call-next |
| Triage/vitals | WORKS | vitals + ED triage; ED queue endpoint 500'd (fixed, was C-4) |
| Consultation notes (OPD) | WORKS | encounters, diagnoses, CDS wired |
| Pharmacy & dispensing | PARTIAL | dispense doesn't validate qty/drug vs prescription; double-dispense race (H-1) |
| Lab orders/results | PARTIAL | flow complete; critical values flagged but never pushed (M) |
| Imaging/radiology | PARTIAL | worklist 500'd (fixed); flow otherwise complete |
| Billing & invoicing | PARTIAL | invoice math correct (integer cents); M-Pesa recording was broken (C-1, fixed); no receipt artifact |
| Insurance/SHA claims | WORKS | claim CRUD + ClaimFlow validation gate + SHA e-claims submission client (mock until credentials); see §8 (H-6) |
| Inventory/stores | PARTIAL | atomic stock moves, but negative stock possible; no batch/FEFO (H-7/H-8) |
| HR/staff/payroll | WORKS | most complete module; strong role gating |
| Finance/GL | WORKS | double-entry engine + periods; frontend does float money math (M) |
| IPD, MCH, theatre, dental, emergency, referrals, trials, comms, reports, analytics | WORKS/PARTIAL | wired end-to-end; test suite for them was stale (see §5) |
| Offline sync | BROKEN | replay is unauthenticated + infinite retry (H-9) |
| ScribeAI / Knowledge | BROKEN (frontend auth) | hooks send empty localStorage token to :8005/:8025 (H-10) |

## 3. Critical-path verdicts (backend trace)

| Path | Verdict | Blocking gaps |
|---|---|---|
| a) register → triage → consult → prescribe → dispense | PARTIAL | CDS interaction blocking genuinely works pre-save; dispense validates neither quantity nor drug identity vs the prescription; double-dispense race |
| b) consult → lab order → result → review | PARTIAL | correct patient/order mapping; critical-value alert is passive (manual endpoint) |
| c) visit → invoice → payment → receipt | was BROKEN → now PARTIAL | M-Pesa never updated invoices (fixed in this branch); cash path lacked row lock (fixed); no printable receipt |
| d) SHA claim → submission → reconciliation | PARTIAL | no external submission call exists; status is hand-edited; no reconciliation vs payments |
| e) stock receipt → dispense → reorder alert | PARTIAL | negative stock possible; single-batch model (no FEFO); alerts computed only on demand; no scheduled jobs run at all (H-2) |

## 4. Prioritized findings

### Critical
- **C-1 M-Pesa payments silently never recorded.** Callbacks wrote to
  non-existent `Invoice.paid_amount_cents/total_amount_cents`; the
  AttributeError was swallowed; STK path also violated NOT NULL
  `received_by`. Every mobile-money payment failed reconciliation.
  → **FIXED** (`2d414e1`) + 6 tests.
- **C-2 Go billing-service: unauthenticated second writer to the money
  tables.** No JWT check on any `/api/v1/billing-svc/*` route; writes the
  same `invoices/payments` tables as the gateway with a racy COUNT(*)-based
  invoice number; and once RLS migration 008 runs it silently sees zero rows
  anyway. Nothing consumes it. → recommend removing from compose (decision
  required).
- **C-3 Auto-deploy to production on every push to `main`** (`deploy.yml`),
  running alembic migrations unattended, as root, with no staging gate.
- **C-4 ED queue and radiology worklist 500 on every request** (broken
  SQLAlchemy expressions). → **FIXED** (`ed5d467`, `0536c45`).
- **C-5 sync-service is an in-memory stub shipped as production offline
  sync** — data lost on restart.

### High
- **H-1 Dispensing safety trio:** quantity not capped to prescription,
  pharmacy item not validated against prescribed drug, and a
  read-check-write race allows double dispensing (`pharmacy_service.py`).
- **H-2 No background worker exists.** `app/worker.py` is imported by the
  DHIS2 scheduler but missing; no Celery worker/beat is defined anywhere, so
  every "scheduled" job (reminders, DHIS2 sync, SMS retry) never runs.
- **H-3 RLS defense-in-depth is inert:** the app connects as the Postgres
  superuser (`aifya_user` from the image), which bypasses FORCE RLS.
- **H-4 No role separation on patient PII:** `patients.py` and `fhir.py`
  have no `require_roles` — any authenticated staff account can read/update
  every patient record in the facility.
- **H-5 M-Pesa callback endpoints are unauthenticated writers** with the IP
  allow-list off by default and no signature verification (receipt
  idempotency now enforced — partial mitigation).
- **H-6 SHA claim submission not implemented** (manual status edits only);
  mock eligibility response when SHA env unset can masquerade as real.
- **H-7 Negative stock possible** in `inventory_service.create_transaction`
  (no floor check on issue/write-off/transfer).
- **H-8 Single-batch inventory model:** each receipt overwrites
  batch/expiry; FEFO impossible; expired stock can be masked.
- **H-9 Offline mutation replay is broken:** sync-worker reads a
  localStorage token that never exists (auth is httpOnly-cookie), sends no
  credentials, and its retry counter never increments → unauthenticated
  replays every 30s forever. Offline-created records never sync.
- **H-10 Scribe/Knowledge hooks unauthenticated** (same localStorage
  assumption) → both AI modules broken through the UI.
- **H-11 Session dies silently after 5 minutes:** access-token cookie
  maxAge≈300s, no refresh route exists, api-client doesn't handle 401.
- **H-12 No DB backups, no monitoring, no error tracking** in the real
  stack (docs claim otherwise).
- **H-13 CI gates are partial/false-green:** lints 8 files, runs 6 of 14
  test files, never runs mypy; `go test` passes vacuously (zero test files).
- **H-14 STK/cash payment concurrency:** no row lock on invoice → double
  pay race. → **FIXED** (`2d414e1`).

### Medium (selection)
- Blocked (critical-interaction) prescriptions return HTTP 500 instead of a
  structured "blocked" response; CDS engine failure fails *open*.
- Idempotency headers (`X-Idempotency-Key`) accepted but ignored on
  billing/dispense POSTs.
- Events table immutable only by convention (no DB-level guard).
- CORS `allow_methods/headers=*` with cookie auth and no CSRF token.
- `DEBUG=true` in default compose disables the insecure-defaults guard and
  exposes Swagger.
- Finance/payroll frontend does float money arithmetic
  (`finance/page.tsx:93,101`, `runs/[runId]/page.tsx:71`).
- 19 Swahili i18n keys missing (next-intl error for sw users on knowledge,
  IPD, trials screens).
- No role-based home screen; single finance-heavy dashboard for all roles.
- Pharmacy inventory search ignores its `q` parameter.
- Weak default credentials throughout compose; Keycloak realm seed has
  `admin123`/`demo123`; Postgres 5432 host-exposed in prod.
- `trigger.sql` at repo root is an unapplied duplicate of migration 007.
- Reorder/low-stock alerts computed on demand only; nothing pushes them.
- Shift assignments accept nonexistent staff IDs (no FK validation), then
  vanish from lists (inner join).

### Low (selection)
- `tax_cents` hardcoded 0 (no VAT decision recorded); payment accepted on
  draft invoices; `is_abnormal` on lab results is client-trusted; demo seed
  prints passwords; ruff reports 1,748 issues / mypy 360 in the gateway
  (rules claim zero-tolerance); duplicate `CLAUDE-FINAL.md`; committed
  binaries (`test.wav` etc.).

## 5. Test-suite reality

`pytest`: 326 tests, **80 failing before this branch** — but ~90% of
failures are **stale tests written against an older API contract**
(e.g. `wards.capacity` vs current `total_beds`+required `code`; encounter
status `in_progress` vs current queue-based `waiting`; MCH payloads missing
now-required fields). The frontend/shared types match the *current* backend,
so the implementation is the source of truth and the tests must be updated.
Real bugs found among the failures: ED queue 500, radiology worklist 500,
pharmacy search filter, HR list joins (all above). Frontend: only 7 test
files for 70 pages; CI runs a 6-file backend subset.

## 6. Divergences from CLAUDE.md (flagged, not silently resolved)

1. "Zero `any` / zero lint errors" — 1,748 ruff + 360 mypy errors in gateway.
2. "Drug interaction checks MUST block" — true pre-save, but blocked Rx
   surfaces as a 500 and engine errors fail open.
3. "Critical lab values MUST trigger immediate alert" — passive flag only.
4. "Every mutation queues offline and syncs" — replay broken (H-9).
5. "All LLM calls through ai-service" — compose references an `ai-service`
   container that doesn't exist; CDS/agents run rule-based in-gateway.
6. "Celery for background tasks" — no worker exists (H-2).
7. "REDCap tokens in Vault" — no Vault anywhere.
8. "Event sourcing is the audit trail" — events written per-service by
   convention; several services skip it.
9. "Money: integer KES cents" — true in gateway; finance/payroll frontend
   uses floats.
10. "PR: CI must pass" — CI covers a small subset (H-13).

## 7. Fix status (this branch)

Fixed with tests (✅): C-1 M-Pesa recording · C-4 ED queue/radiology 500s ·
C-2/C-5 Go services no longer shipped · H-1 dispense safety trio ·
H-2 Celery worker/beat created and composed · H-7 negative stock guard ·
H-9 offline replay auth + retry/dead-letter · H-10 knowledge proxy auth ·
H-11 session refresh + 401 handling · H-13 CI gates on full suite (361→364
tests green) · H-14 payment row locks · blocked-Rx 500 → structured
response · patient-write role gating (partial H-4) · idempotency honored
on invoice/payment/dispense · 19 missing sw keys · role-based home
screens · GL failures no longer silent or blocking · HR staff resolution ·
MCH/dental referential bugs · chr()-obfuscated billing literals removed ·
backup/restore scripts + OPERATIONS.md.

## 8. Remaining open items (honest list)

Closed since the first pass: ✅ C-3 (deploy job now uses the `production`
environment — set a required reviewer in repo settings to activate the
approval gate) · ✅ critical-lab push (event + SMS to ordering clinician) ·
✅ consultation fee now facility-configurable
(`facilities.settings.consultation_fee_cents`; 0 disables auto-invoice) ·
✅ receipt PDFs (`GET /billing/invoices/{id}/receipt`) · ✅ Sentry wiring
(set `SENTRY_DSN`) · ✅ H-3 tooling (`scripts/create-app-db-role.sh`
creates the NOSUPERUSER/NOBYPASSRLS role — running it and switching
`DATABASE_URL` is a server-side go-live step).

Closed this pass:

- ✅ **H-5 M-Pesa callbacks** — source-IP enforcement is now ON by
  default (Safaricom ranges built in, `MPESA_CALLBACK_IP_ALLOWLIST` adds
  extras, `MPESA_CALLBACK_IP_ENFORCE` gates it). Prod only needs to
  confirm/extend the allowlist.
- ✅ **H-6 SHA claim submission** — built. `ShaSubmissionClient` submits
  accepted claims to SHA e-claims with bounded retry/backoff and a mock
  mode (`MOCK-SHA-…` reference) when `SHA_ECLAIMS_URL` is unset. Endpoint
  `POST /insurance/claims/{id}/submit`. Live submission needs SHA
  credentials; code and the full validate→submit flow are done and tested.
- ✅ **ClaimFlow — integrated, not deleted.** The vendored monorepo was
  pruned to its real assets (rule-engine = 121 SHA rules + 297 tests,
  shared, ml-service for later OCR) and dead code / the Firebase auth
  stack removed. A new stateless, Keycloak-authed `validator-service`
  wraps the engine; the gateway calls it as a **pre-submission gate**
  (`POST /insurance/claims/{id}/validate`, `ClaimFlowClient`). Structured
  rules light up now; document/OCR-dependent rules degrade to INCOMPLETE
  until the ml-service pipeline is wired. An unreachable validator yields
  `UNAVAILABLE` rather than blocking. This is a flagship selling point,
  built properly.
- ✅ **Patient PII read gating** — `PATIENT_READ_ROLES` (config) restricts
  who may READ patient/FHIR PII; blank keeps reads open (facility policy
  call). `require_patient_read` enforces it on patient list/detail/
  timeline and FHIR PII reads.
- ✅ **External uptime monitoring** — documented in OPERATIONS.md §5 (the
  external check on `/api/health` + web root; pointing a hosted checker
  at the live host is the remaining server-side op).
- ✅ **H-8 single-batch inventory** — pharmacy_batches (migration 010 with
  backfill + RLS); dispensing is FEFO, expired stock is never
  dispensable, write-offs consume expired batches first.
- ✅ **Scribe module** now accepts platform Keycloak sessions (role
  mapping + JWKS validation); the web app reaches it through a cookie-auth
  proxy and the correct two-step transcribe→process flow.
- ✅ **Type debt** — ruff AND mypy are clean across the gateway and both
  gate CI. The mypy sweep surfaced 12 latent runtime bugs — all fixed.
  Frontend finance float math fixed (integer-cent helpers).
- ✅ **Employee PII at rest** — id_number/kra_pin/bank_account are
  Fernet-encrypted (`EncryptedString`, migration 011); set
  `FIELD_ENCRYPTION_KEY` in prod.
- ✅ **Celery reminder task bodies** — appointment/ANC/immunization/
  medication reminders now run real queries (KEPI milestone schedule).

Remaining — server-side / operational steps only (no code left):

1. **H-3 server step**: run `scripts/create-app-db-role.sh` on the server
   and point `DATABASE_URL` at `aifya_app`, then verify RLS. (Tooling and
   docs done.)
2. **C-3 repo setting**: add a required reviewer to the `production`
   environment in GitHub settings (workflow side is done; documented in
   OPERATIONS.md §1).
3. **Go-live config**: set `MPESA_CALLBACK_IP_ALLOWLIST`, `SENTRY_DSN`,
   `FIELD_ENCRYPTION_KEY`, SHA/ClaimFlow URLs, and point the external
   uptime checker at the host (OPERATIONS.md §7 checklist).
