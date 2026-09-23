# Claude Cowork Brief — Full black-box QA of the Aifya HMS beta (browser-driven)

Paste everything below into Claude Cowork. It drives the live web app with the
Claude-in-Chrome browser tool, runs ~100+ diverse cases across every module,
hammers boundary/out-of-range inputs, stress-tests the database through the UI,
and produces a single comprehensive gap report. Do **not** stop at the first
bug — log everything and keep going.

---

## 0. Mission

You are a senior QA + clinical-safety + performance tester. Your job is to find
**every gap** in the Aifya Hospital Management System **before real clinicians
use it**. Aifya is an AI-native HMIS for Kenyan hospitals (49 modules; OPD, IPD,
pharmacy, lab, billing, finance, MCH, emergency, theatre, insurance/SHA claims,
HR/payroll, analytics, clinical trials). Be adversarial, be thorough, assume
nothing works until you have proven it in the browser. Capture a screenshot for
every defect.

**Target:** `https://www.aifyamed.com` (public beta — no login required; it runs
against a single synthetic facility/user). Frontend routes are locale-prefixed,
e.g. `https://www.aifyamed.com/en/patients/register`. The REST API is at
`https://api.aifyamed.com/api/v1/...` (you may call it directly with the browser
or fetch to cross-check what the UI shows vs. what the server stored).

**Languages:** English (`/en`) and Swahili (`/sw`). Dark mode and light mode
both ship. Offline-first PWA. Command palette on **Cmd/Ctrl+K**.

---

## 1. Rules of engagement (read first)

1. **This is a shared beta with real-looking data — never delete or overwrite
   anything you did not create.** Only soft-delete/cancel records you made.
2. **Tag every record you create** so it is identifiable and cleanable: prefix
   names/notes with `QA-<timestamp>` (e.g. first name `QA-Test`, last name
   `Case042`). Use obviously fake phone numbers (`07000000NN`) and IDs.
3. **Keep a running evidence log as you go** (don't rely on memory): for each
   case record module, action, input, expected, actual, pass/fail, severity,
   screenshot filename, URL, and the timestamp.
4. Do not attempt real payment processing, real M-Pesa transactions, real SHA
   submissions, or send real SMS/email. If a flow would contact an external
   provider, note it and stop at the confirmation step.
5. If a step is destructive or irreversible and you are unsure, **screenshot the
   current state, note it as "blocked — needs confirmation", and move on.**
6. When something fails, try to **reproduce it once more** and capture the exact
   steps; note whether it is deterministic or intermittent.
7. Watch the browser devtools **Console** and **Network** tabs throughout. Log
   every JS error, every 4xx/5xx response, every request that takes >2 s, and
   any request that hangs. A bare `Failed to fetch` with no user-facing message
   is a **High** defect.

---

## 2. Cross-cutting checks — apply on EVERY screen you visit

For each page you open, quickly verify all of these and log any failure:

- **No raw i18n keys** rendered as text (e.g. `opd.prescriptionStatus.pending`,
  any string matching `^[a-z0-9]+(\.[a-zA-Z0-9]+){1,}$`). Check **both** `/en`
  and `/sw`. Swahili pages must not fall back to raw keys or blank labels.
- **Dark mode**: toggle it; every element must remain legible (no black-on-black,
  no white-on-white, no invisible borders/icons).
- **Responsive**: check desktop (1440px) and mobile (~390px) widths. The body
  must never scroll horizontally; tables/wide content should scroll inside their
  own container.
- **Loading & empty states**: is there a spinner/skeleton, and a sensible empty
  state (not a crash or endless spinner) when there's no data?
- **Error handling**: network errors must show a friendly message or an offline
  badge — never a bare stack trace, blank screen, or silent no-op.
- **Offline behaviour**: with devtools set to Offline, core workflows
  (registration, vitals, prescriptions) must still work and queue for sync; an
  offline indicator should appear; going back online should sync.
- **Command palette (Cmd/Ctrl+K)**: opens, searches patients + actions + modules,
  and navigation works.
- **3-click rule**: common clinical actions should be reachable within ~3 clicks.
- **Buttons never silently no-op**: every submit either succeeds visibly, shows a
  validation error, or shows a server error. A click that "does nothing" is a bug.

---

## 3. Module-by-module functional cases (the bulk — aim for ≥100 total)

Cover **all** of these modules. Within each, do the happy path first, then the
negatives/edge cases. Distribute ~100+ cases across them (suggested counts in
brackets). Record each as a numbered case in your log.

### A. Patient registration & records `/en/patients` [12]
- Register a valid patient end-to-end; confirm it appears in the list and detail.
- **Duplicate detection (D7):** register a second patient with the same National
  ID → expect a "possible duplicate" prompt; repeat with same phone, and with
  same name+DOB. Confirm "use existing / register anyway" both work.
- **DOB validation (D8):** try a future DOB, a DOB >120 years ago, today's date
  (newborn — must pass), an empty DOB, and a malformed date. Expect clear
  per-field errors; valid ones save.
- Required-field enforcement: submit with each required field blank in turn.
- Very long names (300+ chars), unicode/emoji names, names with quotes/`<script>`.
- **Bulk import (D11):** download the CSV template; import a file with ~10 rows
  including 2 deliberately invalid rows → expect valid rows created and per-row
  errors listed. Then attempt a **300-row** import (see §6 stress).
- Search patients by name, MRN, phone; test partial and no-match queries.
- Edit a patient; verify the change persists after reload.

### B. OPD / consultation `/en/opd` [14]
- Start an OPD encounter for a patient; walk the guided flow.
- **Vitals:** enter normal vitals; then out-of-range (see §5) — BP 400/300,
  temp 60°C, weight 0 / 999 kg, negative values, non-numeric.
- **Diagnosis / ICD-10 (D5):** type `B54` → expect malaria to autocomplete and
  auto-fill the description; select it. Try a gibberish code (`ZZZ999`) → must
  not save as a valid diagnosis. Confirm the stored code+description is canonical.
- **Prescription (D1 path + Tier 4):** prescribe a normal drug; then:
  - prescribe a drug the patient is **allergic** to → expect a visible,
    acknowledgeable alert / block.
  - prescribe an **interacting pair** (e.g. warfarin then aspirin, or warfarin +
    fluconazole) → expect a visible interaction alert; confirm you can acknowledge
    and that the acknowledgement/override reason is recorded.
  - **Paediatric dose (Tier 4):** for a child with a recorded weight (e.g. 15 kg),
    prescribe an adult dose of a weight-dosed drug (e.g. Paracetamol 1000 mg) →
    expect a dose-range warning; an in-range dose (e.g. 150 mg) → no warning.
- **Lab order (D2/D6):** order a Malaria RDT from the **catalog type-ahead** →
  confirm code/name/price auto-fill; then confirm a **lab line appears on the
  patient's invoice** with the correct price and the invoice total/balance update.
- Status badges (prescription/billing) must show human labels (D9), not raw keys.

### C. Pharmacy `/en/pharmacy` [10]
- **Dispense (D1):** dispense a prescription (e.g. Coartem qty 6); confirm it
  leaves the dispensing queue, shows `dispensed`, and the drug **stock decrements
  by exactly the dispensed quantity** (e.g. 150 → 144).
- **No negative stock:** try to dispense **more than available** → must be
  rejected with a clear message; stock never goes negative.
- Double-submit / rapid double-click the dispense button → must be idempotent
  (no double decrement, no duplicate payment).
- Offline dispense → must queue and NOT report success falsely; sync when online.
- Inventory list, stock alerts (low/expired), add a drug, pharmacy bulk import.
- KEML formulary flag visible; search the formulary.

### D. Laboratory `/en/laboratory` [10]
- Worklist loads; open an order detail.
- **Result entry (D4):** enter a result value and leave Interpretation as "—" →
  must save (or show a clear required error) — it must **not** silently no-op.
  Submit with an empty result value → clear per-field error.
- Enter a **critical** result (e.g. potassium 7.2) → confirm it is flagged
  critical and an escalation/notification path fires (not just a badge).
- Verify/approve a result; confirm QA state transitions (pending → preliminary →
  final) hold and cannot be skipped.
- Lab catalog type-ahead search; uncatalogued free-text fallback flagged.

### E. Billing & payments `/en/billing` [8]
- Open an invoice with a balance; **Record Payment (D10):** the amount must be
  **pre-filled with the outstanding balance** (a real, editable value — not a
  greyed placeholder) and submittable without retyping.
- Pay an amount `> balance` (overpayment) → rejected or handled per policy.
- Pay `0` / negative / non-numeric → rejected with a clear message.
- Finalize an invoice; waive an invoice; partial payment then a second payment.
- Confirm invoice total = sum of line items at all times.

### F. Finance / General Ledger `/en/finance` [8]
- **GL/AR reconciliation (D3):** Finance dashboard AR and Chart-of-Accounts
  balances must reflect real activity — **not all zeros while invoices exist**.
  Record: does `Billing outstanding == AR-Patient + AR-Insurance balance`?
- Every posted invoice/payment should produce **balanced** journal entries
  (debits == credits). Spot-check a few accounts (Cash, Bank, AR, Inventory).
- Check money is displayed to 2 decimals with no floating-point artefacts (e.g.
  never `1234.5600000001`). Verify KES formatting and totals add up to the cent.
- Accounting periods: open/closed period behaviour.

### G. IPD / admissions `/en/ipd` [4] · MCH `/en/mch` [4] · Emergency `/en/emergency` [4]
- IPD: admit a patient, assign a bed/ward, record a ward round, discharge.
- MCH: antenatal profile, visit schedule, danger-sign flags.
- Emergency: SATS triage — enter vitals that should map to each triage colour;
  confirm the category and priority are computed correctly.

### H. Theatre `/en/theatre` [3]
- Confirm at least one operating theatre exists (seeded). Schedule a surgical
  case against it; check for double-booking prevention.

### I. Insurance / SHA claims `/en/insurance` [5]
- Open the claims list (this previously errored on a missing column — confirm it
  now loads). Create a claim from an invoice; run the ClaimFlow/SHA pre-submission
  validation; review the validation decision/result. Do **not** actually submit
  to SHA.

### J. Inventory (non-pharmacy) `/en/inventory` [3] · Dental `/en/dental` [2] · Radiology/Imaging `/en/radiology` [2]
- Inventory: stock in/out, no-negative-stock, bulk import.
- Dental: charting, procedure + billing linkage.
- Radiology: order a study, enter/verify a report.

### K. HR `/en/hr` [3] · Payroll `/en/payroll` [3]
- HR: add staff, roles, departments.
- Payroll: run a payroll cycle for a test employee; check PAYE/NSSF/SHIF
  computations and that bank details are protected (not shown in plain text where
  they shouldn't be).

### L. Analytics / Reports `/en/analytics` `/en/reports` [4]
- Dashboards load with real numbers; "Top Diagnoses" groups by canonical ICD-10
  code (from D5). Date-range filters work. Export where available.

### M. Appointments `/en/appointments` [2] · Referrals `/en/referrals` [2] ·
### Clinical Trials `/en/trials` [3] · Communications `/en/communications` [2] ·
### Settings `/en/settings` [2] · Knowledge/Help `/en/knowledge` `/en/user-guide` [2]
- Appointments: book/reschedule/cancel; double-booking check.
- Referrals: create a referral, generate the referral note/letter.
- Trials: enrol a test patient, confirm the trial alert banner appears on that
  patient's encounters; AI screening; SAE/adverse-event reporting path.
- Communications/help/settings: smoke-test that they load and basic actions work.

---

## 4. Regression re-verification of the 23-Jul fixes (must all still hold)

Explicitly re-test each and mark PASS/FAIL in a dedicated table:

- **D1** pharmacy dispense decrements stock, idempotent, no silent failure.
- **D2** lab order adds a priced line to the encounter invoice.
- **D3** GL/AR reconciles; no all-zero ledger with live invoices.
- **D4** lab result entry never silently no-ops on unset Interpretation.
- **D5** ICD-10 lookup validates; invalid codes can't be saved as valid.
- **D6** lab test catalog type-ahead fills code/name/price.
- **D7** duplicate-patient prompt before creating a second record.
- **D8** future/implausible DOB rejected; today's date accepted.
- **D9** no raw i18n keys in status badges (en + sw).
- **D10** payment amount pre-filled with outstanding balance.
- **D11** bulk patient import with per-row validation.
- **Tier 4** drug interaction + allergy alert, paediatric dose warning, critical
  lab escalation.

---

## 5. Boundary & adversarial input matrix (out-of-range) — apply to numeric/date/text fields everywhere

For every input you can reach, try the relevant hostile values and log how the
app responds (accepted silently = bug; clear rejection = pass):

- **Money:** `0`, negative, `0.001` (sub-cent), `999999999999`, `1e9`, `abc`,
  `1,234.56` with separators, empty. Confirm integer-cents handling (no float
  drift), and that amounts respect `>= 0.01` and `<= balance` where applicable.
- **Quantities / stock / doses:** `0`, negative, huge (`2^31+`), decimals where
  integers are expected, non-numeric.
- **Dates:** future where past is required (DOB, onset), year `0001`/`9999`,
  Feb 30, `2023-13-45`, empty, and timezone edge (records should be Africa/Nairobi).
- **Ages/weights:** neonate (0–1 kg), 120+ years, negative age, 500 kg.
- **Text:** empty, whitespace-only, 10 000-char blob, unicode/emoji, RTL text,
  SQL-ish (`'; DROP TABLE patients;--`), XSS (`<img src=x onerror=alert(1)>`),
  and leading/trailing spaces. Confirm no injection executes and no 500.
- **Phone/National ID/SHA numbers:** wrong length, letters, `+254`/`0` formats.
- **Enums/dropdowns:** submit an out-of-list value via the API directly and
  confirm the server rejects it (don't trust client-side only).
- **IDs in the URL:** open a detail page with a random/nonexistent UUID and a
  malformed ID → expect a clean 404/not-found, not a crash.

---

## 6. Database & performance / stress testing (through the UI + API)

Goal: surface slow queries, N+1s, pagination breakage, lock contention, missing
indexes, and data-integrity failures under volume. Record timings and any error.

1. **Volume via bulk import (D11):** import **300 patients** in one go. Measure
   the time, confirm the count is exactly right, no duplicates, no dropped rows,
   and the patient list/search stays responsive afterwards. Then import a second
   batch to reach ~500–1000 and repeat the checks.
2. **Large-list pagination & search:** page deep into the now-large patient list;
   test first/last/random pages, page-size limits, and search with a broad term
   that returns many rows. Watch for slow responses (>2 s) or timeouts.
3. **Concurrency / race conditions:** open the same patient/invoice in **two
   browser tabs** and act simultaneously — e.g. record a payment in both, dispense
   the same prescription in both, edit the same record in both. Confirm no double
   decrement, no double payment, no lost update; idempotency keys hold.
4. **Rapid repeated submits:** double/triple-click submit on registration,
   dispense, payment, prescription — confirm exactly one record is created.
5. **Sustained interaction:** for ~10–15 minutes, loop through create→read→update
   across modules; watch memory growth in the tab, response-time drift, and any
   creeping 5xx rate.
6. **API-level load (if you can run scripts):** hit read-heavy endpoints
   (`GET /api/v1/patients`, `/laboratory/worklist`, `/finance/...`,
   `/reports/...`) with, say, 20–50 concurrent requests for a couple of minutes
   and record p50/p95 latency, error rate, and any endpoint that degrades sharply.
   If a load tool (k6/Locust/ab) is available to you, use it and attach results;
   otherwise approximate with concurrent fetches from the browser console.
   **Do not** load-test write endpoints that would create unbounded junk data —
   keep writes bounded and tagged.
7. **Financial invariant under load:** after all the billing/payment activity
   above, re-check §3.F — `billing outstanding == AR balance` and journal entries
   still balance. A drift under concurrency is a **Critical** finding.
8. **Data integrity after stress:** spot-check that invoice totals still equal
   line sums, stock totals equal sum of batch quantities, and no orphaned rows
   surfaced (e.g. a payment without an invoice).

> Note the tester cannot open a psql shell against production. "Database stress"
> here means driving realistic and abusive load **through the app/API** and
> watching for the DB-level symptoms above (latency, timeouts, deadlocks,
> integrity drift, incorrect aggregates). If direct DB access is later provided,
> add: table row counts, slow-query log review, missing-index checks (EXPLAIN on
> the heaviest queries), and connection-pool exhaustion behaviour.

---

## 7. Security & authorization spot-checks (even on the beta)

- **Tenant isolation:** confirm you only ever see the beta facility's data; try
  requesting another facility's IDs via the API and expect rejection/empty.
- **PII gating:** confirm patient PII isn't exposed on endpoints/roles that
  shouldn't see it.
- **Injection/XSS:** the payloads from §5 must never execute or 500.
- **Idempotency:** repeated POST with the same `X-Idempotency-Key` must not
  duplicate.
- **Direct object access:** guessing/altering IDs in URLs or API calls must not
  leak or mutate records you shouldn't touch.

---

## 8. Severity rubric (use these consistently)

- **Critical** — patient-safety risk, data loss/corruption, financial mis-posting,
  security/tenant leak, or a core workflow completely broken.
- **High** — a primary workflow fails or silently no-ops; money/stock/clinical
  numbers wrong; unhandled 5xx with no user feedback.
- **Medium** — a secondary flow broken, missing validation, confusing/blocking UX,
  wrong-but-non-dangerous value, missing i18n on a non-critical string.
- **Low** — cosmetic, minor copy, dark-mode contrast, small responsive glitch.

---

## 9. Required deliverable — one comprehensive report

Produce a single Markdown report (and, if you can, an HTML version) titled
**"Aifya HMS — Pre-launch QA Gap Report (<date>)"** containing:

1. **Executive summary** — go / no-go recommendation, total cases run, pass/fail
   counts, and a severity breakdown (Critical/High/Medium/Low counts).
2. **Coverage matrix** — every module × (happy path, negative/boundary, i18n,
   dark mode, offline, performance) with ✅/⚠️/❌/— so gaps in *coverage* are
   visible, not just failures.
3. **Findings table**, sorted by severity, each with: ID, module, title, severity,
   steps to reproduce, expected vs actual, evidence (screenshot filename +
   console/network error + request/response), URL, deterministic vs intermittent.
4. **Regression status** — the D1–D11 + Tier-4 table from §4 with PASS/FAIL.
5. **Financial-integrity findings** — the invariant checks (invoice=lines,
   AR=outstanding, balanced journals, no float drift).
6. **Performance & DB stress results** — volume test timings, pagination/search
   latency, concurrency/race outcomes, p50/p95 under load, and any degradation.
7. **Clinical-safety findings** — interaction/allergy alerts, paediatric dosing,
   critical-lab escalation, triage correctness.
8. **Top 10 things to fix before human users**, ranked.
9. **Test-data cleanup list** — the tagged records you created, so they can be
   removed.

Keep going until you have run **at least 100 cases** across the modules above and
completed §5, §6, and §7. Do not summarize prematurely — the value is in breadth
and in the reproduction detail. Log every gap, however small.

---

# Appendix A — Direct database stress & integrity testing (psql access)

> **Audience:** the person with SSH access to the Contabo host and `psql` to the
> production Postgres — **not** the browser agent (which cannot reach the DB
> shell). Run this alongside the §6 UI/API load so DB-level symptoms and app-level
> symptoms line up on the same timeline. **Do everything read-only first; the only
> writes are the clearly-marked load-generation and the tagged test data, and a
> final cleanup.** Take a backup before any write load.

Column/table names below follow the models in `docs/database-schema.md` — **adjust
any name that differs in the live schema** (verify with `\d <table>`). The DB is
PostgreSQL 16 + TimescaleDB; container `aifya-postgres`, database `aifya`.

## A.0 Connect & baseline

```bash
# On the Contabo host:
docker compose exec -T -u postgres postgres psql -d aifya
```

```sql
-- Enable timing + query stats for this session
\timing on
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;   -- if not already loaded
SELECT version();
SELECT * FROM pg_stat_statements_reset();            -- clear before the load run

-- Row-count baseline for the heavy tables (snapshot before + after the load run)
SELECT relname, n_live_tup
FROM pg_stat_user_tables
ORDER BY n_live_tup DESC
LIMIT 40;

-- Table + index sizes (find fat tables / oversized or unused indexes)
SELECT relname,
       pg_size_pretty(pg_total_relation_size(relid))  AS total,
       pg_size_pretty(pg_relation_size(relid))         AS heap,
       pg_size_pretty(pg_indexes_size(relid))          AS indexes
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 30;
```

## A.1 Migration / schema-drift reconciliation (do this FIRST)

This app has already been bitten by **baseline-stamp drift** — Alembic's version
was ahead of the physical schema, so `pharmacy_batches` and several
`insurance_claims` columns were missing. Prove the live schema matches the models.

```sql
-- What Alembic thinks the schema is:
SELECT version_num FROM alembic_version;   -- must equal the repo HEAD revision
```

```bash
# What HEAD actually is, from the code:
docker compose exec -T api-gateway python -m alembic heads
# And what the DB reports it's at:
docker compose exec -T api-gateway python -m alembic current
```

```sql
-- Spot-check that columns/tables added by recent migrations physically exist
-- (these were the drift victims — extend the list from docs/database-schema.md):
SELECT to_regclass('public.pharmacy_batches')        AS pharmacy_batches,
       to_regclass('public.lab_test_catalog')         AS lab_test_catalog,
       to_regclass('public.operating_theatres')       AS operating_theatres;

SELECT column_name
FROM information_schema.columns
WHERE table_name = 'insurance_claims'
  AND column_name IN ('validation_decision','validation_result','validated_at');
-- expect 3 rows

SELECT conname FROM pg_constraint
WHERE conname IN ('ck_pharmacy_items_qty_nonneg','ck_pharmacy_batches_qty_nonneg');
-- expect 2 rows (the no-negative-stock guards)
```

A better, exhaustive check: dump the live schema and diff it against a schema
built cleanly from the models on a scratch Postgres — any table/column/constraint
present in one but not the other is drift.

## A.2 Data-integrity invariants (must hold at all times; re-run after load)

Each query should return **zero rows** (or the stated equality). A non-empty
result is a **Critical** finding.

```sql
-- 1) Every invoice total equals the sum of its line items
SELECT i.id, i.total_cents, COALESCE(SUM(li.total_cents),0) AS line_sum
FROM invoices i
LEFT JOIN invoice_items li ON li.invoice_id = i.id AND li.is_deleted = false
WHERE i.is_deleted = false
GROUP BY i.id, i.total_cents
HAVING i.total_cents <> COALESCE(SUM(li.total_cents),0);

-- 2) Billing outstanding == AR account balance (the D3 invariant)
--    (a) sum of unpaid invoice balances:
SELECT COALESCE(SUM(balance_cents),0) AS billing_outstanding
FROM invoices WHERE is_deleted = false AND status <> 'cancelled';
--    (b) AR balance from posted double-entry lines (adjust account codes/table):
SELECT a.code, COALESCE(SUM(te.debit_cents - te.credit_cents),0) AS balance
FROM transaction_entries te JOIN accounts a ON a.id = te.account_id
WHERE a.code IN ('1100','1150')          -- AR-Patient / AR-Insurance
GROUP BY a.code;
-- (a) must equal the sum of the (b) AR balances.

-- 3) Every posted transaction is balanced (debits == credits)
SELECT transaction_id, SUM(debit_cents) AS dr, SUM(credit_cents) AS cr
FROM transaction_entries
GROUP BY transaction_id
HAVING SUM(debit_cents) <> SUM(credit_cents);

-- 4) Pharmacy on-hand equals the sum of its non-deleted batch remainders
SELECT pi.id, pi.current_quantity, COALESCE(SUM(pb.quantity_remaining),0) AS batch_sum
FROM pharmacy_items pi
LEFT JOIN pharmacy_batches pb ON pb.pharmacy_item_id = pi.id AND pb.is_deleted = false
WHERE pi.is_deleted = false
GROUP BY pi.id, pi.current_quantity
HAVING pi.current_quantity <> COALESCE(SUM(pb.quantity_remaining),0);

-- 5) No negative stock anywhere (the guard should make this impossible)
SELECT id FROM pharmacy_items  WHERE current_quantity  < 0;
SELECT id FROM pharmacy_batches WHERE quantity_remaining < 0;

-- 6) No orphans: payments without a live invoice; line items without an invoice
SELECT p.id FROM payments p
LEFT JOIN invoices i ON i.id = p.invoice_id WHERE i.id IS NULL;
SELECT li.id FROM invoice_items li
LEFT JOIN invoices i ON i.id = li.invoice_id WHERE i.id IS NULL;

-- 7) Event-sourcing integrity: no duplicate (stream_type, stream_id, version)
SELECT stream_type, stream_id, version, COUNT(*)
FROM events GROUP BY stream_type, stream_id, version HAVING COUNT(*) > 1;

-- 8) Multi-tenancy: every tenant-scoped row has a facility_id
SELECT 'patients' AS t, COUNT(*) FROM patients WHERE facility_id IS NULL
UNION ALL SELECT 'invoices', COUNT(*) FROM invoices WHERE facility_id IS NULL
UNION ALL SELECT 'prescriptions', COUNT(*) FROM prescriptions WHERE facility_id IS NULL;
```

## A.3 Find the slow / heavy queries

```sql
-- Top queries by total time and by mean time (run AFTER the load in §6/A.5)
SELECT round(total_exec_time::numeric,1) AS total_ms,
       calls,
       round(mean_exec_time::numeric,2)  AS mean_ms,
       round((100*total_exec_time/SUM(total_exec_time) OVER ())::numeric,1) AS pct,
       left(query,120) AS query
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 25;
```

Then `EXPLAIN (ANALYZE, BUFFERS)` the app's heaviest real queries and look for
**Seq Scan on large tables, sort spills to disk, and nested-loop blowups**:

```sql
-- Patient search (the list/search endpoint) — after loading 500–1000 patients:
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM patients
WHERE facility_id = '<beta-facility-uuid>'
  AND is_deleted = false
  AND (first_name ILIKE '%wan%' OR last_name ILIKE '%wan%' OR mrn ILIKE '%wan%')
ORDER BY created_at DESC LIMIT 20 OFFSET 0;

-- Lab worklist aggregation, finance rollups, and "Top Diagnoses" GROUP BY —
-- pull the exact SQL from pg_stat_statements and EXPLAIN ANALYZE each.
```

Flag any frequent query doing a sequential scan where an index on
`(facility_id, …)` would help; `ILIKE '%x%'` leading-wildcard searches can't use a
btree — note whether a trigram (`pg_trgm`) index is warranted.

## A.4 Locks, deadlocks & long transactions (watch during the §6 concurrency tests)

```sql
-- Live blocking chains while the two-tab / concurrent-write tests run:
SELECT blocked.pid AS blocked_pid, blocked.query AS blocked_query,
       blocking.pid AS blocking_pid, blocking.query AS blocking_query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking
  ON blocking.pid = ANY (pg_blocking_pids(blocked.pid));

-- Long-running / idle-in-transaction sessions (connection leaks):
SELECT pid, state, wait_event_type, wait_event,
       now() - xact_start AS xact_age, left(query,80) AS query
FROM pg_stat_activity
WHERE state <> 'idle' AND xact_start IS NOT NULL
ORDER BY xact_start;

-- Deadlocks/conflicts since reset:
SELECT datname, deadlocks, conflicts, temp_files, temp_bytes
FROM pg_stat_database WHERE datname = 'aifya';
```

## A.5 Generate real DB load (bounded, backup first)

```sql
-- Read load: replay the app's heaviest SELECT concurrently.
-- Put ONE representative statement (with a literal facility_id) in bench.sql, then:
```
```bash
# ~20 concurrent clients, 60 s, read-only:
docker compose exec -T -u postgres postgres \
  pgbench -n -c 20 -T 60 -f /tmp/bench.sql aifya
# Record TPS and latency (avg + stddev). Watch A.4 in another session.
```

For a realistic write mix, prefer driving the **API** (§6) so the app's
transactions/idempotency/RLS are exercised — raw `INSERT`s bypass business logic.
A small async load script (asyncpg or the app's client) hitting
`POST /patients`, `POST /encounters`, dispense and payment endpoints with bounded,
tagged data gives the truest picture; capture p50/p95 and correlate with A.3/A.4.

**Connection-pool exhaustion:** check `max_connections` and the app pool size, then
open connections up to the limit and confirm the app **degrades gracefully**
(queues / clear error) rather than 500-storming:

```sql
SHOW max_connections;
SELECT count(*), state FROM pg_stat_activity GROUP BY state;
```

## A.6 Bloat, autovacuum & TimescaleDB health

```sql
-- Dead tuples / vacuum lag on hot tables (events, vitals, invoices, transactions):
SELECT relname, n_live_tup, n_dead_tup,
       round(100*n_dead_tup/GREATEST(n_live_tup,1),1) AS dead_pct,
       last_autovacuum, last_autoanalyze
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC LIMIT 20;

-- TimescaleDB hypertables + chunk counts (vitals/events time-series, if used):
SELECT hypertable_name, num_chunks
FROM timescaledb_information.hypertables;
```

The deploy logs showed the TimescaleDB extension was **out of date** (installed
2.27.1 vs 2.28.3) — note it as an ops item; plan the extension upgrade in a
maintenance window.

## A.7 Backup / restore & PITR sanity (do NOT skip before load testing)

```bash
# Verify a restorable logical backup exists and actually restores to a scratch DB:
docker compose exec -T -u postgres postgres pg_dump -Fc aifya > /tmp/aifya_$(date +%F).dump
# Restore into a throwaway DB and run the A.2 integrity checks against it.
```
Confirm WAL archiving / PITR is configured (or flag its absence as a High ops gap),
and record the RPO/RTO the current setup actually delivers.

## A.8 Report additions (fold into §9)

Add to the QA report a **Database section** with: the schema-drift result (A.1),
every A.2 invariant with pass/fail and offending row counts, the top-25 slow
queries with EXPLAIN verdicts and index recommendations (A.3), lock/deadlock and
idle-in-transaction observations under concurrency (A.4), pgbench/API-load TPS +
p50/p95 and the connection-pool behaviour (A.5), bloat/vacuum + TimescaleDB notes
(A.6), and the backup/restore/PITR status (A.7). Finish with a prioritized list of
**indexes to add, queries to fix, and ops items** (extension upgrade, backups).

## A.9 Cleanup

Delete only the tagged test data you created (`QA-…`), drop any scratch restore
DB, and `SELECT pg_stat_statements_reset();`. Re-run the A.2 invariants once more
to confirm the database is left consistent.
