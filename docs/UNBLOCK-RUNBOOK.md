# Aifya - how to clear the blocked items

Each blocked item has exactly one thing standing in the way: a console, a
connection string, a browser, or a person. None of them are waiting on further
development.

## At a glance

| Item | Who can clear it | What they need | Effort |
|---|---|---|---|
| Keycloak availability | whoever runs Docker / the server | Docker or server access | 10 minutes |
| `facility_id` mapper | Keycloak administrator | admin console login | 5 minutes |
| Browser testing | any tester | a browser + a running app | half a day |
| GitHub / Vercel / server checks | repo owner + server admin | admin rights | 1 hour |
| Pharmacist review | pharmacist or clinical officer | the review pack | a few hours |
| Production-data verification | anyone with the DB URL | one command (script provided) | 5 minutes |
| New regression tests | CI, or a working Python | a pull request | 5 minutes |

---

## 1. Keycloak availability

**Blocked by:** no provider running. Verified again today - `localhost:8080`
returns "connection refused".

**Steps**

1. Bring up the service (locally):
   ```
   docker compose up -d postgres keycloak
   ```
   Wait about a minute; Keycloak is slow to start the first time.
2. Confirm the realm is published. This URL must return JSON, not an error:
   ```
   http://localhost:8080/realms/aifya/.well-known/openid-configuration
   ```
3. Confirm signing keys are published too:
   ```
   http://localhost:8080/realms/aifya/protocol/openid-connect/certs
   ```
4. In production the same must be true at your `KEYCLOAK_URL` (for example
   `https://auth.aifyamed.com`). The web container reaches it internally at
   `http://keycloak:8080`; the browser reaches it at the public URL, so both must
   work.
5. **Add Keycloak to the backup routine before you rely on it.** It stores every
   user id. If it is lost and re-imported, the provider issues *new* user ids,
   and every staff-to-provider link has to be repaired by hand before anyone can
   sign in again.

**Done when:** both URLs above return content, and Keycloak is in the backup
routine.

---

## 2. Keycloak `facility_id` mapper

**Blocked by:** needs the Keycloak admin console.

The mapper is what puts a user's facility into their token. Without it the API
cannot tell which hospital the caller belongs to, and every request is refused
after a successful login.

**Steps**

1. Sign in to the Keycloak admin console.
2. Realm **aifya** -> **Client scopes** -> **aifya-scope** -> **Mappers** ->
   **facility_id**.
3. Confirm every setting:
   - Mapper type: **User Attribute**
   - User attribute: `facility_id`
   - Token claim name: `facility_id`
   - Claim JSON type: **String**
   - Add to ID token: **On**
   - Add to access token: **On**
   - Add to userinfo: **On**
4. Then check the users actually carry it. **Users** -> open a user ->
   **Attributes** -> there must be a `facility_id` whose value is the UUID of a
   real facility in the database.
5. Repeat for the audience mapper `aifya-api-audience` in the same scope: it must
   include the client audience `aifya-api`, on the access token only. The API
   checks this audience on every request.

**Done when:** a pilot user can sign in and their access token contains a
non-empty `facility_id`.

**Why this might already look wrong:** this repository's realm files declare both
mappers correctly. Keycloak only applies a realm file when the realm is created
for the first time, so a realm that already existed before the file changed will
not have them. Fix it in the console, or delete the realm and re-import.

---

## 3. Browser testing

**Blocked by:** needs a person with a browser and a running application.

**Steps**

1. Start the stack (`docker compose up -d`), or run the API and web app directly.
2. Work through the checklist in section 8 of
   `docs/ACCESS-CONTROL-STATUS-REPORT.md`. For each line record: module, steps,
   expected, actual, and a screenshot if it fails.
3. Prioritise, if time is short:
   - OPD consultation end to end
   - Draft invoice: payment and waiver must both be refused
   - Two users calling different patients from the OPD queue at the same time
   - Two users registering patients at the same time
4. Only start this once item 1 is done, otherwise sign-in cannot be tested.

**Done when:** every checklist line is marked pass or fail, with evidence for the
failures.

---

## 4. GitHub, Vercel and server checks

**Blocked by:** needs admin rights on three systems.

### GitHub

1. Settings -> Branches -> protect `main`:
   - Require a pull request before merging.
   - Require status checks: select the **CI / Web** and **CI / API Gateway** jobs.
   - Require a reviewer for the `production` environment.
2. Two open PRs are waiting on a decision: the manual deploy gate, and the large
   review branch. The large one should not merge without a green CI run and a
   separate technical review.

### Vercel

1. Set the environment variables in the table in `docs/DEPLOYMENT.md` section
   5.1, and add `AUTH_PROVIDER` alongside them.
2. Confirm `COOKIE_DOMAIN=.aifyamed.com` is present. Without it the session
   cookie is scoped to `www` and is not sent to `api`, and every API call fails.

### Server

Collect this evidence and keep it with the report:

```
dig +short aifyamed.com
ss -ltnp | grep -E ':(80|443) '
ss -ltnp | grep -E ':(8000|8080|8030) '
certbot certificates
```

The third command is the one that matters for hardening: `8000`, `8080` and
`8030` must **not** be bound to a public interface. Before changing that, confirm
nothing external connects to them directly.

**Done when:** the Production Healthcheck workflow is green and the public
domains answer normally.

---

## 5. Pharmacist review

**Blocked by:** needs a pharmacist or clinical officer. This is a professional
judgement, not a software decision, and it should not be signed off by
engineering.

Four things need a decision:

| # | Item | Where it lives |
|---|---|---|
| 1 | Allergy terminology variants - sulfa / sulpha / sulphur, PCN, opiate-related | `services/api-gateway/app/services/pharmacy_seed.py` |
| 2 | The contraceptive / rifampicin interaction list | pharmacy interaction rules |
| 3 | Adult vital-sign thresholds being applied where paediatric values are needed | `app/schemas/vital.py`, `app/services/vitals_service.py` |
| 4 | ANC risk escalation not weighing diastolic blood pressure and proteinuria | `app/services/mch_service.py`, `app/routers/mch.py` |

**How to make this cheap:** ask for one line per rule - *correct*, or *change to
X*. The reviewer should not have to read code; the rules should be handed to them
as a plain list.

**Done when:** each of the four items has a signed decision on file.

---

## 6. Production-data verification

**Blocked by:** needs the production database connection string. Nothing else.

A read-only script is provided, so this is one command:

```
psql "$DATABASE_URL" -f services/api-gateway/scripts/production_readiness_check.sql
```

Strip `+asyncpg` from the connection string first, or `psql` will silently prompt
for a password:

```
postgresql://user:password@host:5432/dbname
```

It writes nothing. It answers, in one pass:

- the migration the database is actually on
- whether `payments.received_by`, `employees.id_number` and `employees.kra_pin`
  can hold real data
- whether row level security is **enabled and forced** on the patient-data tables
- roles, permissions and assignments in the access matrix
- per-facility counts of patients, encounters, invoices, staff and departments
- whether the clinical data looks genuine or demo-seeded
- whether a dental workflow is actually configured
- which staff would be refused at identity-provider sign-in

**Done when:** the output is saved into the report as the production evidence.

**Already known from the local copy** (run today, so the script is proven to
work): migration `029_role_permissions`; 32 roles, 46 permissions, 491
assignments; row level security enabled and forced on all seven relevant tables;
MKU has 4 departments and 3 doctors, Kenyatta has 0 departments, and there is a
Dental Clinic at MKU but **no dentist anywhere**.

---

## 7. The new regression tests

**Blocked by:** the local Python environment. This is the one item that is purely
a tooling problem.

The tests are written and are in the repository at
`services/api-gateway/tests/test_keycloak_identity_binding.py`. They could not be
run on this machine because the project's virtual environment points at a Python
3.12 that is no longer installed:

```
No Python at '"C:\Users\User\AppData\Local\Programs\Python\Python312\python.exe'
```

Three ways to run them, easiest first.

### Option A - let CI run them (recommended, no setup)

Open a pull request. The pipeline already installs the test dependencies and runs
the whole suite:

1. Push the branch and open a pull request.
2. Wait for the **CI / API Gateway** check.
3. Open it and read the **Tests (full suite)** step.

Done when that step is green.

### Option B - repair the local environment

Reinstall Python 3.12 from python.org (the venv is pinned to it), then:

```
cd services/api-gateway
uv venv --python 3.12
uv pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest tests/test_keycloak_identity_binding.py -q
```

Or, without `uv`:

```
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m pytest -q
```

### Option C - run them in the container

The image ships runtime dependencies only, so the test extra has to be added:

```
docker compose run --rm api-gateway sh -c "uv pip install --system -e '.[dev]' && python -m pytest tests/test_keycloak_identity_binding.py -q"
```

**Done when:** nine tests report as passed.

**Also worth knowing:** the same pipeline runs `ruff check app` and `mypy app`, so
a pull request will catch any style or typing problem in the fix as well as the
tests.
