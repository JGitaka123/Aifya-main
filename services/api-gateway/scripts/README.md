# Aifya - Operational Scripts

Standalone scripts for demo seeding, one-time DB setup (non-Docker), and ops.

## One-time database setup (no Docker)

These three steps create the roles/database, the schema, and the security
layer **exactly once**, before you seed.

Run in this order from a PowerShell prompt:

```powershell
# 1) Create roles (aifya_user / aifya_app_role) + the aifya database.
#    Replace YOUR_POSTGRES_PASSWORD with the superuser password you chose
#    when installing PostgreSQL.
$env:PGPASSWORD = "YOUR_POSTGRES_PASSWORD"
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -d postgres `
  -f "C:\Users\User\Downloads\Aifya-main\Aifya-main\services\api-gateway\scripts\db_setup_roles.sql"

# 2) Create every table (migrations run as aifya_user, matching .env)
cd C:\Users\User\Downloads\Aifya-main\Aifya-main\services\api-gateway
$env:DATABASE_URL = "postgresql+asyncpg://aifya_user:aifya_dev_password@localhost:5432/aifya"
.\.venv\Scripts\python.exe -m alembic upgrade head

# 3) Apply the security baseline: least-privilege, PII helpers, RLS,
#    audit trail. Run AFTER step 2 because it touches patients/encounters.
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -d aifya `
  -f "C:\Users\User\Downloads\Aifya-main\Aifya-main\services\api-gateway\scripts\db_security_baseline.sql"
```

Notes:

- `db_setup_roles.sql` sets the `aifya_user` password to `aifya_dev_password`,
  which is what `services/api-gateway/.env` already uses. If your DB was
  created earlier (e.g. by Docker) this also **fixes the
  `password authentication failed for user "aifya_user"` error**.
- `db_security_baseline.sql` is idempotent and safe to re-run. It creates the
  `audit_logs` trail, `encrypt_pii/decrypt_pii` helpers, the
  `set_facility_context()` helper, role-scoped RLS policies with `WITH CHECK`
  on `patients`/`encounters`, and audit triggers on both tables.
- After the security baseline, every DB connection must set
  `app.current_facility_id` before touching facility data - the API already
  does this per request and the seed script does it per session.

## `seed_demo.py` - Comprehensive Demo Seed

Loads everything needed to demo Aifya end-to-end against a clean database.
The script is **idempotent**: re-running it does not create duplicates.

### Run

After the three setup steps above:

```powershell
cd C:\Users\User\Downloads\Aifya-main\Aifya-main\services\api-gateway
$env:DATABASE_URL = "postgresql+asyncpg://aifya_user:aifya_dev_password@localhost:5432/aifya"
.\.venv\Scripts\python.exe scripts\seed_demo.py
```

The demo facility is created at the configured `BETA_FACILITY_ID`
(`00000000-0000-0000-0000-000000000001`) so seeded rows are visible in
public-beta / no-login mode without Keycloak. The script sets
`app.current_facility_id` on its session so Row-Level Security does not
block reads or writes.

To soft-delete all demo data:

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py --reset
```

### What it Creates

| Section                       | Count   | Notes                                                   |
| ----------------------------- | ------- | ------------------------------------------------------- |
| Facility                      | 1       | "Aifya Demo Hospital" (`AIFYA-DEMO`, MFL `99999`)       |
| Departments                   | 8       | OPD, IPD, Pharmacy, Lab, Radiology, MCH, ER, Admin      |
| Staff (HMIS users)            | 10      | Doctors, nurses, pharmacist, lab tech, cashier, HR      |
| Patients                      | 50      | Mix of ages 1mo to 75y, SHA / private / cash, pregnant  |
| Appointments                  | 50      | One per patient over the next 14 days (4 today)         |
| OPD Encounters + Vitals       | 50      | `encounter_type = 'opd'` queue rows + vitals each       |
| Dashboard outpatient visits   | 50      | `encounter_type = 'outpatient'` dated today + 7/day for the prior 13 days for the 14-day trend chart |
| Pharmacy items                | 15      | Common Kenyan hospital drugs with stock + KES pricing   |
| Insurance schemes             | 1       | SHA                                                     |
| Chart of Accounts             | 27      | From `app.services.finance.seed_data`                   |
| Posting rules                 | ~12     | invoice_cash, invoice_insurance, payroll_run, etc.      |
| Accounting periods            | 26      | 12 monthly + 1 fiscal year for current and prior year   |
| Invoices                      | 25      | Mix of cash (60%) and insurance (40%) + GL postings     |
| Payments                      | ~15     | Insurance settlements (full + partial)                  |
| Expense postings              | 8       | Rent, utilities, supplies, etc.                         |
| Statutory rates               | 11+     | PAYE bands, NSSF tiers, SHIF, HL, personal relief       |
| Leave types                   | 7       | Annual, sick, maternity, paternity, etc.                |
| Employees (payroll)           | 12      | Full KRA PIN, NSSF, SHIF, bank, salary structure        |
| Payroll runs                  | 1       | Previous month, approved + GL-posted                    |
| Leave requests                | 5       | Approved / pending / rejected mix                       |
| Fixed assets                  | 4       | Ultrasound, X-ray, ICU monitor, hospital beds           |
| Budget lines                  | 10      | Departmental budgets for current month                  |
| Recurring templates           | 3       | Rent, payroll, insurance premium                        |
| M-Pesa STK Push samples       | 5       | Mix of success, pending, failed                         |

### What the Dashboard Should Show After Seeding

The executive dashboard (`GET /api/v1/reports/dashboard`) is driven by real
rows in the database:

| Dashboard card          | Expected value | Counted from                                  |
| ----------------------- | -------------- | --------------------------------------------- |
| Total Patients          | 50             | `patients` (not soft-deleted)                 |
| Patients today/month    | 50             | `patients.created_at`                         |
| OPD visits today        | 50             | `encounters` type `outpatient`, dated today   |
| OPD visits month        | 50             | same, since month start                       |
| Appointments today      | 4              | `appointments.appointment_date = today`       |
| Revenue today / month   | from seeded payments | `payments.amount_cents`                   |

Other cards (lab, pharmacy, imaging, admissions, ANC) stay at 0 unless extra
demo rows are added for those modules - the seed currently covers patients,
encounters/vitals, appointments, pharmacy stock, finance, and payroll.

### Idempotency

The script uses **deterministic UUIDs** generated from
`uuid5(DEMO_NAMESPACE, label)` for every entity it creates. Re-running
yields identical IDs, so unique-index inserts collide cleanly with
"already exists" check-then-skip logic.

For entities without a natural unique key (invoices, payments, expenses,
payroll runs), the script skips work entirely once any rows are detected
for the demo facility.

### Login Credentials

The script seeds the **database only** - it does **NOT** create users in
Keycloak. After seeding, a Keycloak admin must create matching users in
the `aifya` realm so demo logins work:

| Email                  | Password         | Role                  |
| ---------------------- | ---------------- | --------------------- |
| admin@aifya.co.ke      | DemoAdmin2026!   | Admin / Finance       |
| doctor@aifya.co.ke     | DemoDoctor2026!  | Doctor                |
| nurse@aifya.co.ke      | DemoNurse2026!   | Nurse                 |
| pharmacy@aifya.co.ke   | DemoPharm2026!   | Pharmacist            |
| lab@aifya.co.ke        | DemoLab2026!     | Lab Tech              |
| cashier@aifya.co.ke    | DemoCash2026!    | Cashier / Billing     |
| hr@aifya.co.ke         | DemoHR2026!      | HR Admin              |
| reception@aifya.co.ke  | DemoRec2026!     | Receptionist          |

Each `Staff` row carries a deterministic `keycloak_user_id`. After creating
the Keycloak users, link Keycloak's user IDs to the existing
`Staff.keycloak_user_id` values.

### Engines Exercised (not raw SQL)

The script intentionally uses the production code paths to exercise the real
engines:

- `app.services.finance.posting_engine.post_transaction()` for every invoice
  / payment / expense - balanced double-entry journal, period locks,
  idempotency keys.
- `app.services.payroll.engine.run_monthly_payroll()` for the demo run.
- `app.services.payroll.gl_integration.post_payroll_to_gl()` for the payroll
  - finance bridge.

### Caveats

- The payroll-to-GL bridge references account codes that differ from the
  codes seeded by `seed_facility_finance`; it fails gracefully with a `WARN`
  log - expected for the demo, does not break the seed.
- The seed runs in a single committed DB session at the end - partial
  failures roll back cleanly.
- If `.venv\Scripts\python.exe` ever fails with "No Python at ...Python312",
  recreate the virtualenv once from a normal terminal:
  `uv venv .venv --python 3.12` then `uv pip sync uv.lock`.