# Aifya — Clinical Trials Module & Final Consolidated Specification
## Module 49: Clinical Research & Trials Management
## REDCap Integration · ICH-GCP Compliant · AI-Powered Screening
### Final Specification for Claude Code · v2.0 · April 2026

---

# SECTION A: CLINICAL TRIALS MODULE — COMPLETE SPECIFICATION

## A.1 Module Overview

The Clinical Trials module is triggered when ANY patient in Aifya is identified as participating in — or potentially eligible for — a clinical trial. It manages the full lifecycle from protocol setup through enrollment, data capture, adverse event reporting, and automated bi-directional sync with REDCap.

**What makes this world-class:**
- **AI-powered patient screening** — DeepSeek-R1 continuously scans encounters against active trial eligibility criteria and surfaces matches to investigators
- **Zero double-entry** — Clinical data captured during routine care (vitals, labs, diagnoses, medications) flows automatically to REDCap via FHIR, eliminating manual CRF transcription
- **Real-time protocol adherence monitoring** — AI alerts when a trial patient's care deviates from the protocol schedule
- **Built-in GCP compliance** — Audit trail, electronic consent with witness signature, SAE reporting timelines, source document verification

## A.2 Data Model

```sql
-- =============================================================
-- CLINICAL TRIALS REGISTRY
-- =============================================================
CREATE TABLE clinical_trials (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id       UUID NOT NULL REFERENCES facilities(id),
    -- Trial identification
    trial_code        VARCHAR(50) NOT NULL UNIQUE,       -- Internal code (e.g., "AIFYA-TB-001")
    nct_number        VARCHAR(20),                       -- ClinicalTrials.gov NCT number
    pactr_number      VARCHAR(20),                       -- Pan African Clinical Trials Registry
    title             TEXT NOT NULL,
    short_title       VARCHAR(200),
    -- Classification
    phase             VARCHAR(10) CHECK (phase IN ('I', 'II', 'III', 'IV', 'observational', 'registry')),
    study_type        VARCHAR(30) NOT NULL CHECK (study_type IN (
                        'interventional', 'observational', 'registry',
                        'diagnostic', 'pragmatic', 'adaptive'
                      )),
    therapeutic_area  VARCHAR(100),                      -- e.g., 'infectious_disease', 'oncology'
    -- Sponsor & oversight
    sponsor           VARCHAR(200) NOT NULL,
    principal_investigator_id UUID REFERENCES staff(id),
    co_investigators  JSONB DEFAULT '[]',                -- [{staff_id, role}]
    irb_approval_number VARCHAR(50),
    irb_approval_date DATE,
    irb_expiry_date   DATE,
    ethics_committee  VARCHAR(200),                      -- e.g., "KEMRI Ethics Review Committee"
    nacosti_permit    VARCHAR(50),                       -- Kenya NACOSTI research permit
    -- Protocol
    protocol_version  VARCHAR(20) NOT NULL,
    protocol_date     DATE NOT NULL,
    protocol_document_url VARCHAR(500),                  -- Stored in MinIO
    amendments        JSONB DEFAULT '[]',                -- [{version, date, summary, document_url}]
    -- Eligibility criteria (structured for AI screening)
    inclusion_criteria JSONB NOT NULL,                   -- [{criterion_id, description, type, parameters}]
    exclusion_criteria JSONB NOT NULL,                   -- same structure
    target_enrollment INTEGER,
    -- REDCap integration
    redcap_project_id INTEGER,                           -- REDCap project ID
    redcap_api_url    VARCHAR(500),                      -- REDCap instance URL
    redcap_api_token_vault_key VARCHAR(100),             -- Reference to Vault secret (NEVER store token in DB)
    redcap_field_mapping JSONB DEFAULT '{}',             -- {aifya_field: redcap_field} mapping
    redcap_sync_enabled BOOLEAN DEFAULT TRUE,
    redcap_sync_mode  VARCHAR(20) DEFAULT 'bidirectional' CHECK (redcap_sync_mode IN (
                        'push_only', 'pull_only', 'bidirectional'
                      )),
    -- Status
    status            VARCHAR(20) DEFAULT 'setup' CHECK (status IN (
                        'setup', 'recruiting', 'active', 'follow_up',
                        'completed', 'suspended', 'terminated', 'withdrawn'
                      )),
    -- Dates
    start_date        DATE,
    end_date          DATE,
    -- Audit
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by        UUID NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted        BOOLEAN DEFAULT FALSE
);

-- =============================================================
-- TRIAL PARTICIPANTS (links patients to trials)
-- =============================================================
CREATE TABLE trial_participants (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trial_id          UUID NOT NULL REFERENCES clinical_trials(id),
    patient_id        UUID NOT NULL REFERENCES patients(id),
    facility_id       UUID NOT NULL,
    -- Identifiers
    participant_number VARCHAR(30) NOT NULL,              -- Study-specific ID (blinded)
    randomization_arm VARCHAR(50),                        -- Treatment arm / group
    randomization_date TIMESTAMPTZ,
    -- Status
    status            VARCHAR(20) NOT NULL DEFAULT 'screened' CHECK (status IN (
                        'pre_screened', 'screened', 'screen_failed',
                        'enrolled', 'active', 'on_hold', 'completed',
                        'withdrawn', 'lost_to_followup', 'deceased'
                      )),
    -- Screening
    screening_date    TIMESTAMPTZ,
    screened_by       UUID REFERENCES staff(id),
    screen_fail_reason TEXT,
    eligibility_check JSONB DEFAULT '{}',                 -- {criterion_id: {met: bool, value, date}}
    ai_eligibility_score FLOAT,                          -- AI confidence that patient is eligible (0-1)
    -- Consent
    consent_version   VARCHAR(20),
    consent_date      TIMESTAMPTZ,
    consent_document_url VARCHAR(500),                   -- Signed consent form (scanned/digital)
    consent_witness   VARCHAR(200),
    consent_withdrawn BOOLEAN DEFAULT FALSE,
    consent_withdrawn_date TIMESTAMPTZ,
    consent_withdrawn_reason TEXT,
    -- Enrollment
    enrollment_date   TIMESTAMPTZ,
    enrolled_by       UUID REFERENCES staff(id),
    -- Completion
    completion_date   TIMESTAMPTZ,
    completion_status VARCHAR(30),                        -- 'completed_per_protocol', 'early_termination', etc.
    withdrawal_reason TEXT,
    -- REDCap
    redcap_record_id  VARCHAR(50),                       -- Record ID in REDCap
    last_redcap_sync  TIMESTAMPTZ,
    redcap_sync_status VARCHAR(20) DEFAULT 'pending',    -- 'synced', 'pending', 'error', 'conflict'
    -- Audit
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by        UUID NOT NULL,
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_deleted        BOOLEAN DEFAULT FALSE,
    UNIQUE(trial_id, patient_id),
    UNIQUE(trial_id, participant_number)
);

-- =============================================================
-- TRIAL VISITS / STUDY SCHEDULE
-- =============================================================
CREATE TABLE trial_visit_schedule (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trial_id          UUID NOT NULL REFERENCES clinical_trials(id),
    visit_code        VARCHAR(20) NOT NULL,               -- e.g., "V1", "V2", "D14", "W4", "EOS"
    visit_name        VARCHAR(100) NOT NULL,              -- e.g., "Screening", "Day 14", "Week 4", "End of Study"
    day_from_enrollment INTEGER NOT NULL,                  -- Scheduled day (0 = enrollment)
    window_before_days INTEGER DEFAULT 0,                  -- Allowed window (e.g., -3 days)
    window_after_days INTEGER DEFAULT 0,                   -- Allowed window (e.g., +3 days)
    -- Required procedures/assessments for this visit
    required_assessments JSONB NOT NULL DEFAULT '[]',      -- [{type, code, description}]
    -- type: 'vital_signs', 'lab_test', 'questionnaire', 'physical_exam',
    --       'imaging', 'ecg', 'medication_dispensing', 'adverse_event_review'
    is_mandatory      BOOLEAN DEFAULT TRUE,
    sort_order        INTEGER DEFAULT 0,
    -- Audit
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE trial_participant_visits (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id    UUID NOT NULL REFERENCES trial_participants(id),
    schedule_id       UUID NOT NULL REFERENCES trial_visit_schedule(id),
    encounter_id      UUID REFERENCES encounters(id),     -- Links to clinical encounter
    -- Timing
    scheduled_date    DATE NOT NULL,
    actual_date       DATE,
    status            VARCHAR(20) DEFAULT 'scheduled' CHECK (status IN (
                        'scheduled', 'completed', 'missed', 'cancelled',
                        'out_of_window', 'unscheduled'
                      )),
    -- Completion tracking
    assessments_completed JSONB DEFAULT '[]',              -- [{assessment_id, completed: bool, value, notes}]
    protocol_deviations JSONB DEFAULT '[]',                -- [{type, description, severity, corrective_action}]
    -- AI monitoring
    ai_window_alert   BOOLEAN DEFAULT FALSE,               -- True if visit is approaching window limit
    ai_missing_assessments JSONB DEFAULT '[]',             -- AI-detected missing required procedures
    -- REDCap sync
    redcap_synced     BOOLEAN DEFAULT FALSE,
    redcap_sync_at    TIMESTAMPTZ,
    -- Audit
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by        UUID NOT NULL,
    facility_id       UUID NOT NULL
);

-- =============================================================
-- ADVERSE EVENTS
-- =============================================================
CREATE TABLE trial_adverse_events (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    participant_id    UUID NOT NULL REFERENCES trial_participants(id),
    trial_id          UUID NOT NULL REFERENCES clinical_trials(id),
    -- Classification
    ae_term           TEXT NOT NULL,                       -- Verbatim term
    meddra_code       VARCHAR(20),                        -- MedDRA preferred term code
    meddra_pt         VARCHAR(200),                       -- MedDRA preferred term
    meddra_soc        VARCHAR(200),                       -- MedDRA System Organ Class
    ctcae_grade       SMALLINT CHECK (ctcae_grade BETWEEN 1 AND 5),  -- CTCAE v5.0 grade
    -- Severity & seriousness
    severity          VARCHAR(10) NOT NULL CHECK (severity IN ('mild', 'moderate', 'severe')),
    is_serious        BOOLEAN DEFAULT FALSE,               -- SAE flag
    seriousness_criteria JSONB DEFAULT '[]',               -- ['death', 'life_threatening', 'hospitalization',
                                                           --  'disability', 'congenital_anomaly', 'medically_important']
    -- Causality
    relatedness       VARCHAR(30) CHECK (relatedness IN (
                        'unrelated', 'unlikely', 'possible', 'probable', 'definite'
                      )),
    -- Dates
    onset_date        DATE NOT NULL,
    resolution_date   DATE,
    -- Outcome
    outcome           VARCHAR(30) CHECK (outcome IN (
                        'recovered', 'recovering', 'not_recovered',
                        'recovered_with_sequelae', 'fatal', 'unknown'
                      )),
    action_taken      VARCHAR(30) CHECK (action_taken IN (
                        'none', 'dose_reduced', 'dose_interrupted',
                        'permanently_discontinued', 'not_applicable'
                      )),
    -- Reporting
    reported_by       UUID NOT NULL REFERENCES staff(id),
    reported_date     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- SAE reporting (time-critical)
    sae_aware_date    TIMESTAMPTZ,                        -- Date investigator became aware
    sae_reported_to_sponsor TIMESTAMPTZ,                  -- MUST be within 24 hours of awareness
    sae_reported_to_irb TIMESTAMPTZ,
    sae_report_document_url VARCHAR(500),                 -- CIOMS form or equivalent
    -- REDCap
    redcap_synced     BOOLEAN DEFAULT FALSE,
    -- Audit
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by        UUID NOT NULL,
    facility_id       UUID NOT NULL
);

-- =============================================================
-- AI SCREENING LOG (tracks AI-suggested trial matches)
-- =============================================================
CREATE TABLE trial_ai_screening (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id        UUID NOT NULL REFERENCES patients(id),
    trial_id          UUID NOT NULL REFERENCES clinical_trials(id),
    encounter_id      UUID REFERENCES encounters(id),     -- Encounter that triggered the match
    -- AI assessment
    eligibility_score FLOAT NOT NULL,                     -- 0-1 confidence
    criteria_met      JSONB NOT NULL,                     -- [{criterion_id, met: bool, evidence}]
    criteria_not_met  JSONB DEFAULT '[]',
    criteria_unknown  JSONB DEFAULT '[]',                 -- Criteria that need additional data
    ai_reasoning      TEXT,                               -- AI explanation of eligibility assessment
    model_version     VARCHAR(50),
    -- Investigator action
    investigator_reviewed BOOLEAN DEFAULT FALSE,
    investigator_id   UUID REFERENCES staff(id),
    investigator_decision VARCHAR(20) CHECK (investigator_decision IN (
                        'proceed_to_screen', 'not_eligible', 'defer', 'already_screened'
                      )),
    review_notes      TEXT,
    -- Audit
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    facility_id       UUID NOT NULL
);
```

## A.3 REDCap Integration Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AIFYA ←→ REDCap SYNC ENGINE                      │
│                                                                      │
│  ┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐  │
│  │ Aifya FHIR  │     │ FHIR-to-REDCap   │     │ REDCap           │  │
│  │ Resources   │────▶│ Mapper Service    │────▶│ API (v14.x)      │  │
│  │             │     │                  │     │                  │  │
│  │ Patient     │     │ • Field mapping   │     │ POST /record     │  │
│  │ Encounter   │     │ • Data transform  │     │ POST /file       │  │
│  │ Observation │     │ • Conflict detect │     │ GET /record      │  │
│  │ Condition   │     │ • Consent check   │     │ GET /metadata    │  │
│  │ MedRequest  │     │ • De-ID if needed │     │ GET /event       │  │
│  │ Procedure   │     │ • Audit logging   │     │                  │  │
│  │ DiagReport  │     │                  │     │                  │  │
│  └─────────────┘     └──────────────────┘     └──────────────────┘  │
│                                                                      │
│  Sync Modes:                                                         │
│  ├── Real-time push: AE/SAE events → immediate REDCap sync          │
│  ├── Visit-triggered: On visit completion → sync visit CRF data     │
│  ├── Scheduled batch: Nightly sync of labs, vitals, medications     │
│  └── Manual: Investigator-triggered full resync                     │
│                                                                      │
│  Data Elements Auto-Synced:                                          │
│  ├── Demographics (Patient resource → REDCap demographics form)      │
│  ├── Vitals (Observation → REDCap vital signs instrument)           │
│  ├── Lab results (DiagnosticReport → REDCap lab instrument)         │
│  ├── Medications (MedicationRequest → REDCap concomitant meds)      │
│  ├── Diagnoses (Condition → REDCap medical history / AEs)           │
│  ├── Procedures (Procedure → REDCap procedures instrument)          │
│  └── Adverse events (custom → REDCap AE instrument)                 │
└─────────────────────────────────────────────────────────────────────┘
```

### REDCap API Integration Code Pattern

```python
# services/api-gateway/app/utils/redcap_client.py

import httpx
from typing import Any
from app.config import vault_client

class REDCapClient:
    """REDCap API v14.x client with FHIR-aligned data mapping."""
    
    def __init__(self, trial_id: str):
        trial = get_trial(trial_id)
        self.api_url = trial.redcap_api_url
        # NEVER hardcode tokens. Always retrieve from Vault.
        self.token = vault_client.read_secret(trial.redcap_api_token_vault_key)
    
    async def import_record(self, record_id: str, data: dict[str, Any]) -> dict:
        """Push a single record to REDCap."""
        payload = {
            "token": self.token,
            "content": "record",
            "format": "json",
            "type": "flat",
            "overwriteBehavior": "normal",  # Only overwrite non-blank fields
            "forceAutoNumber": "false",
            "data": json.dumps([{"record_id": record_id, **data}]),
            "returnContent": "ids"
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.api_url, data=payload)
            response.raise_for_status()
            return response.json()
    
    async def export_record(self, record_id: str) -> dict:
        """Pull a single record from REDCap."""
        payload = {
            "token": self.token,
            "content": "record",
            "format": "json",
            "type": "flat",
            "records[0]": record_id
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.api_url, data=payload)
            response.raise_for_status()
            records = response.json()
            return records[0] if records else {}
    
    async def upload_file(self, record_id: str, field: str, file_path: str) -> None:
        """Upload file (consent form, SAE report) to REDCap."""
        payload = {
            "token": self.token,
            "content": "file",
            "action": "import",
            "record": record_id,
            "field": field,
        }
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(self.api_url, data=payload, files=files)
                response.raise_for_status()
    
    async def get_project_metadata(self) -> list[dict]:
        """Get REDCap project field definitions for mapping validation."""
        payload = {
            "token": self.token,
            "content": "metadata",
            "format": "json"
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(self.api_url, data=payload)
            response.raise_for_status()
            return response.json()
```

## A.4 AI-Powered Trial Screening Pipeline

```
Every Clinical Encounter
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│              AI TRIAL SCREENING ENGINE                     │
│              (Runs as background Celery task)              │
│                                                           │
│  1. Extract patient clinical profile from encounter:      │
│     • Diagnoses (ICD-10)                                  │
│     • Lab results (recent 90 days)                        │
│     • Medications (current)                               │
│     • Demographics (age, gender)                          │
│     • Vitals (recent)                                     │
│                                                           │
│  2. For each ACTIVE trial with status='recruiting':       │
│     • Compare patient profile against inclusion criteria  │
│     • Check exclusion criteria                            │
│     • Calculate eligibility score (0-1)                   │
│     • If score > 0.7: create trial_ai_screening record    │
│                                                           │
│  3. Notify investigator:                                  │
│     • In-app notification: "Patient [name] may be         │
│       eligible for [trial]. Eligibility score: 87%"       │
│     • Badge on patient's encounter: "Trial Match 🔬"      │
│                                                           │
│  Model: DeepSeek-R1 (complex reasoning for eligibility)   │
│  Runs: After every encounter completion (async)           │
└──────────────────────────────────────────────────────────┘
```

### Eligibility Criteria as Structured Data

```json
// clinical_trials.inclusion_criteria example
[
  {
    "criterion_id": "IC01",
    "description": "Age 18-65 years",
    "type": "demographic",
    "field": "age",
    "operator": "between",
    "value": [18, 65]
  },
  {
    "criterion_id": "IC02", 
    "description": "Confirmed diagnosis of pulmonary tuberculosis",
    "type": "diagnosis",
    "icd10_codes": ["A15.0", "A15.1", "A15.2", "A15.3"],
    "timeframe_days": 90
  },
  {
    "criterion_id": "IC03",
    "description": "Sputum smear positive or GeneXpert positive",
    "type": "lab_result",
    "test_codes": ["smear_afb", "genexpert_mtb"],
    "required_value": "positive",
    "timeframe_days": 30
  },
  {
    "criterion_id": "IC04",
    "description": "HIV status known",
    "type": "lab_result",
    "test_codes": ["hiv_rapid", "hiv_elisa"],
    "required_value": "any_result",
    "timeframe_days": 180
  }
]
```

AI uses structured criteria for automated matching AND free-text criteria for complex reasoning (e.g., "Patient must be able to provide informed consent" — requires clinical judgment).

## A.5 Clinical Trials API Endpoints

```yaml
# ---------- TRIALS MANAGEMENT ----------
POST   /api/v1/trials                           # Register new trial
GET    /api/v1/trials                           # List trials (?status=recruiting)
GET    /api/v1/trials/{id}                      # Trial detail with enrollment stats
PATCH  /api/v1/trials/{id}                      # Update trial (status, protocol amendment)
POST   /api/v1/trials/{id}/protocol-amendment   # Record protocol amendment

# ---------- SCREENING & ENROLLMENT ----------
GET    /api/v1/trials/{id}/ai-matches           # AI-suggested eligible patients
POST   /api/v1/trials/{id}/screen               # Screen patient for trial
POST   /api/v1/trials/{id}/enroll               # Enroll patient
PATCH  /api/v1/trials/{id}/participants/{pid}   # Update participant status
POST   /api/v1/trials/{id}/participants/{pid}/consent       # Record consent
POST   /api/v1/trials/{id}/participants/{pid}/randomize     # Randomize participant

# ---------- VISITS & DATA COLLECTION ----------
GET    /api/v1/trials/{id}/participants/{pid}/schedule      # Visit schedule with status
POST   /api/v1/trials/{id}/participants/{pid}/visits        # Record visit completion
GET    /api/v1/trials/{id}/visits/upcoming                  # All upcoming visits across participants
GET    /api/v1/trials/{id}/visits/overdue                   # Overdue/missed visits

# ---------- ADVERSE EVENTS ----------
POST   /api/v1/trials/{id}/participants/{pid}/adverse-events    # Report AE
GET    /api/v1/trials/{id}/adverse-events                       # All AEs for trial
PATCH  /api/v1/adverse-events/{id}                              # Update AE (follow-up, resolution)
POST   /api/v1/adverse-events/{id}/report-sae                  # Generate SAE report (CIOMS form)

# ---------- REDCap SYNC ----------
POST   /api/v1/trials/{id}/redcap/sync                    # Trigger full sync
GET    /api/v1/trials/{id}/redcap/status                   # Sync status & errors
POST   /api/v1/trials/{id}/redcap/mapping                  # Configure field mapping
GET    /api/v1/trials/{id}/redcap/mapping                  # View current mapping
POST   /api/v1/trials/{id}/redcap/validate                 # Validate mapping against REDCap metadata

# ---------- ANALYTICS ----------
GET    /api/v1/trials/{id}/dashboard                       # Trial dashboard (enrollment, visits, AEs)
GET    /api/v1/trials/{id}/enrollment-curve                # Enrollment vs. target over time
GET    /api/v1/trials/{id}/protocol-deviations             # Protocol deviation summary
GET    /api/v1/trials/site-performance                     # Cross-trial site performance metrics
```

## A.6 Frontend Components

```
apps/web/src/
├── app/(dashboard)/trials/
│   ├── page.tsx                    # Trial registry list
│   ├── [id]/
│   │   ├── page.tsx               # Trial dashboard (enrollment curve, visit calendar, AE summary)
│   │   ├── participants/page.tsx  # Participant list with status filters
│   │   ├── screening/page.tsx     # AI-suggested matches + screening workflow
│   │   ├── visits/page.tsx        # Visit schedule matrix (participants × visits)
│   │   ├── adverse-events/page.tsx
│   │   ├── redcap/page.tsx        # REDCap sync status, mapping config
│   │   └── settings/page.tsx      # Trial config, protocol uploads
│   └── new/page.tsx               # New trial setup wizard
├── components/trials/
│   ├── TrialDashboard.tsx          # Enrollment curve + key metrics
│   ├── ScreeningWorkflow.tsx       # Step-by-step screening with eligibility checklist
│   ├── ConsentCapture.tsx          # Digital consent with witness signature pad
│   ├── VisitMatrix.tsx             # Swim-lane view: participants × scheduled visits
│   ├── AdverseEventForm.tsx        # Structured AE/SAE reporting form
│   ├── REDCapSyncStatus.tsx        # Real-time sync status with error details
│   ├── EligibilityBadge.tsx        # Shows on patient encounter when AI match detected
│   ├── ProtocolDeviationLog.tsx
│   └── TrialAlertBanner.tsx        # "This patient is enrolled in [trial]. Protocol visit due in 3 days."
```

## A.7 Trial Alert Banner in Clinical Encounter

When a clinician opens ANY encounter for a patient enrolled in a trial:

```
┌──────────────────────────────────────────────────────────────────┐
│ 🔬 CLINICAL TRIAL: AIFYA-TB-001 (Phase III)                     │
│ Participant #: TB-042  │  Arm: Treatment B  │  Status: Active    │
│ Next visit: V4 (Week 8) due 15 Apr 2026 [3 days]               │
│ Required: Vitals, CBC, Sputum AFB, CXR, QoL questionnaire       │
│                                              [View Protocol ➜]  │
└──────────────────────────────────────────────────────────────────┘
```

This banner is ALWAYS visible during the encounter. It ensures the clinician doesn't forget trial-required assessments.

---

# SECTION B: UPDATED FINAL MODULE COUNT

**Previous: 48 modules. Updated: 49 modules.**

Module 49: **Clinical Trials & Research Management** (with REDCap integration)

This module sits within the **Analytics & Research** section:

```
📊 ANALYTICS & RESEARCH (5 modules)  ← was 4
├── Facility Dashboards (Metabase)
├── Central Analytics (Superset)
├── Research Data Platform
├── MOH Reporting & DHIS2
└── Clinical Trials & REDCap         ← NEW (Module 49)
```

---

# SECTION C: CONSOLIDATED SPECIFICATION SUMMARY

## Complete Document Package for Claude Code

| # | Document | Purpose | Lines | When Claude Code Reads It |
|---|---|---|---|---|
| 1 | **CLAUDE.md** (root) | Project config, commands, rules | ~160 | Every session (auto-loaded) |
| 2 | **docs/database-schema.md** | Complete SQL for all 49 modules | ~3000 | When touching DB/models |
| 3 | **docs/api-contracts.md** | All API endpoints + schemas | ~2000 | When building endpoints |
| 4 | **docs/frontend-patterns.md** | Component patterns, hooks, i18n | ~1000 | When building UI |
| 5 | **docs/ai-integration.md** | Model routing, prompts, guardrails | ~1200 | When touching AI pipeline |
| 6 | **docs/clinical-workflows.md** | Step-by-step department flows | ~1500 | When building clinical modules |
| 7 | **docs/clinical-trials.md** | This document (trials + REDCap) | ~800 | When building trials module |
| 8 | **docs/kenya-compliance.md** | DPA, DHA, SHA, ODPC, audit | ~600 | When touching compliance |
| 9 | **docs/analytics.md** | Dashboard specs, warehouse schema | ~800 | When building dashboards |
| 10 | **docs/module-specs.md** | All 49 module specifications | ~4000 | When building specific modules |
| 11 | **docs/testing-strategy.md** | Clinical scenarios, offline tests | ~600 | When writing tests |

**Total if all loaded:** ~16K lines (~35K tokens)
**Per session (progressive disclosure):** ~3-5K tokens
**Token savings:** ~85% per session

---

# SECTION D: KEY ARCHITECTURAL DECISIONS (FINAL)

These are the non-negotiable decisions that Claude Code must follow:

| Decision | Choice | Rationale |
|---|---|---|
| Clinical data pattern | **Event Sourcing + CQRS** | Legally defensible audit trail. AI replay capability. |
| Module activation | **Feature flags per facility** | Not every hospital needs all 49 modules. |
| AI workflow pattern | **Agentic (multi-step chains)** | Discharge agent, screening agent, claims agent. |
| AI improvement | **Continuous learning from corrections** | Monthly LoRA fine-tuning on clinician edits. |
| REDCap integration | **FHIR-based bidirectional sync** | Uses REDCap CDIS pattern. Zero double-entry. |
| Offline strategy | **IndexedDB + background sync queue** | Core workflows work fully offline. |
| Multi-tenancy | **facility_id filter + PostgreSQL RLS** | Defense-in-depth data isolation. |
| Authentication | **Keycloak OIDC + RBAC** | Clinical role granularity. Break-glass emergency access. |
| Print/documents | **Server-side PDF generation** | Professional letterhead. No browser print artifacts. |
| Financial | **Double-entry GL + Kenya chart of accounts** | Full accounting, not just billing. |
| Research | **De-identified warehouse + MLflow + Jupyter** | Publication-ready data infrastructure. |
| Monitoring | **Prometheus + Grafana + Loki + Tempo** | Full observability stack. AI drift detection. |

---

*End of Final Specification.*
*Aifya — Akili kwa Afya — Intelligence for Health.*
*49 modules. AI-native. REDCap-integrated. Built for Africa.*
