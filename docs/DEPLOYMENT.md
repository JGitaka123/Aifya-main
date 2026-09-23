# Aifya — Production Deployment Guide (www.aifyamed.com)

Target topology, chosen for **efficiency, reliability, onboarding, and
scaling**:

- **Frontend** → **Vercel** (Next.js), served at `https://www.aifyamed.com`
- **Backend** → **Contabo** single host, `docker compose` (FastAPI +
  Postgres + Keycloak + Redis + MinIO + Qdrant + Celery + ClaimFlow
  validator), served at `https://api.aifyamed.com`
- **AI** → **managed OpenAI-compatible API** for now (self-hosted vLLM on
  GPU deferred; the ClaimFlow rule engine needs no GPU and ships today)

> This complements OPERATIONS.md (day-2 ops: backups, rollback, incidents).
> Read this for the initial build-out; read OPERATIONS.md to run it.

---

## 1. Architecture

```mermaid
graph TD
  U[Clinician browser / PWA] -->|HTTPS| V[Vercel: www.aifyamed.com<br/>Next.js SSR + static + BFF auth routes]
  U -->|HTTPS API calls with cookie| API[Contabo: api.aifyamed.com<br/>FastAPI api-gateway]
  V -->|OIDC redirect| KC[Contabo: auth.aifyamed.com<br/>Keycloak]
  U -->|login redirect| KC
  API --> PG[(Postgres 16)]
  API --> RD[(Redis)]
  API --> MO[(MinIO objects)]
  API --> QD[(Qdrant)]
  API --> CF[claimflow-validator :8030]
  API -->|OpenAI-compatible /v1| AI[Managed AI API]
  W[Celery worker/beat] --> PG
  W --> RD
  subgraph Contabo host (docker compose)
    API
    KC
    PG
    RD
    MO
    QD
    CF
    W
  end
```

**Why this split.** The browser talks to the API **directly** at
`api.aifyamed.com` (not proxied through Vercel), so heavy traffic — patient
lists, file up/downloads via MinIO — never consumes Vercel bandwidth or
function time. Vercel does what it is best at: global edge delivery of the
app shell, instant rollbacks, and preview deploys per PR. Auth cookies are
scoped to the parent domain so the two hosts share one session (see §4).

---

## 2. DNS (at your registrar / Cloudflare)

| Record | Name | Points to | Notes |
|---|---|---|---|
| CNAME | `www` | Vercel (`cname.vercel-dns.com`) | Vercel gives the exact target |
| A / ALIAS | `aifyamed.com` (apex) | Vercel or a redirect to `www` | Vercel supports apex via A record |
| A | `api` | Contabo server IP | backend |
| A | `auth` | Contabo server IP | Keycloak |
| A | `files` | Contabo server IP | (optional) MinIO public bucket for documents |

If you use Cloudflare, set `api`/`auth` to **DNS-only (grey cloud)** first
so Let's Encrypt HTTP-01 works, or use Cloudflare Origin certs. Keep the
app domain (`www`) proxied (orange) for Vercel — actually Vercel manages
its own certs, so point `www` straight at Vercel (grey cloud / CNAME).

---

## 3. Contabo server build-out

### 3.1 Base

```bash
# Ubuntu 22.04/24.04 on the Contabo VPS
sudo apt update && sudo apt -y install docker.io docker-compose-plugin git
sudo systemctl enable --now docker
sudo mkdir -p /root/Aifya && cd /root/Aifya
git clone <your repo> .        # or the CI rsync target used by deploy.yml
```

### 3.2 TLS + reverse proxy

The compose stack publishes `api-gateway` on `127.0.0.1:8000` and
`keycloak` on `127.0.0.1:8080`. Put a TLS terminator in front. **Caddy**
(automatic Let's Encrypt) is version-controlled at
**`infrastructure/caddy/Caddyfile`** — install it:

```bash
sudo apt -y install caddy
sudo cp /root/Aifya/infrastructure/caddy/Caddyfile /etc/caddy/Caddyfile
# edit the `email` line, then:
sudo systemctl reload caddy
```

The committed Caddyfile fronts `api.aifyamed.com` → 8000 and
`auth.aifyamed.com` → 8080 (with gzip/zstd and a request-body cap), plus a
commented-out optional `files.aifyamed.com` → MinIO. Point the `api`/`auth`
A records at this host **before** reloading Caddy, or ACME HTTP-01 fails.
(Traefik works too — the compose file labels services — but Caddy is
simpler for one host.)

### 3.3 Firewall

```bash
sudo ufw allow 22/tcp        # SSH from admin IPs ideally, not 0.0.0.0
sudo ufw allow 80,443/tcp    # Caddy
sudo ufw enable
```

**Do NOT expose** 5432 (Postgres), 6379 (Redis), 9000/9001 (MinIO),
6333 (Qdrant), 8030 (validator) publicly — they stay on the docker network
and localhost only.

### 3.4 App DB role (RLS) — from OPERATIONS.md / audit H-3

```bash
./scripts/create-app-db-role.sh   # creates NOSUPERUSER/NOBYPASSRLS aifya_app
# then set DATABASE_URL to the aifya_app role in .env
```

### 3.5 Bring it up

```bash
export COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
$COMPOSE build
$COMPOSE up -d
```

There is no manual migration step: the one-shot `db-migrate` service runs
`alembic upgrade head` and every service that reads the schema
(`api-gateway`, `api-worker`, `api-beat`, `knowledge-service`,
`knowledge-worker`, `scribe-service`) waits for it to exit 0 before starting.
It is idempotent, so re-running it is safe:

```bash
$COMPOSE run --rm db-migrate
```

---

## 4. The one thing that will silently break: session cookies

The browser calls `api.aifyamed.com` directly and relies on the httpOnly
`access_token` cookie set by the Next.js BFF on `www.aifyamed.com`. A
host-only cookie on `www` is **not** sent to `api`. Because both hosts share
the registrable domain `aifyamed.com` (same-site), the fix is a
**parent-domain cookie**, not `SameSite=None`.

Set on **Vercel**:

```
COOKIE_DOMAIN=.aifyamed.com
```

The auth routes honour this (`sessionCookieOptions` in
`apps/web/src/lib/auth/session.ts`); unset = host-only (local/single-host).
With it set, `Domain=.aifyamed.com; SameSite=Lax; Secure` cookies flow to
both `www` and `api`.

Set on **Contabo** (`.env`, consumed by the API):

```
CORS_ORIGINS=https://www.aifyamed.com
# (CORS already runs with allow_credentials=true)
```

---

## 5. Environment matrix

### 5.1 Vercel (Project → Settings → Environment Variables)

| Var | Value |
|---|---|
| `NEXT_PUBLIC_API_URL` | `https://api.aifyamed.com` |
| `COOKIE_DOMAIN` | `.aifyamed.com` |
| `NEXTAUTH_URL` | `https://www.aifyamed.com` |
| `KEYCLOAK_URL` (server-side token calls) | `https://auth.aifyamed.com` |
| `NEXT_PUBLIC_KEYCLOAK_URL` | `https://auth.aifyamed.com` |
| `KEYCLOAK_REALM` | `aifya` |
| `KEYCLOAK_CLIENT_ID` | `aifya-web` |
| `KEYCLOAK_CLIENT_SECRET` | optional — only if you make `aifya-web` confidential (default is public + PKCE) |
| `NEXT_PUBLIC_APP_URL` | `https://www.aifyamed.com` |

Project settings: **Root Directory = `apps/web`**, Framework = Next.js
(auto-detected). Leave Build/Install on the defaults — `apps/web`
(`@aifya/web`) has no workspace dependencies, so it installs standalone;
keep "Include files outside the Root Directory" **on** so the root
`pnpm-lock.yaml` is used. Add the domain `www.aifyamed.com` (and redirect
the apex) under Settings → Domains.

`apps/web/vercel.json` (committed) pins `framework: nextjs`, disables the
self-hosting `standalone` output on Vercel (`NEXT_OUTPUT_STANDALONE=false`
— it would otherwise fight Vercel's native build), and sets baseline
security headers (nosniff, frame-deny, referrer-policy, HSTS).

### 5.2 Contabo `.env` (backend)

| Var | Value / note |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://aifya_app:…@postgres/aifya` (non-superuser) |
| `SECRET_KEY` | strong 64-hex |
| `FIELD_ENCRYPTION_KEY` | explicit key (employee PII at rest) |
| `CORS_ORIGINS` | `https://www.aifyamed.com` |
| `KEYCLOAK_URL` | `https://auth.aifyamed.com` |
| `KEYCLOAK_REALM` | `aifya` |
| `MPESA_CALLBACK_IP_ALLOWLIST` | Safaricom IPs (enforcement on by default) |
| `SENTRY_DSN` | error tracking |
| `CLAIMFLOW_VALIDATOR_URL` | `http://claimflow-validator:8030` (internal) |
| `SHA_ECLAIMS_URL` / `SHA_ECLAIMS_API_KEY` | when SHA credentials arrive (mock until then) |
| `PATIENT_READ_ROLES` | optional DPA read gating |
| `ANTHROPIC_API_KEY` | managed AI via LiteLLM (see §7) |
| `WHISPER_OPENAI_API_KEY` | Whisper transcription provider (see §7) |

---

## 6. Keycloak (auth.aifyamed.com) — turnkey via realm import

The prod compose overlay runs Keycloak in **production mode**
(`start --import-realm`, `KC_HTTP_ENABLED=true` behind Caddy TLS) and
imports **`infrastructure/keycloak/aifya-realm.prod.json`** on first boot.
That file is the auth setup — no manual console clicking:

- Realm `aifya`, with a password policy (min 12, mixed case + digit,
  not-username) and brute-force protection.
- Client **`aifya-web`** (public + **PKCE S256**; the token exchange runs
  server-side in the Next.js BFF): redirect + post-logout + web-origins
  already set to `https://www.aifyamed.com` (and the apex).
- Client **`aifya-api`** (bearer-only); the gateway validates JWTs via the
  realm JWKS.
- `aifya-scope` maps the `facility_id` user attribute into the token and
  adds the `aifya-api` audience.
- All app roles: `admin`, `facility_admin`, `doctor`, `nurse`,
  `pharmacist`, `lab_tech`, `cashier`, `billing_officer`, `records`,
  `receptionist`, `radiologist`, `investigator`, `research_coordinator`.
- **One admin user** `admin@aifyamed.com` with **no shipped password** and
  a forced `UPDATE_PASSWORD` — set its password on first boot via the
  master admin console (or a reset email). No demo accounts, no `admin123`.

First-boot steps:

1. Set `KEYCLOAK_ADMIN` / `KEYCLOAK_ADMIN_PASSWORD` (master realm bootstrap)
   in the server `.env` to a strong value.
2. Deploy; the realm imports automatically.
3. In the master admin console (`https://auth.aifyamed.com/admin`), set the
   `admin@aifyamed.com` password, then enable OTP/2FA for admin roles.
4. Create each facility's users with roles + their `facility_id` attribute
   (or via a seed script) — this is the onboarding step (§9).

> The dev realm (`aifya-realm.json`, with demo users + localhost URIs) is
> used only by the base compose for local work; the prod overlay replaces
> it with `aifya-realm.prod.json` at the same import path.

> If you later want a confidential `aifya-web` (client secret instead of
> PKCE), flip `publicClient` to `false`, add the secret to Keycloak, and set
> `KEYCLOAK_CLIENT_SECRET` on Vercel — the BFF already sends it when present.

---

## 7. Managed AI — LiteLLM proxy (ships in the stack)

Every AI service speaks the **OpenAI-compatible `/v1`** protocol, so the
compose stack now includes a **LiteLLM proxy** (`litellm` service +
`infrastructure/litellm/config.yaml`). ScribeAI and knowledge call one
stable internal endpoint (`http://litellm:4000/v1`); LiteLLM forwards to
managed providers. No app code knows which model is behind it.

Wiring (already in `docker-compose.yml`):

- `scribe-service` → `OPENAI_BASE_URL=http://litellm:4000/v1`
- `knowledge-service` → `VLLM_BASE_URL=http://litellm:4000/v1`,
  `GENERATION_MODEL=claude-sonnet`
- LiteLLM maps `gpt-4o`/`claude-sonnet`/`claude-haiku` → Anthropic Claude,
  and `whisper-1` → an OpenAI-compatible **transcription** provider
  (Anthropic can't transcribe audio).

**To turn it on**, set in the server `.env`:

```
ANTHROPIC_API_KEY=...            # Claude chat / clinical reasoning
WHISPER_OPENAI_API_KEY=...       # only if Whisper transcription → OpenAI
```

Edit `infrastructure/litellm/config.yaml` to pick exact model ids or add a
transcription provider (Groq `whisper-large-v3`, Deepgram, or self-hosted
faster-whisper). The proxy runs **keyless and bound to host loopback
(`127.0.0.1:4000`) only** — reachable by the app over the docker network
and by the deploy's health probe, never off-host; the provider keys live
only inside that container. Liveness: `GET /health/liveliness`.

**Later — self-hosted vLLM (CLAUDE.md end-state):** when a GPU host exists
(RunPod/Lambda/Hetzner-GPU), either point LiteLLM's `model_list` at it or
override `OPENAI_BASE_URL`/`VLLM_BASE_URL` straight at vLLM. No app change.

> Clinical-data note: confirm the chosen provider's data-retention terms
> against Kenya DPA / your BAA before sending patient text. LiteLLM is the
> single choke point to enforce redaction/logging/model policy centrally.

---

## 8. Deploy flow

**Frontend (Vercel):** connect the GitHub repo; every push to `main`
auto-deploys `www.aifyamed.com`, every PR gets a preview URL. No SSH.

**Backend (Contabo):** `.github/workflows/deploy.yml` is **backend-only** —
it rsyncs the backend sources (api-gateway + the ClaimFlow validator's build
context) over SSH, builds `api-gateway` + `claimflow-validator`, runs
`alembic upgrade head`, and health-checks Keycloak, the API, and the
validator. It no longer builds or ships the web app (Vercel owns that). It
runs in the GitHub `production` environment — set a required reviewer to
arm the approval gate (audit C-3). It triggers only on changes under
`services/`, the compose files, or `infrastructure/`.

---

## 9. The four axes — concrete choices

**Efficiency**
- Browser→API direct (no Vercel proxy) = no double bandwidth, no function
  cost on data/file traffic.
- One Contabo host runs the whole backend; `docker compose` keeps it a
  single `up -d`.
- esbuild-bundled ClaimFlow validator = small image, fast boot.

**Reliability**
- Vercel gives the frontend a CDN + instant rollback independent of the
  backend.
- Offline-first PWA (IndexedDB queue) rides out brief API/network outages —
  core workflows keep working, then sync.
- Nightly `pg_dump` + a tested restore drill (OPERATIONS.md §3–4).
- External uptime check on `https://api.aifyamed.com/api/health` +
  `https://www.aifyamed.com` (OPERATIONS.md §5) + Sentry.
- **Single-host risk:** the Contabo box is the backend SPOF. Mitigate with
  daily off-host backups now; graduate to a managed Postgres + a second app
  host when load justifies it (§10).

**Onboarding**
- New facility = a `facilities` row + Keycloak users with roles; tenant
  isolation is by `facility_id` + Postgres RLS, so one backend serves many
  facilities with no per-facility deploy.
- Seed script / admin UI creates the facility, its schemes, and first admin.
- `PATIENT_READ_ROLES` lets a facility tighten PII reads without a code
  change.

**Scaling**
- Vertical first: Contabo plans scale CPU/RAM cheaply; Postgres + Redis on
  one host handle many facilities before you need more.
- Horizontal when needed: move Postgres to managed (or a replica), run a
  second api-gateway behind Caddy, scale Celery workers by concurrency/
  queue. The app is stateless behind the DB/Redis/MinIO, so this is
  additive.
- AI scales independently: swap the managed API tier or stand up vLLM on
  GPU — no app change (§7).

---

## 10. Growth path (when one host isn't enough)

1. **Backups off-host** (do immediately): rsync dumps to object storage.
2. **Managed Postgres** (first bottleneck): point `DATABASE_URL` at it;
   drop the postgres container. Gives PITR + failover.
3. **Second app host**: Caddy load-balances two `api-gateway` containers;
   Redis/MinIO/Postgres become shared services.
4. **GPU AI**: dedicated vLLM host; flip the `/v1` base URLs.
5. **Object storage**: move MinIO → S3-compatible managed store for
   document durability.

---

## 11. Go-live checklist (this topology)

- [ ] DNS: `www` → Vercel, `api`/`auth` → Contabo, certs issued
- [ ] Vercel: Root Dir `apps/web`, env vars incl. `COOKIE_DOMAIN=.aifyamed.com`,
      domain `www.aifyamed.com` verified
- [ ] Contabo `.env`: `CORS_ORIGINS=https://www.aifyamed.com`, non-superuser
      `DATABASE_URL`, `SECRET_KEY`, `FIELD_ENCRYPTION_KEY`, `SENTRY_DSN`,
      `MPESA_CALLBACK_IP_ALLOWLIST`
- [ ] Keycloak: `aifya-realm.prod.json` imported (auto on first boot);
      `KEYCLOAK_ADMIN_PASSWORD` strong; `admin@aifyamed.com` password set +
      2FA enabled for admins
- [ ] `alembic upgrade head` run; RLS verified with a cross-facility read
- [ ] Managed AI: `ANTHROPIC_API_KEY` (+ `WHISPER_OPENAI_API_KEY`) set;
      `infrastructure/litellm/config.yaml` model ids confirmed
- [ ] Login round-trip works: `www` → Keycloak → callback → API call to
      `api.aifyamed.com` returns data (proves the cross-host cookie)
- [ ] Firewall: only 80/443 (+ SSH) public; data ports internal only
- [ ] Backups cron installed + one restore drill done
- [ ] Uptime check + Sentry live; GitHub `production` reviewer set
- [ ] GitHub Actions secrets set for the backend deploy: `PRODUCTION_ENV`,
      `SERVER_IP`, `SERVER_USER`, `DEPLOY_KEY` (web is deployed by Vercel)

---

### Appendix — verified in this branch

- Web production build: **compiles clean** (`pnpm build`, all routes).
- Web server boot + auth middleware: `/` → login redirect, `/api/auth/me`
  unauth → 401 (verified with `next start`).
- ClaimFlow validator: **boots on plain `node`** and runs all **121 rules**
  end-to-end (esbuild bundle fix — the prior image would have crashed).
- Cross-host session cookie (`COOKIE_DOMAIN`) wired into the auth routes;
  tsc + eslint + 68 web tests green.
