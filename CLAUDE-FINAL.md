# Aifya — AI-Native Hospital Management System
> "Akili kwa Afya" — Intelligence for Health

## Project
49-module AI-native HMIS for Kenyan hospitals. Self-hosted LLMs (DeepSeek-R1 671B, Qwen 3.5 72B) on A100 80GB GPUs. Three flagship AI modules: **ScribeAI** (ambient clinical documentation), **ClaimFlow** (SHA claims automation), **Clinical Trials** (AI screening + REDCap sync). Offline-first. English + Swahili. FHIR R4. Event-sourced clinical data.

## Stack
**Frontend:** Next.js 15 (App Router), React 19, TypeScript 5.5+ strict, Tailwind 4, shadcn/ui, TanStack Query 5, TanStack Table 8, Zustand 5, React Hook Form + Zod, next-intl (en/sw), Recharts, Socket.IO, Workbox (PWA)
**Backend:** Python 3.12+ / FastAPI 0.115+ / SQLAlchemy 2 async / Pydantic 2 / Celery 5
**Go services:** Go 1.22+ / Gin (billing-service, sync-service)
**Data:** PostgreSQL 16 + TimescaleDB, Redis 7, Qdrant, MinIO, Kafka 3.7+
**AI:** vLLM 0.6+ (ports 8001-8004), faster-whisper, LlamaIndex, BGE-M3, MedGemma 27B
**Analytics:** Apache Superset, Metabase, dbt, Airflow, MLflow, JupyterHub
**Infra:** Docker, K3s, Traefik, Keycloak 25, Prometheus/Grafana/Loki/Tempo, Vault
**Integrations:** REDCap API v14+, SHA e-Claims, DHIS2, M-Pesa Daraja, FHIR R4, HL7/ASTM, KRA eTIMS

## Commands
```bash
make dev              # Docker compose up all services
make test             # All tests (Python + Go + JS)
make lint             # ESLint + Ruff + golangci-lint
make typecheck        # tsc --noEmit + mypy

cd apps/web && pnpm dev                                # Next.js dev
cd apps/web && pnpm test                               # Vitest
cd services/api-gateway && python -m pytest            # Backend tests
cd services/api-gateway && alembic upgrade head        # DB migrations
cd services/api-gateway && alembic revision --autogenerate -m "desc"
cd services/billing-service && go test ./...           # Go tests
```

## Architecture Docs — READ BEFORE CODING
Detailed specs in `docs/`. Read the relevant file BEFORE writing code for that area:
- @docs/database-schema.md — SQL for all 49 modules, indexes, event sourcing tables
- @docs/api-contracts.md — All endpoints, Pydantic schemas, OpenAPI
- @docs/frontend-patterns.md — Components, hooks, offline-first, i18n, dark mode
- @docs/ai-integration.md — ScribeAI, ClaimFlow, model routing, prompts, guardrails, agents
- @docs/clinical-workflows.md — OPD, IPD, pharmacy, lab, billing, emergency, MCH flows
- @docs/clinical-trials.md — Trial management, REDCap integration, AI screening, GCP compliance
- @docs/kenya-compliance.md — DPA, Digital Health Act, SHA, ODPC, consent, audit trail
- @docs/analytics.md — Dashboards, data warehouse, Superset/Metabase, DHIS2 auto-reporting
- @docs/module-specs.md — All 49 module specs with fields, UI wireframes, business rules
- @docs/testing-strategy.md — Clinical scenarios, offline tests, AE reporting tests

## IMPORTANT Rules

### Code Quality (YOU MUST follow)
- Zero `any` in TypeScript. Zero bare `except:` in Python. Full type hints everywhere.
- Every public function: docstring/JSDoc with @param, @returns.
- Every API endpoint: Pydantic schema → auto-generates OpenAPI.
- Every DB migration: reversible. Never drop columns — use `is_deprecated`.
- Run `make lint && make typecheck` before commit. Fix ALL errors.

### Clinical Safety (CRITICAL)
- AI NEVER auto-commits to patient records. Always clinician sign-off.
- Drug interaction checks MUST run before prescription save. Block on critical interaction.
- Critical lab values MUST trigger immediate alert.
- SAE (Serious Adverse Events) in clinical trials MUST be reportable within 24 hours.
- Every data access logged to immutable event store. Soft-delete only. 20-year retention.

### Event Sourcing (Clinical Data)
- Clinical streams (encounters, notes, prescriptions, diagnoses, vitals, trial visits) use event sourcing.
- Write to `events` table (immutable). Read from materialized views (PostgreSQL).
- Event types: PascalCase verbs (`PatientRegistered`, `PrescriptionCreated`, `AdverseEventReported`).
- Events are the audit trail. No separate audit_log needed for clinical data.

### Offline-First (CRITICAL)
- Every data hook: cache to IndexedDB via `useOfflineQuery`.
- Every mutation: queue locally if offline, sync when connected.
- Never show error screens for network issues. Show `<OfflineIndicator>` badge.
- Core workflows (registration, vitals, prescriptions) MUST work fully offline.

### Multi-Tenancy
- Every query filtered by `facility_id` from JWT. No cross-facility data leaks.
- PostgreSQL Row-Level Security as defense-in-depth.

### Naming
- DB: `snake_case` plural (`trial_participants`). Columns: `snake_case`.
- Python: `snake_case` functions, `PascalCase` classes. API: `/api/v1/kebab-case`.
- React: `PascalCase` files. Hooks: `use` prefix. Money: integer KES cents. Time: ISO 8601 Africa/Nairobi.

### Frontend
- shadcn/ui only. No other UI libs. Tailwind only. No CSS files.
- TanStack Query for server state. Zustand only for ephemeral client state.
- i18n: every user-facing string through `useTranslations()`. No hardcoded text.
- Dark mode: `dark:` variants on every component. 3-click rule for clinical actions.
- Command palette (Cmd+K): primary navigation. Must search patients, actions, modules.

### Backend
- Service layer: Router → Service → Repository. No business logic in routers.
- SQLAlchemy async. External API calls via dedicated client classes in `utils/`.
- Background tasks via Celery. Never block API on external calls.
- Idempotency: all POST/PATCH support `X-Idempotency-Key` header.

### AI Integration
- All LLM calls through `ai-service`. Never call vLLM from api-gateway directly.
- Routing: simple→Qwen 72B (8002), medium→Distill-32B (8003), complex→R1 (8001), medical→MedGemma 27B (8004).
- Log every AI I/O to `ai_interactions` event. Prompts in `services/ai-service/app/prompts/`.
- Medical guardrails validate every AI response. Trial screening runs as async Celery task.
- **Agentic workflows:** Discharge agent, screening agent, claims agent chain multiple AI steps.

### Clinical Trials
- Trial patients get alert banner on EVERY clinical encounter showing trial, arm, next visit.
- AI screening scans encounters against active trial criteria (async, background).
- REDCap sync via API. Tokens in Vault (NEVER in DB or code). FHIR-mapped field sync.
- SAE must be reportable to sponsor within 24 hours. AI pre-fills CIOMS form.
- Protocol deviation tracking is mandatory for GCP/ICH compliance.

### Hospital Branding
- Facility logo in sidebar header + all printed documents. "Powered by Aifya" in footer only.
- Print: server-side PDF. QR code on every document. A4 layout. 80mm thermal receipts.

### Git
- Branches: `feat/module`, `fix/issue`, `chore/task`
- Commits: `type(scope): desc` (e.g., `feat(trials): add REDCap sync engine`)
- PR: CI must pass + 1 human review. Never commit secrets or patient data.

### When Compacting
Preserve: modified files list, current module, test commands, failing tests, active trial IDs if working on trials module.
