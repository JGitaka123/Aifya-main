# Authentication & Onboarding — setup and go-live runbook

Aifya has two ways to authenticate staff, selected by `AUTH_PROVIDER`, and the
Next.js **BFF** drives both so the browser never holds a token:

- `internal` - an **email and password held in Aifya's own database**. The BFF
  proxies the credentials to the FastAPI API, which issues Aifya's own tokens,
  and the BFF keeps them in httpOnly cookies.
- `keycloak` - the browser is redirected to **Keycloak** (OpenID Connect
  authorization code flow with PKCE), and the tokens Keycloak issues are stored
  in those same cookies. The FastAPI API validates them against Keycloak's
  published JWKS, so Keycloak decides *who* the user is while
  `role_permissions` still decides *what* they may do.

Today the public beta **bypasses** all of this via `BETA_PUBLIC_ACCESS=true`.

This document explains the sign-in / sign-up / invite flows that ship in the
code and exactly how to turn real auth on.

## The flows (already in the codebase)

- **Sign in** - `/{locale}/login` is a branded form that posts to the BFF, which
  verifies the credentials against the Aifya API and sets httpOnly session
  cookies. BFF routes: `apps/web/src/app/api/auth/{login,refresh,logout,me}`.
- **Facility sign-up (gated)** — `/{locale}/signup` posts to
  `POST /api/v1/onboarding/facility-signup`, creating a **pending** facility. A
  super-admin approves it (`POST /api/v1/onboarding/facilities/{id}/approve`),
  which activates the facility, seeds its baseline data (chart of accounts, lab
  catalog, theatres, essential drugs) and provisions the facility-admin user in
  Keycloak with a "set your password" email.
- **Invite staff (invite-only)** — a facility admin uses `/{locale}/settings/team`
  → `POST /api/v1/onboarding/staff-invite`, which creates the Keycloak user
  (role + `facility_id` attribute + set-password email) and a linked `staff` row.
  With `AUTH_PROVIDER=internal` (the default) these two flows create an
  `auth_accounts` row instead of a Keycloak user.

Provisioning uses the **Keycloak Admin API** via `app/utils/keycloak_admin.py`.
If admin credentials are not configured, the invite/approve endpoints return a
clear `503` and nothing else breaks.

## Go-live checklist

### 1. Create the Keycloak admin service-account client
In the `aifya` realm, create a confidential client `aifya-admin`:
- Client authentication: **On** (confidential); Standard flow: Off; Direct
  access grants: Off; **Service accounts roles: On**.
- Under **Service account roles**, assign the `realm-management` client roles
  **`manage-users`** and **`view-users`** (add `manage-realm` only if you later
  automate client/role changes).
- Copy the client secret.

### 2. Configure SMTP in the realm
Keycloak sends the invite / verify-email / password-reset messages, so the realm
needs a working SMTP server (Realm settings → Email). Without it, users are still
created but no email is sent — you'd share a temporary password out-of-band.

### 3. Backend env (`server.env` on Contabo)
```
BETA_PUBLIC_ACCESS=false                      # turn OFF the bypass to enforce auth
AUTH_PROVIDER=keycloak                        # browser redirect + JWKS validation
KEYCLOAK_URL=https://auth.aifyamed.com
KEYCLOAK_REALM=aifya
KEYCLOAK_CLIENT_ID=aifya-api                  # audience the API validates
KEYCLOAK_ADMIN_CLIENT_ID=aifya-admin
KEYCLOAK_ADMIN_CLIENT_SECRET=<secret from step 1>
SUPER_ADMIN_ROLES=admin                       # realm roles allowed to approve signups
FACILITY_SIGNUP_AUTO_APPROVE=false            # true = self-serve (dev only)
CORS_ORIGINS=https://www.aifyamed.com,https://aifyamed.com
```

### 4. Frontend env (Vercel)
```
NEXT_PUBLIC_BETA_PUBLIC_ACCESS=false
AUTH_PROVIDER=keycloak                        # must match the API
NEXT_PUBLIC_KEYCLOAK_URL=https://auth.aifyamed.com
KEYCLOAK_URL=https://auth.aifyamed.com
KEYCLOAK_REALM=aifya
KEYCLOAK_CLIENT_ID=aifya-web                  # public PKCE client
KEYCLOAK_CLIENT_SECRET=                        # empty (public client)
COOKIE_DOMAIN=.aifyamed.com                    # so cookies reach api.aifyamed.com
NEXTAUTH_URL=https://www.aifyamed.com
```
With `AUTH_PROVIDER=keycloak` the sign-in button sends the browser through
`/api/auth/login` -> `/api/auth/keycloak/start` -> Keycloak. The `aifya-web`
client must list the callback as a valid redirect URI:
`https://www.aifyamed.com/api/auth/keycloak/callback` (this repo's realm import
already covers it with `https://www.aifyamed.com/*`), and it must accept the
same origin as a web origin.

### 5. Seed the first super-admin
Approvals require a user holding a `SUPER_ADMIN_ROLES` role (`admin`). Create the
first such user with the existing `keycloak-bootstrap-user.yml` workflow (or the
console), giving them the `admin` realm role and a `facility_id` attribute.

### 6. Flip and verify
1. Set `BETA_PUBLIC_ACCESS=false` on both tiers and redeploy.
2. Visit the app unauthenticated → you should be redirected to `/login`.
3. Sign in as the super-admin.
4. Submit a facility sign-up at `/signup`, approve it from the API/queue, and
   confirm the admin gets a set-password email.
5. As a facility admin, invite a colleague at `/settings/team`.

## Sign-in modes

`AUTH_PROVIDER` selects how a token is produced. The web app reads the **same
variable** as the API, so the two can never disagree about which flow is in
force.

### `internal` (the default)

- `/en/login` renders the branded email + password form and posts the
  credentials to the BFF (`POST /api/auth/login`), which calls
  `POST /api/v1/auth/login` on the API and stores the returned HS256 tokens in
  httpOnly cookies.
- The form also asks for the **hospital** and the **state of duty**. Both are
  matched against the staff record HR keeps, so a valid password cannot open
  the wrong hospital, and the duty the person declares has to be the one HR
  recorded before any workspace opens. The duty options come from
  `GET /api/v1/auth/duties`, fetched by the sign-in page so the picker never
  keeps a second list that can drift.
- `POST /api/auth/refresh` renews them against `POST /api/v1/auth/refresh`.

### `keycloak`

- `/en/login` renders a single **Continue with your hospital account** button
  instead of the password form. `/en/signup` is unchanged: registering a facility
  is a request, not a login, so it never needs an identity provider.
- That button goes to `GET /api/auth/login`, which redirects to
  `GET /api/auth/keycloak/start`. The route mints an anti-CSRF `state` and a PKCE
  verifier, parks them in short-lived httpOnly cookies (`lib/auth/oidc.ts`), and
  sends the browser to
  `{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth`.
- Keycloak returns the browser to `GET /api/auth/keycloak/callback`. That route
  checks the `state` it set, exchanges the one-time code for tokens over a back
  channel (PKCE `code_verifier`, plus a client secret if the client is
  confidential), and stores them in the same `access_token` / `refresh_token`
  cookies the internal flow uses. Every failure path lands back on `/en/login`
  with an `?error=` code and no partial session.
- `POST /api/auth/refresh` renews against Keycloak's token endpoint, storing the
  rotated refresh token. `GET /api/auth/logout` redirects to Keycloak's
  end-session endpoint so the SSO session is cleared too, not just our cookies.
- The API validates the RS256 access token - signature against the realm JWKS,
  plus `issuer` and `audience=aifya-api` - so Keycloak authenticates and
  `role_permissions` still authorizes.

`middleware.ts` is identical in both modes: an unauthenticated page hit is sent
to `GET /api/auth/login?returnTo=...`.

Do not set `AUTH_PROVIDER=keycloak` until a realm is actually reachable. With no
Keycloak running, `POST /auth/login` returns `405` and the redirect has nowhere
to land, so nobody can sign in. `AUTH_PROVIDER` must be set on **both** tiers.

### History

An earlier revision deliberately removed the browser-side Keycloak flow: the OIDC
redirect, `/api/auth/callback`, `lib/auth/oidc.ts` and `docker-compose.keycloak.yml`
were all deleted, which is why the header comment in `lib/auth/session.ts` still
said there was no third-party identity provider. The `keycloak` mode above
restores the redirect through **new** BFF routes under `/api/auth/keycloak/`;
the old `/api/auth/callback` path was not brought back.

The Keycloak **service definition** in `docker-compose.yml` and the realm import
in `infrastructure/keycloak/` were kept, so `docker compose up` can bring a realm
up alongside the API and the web app. The API also still ships
`app/utils/keycloak_admin.py` for the `keycloak` provider mode.

### Google sign-in

**Continue with Google** appears on `/en/login` and `/en/signup`, but no Google
flow is wired yet: clicking it explains that Google sign-in is not switched on and
leaves the email and password form as the way in.

Wiring Google up needs an identity broker, because the API only trusts tokens it
issued itself. Two options:

1. **Keycloak brokers Google** (the approach this repo was originally built for).
   Needs a Google Cloud OAuth client whose authorized redirect URI is
   `http://localhost:8080/realms/aifya/broker/google/endpoint`, a Google identity
   provider in the `aifya` realm, and the browser-side flow re-introduced into the
   web app.
2. **Verify the Google ID token in the BFF** while staying on internal auth. The
   BFF validates the ID token, maps the email to an `auth_accounts` row and mints
   an internal token for it. Needs a new API endpoint.

Either way the browser must first reach an endpoint that can mint an Aifya
session; a Google button on its own cannot sign anyone in.

## Roll back
Set `BETA_PUBLIC_ACCESS=true` on both tiers and redeploy — the app returns to the
open beta immediately; no data changes.

## Notes
- Migration `017` adds `facilities.onboarding_status` (existing facilities
  default to `approved`, so nothing changes for them) and `admin_email`.
- Self-registration in Keycloak stays **off** (`registrationAllowed: false`) —
  all account creation flows through the gated facility sign-up + admin invites,
  which is the correct posture for a patient-data system (DPA / patient safety).
