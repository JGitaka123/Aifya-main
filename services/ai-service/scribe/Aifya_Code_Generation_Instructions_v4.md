# AIFYA HEALTH PLATFORM — Code Generation Master Instructions

> **Purpose**: These instructions are the authoritative engineering prompt for AI-assisted code generation of the Aifya Health Platform. Feed this entire document as context/system instructions to produce production-grade, fully functional code for every subsystem.
>
> **Version**: 4.0 — March 2026
> **Author**: Dr. Jesse Gitaka, PI — GitakaLab, Mount Kenya University
> **First Client**: Mary Help Hospital | **EMR Target**: Q-Afya HMIS (QET Systems)

---

## TABLE OF CONTENTS

1. [Project Identity & Non-Negotiables](#1-project-identity--non-negotiables)
2. [Architecture Constraints](#2-architecture-constraints)
3. [Technology Stack (Mandatory)](#3-technology-stack-mandatory)
4. [Code Generation Sequence](#4-code-generation-sequence)
5. [Module 1: Data Models (models.py)](#5-module-1-data-models)
6. [Module 2: Database Schema (aifya_schema.sql)](#6-module-2-database-schema)
7. [Module 3: Q-Afya EMR Adapter (qafya_adapter.py)](#7-module-3-q-afya-emr-adapter)
8. [Module 4: SHA Rules Engine (sha_engine.py + sha_rules.yaml)](#8-module-4-sha-rules-engine)
9. [Module 5: Clinical NLP Pipeline (nlp_engine.py)](#9-module-5-clinical-nlp-pipeline)
10. [Module 6: Discharge Summary Engine (discharge_engine.py)](#10-module-6-discharge-summary-engine)
11. [Module 7: FastAPI Application (main.py)](#11-module-7-fastapi-application)
12. [Module 8: Authentication & Security (auth.py)](#12-module-8-authentication--security)
13. [Module 9: Frontend — Clinician Console](#13-module-9-frontend-clinician-console)
14. [Module 10: Frontend — Billing Dashboard](#14-module-10-frontend-billing-dashboard)
15. [Module 11: Frontend — Admin Panel](#15-module-11-frontend-admin-panel)
16. [Module 12: Infrastructure (Docker + Config)](#16-module-12-infrastructure)
17. [Module 13: Testing Suite](#17-module-13-testing-suite)
18. [Cross-Cutting Concerns](#18-cross-cutting-concerns)
19. [Quality Gates](#19-quality-gates)
20. [Prompt Templates for Each Module](#20-prompt-templates-for-each-module)

---

## 1. PROJECT IDENTITY & NON-NEGOTIABLES

### What We Are Building

Aifya is a healthcare AI platform for the Kenyan health system that solves the KES 11 billion SHA claims rejection crisis. Phase 1 has **exactly four subsystems**:

| # | Subsystem | What It Does |
|---|-----------|-------------|
| 1 | **AI Ambient Scribe** | Doctor speaks → structured SOAP note with ICD-11 codes writes itself |
| 2 | **SHA Claims Intelligence Engine** | Deterministic rules catch every rejection reason before SHA submission |
| 3 | **Discharge Summary Generator** | Auto-synthesizes multi-encounter inpatient data into discharge summaries |
| 4 | **Q-Afya Integration Adapter** | Bidirectional sync with existing Q-Afya HMIS — read patients, write notes & claims |

### Non-Negotiable Rules

```
RULE 1: LLM extracts and summarizes. Rules engine validates. NEVER mix these.
RULE 2: No pharmacy module. No bed management. No HR. No scope creep.
RULE 3: Security (JWT + audit logging) ships BEFORE any other feature.
RULE 4: Every SHA rule has an ID, severity, message, and suggested fix.
RULE 5: Patient PII is NEVER stored in plaintext. pgcrypto + AES-256.
RULE 6: All code must handle Swahili, Sheng, and English code-switching.
RULE 7: Offline capability via IndexedDB queue is mandatory.
RULE 8: Every write to Q-Afya is logged in the audit trail.
RULE 9: Discharge summaries require 3-stage approval: Draft → Reviewed → Approved.
RULE 10: The system must degrade gracefully — if LLM is down, manual entry + rules engine still works.
```

---

## 2. ARCHITECTURE CONSTRAINTS

### Six-Layer Model (Enforce Strict Separation)

```
L1: Audio Capture      → Web Audio API + MediaRecorder (browser-native, NOT WebRTC)
L2: Transcription      → Whisper Large V3 + pyannote-audio 3.x (speaker diarization)
L3: Clinical NLP       → GPT-4o / Claude Sonnet + Pydantic validation
L4: SHA Rules Engine   → Python + YAML config (ZERO LLM, fully deterministic)
L5: Discharge Engine   → LLM summarization + template engine
L6: Q-Afya Bridge      → asyncpg database connector + HL7 adapter
```

### Data Flow (Every Code Module Must Follow This)

```
Audio → [L1] → [L2: Whisper+pyannote] → Diarized Transcript
     → [L3: LLM extraction] → ClinicalExtraction (Pydantic)
     → [L4: Rules Engine] → ScrubResult
     → [L6: Q-Afya Adapter] → Written to EMR
```

### Key Architectural Decisions to Enforce in Generated Code

- **Async everywhere**: All database operations, API calls, and I/O must use `async/await`. Use `asyncpg` for PostgreSQL, `httpx` for HTTP clients.
- **Pydantic as contract**: `ClinicalExtraction`, `ScrubResult`, `DischargeSummary` are the single source of truth. All components consume and produce these models. If data doesn't fit, it's rejected.
- **Config-driven rules**: SHA rules live in `sha_rules.yaml`, not hardcoded. Non-developers must be able to update rules when SHA policy changes.
- **Abstract adapter pattern**: The `EMRAdapter` ABC allows swapping Q-Afya for KenyaEMR, FunSoft, or Slade360 without touching core pipeline code.
- **Circuit breakers**: Q-Afya DB connection and LLM API calls must have circuit breaker patterns (5 failures / 60s → open → exponential backoff recovery).
- **Structured logging**: Use `structlog` with JSON output, correlation IDs, and request tracing. No `print()` statements.

---

## 3. TECHNOLOGY STACK (MANDATORY)

When generating code, use EXACTLY these technologies. Do not substitute.

### Backend
```
Python 3.12+
FastAPI (latest)
asyncpg (PostgreSQL async driver)
Pydantic v2 (data validation)
PyYAML (rules config)
OpenAI Python SDK (LLM calls)
python-jose[cryptography] (JWT)
passlib[bcrypt] (password hashing)
structlog (logging)
WeasyPrint (PDF generation)
whisper (ASR - openai-whisper or API)
pyannote.audio (speaker diarization)
circuitbreaker (circuit breaker pattern)
```

### Database
```
PostgreSQL 16+ with pgcrypto extension
SQLite (ICD-11 WHO database, read-only)
MinIO (S3-compatible object storage for audio)
```

### Frontend
```
Next.js 14 (App Router)
TypeScript (strict mode)
Tailwind CSS (no custom CSS files)
Zustand (state management - 2 stores only)
Dexie.js (IndexedDB for offline queue)
NextAuth.js (JWT auth integration)
Recharts (dashboard charts)
Lucide React (icons)
```

### Infrastructure
```
Docker + Docker Compose
Nginx (reverse proxy + TLS termination)
```

---

## 4. CODE GENERATION SEQUENCE

Generate modules in THIS order. Each module depends on the ones before it.

```
Step 1:  models.py                    — All Pydantic data models
Step 2:  aifya_schema.sql             — Database DDL
Step 3:  config.py                    — Environment config + settings
Step 4:  auth.py                      — JWT + RBAC middleware
Step 5:  qafya_adapter.py             — Q-Afya EMR integration
Step 6:  sha_rules.yaml               — SHA rule definitions
Step 7:  sha_engine.py                — Rules engine implementation
Step 8:  nlp_engine.py                — Clinical NLP extraction pipeline
Step 9:  discharge_engine.py          — Discharge summary generator
Step 10: main.py                      — FastAPI app tying everything together
Step 11: middleware.py                — Audit logging, CORS, error handlers
Step 12: docker-compose.yml           — Full infrastructure
Step 13: Frontend: layout + auth      — Next.js scaffold + login
Step 14: Frontend: Clinician Console  — Scribe + SOAP + SHA warnings
Step 15: Frontend: Billing Dashboard  — Claims queue + review + analytics
Step 16: Frontend: Admin Panel        — Users + audit + system health
Step 17: tests/                       — Full test suite
```

---

## 5. MODULE 1: DATA MODELS

### File: `app/models.py`

Generate ALL of the following Pydantic v2 models in a single file. These are the contract between every component.

```
MODELS TO GENERATE:
├── Enums
│   ├── Severity          (BLOCK, WARNING, INFO)
│   ├── EncounterType     (outpatient, inpatient, emergency)
│   ├── EncounterStatus   (in_progress, scribed, reviewed, finalized)
│   ├── ScrubStatus       (pending, passed, blocked, warnings_only, overridden)
│   ├── ClaimStatus       (submitted, under_review, approved, rejected, paid)
│   ├── DischargeStatus   (draft, reviewed, approved, sent_to_qafya)
│   └── UserRole          (clinician, billing_admin, facility_admin, superadmin)
│
├── Clinical Models
│   ├── VitalSign         (name, value, loinc_code, confidence: 0.0-1.0)
│   ├── Medication        (name, dose, route, frequency, duration, is_new: bool)
│   ├── Diagnosis         (name, icd11_suggested, icd11_validated, is_primary, confidence)
│   ├── LabOrder          (test_name, loinc_code, urgency)
│   ├── Procedure         (name, ichi_code, requires_preauth: bool)
│   └── ClinicalExtraction (master NLP output — chief_complaint, hpi, vitals[], 
│                            physical_exam, diagnoses[], lab_orders[], medications[],
│                            procedures[], disposition, warnings[], extraction_timestamp)
│
├── Claims Models
│   ├── RuleViolation     (rule_id, rule_name, severity, message, suggested_fix)
│   └── ScrubResult       (status, violations[], scrubbed_at, can_submit: bool)
│
├── Discharge Models
│   └── DischargeSummary  (patient_name, sha_member_no, admission_date, discharge_date,
│                           length_of_stay_days, admission/final diagnosis + ICD-11,
│                           clinical_narrative, procedures[], key_investigations[],
│                           discharge_medications[], condition_at_discharge,
│                           follow_up_plan, red_flags)
│
├── Auth Models
│   ├── UserCreate        (email, password, full_name, role, license_no)
│   ├── UserResponse      (id, email, full_name, role, is_active)
│   └── TokenResponse     (access_token, refresh_token, token_type, expires_in)
│
└── API Request/Response Models
    ├── TranscriptInput   (transcript: str)
    ├── ScrubRequest      (extraction, sha_status, sha_package, amount, encounter_date, 
    │                       encounter_type, has_preauth)
    ├── DischargeRequest  (admission_id, patient_id)
    ├── SyncNoteRequest   (qafya_encounter_id, soap_json)
    └── HealthResponse    (status, components: dict with per-service health)
```

### Critical Model Rules

- All models inherit from `BaseModel` (Pydantic v2)
- Use `Field(...)` with examples for documentation
- Confidence fields: `float = Field(ge=0.0, le=1.0, default=0.8)`
- Timestamps: `datetime = Field(default_factory=datetime.utcnow)`
- All string enums use `str, Enum` pattern for JSON serialization
- Add `model_config = ConfigDict(from_attributes=True)` for ORM compatibility

---

## 6. MODULE 2: DATABASE SCHEMA

### File: `database/aifya_schema.sql`

Generate PostgreSQL 16+ DDL with these exact tables:

```
TABLES:
├── users               — Auth + roles (clinician, billing_admin, facility_admin, superadmin)
│                         PII encrypted: email via pgcrypto
│                         license_no for KMPDB registration
│
├── aifya_encounters    — Core encounter table (enriched layer on top of Q-Afya)
│                         Links to Q-Afya via qafya_encounter_id + qafya_patient_id
│                         Stores: audio_file_ref, raw_transcript, diarized_transcript,
│                         soap_json (JSONB), icd11_primary, icd11_secondary[],
│                         confidence_scores (JSONB), nlp_warnings[],
│                         admission_id (groups inpatient encounters),
│                         status workflow, synced_to_qafya flag
│                         INDEXES on: patient_id, admission_id, encounter_date
│
├── claims              — SHA claim lifecycle
│                         scrub_status, scrub_violations (JSONB),
│                         override tracking (who, why, when),
│                         SHA submission refs + status,
│                         financials (billed, approved, paid),
│                         fhir_bundle (JSONB)
│                         INDEXES on: encounter_id, scrub_status
│
├── discharge_summaries — Structured discharge summaries
│                         admission/discharge dates, length_of_stay,
│                         admission/final diagnosis + ICD-11,
│                         clinical_narrative, procedures (JSONB),
│                         key_investigations (JSONB), discharge_meds (JSONB),
│                         3-stage status: draft → reviewed → approved → sent_to_qafya
│                         INDEXES on: admission_id
│
├── audit_log           — Append-only audit trail
│                         user_id, action, entity_type, entity_id, details (JSONB),
│                         ip_address (INET), created_at
│                         PROTECTED: CREATE RULE prevents DELETE and UPDATE
│
└── facility_config     — Per-facility settings (multi-tenant ready)
                          facility_id, facility_name, facility_level,
                          qafya_db_config (encrypted JSONB),
                          sha_facility_code
```

### Schema Rules

- `CREATE EXTENSION IF NOT EXISTS pgcrypto;`
- `CREATE EXTENSION IF NOT EXISTS "uuid-ossp";`
- All PKs: `UUID PRIMARY KEY DEFAULT uuid_generate_v4()`
- All timestamps: `TIMESTAMPTZ DEFAULT NOW()`
- PII columns use `pgp_sym_encrypt()` / `pgp_sym_decrypt()`
- Check constraints on all enum-like VARCHAR columns
- Audit log is immutable: `CREATE RULE audit_no_delete/update`

---

## 7. MODULE 3: Q-AFYA EMR ADAPTER

### File: `app/adapters/qafya_adapter.py`

Generate a complete bidirectional Q-Afya integration layer.

### Abstract Base (for multi-EMR support)

```python
class EMRAdapter(ABC):
    async def get_patient(identifier: str) -> Optional[dict]
    async def get_patient_encounters(patient_id: str, limit: int = 20) -> list[dict]
    async def get_encounter_labs(encounter_id: str) -> list[dict]
    async def get_encounter_medications(encounter_id: str) -> list[dict]
    async def write_clinical_note(encounter_id: str, soap_json: dict) -> bool
    async def write_discharge_summary(admission_id: str, summary: dict) -> bool
    async def check_sha_status(sha_member_no: str) -> dict
```

### QAfyaAdapter Implementation Requirements

```
READ OPERATIONS (parameterized queries, SQL injection safe):
├── get_patient()              — FROM patient_registration WHERE national_id=$1 OR insurance_no=$1
├── get_patient_encounters()   — FROM patient_encounters WHERE patient_id=$1 ORDER BY date DESC
├── get_encounter_labs()       — FROM lab_results WHERE encounter_id=$1
├── get_encounter_medications()— FROM prescriptions WHERE encounter_id=$1
└── check_sha_status()         — FROM patient_registration WHERE insurance_no=$1

WRITE OPERATIONS (with audit trail):
├── write_clinical_note()      — UPDATE patient_encounters SET clinical_notes=$2, 
│                                 diagnosis_code=$3, last_modified_by='AIFYA_SYSTEM'
└── write_discharge_summary()  — INSERT INTO discharge_summaries ... ON CONFLICT DO UPDATE

CONNECTION MANAGEMENT:
├── asyncpg connection pool (min=2, max=10)
├── Circuit breaker (5 failures / 60s → open → exponential backoff)
├── Health check method returning latency + last_success timestamp
└── Schema validation on startup (warn if expected tables missing)

CONCURRENCY:
├── Optimistic concurrency on writes (check last_modified_at before writing)
└── Connection pool exhaustion → queue with timeout, not crash
```

### Code Quality Requirements

- Every method has docstring explaining what Q-Afya table it touches
- All queries use `$1, $2` parameterized placeholders (NEVER f-strings)
- Structured logging with `structlog` on every operation
- Error handling returns `None` or `False` on failure, never raises to caller
- Configuration via `QAfyaConfig` dataclass with env var fallbacks

---

## 8. MODULE 4: SHA RULES ENGINE

### Files: `app/rules/sha_engine.py` + `app/rules/sha_rules.yaml`

### sha_rules.yaml Structure

```yaml
rules:
  membership:
    - id: SHA-R1
      name: "Member Status"
      severity: BLOCK
      message: "Patient SHA status must be active"
      fix: "Verify SHA card on portal or call SHA helpline"

  preauth:
    - id: SHA-R2a
      name: "Surgical Pre-Auth"
      severity: BLOCK
      applies_to: { procedure_categories: [surgical, invasive] }
      message: "Surgical procedures require SHA pre-authorization"
      fix: "Submit pre-auth request via SHA portal before procedure"
    - id: SHA-R2b
      name: "Imaging Pre-Auth (>KES 5K)"
      severity: BLOCK
      applies_to: { procedure_categories: [imaging], amount_min: 5000 }
    - id: SHA-R2c
      name: "Inpatient Pre-Auth (>48hrs)"
      severity: BLOCK
      applies_to: { encounter_type: inpatient, los_min_hours: 48 }

  clinical_evidence:
    - id: SHA-R3a  → Hypertension: ICD-11 BA00-BA02,JA24 → require LOINC 85354-9 (BP)
    - id: SHA-R3b  → Diabetes: ICD-11 5A10-5A14 → require LOINC 2339-0 or 4548-4
    - id: SHA-R3c  → Malaria: ICD-11 1F40-1F45 → require LOINC 32700-7 or 51587-4
    - id: SHA-R3d  → Pneumonia: ICD-11 CA40-CA42 → require physical_exam field (WARNING)

  coding:
    - id: SHA-R4   → Primary diagnosis MUST have validated ICD-11 code

  tariff:
    - id: SHA-R6   → Amount exceeds gazetted tariff (WARNING, Phase 2 full impl)

  duplicate:
    - id: SHA-R7   → Same patient + ICD-11 + date = BLOCK

  timeliness:
    - id: SHA-R9   → >25 days = WARNING, >30 days = BLOCK
```

### SHARulesEngine Class Requirements

```python
class SHARulesEngine:
    def __init__(self, config_path: str = "sha_rules.yaml")
    
    def scrub(
        self,
        extraction: ClinicalExtraction,    # From NLP pipeline
        patient_sha_status: str,           # From Q-Afya
        patient_sha_package: str,          # PHF, SHIF, ECCIF
        amount_billed: float,              # KES
        encounter_date: datetime,
        encounter_type: str = "outpatient",
        has_preauth: bool = False,
        existing_claims: list = None       # For duplicate detection
    ) -> ScrubResult
```

### Engine Rules

- YAML is loaded once at init, cached in memory
- Each rule check is a private method: `_check_membership()`, `_check_preauth()`, `_check_evidence()`, `_check_duplicates()`, `_check_timeliness()`
- Evidence rules use ICD-11 prefix matching against required LOINC codes
- Result: `blocked` if ANY violation has severity=BLOCK, `warnings_only` if only WARNINGs, `passed` if clean
- `can_submit = True` only when status != "blocked"
- Every violation includes `suggested_fix` text (user-facing, actionable)
- Engine NEVER calls an LLM. It is 100% deterministic.

---

## 9. MODULE 5: CLINICAL NLP PIPELINE

### File: `app/nlp/nlp_engine.py`

### Pipeline Stages to Implement

```
Stage 1: Audio Quality Gate
  - Check SNR (reject < 10dB)
  - Check duration (reject < 5s)
  - Check silence ratio (warn if > 50%)

Stage 2: Transcription (Whisper)
  - Whisper Large V3 (primary)
  - Fallback: Whisper Medium → Whisper API
  - Output: raw text transcript

Stage 3: Speaker Diarization (pyannote)
  - Label segments: [CLINICIAN] and [PATIENT]
  - Output: diarized transcript

Stage 4: LLM Clinical Extraction (Two-Pass)
  - Pass 1 (High recall): Extract all possible clinical entities
  - Pass 2 (High precision): Validate, structure, resolve conflicts
  - Model: GPT-4o with JSON mode enforced
  - Temperature: 0.0 (deterministic)

Stage 5: ICD-11 Validation
  - Direct code lookup in SQLite WHO ICD-11 database
  - Fallback: fuzzy name search (LIKE '%diagnosis%')
  - Unvalidated codes → add to warnings[]

Stage 6: Confidence Calibration
  - Adjust LLM confidence scores based on field type
  - Vitals: typically overconfident (scale × 0.9)
  - Diagnoses: typically underconfident (scale × 1.1, cap at 1.0)

Stage 7: Output
  - Return validated ClinicalExtraction Pydantic model
  - Reject if Pydantic validation fails (return error, not crash)
```

### LLM System Prompt (Include EXACTLY This)

The system prompt MUST include:
- Expert Clinical Informatician persona (Kenyan Level 4/5 hospital)
- Swahili/Sheng medical term dictionary (200+ terms):
  - kichwa inaniuma = headache, homa = fever, tumbo = abdomen
  - kifua = chest, kupumua vibaya = dyspnea, damu = blood
  - mimba = pregnancy, kuharisha = diarrhea, kutapika = vomiting
  - presha = blood pressure, sukari = diabetes, malaria = malaria
  - mwili kuuma = body aches, mgongo = back
- ZERO HALLUCINATION rule: only extract explicitly stated information
- NEGATION detection: "sina homa" = DENIES fever (NOT has fever)
- Speaker attribution: patient-reported = subjective, clinician-observed = objective
- Confidence scoring: 0.0-1.0, <0.7 for unclear/inferred
- JSON-only output: no markdown, no preamble, no explanation

### Retry Logic

```
LLM API calls:
  - 3 attempts with exponential backoff (1s, 2s, 4s)
  - Timeout: 30s per call
  - On permanent failure: return partial extraction with warnings
  - Dead letter queue for failed extractions (store transcript for manual processing)
```

---

## 10. MODULE 6: DISCHARGE SUMMARY ENGINE

### File: `app/discharge/discharge_engine.py`

### DischargeEngine Class

```python
class DischargeEngine:
    def __init__(self, db_pool, qafya: QAfyaAdapter)
    
    async def generate(self, admission_id: str, patient_id: str) -> DischargeSummary
```

### Generation Pipeline

```
1. GATHER (from both Aifya DB and Q-Afya):
   - All encounters for this admission_id (ordered chronologically)
   - All lab results for each encounter (from Q-Afya lab_results table)
   - All medications for each encounter (from Q-Afya prescriptions table)
   - Patient demographics (from Q-Afya patient_registration)

2. SYNTHESIZE (LLM):
   - Build structured payload: patient, encounters[], lab_results[], medications[]
   - LLM prompt: "Senior physician writing discharge summary at Kenyan hospital"
   - Output: clinical_narrative, condition_at_discharge, follow_up_plan, red_flags
   - Rules: tell the STORY, use specific numbers, document diagnosis changes,
            follow-up must include when/where/what tests, red flags must be 
            patient-readable (no jargon), keep under 500 words

3. STRUCTURE:
   - Populate DischargeSummary Pydantic model with all fields
   - Compute length_of_stay_days from admission/discharge dates
   - Extract primary diagnoses from first and last encounters
   - Group labs by test name with temporal trend data
   - Get most recent prescription of each drug for discharge meds

4. VALIDATE:
   - All SHA-required sections must be present
   - Run discharge through rules engine for inpatient claim compliance
   - Flag missing sections as warnings

5. PDF GENERATION:
   - WeasyPrint with HTML template
   - Hospital letterhead support (logo, address, phone)
   - Professional typography and layout
   - Print-ready A4 format

6. APPROVAL WORKFLOW:
   - Status: draft → reviewed (attending) → approved (dept head) → sent_to_qafya
   - Each transition: log user_id + timestamp in audit trail
   - Only "approved" status triggers Q-Afya sync
```

---

## 11. MODULE 7: FASTAPI APPLICATION

### File: `app/main.py`

### Endpoint Map (Generate ALL of These)

```
PATIENT ENDPOINTS:
  GET  /api/v1/patients/{identifier}         → Lookup from Q-Afya by national_id or SHA#
  GET  /api/v1/patients/{id}/encounters      → Patient encounter history

SCRIBE ENDPOINTS:
  POST /api/v1/scribe/process                → Full pipeline: audio → note → scrub
  POST /api/v1/scribe/extract                → Extract from diarized transcript text
  POST /api/v1/scribe/addendum               → Append additional notes to encounter

CLAIMS ENDPOINTS:
  POST /api/v1/claims/scrub                  → Run rules engine on extraction
  GET  /api/v1/claims                        → Claims queue (filterable)
  GET  /api/v1/claims/{id}                   → Single claim detail
  POST /api/v1/claims/{id}/override          → Override warning (billing_admin only)
  POST /api/v1/claims/{id}/submit            → Submit to SHA (Phase 2)

DISCHARGE ENDPOINTS:
  POST /api/v1/discharge/generate            → Generate discharge summary
  GET  /api/v1/discharge/{id}                → Get discharge summary
  PUT  /api/v1/discharge/{id}/status         → Update workflow status
  GET  /api/v1/discharge/{id}/pdf            → Download PDF

SYNC ENDPOINTS:
  POST /api/v1/sync/clinical-note            → Write note to Q-Afya
  POST /api/v1/sync/discharge-summary        → Write discharge to Q-Afya

AUTH ENDPOINTS:
  POST /api/v1/auth/register                 → Create user
  POST /api/v1/auth/login                    → Get JWT tokens
  POST /api/v1/auth/refresh                  → Refresh access token
  POST /api/v1/auth/logout                   → Blacklist token

ADMIN ENDPOINTS:
  GET  /api/v1/admin/users                   → List users
  GET  /api/v1/admin/audit-log               → Audit log (searchable)
  GET  /api/v1/admin/sync-status             → Q-Afya connection status

SYSTEM ENDPOINTS:
  GET  /health                               → Per-component health check
  GET  /docs                                 → Auto-generated OpenAPI docs
```

### Application Lifecycle

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect Aifya DB, connect Q-Afya, init rules engine, init discharge engine
    # Include health check for each component
    yield
    # Shutdown: close all pools gracefully
```

### Middleware Stack

```
1. CORS (frontend origin only)
2. Audit logging (every request → audit_log table)
3. Request ID injection (correlation ID for tracing)
4. Error handling (structured JSON errors, never expose stack traces)
5. Rate limiting (100 req/min per user for scrub endpoint)
```

---

## 12. MODULE 8: AUTHENTICATION & SECURITY

### File: `app/auth/auth.py`

### JWT Configuration

```
Access token:  15 minutes TTL, HS256
Refresh token: 7 days TTL, HS256, stored hash in DB
Token payload: { sub: user_id, role: user_role, facility_id, exp, iat, jti }
Blacklisting:  On logout, add jti to blacklist (Redis or DB table)
```

### RBAC Matrix

```
                     clinician  billing_admin  facility_admin  superadmin
Patient lookup          ✓            ✓              ✓              ✓
Scribe endpoints        ✓            ✗              ✗              ✓
Claims scrub            ✓            ✓              ✗              ✓
Claims override         ✗            ✓              ✗              ✓
Discharge generate      ✓            ✗              ✗              ✓
Discharge approve       ✓            ✗              ✓              ✓
User management         ✗            ✗              ✓              ✓
Audit log view          ✗            ✗              ✓              ✓
System health           ✗            ✗              ✓              ✓
```

### Security Implementation Checklist

```
[ ] Password hashing: bcrypt with salt rounds=12
[ ] PII encryption: pgcrypto pgp_sym_encrypt/decrypt with AES-256
[ ] TLS 1.3 on all connections (including Aifya ↔ Q-Afya database)
[ ] Audit log: append-only, cryptographic hash chain (each entry hashes previous)
[ ] Audio access: requires JWT with audio_access scope
[ ] Patient consent: stored with version tracking, re-consent on changes
[ ] Audio retention: MinIO lifecycle policy, auto-delete after 90 days
[ ] De-identified LLM calls: strip patient names/IDs before sending to LLM API
[ ] Breach detection: alert on bulk lookups, after-hours access patterns
[ ] Data export/deletion: endpoints for DPA 2019 data subject rights
```

---

## 13. MODULE 9: FRONTEND — CLINICIAN CONSOLE

### Directory: `frontend/app/clinician/`

### Components to Generate

```
PatientBanner
├── Display: patient name, SHA member number, status badge, benefit cap
├── Data source: GET /api/v1/patients/{identifier}
├── SHA status: green (active), red (inactive/expired), amber (pending)
└── Prominent display of insurance expiry date

ConsentCapture
├── Modal dialog shown before first audio recording per patient
├── Checkbox: "Patient has given verbal consent for audio recording"
├── Timestamp + clinician_id stored with encounter
├── One-time per patient (stored at patient level, not encounter)
└── Cannot proceed to recording without consent

AmbientScribeWidget
├── CRITICAL: This is the centerpiece of the clinician experience
├── Recording: MediaRecorder API with opus codec
│   ├── Single tap to start/stop (large, obvious button)
│   ├── Pulsing red indicator during recording
│   ├── Audio level meter via Web Audio API AnalyserNode
│   └── Visual waveform showing audio is captured
├── Status machine: idle → recording → transcribing → extracting → ready
├── Progress: show each stage with estimated time remaining
└── Error state: friendly message + manual entry fallback

LiveTranscriptPanel
├── WebSocket connection to Whisper streaming endpoint
├── Text appears in real-time as clinician speaks
├── [CLINICIAN] labels in blue, [PATIENT] labels in green
├── Auto-scroll to bottom as new text arrives
├── Editable: clinician can correct transcript before extraction
└── "Looks good — Extract Note" button at bottom

StructuredSOAPNote
├── Auto-populates from ClinicalExtraction after processing
├── Sections: Subjective, Objective, Assessment, Plan
├── Each field is EDITABLE (clinician can override AI)
├── Confidence badges: green (>0.8), amber (0.5-0.8), red (<0.5)
├── Low-confidence fields highlighted with transcript excerpt for context
├── ICD-11 code shown with validated/unvalidated status
├── Medication table with drug, dose, route, frequency, duration
└── "Finalize & Scrub" button triggers SHA rules engine

InlineSHAWarnings
├── NOT toast notifications — inline next to the relevant SOAP section
├── BLOCK violations: red card with rule ID, message, suggested fix
├── WARNING violations: amber card with message + fix
├── Each warning is actionable: fix button scrolls to relevant field
├── Violations clear in real-time as clinician fixes the note
└── "All Clear ✓" indicator when no violations remain

DischargeSummaryPanel (inpatient encounters only)
├── "Generate Discharge Summary" button (visible for inpatient admissions)
├── Shows loading state during generation (10-15s typical)
├── Rendered summary with all sections editable
├── "Download PDF" button → WeasyPrint-generated PDF
├── Status workflow buttons: Submit for Review → Approve → Sync to Q-Afya
└── Approval chain visible: who reviewed, who approved, timestamps
```

### Zustand Store: `useConsultationStore`

```typescript
interface ConsultationState {
  // Patient
  patient: Patient | null;
  patientLoading: boolean;
  
  // Recording
  isRecording: boolean;
  audioBlob: Blob | null;
  recordingDuration: number;
  
  // Transcript
  transcript: string;
  isTranscribing: boolean;
  
  // Extraction
  extraction: ClinicalExtraction | null;
  isExtracting: boolean;
  
  // Scrub
  scrubResult: ScrubResult | null;
  
  // Status
  encounterStatus: 'idle' | 'recording' | 'transcribing' | 'extracting' | 'scrubbed' | 'finalized';
  
  // Actions
  lookupPatient: (identifier: string) => Promise<void>;
  startRecording: () => void;
  stopRecording: () => void;
  extractNote: () => Promise<void>;
  scrubClaim: () => Promise<void>;
  updateExtraction: (field: string, value: any) => void;
  finalizeAndSync: () => Promise<void>;
}
```

---

## 14. MODULE 10: FRONTEND — BILLING DASHBOARD

### Directory: `frontend/app/billing/`

### Components to Generate

```
RevenueDashboardCards
├── Card 1: "Revenue Protected" — KES total saved from prevented rejections (green)
├── Card 2: "Rejection Rate" — current vs. historical with trend arrow (↓ = good)
├── Card 3: "Claims This Month" — total submitted, with pass/warn/block breakdown
├── Card 4: "Avg Processing Time" — from encounter to claim submission
├── Data source: aggregate queries on claims table
├── Sparkline charts under each card showing 30-day trend
└── Recharts for visualization

ClaimsQueueTable
├── Columns: Patient, Clinician, Date, ICD-11 (with tooltip), Amount (KES), Status, Actions
├── Status badges: green (passed), amber (warnings_only), red (blocked), blue (overridden)
├── Filters: scrub_status, clinician, department, date range
├── Sorting: any column, default by date DESC
├── Pagination: 25 per page with page navigation
├── Row click → opens ClaimReviewDrawer
└── Bulk actions: "Submit All Passed" button

ClaimReviewDrawer
├── Slide-out panel from right side
├── Header: patient name, encounter date, total amount
├── Violations section: each violation as expandable card
│   ├── Rule ID badge (SHA-R3a, etc.)
│   ├── Severity badge (BLOCK / WARNING)
│   ├── Human-readable message
│   ├── Suggested fix (highlighted, actionable)
│   └── Link to relevant SOAP section in encounter
├── Override section (billing_admin only, WARNING violations only):
│   ├── Mandatory justification textarea (min 20 characters)
│   ├── "Override & Submit" button (red, requires confirmation)
│   └── Override creates audit log entry
├── BLOCK violations: no override button, must fix at source
└── Actions: "Send Back to Clinician" with comment, "Submit to SHA"

DischargeClaimsPanel
├── Separate tab for inpatient claims
├── Higher-value claims (KES 50K-500K+) get priority visibility
├── Shows discharge summary status: draft/reviewed/approved
├── Length of stay with pre-auth requirement indicator (>48hrs)
└── "Review Discharge Summary" opens inline viewer
```

### Zustand Store: `useBillingStore`

```typescript
interface BillingState {
  claims: Claim[];
  claimsLoading: boolean;
  filters: {
    status: ScrubStatus | null;
    clinician: string | null;
    dateRange: [Date, Date] | null;
    department: string | null;
  };
  selectedClaim: Claim | null;
  drawerOpen: boolean;
  
  dashboardStats: {
    totalProtected: number;     // KES saved
    rejectionRate: number;      // percentage
    claimsThisMonth: number;
    avgProcessingTime: number;  // hours
    trends: { date: string; value: number }[];
  };
  
  // Actions
  fetchClaims: () => Promise<void>;
  applyFilter: (key: string, value: any) => void;
  selectClaim: (id: string) => void;
  overrideClaim: (id: string, justification: string) => Promise<void>;
  submitClaim: (id: string) => Promise<void>;
  fetchDashboardStats: () => Promise<void>;
}
```

---

## 15. MODULE 11: FRONTEND — ADMIN PANEL

### Directory: `frontend/app/admin/`

### Components to Generate

```
UserManagement
├── User table: name, email, role, active status, created date
├── Create user modal: email, name, role dropdown, license_no (clinicians)
├── Edit user: change role, activate/deactivate
├── NEVER allow password viewing — only reset
└── Role-based: only facility_admin and superadmin can access

AuditLogViewer
├── Searchable, filterable audit log
├── Columns: timestamp, user, action, entity, IP address
├── Filters: user, action type, date range, entity type
├── Detail expansion: shows full JSONB details for each entry
├── Export to CSV for compliance reporting
└── NO deletion capability (append-only enforced at DB level)

QAfyaSyncStatus
├── Real-time connection monitor
├── Status: connected/disconnected with last-check timestamp
├── Latency graph (last 24 hours)
├── Failed sync queue: encounters/notes awaiting sync
├── "Retry Failed Syncs" button
└── Schema validation status: expected vs actual tables

SystemHealth
├── Per-component status cards:
│   ├── Aifya Database: connected, latency, pool utilization
│   ├── Q-Afya Database: connected, latency, last successful read
│   ├── Whisper Service: available, model loaded, GPU utilization
│   ├── MinIO Storage: connected, space used/available
│   └── LLM API: reachable, response time, circuit breaker status
├── SLO dashboard: p99 latency, uptime %, extraction failure rate
└── Alert history: recent SLO breaches with timestamps
```

---

## 16. MODULE 12: INFRASTRUCTURE

### docker-compose.yml

```yaml
# Generate a complete Docker Compose file with:
services:
  aifya-api:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://aifya:${DB_PASSWORD}@aifya-db:5432/aifya
      - QAFYA_DB_HOST=${QAFYA_DB_HOST}
      - QAFYA_DB_PORT=${QAFYA_DB_PORT}
      - QAFYA_DB_NAME=${QAFYA_DB_NAME}
      - QAFYA_DB_USER=${QAFYA_DB_USER}
      - QAFYA_DB_PASSWORD=${QAFYA_DB_PASSWORD}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - JWT_SECRET=${JWT_SECRET}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      - MINIO_ENDPOINT=minio:9000
      - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
      - MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
    depends_on: [aifya-db, minio]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]

  aifya-db:
    image: postgres:16
    volumes: ["aifya_pgdata:/var/lib/postgresql/data"]
    environment:
      - POSTGRES_DB=aifya
      - POSTGRES_USER=aifya
      - POSTGRES_PASSWORD=${DB_PASSWORD}

  minio:
    image: minio/minio
    command: server /data --console-address ":9001"
    volumes: ["minio_data:/data"]

  aifya-frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [aifya-api]

  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/certs:/etc/nginx/certs
    depends_on: [aifya-api, aifya-frontend]
```

### Additional Config Files to Generate

```
backend/Dockerfile           — Python 3.12-slim, pip install, uvicorn entrypoint
backend/requirements.txt     — All Python dependencies pinned
frontend/Dockerfile          — Node 20-alpine, npm install, next build + start
nginx/nginx.conf             — Reverse proxy, TLS termination, API routing
.env.example                 — All environment variables documented
backend/alembic.ini          — Database migration config
backend/alembic/             — Migration scripts directory
```

---

## 17. MODULE 13: TESTING SUITE

### Test Files to Generate

```
tests/
├── test_models.py           — Pydantic model validation (valid + invalid inputs)
├── test_sha_engine.py       — ALL 12 rules with 50+ parameterized test cases
│   ├── test_r1_membership_active → passes
│   ├── test_r1_membership_expired → BLOCK
│   ├── test_r2a_surgical_no_preauth → BLOCK
│   ├── test_r2a_surgical_with_preauth → passes
│   ├── test_r3a_hypertension_no_bp → BLOCK
│   ├── test_r3a_hypertension_with_bp → passes
│   ├── test_r3c_malaria_no_test → BLOCK
│   ├── test_r3c_malaria_with_test → passes
│   ├── test_r4_no_icd11 → BLOCK
│   ├── test_r7_duplicate → BLOCK
│   ├── test_r7_no_duplicate → passes
│   ├── test_r9_within_window → passes
│   ├── test_r9_approaching_deadline → WARNING
│   ├── test_r9_past_deadline → BLOCK
│   └── ... (50+ total)
├── test_qafya_adapter.py    — Mock DB tests for all read/write operations
├── test_nlp_engine.py       — Extraction accuracy with golden transcripts
│   ├── test_english_consultation
│   ├── test_swahili_consultation
│   ├── test_sheng_codeswitching
│   ├── test_negation_detection ("sina homa" → no fever diagnosis)
│   └── test_low_confidence_flagging
├── test_discharge_engine.py — Multi-encounter synthesis tests
├── test_api_endpoints.py    — All endpoints with httpx async client
├── test_auth.py             — JWT generation, validation, RBAC, refresh, blacklist
└── test_audit.py            — Audit log integrity, append-only verification
```

### Testing Standards

```
Framework: pytest + pytest-asyncio
DB testing: testcontainers (PostgreSQL in Docker for integration tests)
API testing: httpx.AsyncClient
Mocking: unittest.mock for LLM API calls, Q-Afya DB
Coverage: >90% for rules engine, >80% for API layer
NLP eval: custom harness with golden dataset of 20+ annotated transcripts
```

---

## 18. CROSS-CUTTING CONCERNS

### Apply These to EVERY Module

```
ERROR HANDLING:
├── Never expose stack traces to API consumers
├── Structured error responses: { "error": str, "code": str, "details": dict }
├── LLM failures → degrade gracefully, never crash
├── Q-Afya connection failures → use circuit breaker, fall back to cached data
└── Pydantic validation errors → return 422 with field-level error details

LOGGING:
├── Use structlog throughout (NEVER print())
├── JSON format for machine parseability
├── Include: correlation_id, user_id, action, duration_ms, status
├── Log levels: DEBUG (dev only), INFO (operations), WARNING (degraded), ERROR (failures)
└── Sensitive data NEVER logged (patient names, national IDs, audio content)

CONFIGURATION:
├── All secrets from environment variables (NEVER in code)
├── .env.example with every variable documented
├── Default values only for non-sensitive settings
├── Pydantic Settings model for validated config loading
└── Separate configs for: development, testing, production

TYPE SAFETY:
├── Python: type hints on EVERY function signature
├── TypeScript: strict mode, no any types, interfaces for all API responses
├── Pydantic: validate ALL inputs and outputs at API boundaries
└── SQL: parameterized queries only ($1, $2), NEVER string formatting

DOCUMENTATION:
├── Every function has a docstring explaining what it does and why
├── Every API endpoint has FastAPI description + response_model
├── Every SHA rule has inline comments explaining the regulation source
├── README.md for each major directory
└── OpenAPI auto-docs at /docs
```

---

## 19. QUALITY GATES

Before considering any module complete, verify:

```
[ ] All functions have type hints and docstrings
[ ] All API endpoints have request/response models
[ ] All database queries are parameterized (no SQL injection)
[ ] All PII fields use pgcrypto encryption
[ ] All operations are logged to audit trail
[ ] All LLM calls have retry logic + timeout + circuit breaker
[ ] All Q-Afya operations have error handling + fallback
[ ] Frontend components handle loading, error, and empty states
[ ] Offline queue (Dexie.js) works for encounter submission
[ ] Tests exist and pass for the module
[ ] No print() statements (structlog only)
[ ] No hardcoded secrets (environment variables only)
[ ] No f-string SQL queries (parameterized only)
[ ] Swahili/Sheng medical terms handled in NLP pipeline
[ ] SHA rule violations include suggested_fix text
```

---

## 20. PROMPT TEMPLATES FOR EACH MODULE

Use these templates when generating individual modules. Copy the relevant template, paste it as the prompt, and generate code.

---

### PROMPT 1: Data Models

```
Generate the complete app/models.py file for the Aifya Health Platform.

Context: Aifya is a healthcare AI platform for Kenyan hospitals. These Pydantic v2 
models are the contract between all components: NLP pipeline, SHA rules engine, 
discharge summary generator, Q-Afya EMR adapter, and FastAPI endpoints.

Requirements:
- Python 3.12+, Pydantic v2 with ConfigDict
- All models listed in the specification (see above: Enums, Clinical Models, 
  Claims Models, Discharge Models, Auth Models, API Models)
- Field validators where appropriate (e.g., confidence 0.0-1.0)
- model_config = ConfigDict(from_attributes=True) for ORM compat
- Comprehensive docstrings on every model
- Example values in Field() for OpenAPI documentation

Generate the complete file. No abbreviations. No TODOs. Production-ready.
```

---

### PROMPT 2: Database Schema

```
Generate the complete database/aifya_schema.sql file for PostgreSQL 16+.

Context: Aifya Health Platform database. Sits alongside Q-Afya HMIS database.
Stores AI-generated clinical content, SHA claim scrub results, audit trails.

Requirements:
- Enable pgcrypto and uuid-ossp extensions
- Tables: users, aifya_encounters, claims, discharge_summaries, audit_log, 
  facility_config
- All PKs: UUID with uuid_generate_v4()
- All timestamps: TIMESTAMPTZ DEFAULT NOW()
- CHECK constraints on all enum VARCHAR columns
- Appropriate indexes on foreign keys and common query patterns
- audit_log: CREATE RULE to prevent DELETE and UPDATE
- Comments on each table and critical columns

Generate the complete SQL file. No abbreviations. No TODOs. Ready to run.
```

---

### PROMPT 3: Q-Afya Adapter

```
Generate the complete app/adapters/qafya_adapter.py file.

Context: Bidirectional integration with Q-Afya HMIS (by QET Systems) at Mary Help 
Hospital. Q-Afya is a web-based HMIS using PostgreSQL. We read patient data and 
write clinical notes + discharge summaries back.

Requirements:
- EMRAdapter abstract base class (for future KenyaEMR, FunSoft support)
- QAfyaConfig dataclass with connection settings
- QAfyaAdapter with asyncpg connection pool (min=2, max=10)
- All 7 abstract methods implemented with parameterized SQL queries
- Circuit breaker on connection (5 failures / 60s threshold)
- Optimistic concurrency on writes (check last_modified_at)
- Schema validation on startup
- structlog logging on every operation
- Error handling: return None/False on failure, never raise

Generate the complete file. Production-grade. Every method fully implemented.
```

---

### PROMPT 4: SHA Rules Engine

```
Generate two files:
1. app/rules/sha_rules.yaml — Complete SHA rule definitions
2. app/rules/sha_engine.py — Rules engine implementation

Context: Deterministic SHA claims validation engine. Catches rejection causes 
before claim submission. ZERO LLM involvement. Config-driven via YAML.

Rules to implement: SHA-R1 (membership), SHA-R2a/b/c (pre-auth), 
SHA-R3a/b/c/d (clinical evidence), SHA-R4 (ICD-11), SHA-R6 (tariff), 
SHA-R7 (duplicate), SHA-R9 (timeliness).

Evidence rules use ICD-11 prefix matching against required LOINC codes.
Result statuses: passed, blocked, warnings_only.
Every violation: rule_id, rule_name, severity, message, suggested_fix.

Generate both files completely. Every rule implemented. Every edge case handled.
```

---

### PROMPT 5: NLP Pipeline

```
Generate the complete app/nlp/nlp_engine.py file.

Context: Clinical NLP pipeline for Kenyan hospital consultations. Converts 
diarized transcripts (English/Swahili/Sheng with code-switching) into 
structured ClinicalExtraction models with validated ICD-11 codes.

Pipeline: Audio quality gate → Whisper transcription → pyannote diarization → 
Two-pass LLM extraction → ICD-11 validation (SQLite) → Confidence calibration → 
Pydantic output.

LLM prompt must include: Kenyan clinical context, 200+ Swahili/Sheng medical 
terms, zero hallucination rule, negation detection, speaker attribution, 
confidence scoring, JSON-only output.

Retry: 3 attempts, exponential backoff, 30s timeout, dead letter queue.
Model cascade: Whisper large-v3 → medium → API fallback.

Generate the complete file. Full Swahili medical dictionary. Production-ready.
```

---

### PROMPT 6: Discharge Engine

```
Generate the complete app/discharge/discharge_engine.py file.

Context: Generates discharge summaries for inpatient admissions at Mary Help 
Hospital. Synthesizes multi-encounter data (clerking, ward rounds, labs, meds, 
procedures) into comprehensive summaries serving as SHA claim justification.

Pipeline: Gather from both DBs → LLM synthesize narrative → Structure into 
DischargeSummary model → Validate SHA sections → Generate PDF.

Narrative rules: tell the story, use specific numbers, document diagnosis changes,
patient-readable follow-up and red flags, <500 words.

Include: PDF generation with WeasyPrint, lab trend grouping, medication 
deduplication, 3-stage approval workflow (draft → reviewed → approved).

Generate the complete file. Full implementation. Production-ready.
```

---

### PROMPT 7: FastAPI Application

```
Generate the complete app/main.py file for the Aifya FastAPI application.

Context: Core API server that ties together all Aifya subsystems. Serves the 
Clinician Console, Billing Dashboard, and Admin Panel frontends.

Endpoints: All patient, scribe, claims, discharge, sync, auth, admin, and 
system endpoints as specified. Every endpoint with proper request/response models,
authentication dependency, role-based access, and error handling.

Lifespan: connect Aifya DB, Q-Afya, init engines on startup; clean shutdown.
Middleware: CORS, audit logging, request ID, error handling, rate limiting.

Generate the complete file. All endpoints. All middleware. Production-ready.
```

---

### PROMPT 8: Frontend — Clinician Console

```
Generate the complete Next.js 14 (App Router + TypeScript) frontend for the 
Aifya Clinician Console.

Components needed:
- PatientBanner (SHA status, benefit cap, insurance expiry)
- ConsentCapture (modal, one-time per patient)
- AmbientScribeWidget (MediaRecorder, audio levels, status machine)
- LiveTranscriptPanel (WebSocket, [CLINICIAN]/[PATIENT] color labels)
- StructuredSOAPNote (editable, confidence badges, ICD-11 display)
- InlineSHAWarnings (inline violations, NOT toasts, actionable fixes)
- DischargeSummaryPanel (generate, edit, approve, PDF download)

State: Zustand useConsultationStore with all fields specified.
Styling: Tailwind CSS only. Medical blue (#1A5276) primary. Clean, professional.
Offline: Dexie.js IndexedDB queue for encounter data.

Generate all component files. Fully functional. Beautiful UX.
```

---

### PROMPT 9: Frontend — Billing Dashboard

```
Generate the complete Next.js 14 Billing Dashboard for Aifya.

Components needed:
- RevenueDashboardCards (4 KPI cards with sparklines using Recharts)
- ClaimsQueueTable (filterable, sortable, paginated, status badges)
- ClaimReviewDrawer (slide-out, violations, override with justification)
- DischargeClaimsPanel (high-value inpatient claims)

State: Zustand useBillingStore with filters, stats, actions.
Styling: Tailwind CSS. Data-dense but readable. KES currency formatting.
Charts: Recharts for trends. Green for protected revenue, red for rejections.

Generate all component files. Production-ready. Billing staff will love it.
```

---

### PROMPT 10: Testing Suite

```
Generate the complete test suite for the Aifya Health Platform.

Files needed:
- tests/test_models.py (Pydantic validation)
- tests/test_sha_engine.py (50+ parameterized rule tests)
- tests/test_qafya_adapter.py (mocked DB operations)
- tests/test_nlp_engine.py (golden transcript eval)
- tests/test_discharge_engine.py (multi-encounter synthesis)
- tests/test_api_endpoints.py (all endpoints with httpx)
- tests/test_auth.py (JWT, RBAC, refresh, blacklist)
- tests/conftest.py (shared fixtures, test database, mock LLM)

Framework: pytest + pytest-asyncio. Mocking: unittest.mock.
SHA rules: 100% rule coverage. API: >80% coverage.

Generate all test files. Comprehensive. Edge cases covered.
```

---

## FINAL NOTES FOR AI CODE GENERATION

When using these instructions:

1. **Feed this entire document as system context** — it provides the complete architectural blueprint.

2. **Generate one module at a time** — use the prompt templates in Section 20. Copy the relevant prompt, paste it, and generate.

3. **Maintain consistency** — every module imports from `models.py`. The Pydantic models ARE the API contract. Never deviate.

4. **Test as you go** — generate tests alongside each module, not after.

5. **Kenyan context matters** — Swahili/Sheng medical terms, KES currency, SHA-specific regulations, Data Protection Act 2019. This is not a generic health app.

6. **User delight is the goal** — clinicians should feel like the system reads their mind. Billing staff should see their rejection rate plummet. Admins should have full visibility. Every interaction should feel fast, clear, and trustworthy.

---

*Generated for: Dr. Jesse Gitaka, GitakaLab, Mount Kenya University*
*Target: Google AI Code Generation (Gemini/Antigravity)*
*Version: 4.0 — March 2026*
