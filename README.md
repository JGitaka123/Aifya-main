# Aifya

> **Akili kwa Afya** — Intelligence for Health

AI-native Hospital Management Information System built for Kenyan hospitals. 49 clinical and administrative modules, offline-first architecture, self-hosted LLMs, and full Kenya compliance (SHA, DPA, DHIS2, KRA eTIMS).

---

## Highlights

- **49 modules** covering the full hospital workflow — OPD, IPD, pharmacy, lab, radiology, billing, MCH, emergency, dental, theatre, HR, inventory, insurance, clinical trials, and more
- **3 flagship AI modules**: ScribeAI (ambient clinical documentation), ClaimFlow (SHA claims automation), Clinical Trials (AI screening + REDCap sync)
- **Offline-first**: core workflows (registration, vitals, prescriptions) work fully offline via IndexedDB + background sync
- **Bilingual**: English and Swahili (next-intl), switchable per user
- **Self-hosted AI**: DeepSeek-R1 671B, Qwen 3.5 72B, Distill-32B, MedGemma 27B on A100 80GB GPUs via vLLM — no patient data leaves the facility
- **Event-sourced clinical data**: immutable audit trail, 20-year retention, FHIR R4 export
- **Multi-tenant**: facility-scoped via JWT + PostgreSQL Row-Level Security

## Architecture

```
                        ┌─────────────────────┐
                        │    Next.js 15 PWA    │
                        │  React 19 + shadcn   │
                        └──────────┬──────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │               │
             ┌──────▼──────┐ ┌────▼─────┐  ┌─────▼──────┐
             │ API Gateway │ │ Billing  │  │   Sync     │
             │  FastAPI    │ │ Go / Gin │  │ Go / Gin   │
             └──────┬──────┘ └──────────┘  └────────────┘
                    │
        ┌───────────┼───────────┬──────────────┐
        │           │           │              │
   ┌────▼───┐  ┌───▼────┐ ┌───▼───┐   ┌─────▼─────┐
   │ Postgres│  │ Redis  │ │ Kafka │   │ AI Service│
   │ 16 +   │  │  7     │ │  3.7  │   │  vLLM     │
   │Timescale│  └────────┘ └───────┘   │  Whisper  │
   └────────┘                          │  Qdrant   │
                                       └───────────┘
```

## Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | Next.js 15 (App Router), React 19, TypeScript 5.5+, Tailwind 4, shadcn/ui, TanStack Query 5, TanStack Table 8, Zustand 5, React Hook Form + Zod, next-intl, Recharts, Socket.IO, Workbox PWA |
| **Backend** | Python 3.12+, FastAPI 0.115+, SQLAlchemy 2 (async), Pydantic 2, Celery 5 |
| **Go Services** | Go 1.22+, Gin (billing-service, sync-service) |
| **Data** | PostgreSQL 16 + TimescaleDB, Redis 7, Qdrant, MinIO, Kafka 3.7+ |
| **AI** | vLLM 0.6+ (4 model endpoints), faster-whisper, LlamaIndex, BGE-M3, MedGemma 27B |
| **Auth** | Keycloak 25 (OIDC/RBAC) |
| **Infra** | Docker Compose (single host), Keycloak, Celery worker/beat — see OPERATIONS.md |
| **Integrations** | SHA e-Claims, DHIS2, M-Pesa Daraja, REDCap v14+, FHIR R4, HL7/ASTM, KRA eTIMS |

## Modules

### Clinical
| Module | Description |
|---|---|
| OPD | Outpatient queue, encounters, triage |
| IPD | Admissions, wards, beds, nursing notes, discharge |
| Emergency | Triage (ESI/KTAS), rapid assessment, disposition |
| Pharmacy | Dispensing queue, inventory, drug interactions |
| Laboratory | Orders, specimen tracking, results, critical alerts |
| Radiology | Imaging orders, PACS viewer, reports |
| MCH | Antenatal, delivery, child health, immunizations |
| Dental | Dental charts, treatment plans, procedures |
| Theatre | Surgical scheduling, operative notes |
| Clinical Trials | Protocol management, AI screening, REDCap sync, SAE reporting |

### Administrative
| Module | Description |
|---|---|
| Patients | Registration, search, demographics, FHIR export |
| Billing | Invoicing, M-Pesa, insurance claims, waivers |
| Insurance | SHA integration, pre-auth, claim tracking |
| Appointments | Scheduling, slots, check-in, no-show analytics |
| HR | Staff profiles, shifts, leave, attendance |
| Inventory | Items, suppliers, purchase orders, stock alerts |
| Communications | SMS/email, templates, bulk messaging |
| Analytics | AI predictions (readmission, stockout, revenue), dashboards |
| Reports | DHIS2 auto-reporting, MOH reports, custom queries |
| Referrals | Inter-facility referrals, status tracking |
| Knowledge Base | Clinical protocols, facility SOPs |
| Settings | Facility config, branding, user management |

### AI-Powered
| Module | Description |
|---|---|
| ScribeAI | Ambient documentation — records consultations, generates SOAP notes |
| ClaimFlow | Automates SHA claim submission, tracks rejections, suggests fixes |
| CDS | Clinical Decision Support — drug interactions, vitals alerts, lab flags |
| AI Screening | Scans encounters against active trial criteria, ranks candidates |

## Project Structure

```
aifya/
├── apps/
│   └── web/                    # Next.js 15 frontend
│       └── src/
│           ├── app/[locale]/   # 25+ page routes
│           ├── components/     # shadcn/ui + custom components
│           ├── hooks/          # TanStack Query hooks (offline-first)
│           └── lib/            # API client, offline store, utils
├── services/
│   ├── api-gateway/            # FastAPI backend (30 routers)
│   │   ├── app/routers/        # All API endpoints
│   │   ├── app/models/         # SQLAlchemy models
│   │   ├── app/schemas/        # Pydantic schemas
│   │   └── tests/              # pytest suite (13 test files)
│   ├── ai-service/             # LLM orchestration (vLLM, Whisper)
│   ├── billing-service/        # Go billing microservice
│   └── sync-service/           # Go offline sync service
├── packages/
│   └── shared/                 # Shared TypeScript types + utils
├── infrastructure/
│   └── keycloak/               # Realm config, roles
├── docs/                       # Architecture specs
├── docker-compose.yml          # Full stack (15+ services)
├── Makefile                    # Dev commands
└── pnpm-workspace.yaml         # Monorepo config
```

## Getting Started

### Prerequisites

- **Node.js 20+** and **pnpm 9+**
- **Python 3.12+** with pip
- **Go 1.22+**
- **Docker** and **Docker Compose**
- **PostgreSQL 16** (or use Docker)

### Quick Start

```bash
# 1. Clone
git clone https://github.com/JGitaka123/Aifya.git
cd Aifya

# 2. Environment
cp .env.example .env
# Edit .env with your database credentials and API keys

# 3. Start infrastructure (Postgres, Redis, Kafka, Keycloak, MinIO)
make dev

# 4. Install frontend dependencies
pnpm install

# 5. Install the backend deps and run database migrations
cd services/api-gateway
uv sync
uv run alembic upgrade head
cd ../..

# 6. Start the API gateway
cd services/api-gateway
uvicorn app.main:app --reload --port 8000 &
cd ../..

# 7. Start the frontend
cd apps/web
pnpm dev
# Open http://localhost:3000
```

### Quick Start on Windows

The block above assumes a Unix shell. On Windows, run each step in its own
`cmd.exe` window and **do not paste the `#` comments** - `cmd.exe` passes them
to the command as arguments, which is what produces errors like
`error: unexpected argument '#' found`.

```bat
REM 1. Infrastructure: PostgreSQL must be listening on port 5432.
REM    Docker Desktop is optional - a native PostgreSQL install works just as
REM    well. If you do have Docker running, this does the same job:
REM    docker compose up -d postgres redis

REM 2. Backend - leave this window running
REM    You do not need a system Python: uv downloads a private CPython for you.
cd services\api-gateway
uv sync
uv run alembic upgrade head
REM --reload-include ".*" also restarts on .env edits. uvicorn only watches
REM *.py by default, so without it a changed .env is silently ignored and the
REM API keeps using the old credentials until you restart it by hand.
uv run uvicorn app.main:app --reload --reload-include ".*" --port 8000

REM 3. Frontend - in a second window, leave it running
cd apps\web
corepack enable
pnpm install
pnpm dev

REM 4. Knowledge service - in a third window, leave it running
REM    The Knowledge tab proxies every request to this process on port 8025.
REM    Without it, uploads and search return "Knowledge service unavailable".
REM    It needs no Docker: uploads are written under
REM    services\ai-service\knowledge\data\files and the embeddings live in the
REM    same PostgreSQL the API uses.
cd ..\..
powershell -ExecutionPolicy Bypass -File scripts\start-knowledge.ps1

REM Open http://localhost:3000
```

If `uv sync` reports `Access is denied` on `.venv`, close any process holding
the folder (a stopped `uvicorn` and OneDrive sync are the usual causes), delete
`services\api-gateway\.venv`, then run `uv sync` again.

If `uvicorn` fails with `uv trampoline failed to canonicalize script path` or
`No Python at '...python.exe'`, the interpreter the venv was built from has
been uninstalled. Delete `services\api-gateway\.venv` and run `uv sync` again -
uv will fetch a fresh Python. Check `scripts\start-knowledge.ps1` output if the
Knowledge tab still reports 502.

### AI Services (Optional)

Requires NVIDIA A100 80GB GPUs with vLLM installed:

```bash
# DeepSeek-R1 671B (complex reasoning) — port 8001
# Qwen 3.5 72B (general tasks) — port 8002
# Distill-32B (fast, simple tasks) — port 8003
# MedGemma 27B (clinical/medical tasks) — port 8004
# Whisper (audio transcription) — port 8005
# See services/ai-service/ for configuration
```

**MedGemma 27B** is Google's medically fine-tuned Gemma 3 model (87.7% on MedQA). It handles:
- Clinical documentation (ScribeAI SOAP notes)
- Trial screening and eligibility matching
- Medical imaging analysis (chest X-ray, retinal scans)
- Drug interaction checks and CDS alerts
- Bilingual patient education (English/Swahili)

VRAM: ~54 GB BF16 or ~27 GB INT8 on a single A100 80GB. 128K context window.

## Development

```bash
# Run focused green tests
make test

# Individual test suites
cd apps/web && pnpm test              # Vitest frontend tests
make test-api                         # Focused API regression suite
make test-api-full                    # Full API pytest suite

# Linting
make lint                             # ESLint + focused Ruff + Go format/vet checks
make lint-api-full                    # Full API Ruff debt gate

# Type checking
make typecheck                        # Shared + web TypeScript
make typecheck-full                   # Shared + web TypeScript + API mypy

# Database
make db-migrate                    # Run migrations
make db-revision msg="description" # Create new migration
```

## Production Deployment

Pushes to `main` run `.github/workflows/deploy.yml`. The workflow builds the
Next.js standalone app, copies web artifacts and backend service sources to the
server, rebuilds/restarts the API gateway plus Go services, runs Alembic
migrations, then checks API and web health before reporting success.

Required GitHub Actions secrets:

```bash
SERVER_IP
SERVER_USER
DEPLOY_KEY
NEXTAUTH_SECRET
PRODUCTION_ENV
KEYCLOAK_CLIENT_SECRET # optional; only needed if the Keycloak web client is confidential
```

`PRODUCTION_ENV` should contain the complete server `.env` file. The deploy
workflow copies it to `/root/Aifya/.env` and locks it to `600` permissions.

Required values inside `PRODUCTION_ENV` for the production compose override:

```bash
DATABASE_URL=postgresql+asyncpg://...
SECRET_KEY=<64+ hex chars from secrets.token_hex(32)>
KEYCLOAK_URL=https://aifyamed.com/auth
KEYCLOAK_REALM=aifya
API_KEYCLOAK_CLIENT_ID=aifya-api
CORS_ORIGINS=https://aifyamed.com
```

`POSTGRES_PASSWORD` is the deployment source of truth. During deploy, the
workflow starts Postgres first, rewrites `DATABASE_URL` with the URL-encoded
`POSTGRES_PASSWORD`, syncs the existing database role password, then runs
Alembic migrations.

Recommended GitHub Actions variables:

```bash
NEXT_PUBLIC_API_URL=https://aifyamed.com/api/v1
API_REWRITE_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_KEYCLOAK_URL=https://aifyamed.com/auth
NEXT_PUBLIC_KEYCLOAK_REALM=aifya
NEXT_PUBLIC_KEYCLOAK_CLIENT_ID=aifya-web
NEXT_PUBLIC_WS_URL=wss://aifyamed.com/ws
NEXTAUTH_URL=https://aifyamed.com
```

## API

The API gateway exposes **30 router modules** at `http://localhost:8000/api/v1/`:

| Area | Endpoints |
|---|---|
| `/patients` | Registration, search, demographics |
| `/encounters` | OPD/IPD encounters, vitals, diagnoses |
| `/pharmacy` | Dispensing, inventory, drug interactions |
| `/billing` | Invoices, payments, waivers |
| `/laboratory` | Orders, results, critical alerts |
| `/radiology` | Imaging orders, reports |
| `/appointments` | Scheduling, check-in |
| `/ipd` | Admissions, wards, beds, discharge |
| `/emergency` | Triage, queue, disposition |
| `/mch` | Antenatal, delivery, immunizations |
| `/hr` | Staff, shifts, leave, attendance |
| `/inventory` | Items, suppliers, purchase orders |
| `/clinical-trials` | Protocols, screening, visits, SAE |
| `/fhir` | FHIR R4 resources (Patient, Encounter, Observation, etc.) |
| `/analytics` | AI predictions, dashboards |
| `/cds` | Clinical decision support evaluations |
| `/licensing` | License validation, module access |
| `/communications` | Messaging, templates |

Interactive API docs at `http://localhost:8000/api/docs` in development.

## Kenya Compliance

- **SHA**: Automated e-Claims submission via ClaimFlow
- **DHIS2**: Auto-reporting of MOH indicators
- **KRA eTIMS**: Tax invoice integration for billing
- **M-Pesa**: Daraja API for patient payments
- **DPA/ODPC**: Consent management, data protection audit trail
- **Digital Health Act**: Compliant record retention (20 years)

## Clinical Safety

- AI **never** auto-commits to patient records — clinician sign-off required
- Drug interaction checks **block** on critical interactions before prescription save
- Critical lab values trigger **immediate** alerts
- Serious Adverse Events (SAE) reportable within **24 hours**
- All data access logged to **immutable event store**

## License

Proprietary. All rights reserved.

---

Built with care for Kenyan healthcare.
