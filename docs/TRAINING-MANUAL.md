# Aifya Hospital Management System — Comprehensive Training Manual

> **"Akili kwa Afya"** — Intelligence for Health

**Version:** 1.0 | **Last Updated:** April 2026 | **Audience:** Administrators, Clinical Staff, IT Teams, Developers

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Architecture](#2-system-architecture)
3. [Getting Started](#3-getting-started)
4. [User Roles & Permissions](#4-user-roles--permissions)
5. [Licensing & Subscription Tiers](#5-licensing--subscription-tiers)
6. [Module Reference](#6-module-reference)
   - [Patient Management](#61-patient-management)
   - [OPD (Outpatient Department)](#62-opd-outpatient-department)
   - [IPD (Inpatient Department)](#63-ipd-inpatient-department)
   - [Emergency Department](#64-emergency-department)
   - [Pharmacy](#65-pharmacy)
   - [Laboratory](#66-laboratory)
   - [Radiology & Imaging](#67-radiology--imaging)
   - [Theatre (Surgery)](#68-theatre-surgery)
   - [Dental](#69-dental)
   - [MCH (Mother & Child Health)](#610-mch-mother--child-health)
   - [Billing & Payments](#611-billing--payments)
   - [Insurance & SHA Claims](#612-insurance--sha-claims)
   - [Inventory Management](#613-inventory-management)
   - [Appointments](#614-appointments)
   - [Referrals](#615-referrals)
   - [HR & Staff Management](#616-hr--staff-management)
   - [Reports & Dashboards](#617-reports--dashboards)
7. [AI-Powered Features](#7-ai-powered-features)
   - [ScribeAI (Ambient Documentation)](#71-scribeai-ambient-documentation)
   - [Clinical Decision Support (CDS)](#72-clinical-decision-support-cds)
   - [Predictive Analytics](#73-predictive-analytics)
   - [AI Medical Imaging](#74-ai-medical-imaging)
   - [Multi-Agent Workflows](#75-multi-agent-workflows)
8. [Integrations](#8-integrations)
   - [M-Pesa Daraja Payments](#81-m-pesa-daraja-payments)
   - [FHIR R4 Interoperability](#82-fhir-r4-interoperability)
   - [MOH / DHIS2 Reporting](#83-moh--dhis2-reporting)
   - [Patient Communications (SMS/WhatsApp)](#84-patient-communications-smswhatsapp)
   - [Federated Analytics & Surveillance](#85-federated-analytics--disease-surveillance)
9. [Offline-First Operation](#9-offline-first-operation)
10. [Clinical Safety Protocols](#10-clinical-safety-protocols)
11. [Kenya Compliance](#11-kenya-compliance)
12. [Administration Guide](#12-administration-guide)
13. [Troubleshooting](#13-troubleshooting)
14. [API Reference](#14-api-reference)
15. [Glossary](#15-glossary)

---

## 1. Introduction

### What is Aifya?

Aifya is an AI-native Hospital Management Information System (HMIS) purpose-built for Kenyan hospitals. It manages the complete hospital workflow — from patient registration through billing — across 49 integrated modules. What sets Aifya apart is deep AI integration: ambient clinical documentation (ScribeAI), automated insurance claims (ClaimFlow), clinical trial screening, predictive analytics, and medical imaging analysis.

### Key Capabilities

- **49 clinical and administrative modules** covering the full hospital workflow
- **AI-native architecture** with self-hosted language models (no cloud AI dependency)
- **Offline-first design** — core clinical workflows function without internet
- **Bilingual interface** — English and Swahili (Kiswahili) throughout
- **FHIR R4 compliant** — standards-based health data exchange
- **Kenya-specific** — M-Pesa payments, SHA insurance, MOH reporting, DHIS2 sync
- **Multi-tenant** — one installation supports multiple facilities with strict data isolation
- **Event-sourced clinical data** — immutable audit trail with 20-year retention

### Who Should Read This Manual?

| Audience | Relevant Sections |
|----------|------------------|
| **Hospital Administrators** | Sections 1-6, 10-12 |
| **Doctors & Clinical Officers** | Sections 6-7, 10 |
| **Nurses** | Sections 6.2-6.4, 6.10, 10 |
| **Pharmacists** | Section 6.5 |
| **Lab Technicians** | Section 6.6 |
| **Billing & Finance** | Sections 6.11-6.12, 8.1 |
| **IT Administrators** | Sections 2-3, 12-14 |
| **Developers** | All sections, especially 2, 12, 14 |

---

## 2. System Architecture

### Overview

```
                    +-------------------+
                    |    Web Browser     |
                    | (Next.js PWA)      |
                    +--------+----------+
                             |
                    +--------v----------+
                    |   Traefik Proxy   |
                    +--------+----------+
                             |
              +--------------+--------------+
              |                             |
    +---------v---------+     +-------------v-----------+
    |   API Gateway     |     |    AI Service           |
    |   (FastAPI)       |     |    (LLM Orchestration)  |
    |   Port 8000       |     |    Port 8025            |
    +---------+---------+     +-------------+-----------+
              |                             |
    +---------v---------+     +-------------v-----------+
    |   PostgreSQL 16   |     |   vLLM Model Servers    |
    |   + TimescaleDB   |     |   8001: DeepSeek-R1     |
    |   Port 5432       |     |   8002: Qwen 72B        |
    +---------+---------+     |   8003: Distill-32B     |
              |               +-------------------------+
    +---------v---------+
    |   Supporting       |
    |   Redis | Kafka    |
    |   MinIO | Qdrant   |
    |   Keycloak         |
    +--------------------+
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Next.js 15, React 19, TypeScript, Tailwind 4 | Progressive Web App |
| **UI Components** | shadcn/ui | Consistent design system |
| **State Management** | TanStack Query 5 (server), Zustand 5 (client) | Data fetching & caching |
| **Internationalization** | next-intl | English + Swahili |
| **Backend** | FastAPI 0.115+, Python 3.12+ | REST API with auto-generated docs |
| **ORM** | SQLAlchemy 2 (async) | Database access |
| **Validation** | Pydantic 2 | Request/response schemas |
| **Database** | PostgreSQL 16 + TimescaleDB | Primary data store |
| **Cache** | Redis 7 | Session cache, rate limiting |
| **Message Queue** | Kafka 3.7+ | Event streaming |
| **Object Storage** | MinIO | Documents, images, audio |
| **Vector DB** | Qdrant | Knowledge base embeddings |
| **Auth** | Keycloak 25 | OAuth2 / OpenID Connect |
| **Background Jobs** | Celery 5 | Async task processing |
| **AI Models** | vLLM 0.6+ | Self-hosted LLM inference |
| **Speech-to-Text** | faster-whisper | ScribeAI audio transcription |

### Multi-Tenant Data Isolation

Every piece of data in Aifya is tagged with a `facility_id`. When a user logs in, their facility is embedded in their authentication token. Every database query automatically filters by this facility, ensuring:

- **No data leaks** between facilities sharing the same installation
- **PostgreSQL Row-Level Security** as defense-in-depth
- **Audit trail** tracking which user at which facility accessed what data

---

## 3. Getting Started

### Prerequisites

- Docker and Docker Compose installed
- Node.js 20+ with pnpm
- Python 3.12+
- Git

### Quick Start

```bash
# Clone the repository
git clone <repository-url>
cd Aifya

# Copy environment configuration
cp .env.example .env
# Edit .env with your facility's settings

# Start all services
make dev

# Access the application
# Web UI:    http://localhost:3000
# API Docs:  http://localhost:8000/api/docs (development only)
# Keycloak:  http://localhost:8080
```

### First Login

1. Navigate to `http://localhost:3000`
2. You will be redirected to the Keycloak login page
3. Enter your credentials (provided by your IT administrator)
4. Upon successful login, you'll see the Dashboard

### Navigation

The sidebar provides access to all modules:

- **Top section:** Dashboard, Patients, Registration, Clinical
- **Clinical:** OPD, IPD, Emergency
- **Support Services:** Pharmacy, Laboratory, Radiology, Theatre, Dental, MCH
- **Finance:** Billing, Insurance, Inventory
- **Administrative:** Appointments, Referrals, HR, Reports, Analytics
- **Advanced:** Communications, Integrations, Knowledge Base
- **System:** Settings

Modules you don't have access to (based on your license tier) appear with a lock icon and link to the upgrade page.

**Clinical** is not another department module. It shows each clinician only the patients routed to them or their department today, so a dentist works from the dental queue without being handed the whole hospital. Reception picks the department when a patient is registered or triaged, and the patient then appears on the right clinician's list.

**Keyboard Shortcut:** Press `Cmd+K` (Mac) or `Ctrl+K` (Windows) to open the Command Palette for quick navigation to any patient, action, or module.

### Dark Mode

Click the sun/moon icon at the bottom of the sidebar to toggle between light and dark themes. All components support both modes.

### Language

Switch between English and Swahili using the language selector. All user-facing text, labels, error messages, and clinical forms are fully translated.

---

## 4. User Roles & Permissions

### Role Definitions

| Role | Access Level | Typical Staff |
|------|-------------|---------------|
| `admin` | Full system access, settings, user management | IT Administrator |
| `facility_manager` | Facility configuration, reports, staff management | Hospital Director |
| `doctor` | Full clinical access, prescriptions, diagnoses | Medical Officer, Consultant |
| `nurse` | Vitals, nursing notes, triage, medication administration | Registered Nurse |
| `pharmacist` | Dispensing, stock management, drug interaction review | Pharmacist |
| `laboratory_technician` | Lab orders, results entry, specimen tracking | Lab Technician |
| `radiologist` | Imaging orders, result reporting | Radiologist |
| `receptionist` | Patient registration, appointments, queue management | Front Desk |
| `accountant` | Billing, payments, financial reports | Finance Staff |
| `hr_officer` | Staff management, shifts, leave, attendance | HR Manager |
| `data_entry` | Limited data entry access | Data Clerk |
| `audit_user` | Read-only access for compliance review | Compliance Officer |

### How Roles Work

- Each user can have **multiple roles** (e.g., a doctor who is also a facility manager)
- Endpoints check for **at least one** matching role — if any role matches, access is granted
- Roles are configured in **Keycloak** by your IT administrator
- The sidebar shows/hides modules based on both **role permissions** and **license tier**

### Role Assignment

1. IT admin logs into Keycloak (`http://localhost:8080`)
2. Navigate to **Users** > Select user > **Role Mappings**
3. Assign appropriate realm roles
4. User must log out and back in for role changes to take effect

---

## 5. Licensing & Subscription Tiers

### Tier Comparison

| Feature | Community (Free) | Professional | Enterprise | Government |
|---------|-----------------|-------------|-----------|-----------|
| **Price (KES/month)** | Free | 25,000 | 150,000 | Custom |
| **Max Users** | 5 | 50 | 500 | 10,000 |
| **Max Patients** | 500 | 50,000 | 500,000 | 5,000,000 |
| **Max Facilities** | 1 | 1 | 10 | 500 |

### Module Availability

#### Community Tier (5 modules)
- Patient Management
- OPD Encounters
- Vitals Recording
- Basic Billing
- Offline Mode

#### Professional Tier (adds 12 modules)
Everything in Community, plus:
- IPD (Inpatient)
- Pharmacy
- Laboratory
- Radiology
- Appointments
- MCH (Mother & Child)
- Dental
- Emergency
- Theatre
- Referrals
- Insurance
- Inventory
- HR & Staff
- Reports
- Custom Reports
- Data Export

#### Enterprise Tier (adds 8 modules)
Everything in Professional, plus:
- ScribeAI (Ambient Documentation)
- ClaimFlow AI (SHA Claims Automation)
- Clinical Trials
- Predictive Analytics
- DHIS2 Sync
- FHIR API
- M-Pesa Billing
- API Access
- White Labeling
- Priority Support
- SLA Guarantee

#### Government Tier (adds 4 modules)
Everything in Enterprise, plus:
- Multi-Facility Management
- County Dashboard
- Aggregate Reporting
- Facility Comparison

### License Enforcement

- License validation happens on **every API request** via middleware
- Results are cached in Redis for 5 minutes to minimize latency
- If license expires, a **7-day grace period** allows continued operation
- After grace period, access is restricted to read-only mode
- The system sends **heartbeat** data (user count, patient count, version) for license monitoring

---

## 6. Module Reference

### 6.1 Patient Management

**Path:** `/patients` | **API:** `/api/v1/patients` | **Module:** `patients`

Patient Management is the foundation of Aifya. Every clinical interaction starts with a patient record.

#### Key Features
- **Registration:** Capture demographics, contact info, next of kin, insurance details
- **MRN Generation:** Automatic Medical Record Number assignment per facility
- **Search:** Find patients by name, MRN, national ID, phone number, or date of birth
- **Profile View:** Complete patient history, encounters, prescriptions, lab results
- **Soft Delete:** Patient records are never hard-deleted (20-year retention requirement)

#### Registration Workflow
1. Receptionist clicks "Register Patient" from sidebar or Command Palette
2. Fill required fields: First Name, Last Name, Date of Birth, Gender
3. Add optional: National ID, Phone, County, Sub-County, Insurance
4. System generates unique MRN
5. Patient appears in the queue for triage

#### Important Fields
| Field | Type | Required | Notes |
|-------|------|----------|-------|
| First Name | Text | Yes | |
| Last Name | Text | Yes | |
| Date of Birth | Date | Yes | Used for age calculations throughout |
| Gender | Select | Yes | Male / Female / Other |
| National ID | Text | No | Kenyan ID or Passport number |
| MRN | Auto | Auto | Generated per facility |
| Phone | Text | No | +254 format for M-Pesa/SMS |
| County | Select | No | Kenya's 47 counties |
| Insurance | Reference | No | Links to insurance scheme |

---

### 6.2 OPD (Outpatient Department)

**Path:** `/opd` | **API:** `/api/v1/encounters` | **Module:** `encounters`

The OPD module manages the outpatient visit workflow from arrival to discharge.

#### Clinical Workflow

```
Patient Arrival → Triage → Queue → Consultation → Prescription/Lab → Billing → Departure
```

1. **Triage (Nurse)**
   - Record vitals: BP, Heart Rate, Temperature, Respiratory Rate, SpO2, Weight, Height
   - Assign triage category: Emergency (Red), Priority (Orange), Urgent (Yellow), Standard (Green), Non-urgent (Blue)
   - CDS system automatically evaluates vitals and flags critical values

2. **Queue Management**
   - Patients ordered by triage severity, then arrival time
   - Real-time queue display shows wait times
   - Doctor selects next patient from queue

3. **Consultation (Doctor)**
   - Review patient history and vitals
   - Record clinical notes (or use ScribeAI for ambient documentation)
   - Enter diagnoses with ICD-10 codes
   - Create prescriptions (CDS checks drug interactions in real-time)
   - Order lab tests or imaging
   - Refer to specialist or admit to IPD if needed

4. **Follow-up Actions**
   - Pharmacy receives prescription for dispensing
   - Lab receives test orders
   - Billing auto-generates invoice
   - Appointment scheduled if follow-up needed

#### CDS Integration
During consultation, the Clinical Decision Support system runs automatically:
- **Drug Interactions:** Checks new prescription against existing medications
- **Allergy Alerts:** Cross-references patient allergies with prescribed drugs
- **Age/Weight Dosing:** Validates dosage for pediatric and geriatric patients
- **Pregnancy Safety:** Flags category X drugs for pregnant patients
- **Critical Vitals:** Alerts on abnormal vital signs

Alert severity levels:
- **Critical (Red):** Cannot be dismissed — blocks action until reviewed
- **High (Red):** Strongly recommended to address
- **Moderate (Amber):** Clinical judgement required
- **Low/Info (Blue):** Informational, can be acknowledged

---

### 6.3 IPD (Inpatient Department)

**Path:** `/ipd` | **API:** `/api/v1/ipd` | **Module:** `ipd`

Manages inpatient admissions, ward assignments, nursing care, and discharges.

#### Key Features
- **Ward Management:** Configure wards (General, ICU, Pediatric, Maternity, Private, Isolation)
- **Bed Board:** Visual bed status display — available, occupied, maintenance, reserved
- **Admission:** Direct from OPD, Emergency, or Theatre
- **Nursing Notes:** Structured documentation by type (assessment, progress, medication, procedure, observation)
- **Discharge Planning:** AI-assisted discharge summary generation (Enterprise tier)

#### Admission Workflow
1. Doctor orders admission from OPD/Emergency encounter
2. Nurse selects available bed from ward board
3. System creates admission record linked to encounter
4. Patient appears on ward census
5. Nursing care documented throughout stay
6. Doctor orders discharge when ready
7. Discharge summary generated (AI-assisted if Enterprise)
8. Final billing calculated

---

### 6.4 Emergency Department

**Path:** `/emergency` | **API:** `/api/v1/emergency` | **Module:** `emergency`

Handles emergency arrivals with rapid triage and treatment tracking.

#### Triage Color System (Kenya Emergency Triage)
| Color | Category | Description | Target Wait |
|-------|----------|-------------|-------------|
| Red | Immediate | Life-threatening | 0 minutes |
| Orange | Very Urgent | Serious risk | 10 minutes |
| Yellow | Urgent | Moderate risk | 60 minutes |
| Green | Standard | Minor issue | 120 minutes |
| Blue | Non-urgent | Can wait | 240 minutes |

#### Emergency Workflow
1. Patient arrives (walk-in, ambulance, referral)
2. Triage nurse assesses and assigns color/priority
3. Treatment area assigned (Resuscitation, Major, Minor, Observation)
4. Doctor assigned automatically or manually
5. Clinical documentation during treatment
6. Disposition: Discharge, Admit, Transfer, or DAMA (Discharged Against Medical Advice)

---

### 6.5 Pharmacy

**Path:** `/pharmacy` | **API:** `/api/v1/pharmacy` | **Module:** `pharmacy`

Complete pharmacy management — dispensing, inventory, stock control.

#### Key Features
- **Dispensing Queue:** Prescriptions from OPD/IPD appear in priority order
- **Drug Inventory:** Track stock levels, expiry dates, batch numbers
- **Stock Alerts:** Automatic alerts for low stock and expiring medications
- **Dispensing Verification:** Pharmacist reviews prescription before dispensing
- **Stock Transactions:** Receipts, adjustments, returns, transfers tracked

#### Dispensing Workflow
1. Prescription arrives from doctor (auto-appears in queue)
2. Pharmacist reviews prescription and CDS alerts
3. Check stock availability
4. Dispense medications, record quantities
5. Patient receives medication with instructions
6. Billing updated automatically

---

### 6.6 Laboratory

**Path:** `/laboratory` | **API:** `/api/v1/laboratory` | **Module:** `laboratory`

Laboratory information system for test ordering, specimen tracking, and results.

#### Key Features
- **Worklist:** Pending orders organized by priority and turnaround time
- **Specimen Tracking:** Barcode-based collection and processing
- **Result Entry:** Structured numeric/text results with reference ranges
- **Critical Values:** Immediate alert system for panic values
- **Verification:** Two-level review — technician enters, senior verifies

#### Lab Workflow
1. Doctor orders tests from OPD/IPD encounter
2. Orders appear on lab worklist
3. Specimen collected and logged
4. Tests performed, results entered
5. Results verified by senior technician
6. Critical values trigger immediate notification to ordering doctor
7. Results available in patient chart

---

### 6.7 Radiology & Imaging

**Path:** `/radiology` | **API:** `/api/v1/radiology` | **Module:** `radiology`

Imaging order management with AI-assisted analysis (Enterprise tier).

#### Supported Modalities
X-Ray, CT Scan, MRI, Ultrasound, Fluoroscopy, Mammography, Nuclear Medicine

#### AI Imaging Analysis (Enterprise)
- **Chest X-ray TB Screening:** AI detects TB probability with lung zone mapping
- **Retinal Scan:** Diabetic retinopathy grading, glaucoma risk assessment
- **General Chest X-ray:** AI-assisted interpretation via multimodal LLM

All AI results are marked "Requires Clinician Review" — the AI provides a preliminary reading that the radiologist must confirm or override.

---

### 6.8 Theatre (Surgery)

**Path:** `/theatre` | **API:** `/api/v1/theatre` | **Module:** `theatre`

Surgical case management, theatre scheduling, and operative documentation.

#### Features
- Theatre room management (Major, Minor, Day Surgery, Emergency, Obstetric)
- Surgical case scheduling with priority levels
- Pre-operative checklists
- Anaesthesia type selection (General, Spinal, Epidural, Local, Sedation)
- Operative notes documentation
- Post-operative monitoring

---

### 6.9 Dental

**Path:** `/dental` | **API:** `/api/v1/dental` | **Module:** `dental`

Dental clinic management with charting and treatment planning.

#### Features
- Dental chart (tooth-by-tooth status tracking)
- Visit documentation
- Treatment plan creation and tracking
- Procedure recording with tooth references

---

### 6.10 MCH (Mother & Child Health)

**Path:** `/mch` | **API:** `/api/v1/mch` | **Module:** `mch`

Comprehensive maternal and child health following Kenya MOH registers (MOH 405, MOH 333, MOH 510).

#### ANC (Antenatal Care)
- ANC profile creation with obstetric history
- Risk assessment (Low/Medium/High/Very High)
- Visit documentation per WHO focused ANC model
- Birth plan recording

#### Delivery
- Labour monitoring
- Delivery record (normal, caesarean, assisted)
- Newborn details (APGAR scores, weight)
- Complications tracking

#### Child Health
- Growth monitoring
- Immunization schedule tracking (Kenya KEPI schedule)
- Milestone documentation
- Well-child visit records

---

### 6.11 Billing & Payments

**Path:** `/billing` | **API:** `/api/v1/billing` | **Module:** `billing`

Complete revenue cycle management with Kenya-specific payment methods.

#### Payment Methods
| Method | Description |
|--------|-----------|
| **Cash** | Direct cash payment |
| **M-Pesa** | Mobile money via Safaricom (STK Push integration) |
| **Insurance** | SHA, NHIF, or private insurance claims |
| **Exemption** | Waiver for eligible patients |

#### Billing Workflow
1. Services rendered create invoice line items automatically
2. Invoice generated with facility-specific numbering
3. Patient pays via preferred method
4. For M-Pesa: STK Push sent to phone, payment confirmed via callback
5. Receipt generated (can print on A4 or 80mm thermal)
6. All amounts stored in **KES cents** for financial precision

---

### 6.12 Insurance & SHA Claims

**Path:** `/insurance` | **API:** `/api/v1/insurance` | **Module:** `insurance`

Insurance scheme management and claims processing.

#### Supported Schemes
- **SHA** (Social Health Authority) — Kenya's national health insurance
- **NHIF** (legacy)
- **Private Insurance** — Multiple scheme support
- **Corporate** — Employer-sponsored plans

#### Claims Workflow
1. Verify patient insurance eligibility at registration
2. Services documented during encounter
3. Claim created with diagnosis codes, procedures, and amounts
4. AI Claims Agent (Enterprise) auto-maps SHA codes and validates completeness
5. Claim submitted electronically
6. Track claim status: Submitted → Under Review → Approved/Rejected → Paid

---

### 6.13 Inventory Management

**Path:** `/inventory` | **API:** `/api/v1/inventory` | **Module:** `inventory`

General inventory management for non-pharmaceutical supplies.

#### Features
- Item categorization (Medical Supplies, Equipment, Office, Cleaning, Kitchen)
- Stock level tracking with reorder points
- Purchase order management
- Supplier directory
- Stock transactions (receipt, issue, adjustment, transfer, return, write-off)
- AI-predicted stockout alerts (Enterprise)

---

### 6.14 Appointments

**Path:** `/appointments` | **API:** `/api/v1/appointments` | **Module:** `appointments`

Appointment scheduling with doctor availability management.

#### Features
- Doctor schedule configuration (days, hours, consultation duration)
- Available slot generation
- Appointment booking with priority levels
- Check-in workflow
- No-show tracking with AI prediction (Enterprise)
- Appointment reminders via SMS/WhatsApp

---

### 6.15 Referrals

**Path:** `/referrals` | **API:** `/api/v1/referrals` | **Module:** `referrals`

Inter-facility referral management.

#### Referral Types
- **External Outbound:** Sending patient to another facility
- **External Inbound:** Receiving patient from another facility
- **Internal:** Specialist referral within the facility

#### Urgency Levels
Routine, Urgent, Emergency

---

### 6.16 HR & Staff Management

**Path:** `/hr` | **API:** `/api/v1/hr` | **Module:** `hr`

Human resources management for hospital staff.

#### Features
- Staff directory with credentials and specializations
- Shift scheduling and assignment
- Leave management (Annual, Sick, Maternity, Paternity, Study, Compassionate, Unpaid)
- Attendance tracking (clock-in/clock-out)
- Department-level staffing overview

---

### 6.17 Reports & Dashboards

**Path:** `/reports` | **API:** `/api/v1/reports` | **Module:** `reports`

Facility reporting and operational dashboards.

#### Built-in Reports
| Report | Code | Description |
|--------|------|-------------|
| OPD Daily | OPD_DAILY | Daily outpatient attendance by date |
| IPD Census | IPD_CENSUS | Admissions, discharges, bed occupancy |
| Lab Workload | LAB_WORKLOAD | Orders, completions, critical results |
| Pharmacy Stock | PHARMACY_STOCK | Current inventory status |
| Revenue Summary | REVENUE_SUMMARY | Revenue by period and payment method |
| MOH 705A | MOH_705A | Outpatient morbidity summary |
| MOH 705B | MOH_705B | Inpatient morbidity summary |
| MOH 710 | MOH_710 | Immunization report |
| MOH 711 | MOH_711 | Integrated RH/HIV/TB/Malaria summary |
| MOH 713 | MOH_713 | Laboratory summary |
| MOH 718 | MOH_718 | Maternity register summary |
| Top Diagnoses | TOP_DIAGNOSES | Top 20 diagnoses by frequency |

#### Facility Dashboard
Real-time overview showing:
- Today's OPD visits, admissions, discharges
- Revenue collected
- Department utilization
- Pending lab orders
- Critical alerts
- 7-day trend charts

---

## 7. AI-Powered Features

> **Enterprise and Government tiers only.** AI features require the `ai_features` flag.

### Clinical Safety Guarantee

**AI never auto-commits to patient records.** Every AI-generated suggestion, prediction, or analysis requires explicit clinician sign-off before being saved to the patient chart. This is a non-negotiable safety requirement.

### AI Model Routing

Aifya uses self-hosted models with automatic routing based on task complexity:

| Complexity | Model | Port | Use Cases |
|-----------|-------|------|-----------|
| Simple | Qwen 3.5 72B | 8002 | Template filling, simple Q&A |
| Medium | Distill-32B | 8003 | Summaries, translations |
| Complex | DeepSeek-R1 671B | 8001 | Multi-step reasoning, agentic workflows |
| Medical | MedGemma 27B | 8004 | Clinical docs, ScribeAI, trial screening, CDS, imaging, prescriptions |

---

### 7.1 ScribeAI (Ambient Documentation)

ScribeAI listens to doctor-patient conversations and automatically extracts structured clinical data.

#### How to Use
1. During consultation, click the **microphone button** in the OPD encounter view
2. The recording indicator pulses while capturing audio
3. Click stop when consultation ends
4. ScribeAI transcribes audio and extracts:
   - Chief complaint
   - History of present illness
   - Vital signs mentioned
   - Diagnoses (with ICD-10/11 codes)
   - Medications prescribed
   - Lab orders
   - Procedures performed
   - Disposition plan
5. Review the extraction panel — each item shows a confidence score
   - Green (90%+): High confidence
   - Amber (70-89%): Review recommended
   - Red (<70%): Manual verification needed
6. Click **Sign Off** to accept or **Discard** to reject

#### Privacy
- Audio is processed by the self-hosted Whisper model — never sent to external services
- Audio files are deleted after processing (not stored permanently)

---

### 7.2 Clinical Decision Support (CDS)

The CDS engine runs automatically during clinical workflows, providing real-time alerts.

#### Alert Categories
| Category | Description |
|----------|-----------|
| Drug-Drug Interaction | Two medications interact dangerously |
| Drug-Allergy | Prescribed drug matches patient's known allergy |
| Drug-Condition | Drug contraindicated for patient's condition |
| Drug-Age | Inappropriate for patient's age group |
| Drug-Pregnancy | Unsafe during pregnancy |
| Drug-Dose | Dosage outside safe range |
| Critical Vital | Vital sign in dangerous range |
| Vital Trend | Deteriorating vital sign pattern |
| Sepsis Risk | qSOFA/SIRS criteria met |
| Lab Critical | Lab result in panic value range |
| Lab Trend | Worsening lab result pattern |

#### Response Actions
- **Block:** Cannot proceed until resolved (critical drug interactions)
- **Warn:** Strong recommendation to reconsider
- **Suggest:** Clinical suggestion for improvement
- **Inform:** Informational notice

Clinicians can **override** warnings with a documented reason, creating an audit trail.

---

### 7.3 Predictive Analytics

**Path:** `/analytics` | **API:** `/api/v1/analytics`

AI-powered predictions for operational planning:

#### Readmission Risk
- Predicts 30-day readmission probability per patient
- Factors: diagnosis severity, comorbidities, age, prior admissions, length of stay, medication count, lab abnormalities
- Risk levels: Low (<20%), Medium (20-50%), High (50-80%), Critical (>80%)

#### Bed Demand Forecast
- Predicts bed occupancy for the next 7 days
- Uses 90-day historical data + day-of-week patterns
- Helps plan staffing and discharge timing

#### No-Show Prediction
- Predicts appointment no-show probability
- Factors: history, day of week, appointment type, lead time, weather, distance
- Suggests interventions (SMS reminder, overbooking)

#### Stockout Prediction
- Predicts inventory stockouts by item
- Based on consumption rate trends
- Urgency levels: Critical, High, Medium, Low

#### Revenue Forecast
- Projects revenue for the next 3 months
- Linear trend analysis with seasonal adjustment
- Confidence bounds for planning

---

### 7.4 AI Medical Imaging

**API:** `/api/v1/imaging`

#### Chest X-ray TB Screening
- Upload chest X-ray image
- AI returns TB probability, affected lung zones, cavitation detection
- High-probability results include recommendation for GeneXpert sputum test
- Results always require radiologist confirmation

#### Retinal Scan Analysis
- Upload fundus photograph
- AI grades diabetic retinopathy (0-4 scale)
- Detects macular edema
- Assesses glaucoma risk
- Generates ophthalmology referral recommendation

#### General Chest X-ray
- Multimodal LLM analyzes chest radiograph
- Reports on cardiac silhouette, lung fields, mediastinum, pleural spaces
- Advisory only — supplements, never replaces, radiologist reading

---

### 7.5 Multi-Agent Workflows

**API:** `/api/v1/agents`

Complex clinical tasks handled by AI agent chains — multiple AI steps coordinated automatically.

#### Discharge Agent (5 steps)
1. Gathers clinical summary from patient record
2. AI generates comprehensive discharge summary
3. AI performs medication reconciliation
4. AI creates follow-up care plan
5. AI generates bilingual (EN/SW) patient education materials

#### SHA Claims Agent (5 steps)
1. Gathers encounter data (diagnoses, procedures, drugs)
2. AI maps clinical data to SHA claim codes
3. AI validates claim completeness
4. AI generates clinical narrative for claim
5. Packages claim for submission

#### Trial Screening Agent (3 steps)
1. Gathers comprehensive patient clinical profile
2. AI matches patient against active trial criteria
3. AI generates screening report with eligibility scores

All agent workflows return with status **"Awaiting Clinician"** — output must be reviewed and approved.

---

## 8. Integrations

### 8.1 M-Pesa Daraja Payments

**API:** `/api/v1/mpesa`

Integrated M-Pesa mobile money payments via Safaricom's Daraja API.

#### STK Push (Lipa Na M-Pesa)
1. Billing clerk enters patient phone number and amount
2. System sends STK Push — patient sees USSD prompt on phone
3. Patient enters M-Pesa PIN to confirm
4. Payment confirmed automatically via callback
5. Invoice updated, receipt generated

#### C2B (Customer to Business)
- Patients can pay directly to the facility's Paybill/Till number
- System auto-matches payments to invoices via account reference
- Unmatched payments logged for manual reconciliation

#### Configuration
Set in `.env`:
```
MPESA_CONSUMER_KEY=your_key
MPESA_CONSUMER_SECRET=your_secret
MPESA_SHORTCODE=your_shortcode
MPESA_PASSKEY=your_passkey
MPESA_ENVIRONMENT=sandbox  # or "production"
MPESA_CALLBACK_URL=https://your-public-url
```

---

### 8.2 FHIR R4 Interoperability

**Path:** `/integrations/fhir` | **API:** `/api/v1/fhir`

Standards-based health data exchange following HL7 FHIR R4.

#### Supported Resources
| FHIR Resource | Aifya Source | Operations |
|--------------|-------------|-----------|
| Patient | Patient records | Read, Search |
| Encounter | OPD/IPD encounters | Read, Search |
| Observation | Vitals, Lab results | Search |
| MedicationRequest | Prescriptions | Search |
| Condition | Diagnoses | Search |
| DiagnosticReport | Lab orders + results | Read |

#### Key Endpoints
- `GET /fhir/metadata` — CapabilityStatement (server description)
- `GET /fhir/Patient/{id}` — Read single patient
- `GET /fhir/Patient?name=John` — Search patients
- `GET /fhir/Observation?patient={id}&category=vital-signs` — Patient vitals

All responses use `application/fhir+json` content type with proper FHIR resource formatting, LOINC codes for observations, and ICD-10 for conditions.

#### FHIR Explorer
The web UI at `/integrations/fhir` provides:
- Server capability statement viewer
- Resource type browser with search parameters
- Interactive resource search and JSON viewer

---

### 8.3 MOH / DHIS2 Reporting

**Path:** `/reports/moh` | **API:** `/api/v1/dhis2`

Automated generation of Kenya Ministry of Health standard reports and DHIS2 submission.

#### Supported MOH Forms

| Form | Title | Content |
|------|-------|---------|
| **MOH 705A** | Outpatient Morbidity Summary | OPD diagnoses by ICD-10, age band, and sex |
| **MOH 705B** | Inpatient Morbidity Summary | IPD diagnoses by ICD-10 and sex |
| **MOH 710** | Immunization Report | Vaccines administered by type and dose |
| **MOH 711** | Integrated Summary | ANC, deliveries, HIV/TB/Malaria indicators |
| **MOH 713** | Laboratory Summary | Lab tests by type, completions, critical results |
| **MOH 718** | Maternity Register Summary | Deliveries by mode, outcome, complications |

#### How to Generate Reports
1. Navigate to Reports > MOH Reports
2. Select reporting period (defaults to previous month)
3. Click "Generate" for individual form or "Generate All"
4. Review report data in table/indicator view
5. If DHIS2 is configured, submit directly to national DHIS2 instance

#### DHIS2 Configuration
Set in `.env`:
```
DHIS2_BASE_URL=https://hiskenya.org
DHIS2_USERNAME=your_username
DHIS2_PASSWORD=your_password
```
Each facility must have its `dhis2_org_unit_id` configured in the facility settings.

#### Automated Monthly Sync
A Celery scheduled task runs on the 5th of each month to auto-generate all MOH forms for the previous month and submit to DHIS2 (if configured).

---

### 8.4 Patient Communications (SMS/WhatsApp)

**Path:** `/communications` | **API:** `/api/v1/communications`

Multi-channel patient engagement — SMS, WhatsApp, and email.

#### Message Categories
- Appointment Reminders
- Lab Results Notification
- Prescription Alerts
- ANC Visit Reminders
- Immunization Reminders
- Discharge Instructions
- Follow-up Reminders
- Billing Notifications
- Custom Messages

#### Features
- **Template System:** Pre-built bilingual (EN/SW) message templates with placeholders
- **Bulk Messaging:** Send to multiple patients at once
- **Delivery Tracking:** Real-time status (Queued → Sent → Delivered → Read → Failed)
- **Patient Preferences:** Respect opt-out preferences per category (Kenya DPA compliance)
- **Consent Management:** Track communication consent per Kenya Data Protection Act

#### Providers
- **SMS:** Africa's Talking API
- **WhatsApp:** Meta WhatsApp Cloud API

---

### 8.5 Federated Analytics & Disease Surveillance

**API:** `/api/v1/federated`

County-level anonymized analytics for public health surveillance.

#### Anonymized Facility Reports
Generates aggregate counts per facility period — total OPD visits, admissions, deliveries, diagnosis counts, lab tests, immunizations. **No patient-identifiable information** is included.

#### Disease Surveillance
Tracks top conditions with trend comparison against previous periods. Alert levels:

| Level | Threshold | Action |
|-------|----------|--------|
| Normal | Baseline | Routine monitoring |
| Watch | 20% above baseline | Enhanced monitoring |
| Alert | 50% above baseline | Prepare outbreak response |
| Outbreak | 100% above baseline | Immediate investigation, notify County CDSC |

#### Notifiable Diseases Tracked
Cholera, Typhoid, Diarrhoea, TB, Dengue, Malaria, HIV, Influenza, Brucellosis, Rabies, Plague, Measles, Neonatal Tetanus — per Kenya Public Health Act.

---

## 9. Offline-First Operation

Aifya is designed to work without internet connectivity — critical for many Kenyan health facilities.

### How It Works

1. **Data Caching:** All data fetched from the server is cached locally in the browser's IndexedDB
2. **Offline Mutations:** When you create or update data while offline, changes are queued locally
3. **Auto-Sync:** When connectivity returns, queued changes sync automatically
4. **Conflict Resolution:** Server data takes priority; conflicts are logged for review

### What Works Offline
- Patient registration
- Vital signs recording
- Prescription writing
- Diagnosis entry
- Basic billing
- Viewing cached patient records

### What Requires Connectivity
- AI features (ScribeAI, CDS, Analytics, Imaging)
- M-Pesa payments
- SMS/WhatsApp sending
- DHIS2 submission
- FHIR data exchange
- Real-time queue updates from other devices

### Visual Indicator
An offline badge appears in the UI when connectivity is lost. A "Syncing..." indicator shows when queued changes are being uploaded.

---

## 10. Clinical Safety Protocols

### Non-Negotiable Rules

1. **AI Never Auto-Commits**
   Every AI suggestion — ScribeAI extractions, CDS alerts, agent workflow outputs, imaging analysis — requires explicit clinician review and sign-off before being recorded in the patient chart.

2. **Drug Interaction Checks**
   Before any prescription is saved, the CDS engine checks for drug-drug interactions, allergy cross-reactions, pregnancy contraindications, and dosage safety. **Critical interactions block the save** until the clinician provides an override reason.

3. **Critical Lab Values**
   When a lab result falls in the panic/critical range, an immediate notification is sent to the ordering physician. This alert cannot be silenced until acknowledged.

4. **Serious Adverse Events (Clinical Trials)**
   SAEs must be reportable to the trial sponsor within 24 hours. The system generates pre-filled CIOMS forms via AI.

5. **Audit Trail**
   All clinical data uses event sourcing — every change creates an immutable event record. No clinical data can be truly deleted (soft-delete only). This provides a complete audit trail for regulatory compliance, with 20-year retention.

6. **Multi-Tenant Isolation**
   Every database query is filtered by facility_id. PostgreSQL Row-Level Security provides defense-in-depth. Cross-facility data access is architecturally impossible.

---

## 11. Kenya Compliance

### Data Protection Act (DPA) / ODPC
- Patient consent tracked and enforced for communications
- Opt-out categories respected per patient preference
- Communication opt-out honored immediately
- Data retention policies configurable per facility

### Digital Health Act
- Event-sourced immutable clinical records
- Complete audit trail for all data access
- Soft-delete only — 20-year retention capability

### SHA (Social Health Authority)
- Integrated e-Claims submission
- SHA code mapping via AI
- Claim validation and narrative generation
- Real-time claim status tracking

### MOH Reporting
- Automated MOH 705A/B, 710, 711, 713, 718 generation
- DHIS2 API integration for electronic submission
- Monthly automated sync on the 5th of each month

### KRA eTIMS
- Invoice data formatted for eTIMS compliance
- Tax calculation per Kenyan tax law

---

## 12. Administration Guide

### Environment Configuration

All configuration is managed via environment variables (`.env` file). Key settings:

#### Database
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/aifya
```

#### Authentication
```bash
KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_REALM=aifya
KEYCLOAK_CLIENT_ID=aifya-web
KEYCLOAK_CLIENT_SECRET=your_secret
```

#### AI Models
```bash
VLLM_DEEPSEEK_R1_URL=http://ai-gpu:8001/v1
VLLM_QWEN_72B_URL=http://ai-gpu:8002/v1
VLLM_DISTILL_32B_URL=http://ai-gpu:8003/v1
VLLM_MEDGEMMA_27B_URL=http://ai-gpu:8004/v1
AI_SERVICE_URL=http://ai-service:8025
```

#### External Services
```bash
# M-Pesa
MPESA_CONSUMER_KEY=key
MPESA_CONSUMER_SECRET=secret
MPESA_SHORTCODE=123456
MPESA_ENVIRONMENT=production

# DHIS2
DHIS2_BASE_URL=https://hiskenya.org
DHIS2_USERNAME=user
DHIS2_PASSWORD=pass

# Communications
AFRICASTALKING_API_KEY=key
AFRICASTALKING_USERNAME=username
WHATSAPP_ACCESS_TOKEN=token
WHATSAPP_PHONE_NUMBER_ID=phone_id
```

### Database Migrations

```bash
# Apply all pending migrations
cd services/api-gateway && alembic upgrade head

# Create a new migration after model changes
cd services/api-gateway && alembic revision --autogenerate -m "add new table"

# Rollback last migration
cd services/api-gateway && alembic downgrade -1
```

**Important:** Never drop columns in migrations. Use `is_deprecated` flag instead.

### User Management

Users are managed in Keycloak:

1. Access Keycloak admin console (`http://localhost:8080`)
2. Login with admin credentials
3. Select the `aifya` realm
4. **Create User:** Users > Add User > Set username, email, first/last name
5. **Set Password:** Credentials tab > Set password > Disable "Temporary"
6. **Assign Roles:** Role Mappings > Add realm roles
7. **Set Facility:** Attributes tab > Add `facility_id` attribute with facility UUID

### Backup & Recovery

```bash
# Database backup
pg_dump -h localhost -U aifya_user aifya > backup_$(date +%Y%m%d).sql

# MinIO backup (documents, images)
mc mirror minio/aifya-documents ./backup-documents/

# Restore database
psql -h localhost -U aifya_user aifya < backup_20260410.sql
```

### Monitoring

| Service | URL | Purpose |
|---------|-----|---------|
| Grafana | http://localhost:3001 | Dashboards and alerts |
| Prometheus | http://localhost:9090 | Metrics collection |
| Loki | (via Grafana) | Log aggregation |
| Tempo | (via Grafana) | Distributed tracing |

---

## 13. Troubleshooting

### Common Issues

#### "You are offline" banner won't go away
- Check your network connection
- Try refreshing the browser
- Clear IndexedDB cache: DevTools > Application > IndexedDB > Delete database

#### Login fails with "Session Expired"
- Keycloak tokens expire after configurable period (default 30 minutes)
- Click the login button to re-authenticate
- If persistent, check Keycloak server status

#### CDS alerts not appearing
- Ensure the `encounters` module is licensed
- Check that the CDS engine service is running
- Verify patient has allergies/medications recorded for interaction checking

#### M-Pesa STK Push not received
- Verify phone number is in correct format (07XX or +254XX)
- Check MPESA_ENVIRONMENT matches your credentials (sandbox vs production)
- Ensure callback URL is publicly accessible
- Check M-Pesa status: GET `/api/v1/mpesa/status`

#### MOH reports show zero data
- Verify the date range covers a period with clinical activity
- Ensure diagnoses have ICD-10 codes assigned
- Check that encounter types are correctly categorized (outpatient vs inpatient)

#### AI features return "service unavailable"
- Verify vLLM model servers are running on ports 8001-8003
- Check GPU memory — large models need A100 80GB
- Review ai-service logs: `docker logs aifya-ai-service`

#### Slow performance
- Check Redis is running (caching reduces database load)
- Monitor PostgreSQL connections: too many concurrent queries may need pool tuning
- Review Grafana dashboards for resource bottlenecks

---

## 14. API Reference

### Base URL
```
http://localhost:8000/api/v1
```

### Authentication
All endpoints (except `/api/health` and M-Pesa callbacks) require a Bearer token:
```
Authorization: Bearer <keycloak_jwt_token>
```

### Idempotency
All POST/PATCH endpoints support idempotency via header:
```
X-Idempotency-Key: <unique-uuid>
```

### Complete Endpoint Map

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| **Patients** | | |
| GET | `/patients` | List patients |
| POST | `/patients` | Register patient |
| GET | `/patients/{id}` | Get patient |
| PATCH | `/patients/{id}` | Update patient |
| **Encounters** | | |
| GET | `/encounters/queue` | OPD queue |
| POST | `/encounters` | Create encounter |
| POST | `/encounters/{id}/vitals` | Record vitals |
| POST | `/encounters/{id}/diagnoses` | Add diagnosis |
| POST | `/encounters/{id}/prescriptions` | Add prescription |
| POST | `/encounters/{id}/lab-orders` | Order lab tests |
| **Pharmacy** | | |
| GET | `/pharmacy/queue` | Dispensing queue |
| POST | `/pharmacy/dispense` | Dispense medication |
| GET | `/pharmacy/inventory` | Stock list |
| **Laboratory** | | |
| GET | `/laboratory/worklist` | Lab worklist |
| POST | `/laboratory/{id}/results` | Enter results |
| POST | `/laboratory/{id}/verify` | Verify results |
| **Billing** | | |
| GET | `/billing/invoices` | Invoice list |
| POST | `/billing/invoices` | Create invoice |
| POST | `/billing/invoices/{id}/pay` | Record payment |
| **IPD** | | |
| GET | `/ipd/wards` | Ward list |
| POST | `/ipd/admissions` | Admit patient |
| POST | `/ipd/admissions/{id}/discharge` | Discharge |
| **M-Pesa** | | |
| POST | `/mpesa/stk-push` | Initiate payment |
| GET | `/mpesa/stk-status/{id}` | Check status |
| **FHIR** | | |
| GET | `/fhir/metadata` | Capability statement |
| GET | `/fhir/Patient/{id}` | Read patient |
| GET | `/fhir/Patient?name=X` | Search patients |
| GET | `/fhir/Observation?patient=X` | Search observations |
| **DHIS2** | | |
| POST | `/dhis2/moh/generate` | Generate MOH form |
| GET | `/dhis2/moh/generate-all` | Generate all forms |
| GET | `/dhis2/moh/forms` | List form types |
| **AI Agents** | | |
| POST | `/agents/discharge` | Run discharge agent |
| POST | `/agents/claims` | Run claims agent |
| POST | `/agents/screening` | Run screening agent |
| **Analytics** | | |
| GET | `/analytics/dashboard` | Full dashboard |
| GET | `/analytics/readmission-risk/{id}` | Patient risk |
| GET | `/analytics/bed-forecast` | Bed demand |
| **Federated** | | |
| GET | `/federated/surveillance` | Disease surveillance |
| GET | `/federated/outbreaks` | Outbreak alerts |
| GET | `/federated/facility-report` | Anonymized report |

### Interactive Documentation
In development mode, full interactive API documentation is available at:
- **Swagger UI:** `http://localhost:8000/api/docs`
- **ReDoc:** `http://localhost:8000/api/redoc`
- **OpenAPI JSON:** `http://localhost:8000/api/openapi.json`

These are disabled in production for security.

---

## 15. Glossary

| Term | Definition |
|------|-----------|
| **ANC** | Antenatal Care — prenatal care during pregnancy |
| **C2B** | Customer to Business — M-Pesa payment to Paybill/Till |
| **CDS** | Clinical Decision Support — automated clinical safety alerts |
| **CIOMS** | Council for International Organizations of Medical Sciences — SAE reporting form |
| **DHIS2** | District Health Information Software — Kenya's national health data platform |
| **DPA** | Data Protection Act — Kenya's data privacy law |
| **FHIR** | Fast Healthcare Interoperability Resources — HL7 health data standard |
| **GCP** | Good Clinical Practice — clinical trial compliance standard |
| **HMIS** | Hospital Management Information System |
| **ICD-10** | International Classification of Diseases, 10th Revision |
| **IPD** | Inpatient Department |
| **KEPI** | Kenya Expanded Programme on Immunization |
| **KES** | Kenyan Shilling |
| **LOINC** | Logical Observation Identifiers Names and Codes — lab test coding |
| **MCH** | Mother and Child Health |
| **MOH** | Ministry of Health |
| **MRN** | Medical Record Number |
| **NHIF** | National Hospital Insurance Fund (legacy, now SHA) |
| **ODPC** | Office of the Data Protection Commissioner |
| **OPD** | Outpatient Department |
| **PWA** | Progressive Web App |
| **qSOFA** | Quick Sequential Organ Failure Assessment — sepsis screening |
| **RAG** | Retrieval-Augmented Generation — AI + knowledge base search |
| **SAE** | Serious Adverse Event |
| **SHA** | Social Health Authority — Kenya's national health insurance |
| **SIRS** | Systemic Inflammatory Response Syndrome |
| **STK Push** | SIM Toolkit Push — M-Pesa payment prompt to phone |
| **vLLM** | Very Large Language Model inference engine |

---

**Aifya** — Akili kwa Afya — Intelligence for Health

For support, contact your facility's IT administrator or the Aifya support team.
