# Authentication & Onboarding — setup and go-live runbook

Aifya authenticates staff with an **email and password held in its own
database**: the Next.js **BFF** proxies the credentials to the FastAPI API,
which issues Aifya's own tokens, and the BFF keeps them in httpOnly cookies.
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
NEXT_PUBLIC_KEYCLOAK_URL=https://auth.aifyamed.com
KEYCLOAK_URL=https://auth.aifyamed.com
KEYCLOAK_REALM=aifya
KEYCLOAK_CLIENT_ID=aifya-web                  # public PKCE client
KEYCLOAK_CLIENT_SECRET=                        # empty (public client)
COOKIE_DOMAIN=.aifyamed.com                    # so cookies reach api.aifyamed.com
NEXTAUTH_URL=https://www.aifyamed.com
```
The built-in sign-in posts to `/api/auth/login` on the same origin, so no Keycloak redirect URI is needed for it.

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

There is one sign-in mode in the web app: **Aifya's own email and password form**.

- `/en/login` posts the credentials to the BFF (`POST /api/auth/login`), which
  calls `POST /api/v1/auth/login` on the API and stores the returned tokens in
  httpOnly cookies.
- `/en/signup` collects the facility request and posts it to
  `POST /api/v1/onboarding/facility-signup`. Registering a facility is a request,
  not a login, so it never needs an identity provider.
- `GET /api/auth/login?returnTo=...` is the redirect used by `middleware.ts` for
  an unauthenticated page hit. It sends the browser to `/en/login`, so there is
  no external hop.

The API selects its token strategy with `AUTH_PROVIDER` in
`services/api-gateway/.env`:

- `internal` (the default) - `POST /auth/login` verifies the password against
  `auth_accounts` and issues Aifya's own HS256 tokens.
- `keycloak` - `POST /auth/login` returns `405` and the API expects realm RS256
  tokens instead. Nothing in the web app can authenticate in this mode, so leave
  it unset unless you are deliberately running Keycloak as the token issuer.

If the API is left on `keycloak` while the web app runs the branded form, every
sign-in fails with *Password login is disabled. Use the OIDC redirect flow.* Set
`AUTH_PROVIDER=internal` in `services/api-gateway/.env` and restart the API.

### What was removed

The browser never talks to Keycloak any more. These were deleted from the web app
so that no request can be bounced to port 8080:

- `GET /api/auth/login` no longer builds an authorization-code + PKCE redirect.
- `/api/auth/callback` (the OIDC token exchange) is gone, along with the legacy
  `/{locale}/auth/callback` shim.
- `lib/auth/oidc.ts` and `lib/auth/sso.ts` are gone. The cookie helpers they also
  held now live in `lib/auth/session.ts`.
- `docker-compose.keycloak.yml` (the standalone Keycloak service) is gone.

The Keycloak **service definitions** in `docker-compose.yml` and
`docker-compose.prod.yml` are still present, and `infrastructure/keycloak/` still
holds the realm import. The documented dev commands never start them, and other
compose services list `keycloak` in `depends_on`, so deleting the entries would
break `docker compose up`. The API also still ships `app/utils/keycloak_admin.py`
for the `keycloak` provider mode.

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
