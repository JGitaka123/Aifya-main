# Aifya HMIS - Access Control and Clinician Workflow

## Implementation Status Report

| | |
|---|---|
| **Prepared for** | Hospital Management / Project Sponsor |
| **Prepared by** | _[your name]_ |
| **Date** | 25 September 2026 |
| **Subject** | Role-based access control and clinician queue: what is built, what is verified, what must happen before go-live |
| **Status** | Development complete and verified. **Not yet switched on.** Two blockers remain. |

---

## 1. Purpose

This report covers the piece of Aifya that answers two questions:

1. **Who is this member of staff?** (sign-in)
2. **What are they allowed to see and do once they are in?** (access control)

It also covers the clinician queue, because access control is what makes the queue correct: a doctor must see only the patients routed to their own department, and only authorised people may open a clinical record.

The business scenario this work exists to support is the one raised by the clinical team:

> Reception registers a patient with a dental problem, routes them to Dental, and the dental clinician finds that patient waiting in their own queue - and nobody else's.

---

## 2. Executive summary

- **The access-control model is built and complete.** 32 staff roles and 46 permissions are defined, seeded into the database, and verified to match the application code exactly. There is no drift between them.
- **Hospital-identity-provider sign-in (Keycloak) is now implemented end to end in the web application.** It was previously only half-present: the back end could validate Keycloak tokens, but the browser-side sign-in flow had been removed, so it could never actually be used. That flow now exists, builds cleanly, and passes 11 logic checks.
- **The clinician queue is department-scoped and working**: waiting / in consultation / completed, filtered to the clinician's own department.
- **Production is reported to be running in open (BETA) access mode**, which bypasses sign-in altogether. The new sign-in path is implemented but switched off. This working copy is set the other way (built-in passwords active), so the two environments do not currently behave the same - see blockers 1 to 3.
- **Two blockers must be cleared before go-live.** One is infrastructure (the identity provider is not running). The other is a real defect in how the API links an identity-provider user to a staff record; switching on without fixing it would break doctor assignment and department-scoped queues.
- **One larger gap remains, and it needs a management decision.** The permission matrix is enforced on only 9 of 353 API endpoints. Editing the role matrix today changes the menus and the clinical/OPD workflow, but it does not yet gate billing, laboratory, pharmacy or HR. This is the main outstanding body of work.

---

## 3. What has been delivered

### 3.1 Access control (authorisation)

- A single, editable source of truth: **32 roles, 46 permissions, and 491 role-permission assignments**, seeded by a script that can be re-run safely. The 491 is the number of assignments actually present; it is not 32 x 46 (that would be 1,472 possible combinations), and the two figures should not be presented as the same thing.
- The same 46 permissions are defined identically in three places - the database, the API, and the web application - and were verified by direct comparison. **Zero mismatches.**
- Two extension layers are in place for per-facility and per-individual adjustments. Neither is in use yet (0 rows), so behaviour today is the shipped baseline.

### 3.2 Hospital identity-provider sign-in (authentication)

Staff can now be signed in through the hospital's identity provider instead of an Aifya-held password, with:

- Redirect to the provider, with proof that the response genuinely came back from our own request (anti-tampering).
- Secure back-channel exchange of the one-time code, so the password is never handled by Aifya.
- Session tokens stored in server-only cookies that browser code cannot read.
- Automatic token renewal, and full sign-out that also ends the session at the identity provider.
- Clear, non-technical error handling - a cancelled or failed sign-in returns to the sign-in page with a plain message, never a half-open session.
- The provider's user number is translated into the staff record it belongs to, so the clinical record, the department queue, per-person permissions and the audit trail all name the right person. A provider account with no active staff record behind it is refused rather than half-accepted.

### 3.3 Clinician queue and routing

- Encounters carry a clear status: **waiting -> in consultation -> completed**.
- The queue is filtered by department, so a clinician sees the patients routed to their unit and not another department's workload.
- Test records without a department assigned fall back to the unclaimed list, so a misconfigured staff record shows an explanatory state rather than silently hiding patients.

### 3.4 Defects fixed along the way

- **The API could not start at all.** The permissions table had been created without a primary key, which crashed the application on import. Fixed.
- **The audit trail recorded a blank "who did this".** The acting user was being overwritten as requests passed through. Fixed.
- **The Settings menu was visible to all 32 roles.** It now requires the `settings.manage` permission, which 4 administrative roles hold.

---

## 4. What has been verified

Every line below was checked directly on the current code and database, not assumed.

| Check | Result |
|---|---|
| API type checking | **0 errors** |
| Web application linting | **0 errors** (1 pre-existing cosmetic warning) |
| Web application production build | **0 errors**; all routes compiled, including both new sign-in routes |
| Sign-in flow logic tests | **11 of 11 pass** |
| Roles / permissions in the database | **32 roles, 46 permissions, 491 rows** |
| Permission drift: code vs database | **0 differences** |
| Identity provider reachable | **No - connection refused** (see blocker 1) |
| Staff-to-provider identity lookup, run against the live database | **Finds the linked staff record** |
| Same lookup without the tenant published first | **Returns 0 rows** - confirms the tenant must be set before the read |
| Same lookup for an unknown provider user | **Returns nothing**, so an unlinked account is refused |
| Database columns: `payments.received_by` | **UUID, nullable** - allows the M-Pesa workflow |
| Database columns: `employees.id_number`, `employees.kra_pin` | **Both 255 characters, nullable** - ample capacity |
| Row-level security on `patients`, `encounters`, `invoices`, `lab_test_catalog` | **Enabled and forced on all four** |

The 11 sign-in checks cover: the cryptographic proof that a response belongs to our request, randomness and uniqueness of the security values, the parameter set sent to the provider, the sign-out address, rejection of malicious redirect targets (`https://evil...`, `//evil...`, `javascript:`), and the exact security flags on the session cookies.

### 4.1 Work executed in this pass

Three items in this report were completed and are ready for review:

1. **The identity link defect (blocker 3) is fixed**, with regression tests added alongside it.
2. **The arithmetic was corrected.** An earlier draft showed "32 roles x 46 permissions = 491", which is wrong: 32 x 46 is 1,472 possible combinations, while 491 is the number of assignments actually present. The two figures are no longer presented as the same thing.
3. **The database readiness checks were run** - column capacities and row-level security. Results are in the table above.

Two things could not be executed here, and still need the access listed against them: the identity provider is not running (blocker 1), and the automated test suite could not be run locally because the Python environment in this working copy is incomplete. The new tests therefore still need to pass in the pipeline before the fix is treated as confirmed.

---

## 5. What must happen before go-live

### Blocker 1 - The hospital identity provider is not running

Verified just now: the address returns "connection refused". Sign-in through the provider cannot work until it is hosted and started, and until it is included in the hospital's backup and monitoring arrangements.

**Owner: IT / infrastructure. No code change required.**

### Blocker 2 - Production runs in open (BETA) access mode

Production is reported to run with `BETA_PUBLIC_ACCESS=true`, which bypasses sign-in altogether: there is no authentication in front of the application there, and every user is treated as the same configured account. That is not the same as built-in password mode - it is no authentication at all - and it means none of the sign-in work above can take effect until the flag is turned off.

This working copy is set the other way (`BETA_PUBLIC_ACCESS=false`, built-in passwords active), so the two environments do not currently behave the same. That difference should be confirmed before anything is switched.

Turning the flag off is a management decision, and it must not happen before blockers 1 and 3 are cleared and a rollback is available. With the flag off and neither sign-in path working, nobody can get in.

**Owner: management decision, then engineering.**

### Blocker 3 - Identity link defect (FIXED in code; needs a live check)

**This was the most important technical finding in this report. It has now been fixed.**

The API assumed the identity provider's user number was the same as the internal staff record number. In the database they are two different numbers, deliberately linked by a separate column (`staff.keycloak_user_id`), and nothing in the sign-in path performed that link.

Confirmed on live data: a doctor at MKU has staff record `daabe75d-...` but identity-provider record `b9b19054-...`.

Had it been switched on as-is:

- A doctor's queue would **not** have scoped to their department, because their staff profile would not have been found.
- Starting a consultation would have recorded a doctor number that does not exist against the patient's encounter.
- Audit entries would have named the wrong user.

**What was changed:** the sign-in path now translates the provider's user number into the staff record it belongs to, and refuses the sign-in when there is no active staff record behind it. It refuses rather than carrying on with the provider's number, because a wrong user number fails silently - the record saves, the queue is simply empty, and the audit trail names nobody.

**Evidence:** the lookup was run against the live database. It finds the linked doctor; it returns nothing when the tenant is not published first, which is why the fix publishes it; and it returns nothing for an unknown provider user, so an unlinked account is refused rather than half-accepted. Regression tests were added alongside the fix.

**Remaining:** this has not been exercised against a running identity provider, because none is running (blocker 1). It also means every staff record must carry the correct provider user number - if the provider is re-imported and issues new user numbers, those links must be repaired before anyone can sign in.

### Blocker 4 - Every identity-provider user needs a facility

Each user must carry the identity of the facility they belong to. Without it, sign-in succeeds and then every screen fails. This is resolved by correct provisioning, not code.

### Blocker 5 - Provider configuration is applied only on first start

Configuration changes made recently will **not** take effect if the provider already holds an existing setup. Either the provider's data volume is cleared and re-imported, or the same settings are applied by hand.

---

## 6. Data readiness

Current state of the live database:

| Facility | Departments | Staff records |
|---|---|---|
| MKU Hospital | 4 (Outpatient, Dental Clinic, Laboratory, Pharmacy) | 4 |
| Kenyatta Hospital | **0** | 1 |
| Aifya Platform | 0 | 1 |
| Aifya Platform (identity-provider tenant) | 0 | 1 |

Roles actually held by people: **doctor x3, facility administrator x2, platform administrator x2.**

**Two gaps directly block the dental scenario:**

1. **Kenyatta Hospital has no departments.** A receptionist there has no destination to route a patient to.
2. **Nobody holds the dental role.** A dental patient would be routed into a queue with no clinician in it. (The dental module itself exists; the role was simply never assigned.)

Both are data setup tasks, not development.

---

## 7. The remaining gap: enforcement coverage

**353 API endpoints exist. The permission matrix is enforced on 9 of them.**

| Enforcement style | Endpoints |
|---|---|
| Permission matrix (editable without a code release) | **9** (all in the clinical / OPD workflow) |
| Hard-coded role lists | **130** |
| Patient-record read gate | **18** |

**What this means in practice, in plain terms:**

- Editing the role matrix **does** change which menus appear, and **does** control the clinical/OPD workflow.
- Editing it **does not yet** control billing, laboratory, pharmacy, inventory, HR, referrals, imaging and the rest.
- A role granted "view billing" would see the Billing menu and then be refused when they open it. A role denied it would lose the menu, but the billing function would still respond if called directly.

**Why it matters:** this is a confidentiality gap *inside* a facility - for example, a pharmacy account could reach billing functions it was never intended to. All endpoints still require a valid, authenticated session for the correct facility, so there is no cross-hospital exposure. It is a gap in role separation within a hospital, not a multi-tenant leak.

**This is the largest outstanding body of work and needs to be scoped and approved.**

---

## 8. Decisions needed from management

| # | Decision | Why it is needed |
|---|---|---|
| 1 | Approve hosting, backing up and monitoring the hospital identity provider | Blocker 1 |
| 2 | ~~Approve the identity-link fix~~ | **Executed.** Blocker 3 is fixed in code; the remaining ask is to have it pass in the pipeline and then verified against a live provider |
| 3 | Approve a work package to extend permission enforcement across the remaining API endpoints | Closes the role-separation gap; needs prioritisation by module |
| 4 | Approve building a role-administration screen | The Settings page links to one that does not exist. Today, changing a role means changing the database directly |
| 5 | Confirm who may change roles, and how changes are reviewed | Governance; this is the control that protects patient data |
| 6 | Provide the missing setup data: departments for Kenyatta, a dental clinician per facility | Unblocks the clinical scenario |
| 7 | Confirm whether a clinician's queue should display whether the patient has paid | Open question raised by the clinical team; currently this requires billing permission, which clinical staff do not hold |

---

## 9. Recommended sequence

1. ~~Fix the identity link (blocker 3) and add regression tests.~~ **Done in this pass. It still has to pass in the pipeline and be verified against a live provider.**
2. **Stand up the identity provider** (blocker 1), import the configuration, and set each user's facility.
3. **Pilot sign-in**: one user per role at MKU. Confirm each sees the correct menus and the correct queue.
4. **Extend enforcement** module by module, starting where confidentiality risk is highest (billing, pharmacy, laboratory, HR).
5. **Build the role-administration screen** so access changes no longer need a database change.
6. **Seed the missing data** (Kenyatta departments, a dental clinician) and run the reception -> dental -> consultation flow end to end with the clinical team.

---

## 10. Appendix - what the clinical flow looks like today

| Step | State | Notes |
|---|---|---|
| Patient arrives, is registered by reception | Working | |
| Reception routes the patient to a department | Working where a department exists | Kenyatta has none |
| The patient appears in that department's queue as **waiting** | Working | Department-scoped |
| The clinician starts the consultation | Working | Moves to **in consultation** |
| The consultation is completed | Working | Moves to **completed** |
| The clinician's queue is scoped to their own department | Working today; **blocked once the identity provider is switched on** | Blocker 3 |

The counts a clinician sees (waiting / in consultation / completed / total) are therefore reliable **in this working copy today**. They cannot be relied upon in production, which bypasses sign-in and so treats every user as the same account, nor after switching to the identity provider until blocker 3 is fixed.

---

## 11. Appendix - files changed

| Area | Files |
|---|---|
| Identity-provider sign-in | `apps/web/src/app/api/auth/keycloak/start/route.ts`, `apps/web/src/app/api/auth/keycloak/callback/route.ts`, `apps/web/src/lib/auth/oidc.ts`, `apps/web/src/lib/auth/config.ts` |
| Sign-in entry points | `apps/web/src/app/api/auth/login/route.ts`, `refresh/route.ts`, `logout/route.ts` |
| Sign-in page | `apps/web/src/app/[locale]/login/page.tsx`, `apps/web/src/app/[locale]/login/LoginForm.tsx` |
| Session cookies | `apps/web/src/lib/auth/session.ts` |
| Access control | `services/api-gateway/app/auth/permissions.py`, `services/api-gateway/app/models/role_permission.py`, `services/api-gateway/scripts/rbac_role_permissions.sql` |
| Clinician queue | `services/api-gateway/app/services/clinical_workspace.py`, `services/api-gateway/app/routers/encounters.py` |
| Staff-to-provider identity link | `services/api-gateway/app/auth/dependencies.py` |
| Regression tests for the link | `services/api-gateway/tests/test_keycloak_identity_binding.py` |
| Production readiness check | `services/api-gateway/scripts/production_readiness_check.sql` |
| How to clear the blocked items | `docs/UNBLOCK-RUNBOOK.md` |
| Identity provider config | `infrastructure/keycloak/aifya-realm.json`, `infrastructure/keycloak/aifya-realm.prod.json` |
| Configuration | `docker-compose.yml`, `.env.example` |
| Documentation | `docs/AUTH-SETUP.md`, `docs/DEPLOYMENT.md` |
