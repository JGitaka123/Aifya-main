// Mock User Data
export const MOCK_USER = {
    id: "u-1",
    email: "admin@aifya.com",
    full_name: "Dr. Alice Smith",
    role: "superadmin",
    is_active: true,
    license_no: "MED-12345",
};

// Mock Stats and Health
export const MOCK_STATS = {
    claims: {
        total: 1250,
        blocked: 45,
        passed: 1105,
        warnings_only: 65,
        overridden: 35,
        today_count: 24,
        total_billed: 4500000,
        total_approved: 3800000,
        by_status: {
            pending: 120,
            approved: 950,
            rejected: 80,
        },
    },
    health: {
        status: "healthy",
        components: {
            api: "ok",
            database: "ok",
            redis: "ok",
            llm_provider: "ok",
        },
    },
};

// Mock Patients
export const MOCK_PATIENTS = [
    {
        id: "P-1001",
        full_name: "John Doe",
        gender: "male",
        dob: "1980-05-15",
        phone: "+254 711 222 333",
        email: "john.doe@example.com",
        address: "123 Nairobi St, Westlands",
        blood_group: "O+",
        allergies: ["Penicillin", "Peanuts"],
        national_id: "23456789",
        insurance_provider: "NHIF",
        insurance_member_no: "NHIF-123456",
        insurance_status: "ACTIVE",
        insurance_package: "SHIF-PREMIUM",
        max_benefit_cap: 500000
    },
    {
        id: "P-1002",
        full_name: "Mary Wambui",
        gender: "female",
        dob: "1992-08-24",
        phone: "+254 722 000 111",
        national_id: "98765432",
        insurance_provider: "SHA",
        insurance_member_no: "SHA-998877",
        insurance_status: "ACTIVE",
        insurance_package: "SHA-STANDARD",
        max_benefit_cap: 200000
    },
];

// Mock Encounters for Patient P-1001
export const MOCK_ENCOUNTERS = [
    {
        id: "E-5001",
        date: "2026-03-15T10:00:00Z",
        type: "Outpatient",
        clinician: "Dr. Alice Smith",
        facility: "Mary Help Hospital",
        status: "Completed",
        soap: {
            subjective: "Patient reports persistent cough and mild fever for 3 days.",
            objective: "Temp: 38.2°C, BP: 120/80, Pulse: 78. Lungs show mild wheezing.",
            assessment: "Acute Bronchitis",
            plan: "Prescribed Amoxicillin 500mg TDS for 5 days. Advised rest and fluids.",
        },
    },
];

// Mock SOAP Note for Scribe (Matches ClinicalExtraction interface)
export const MOCK_SOAP_NOTE = {
    chief_complaint: "Sharp lower back pain radiating to right leg",
    hpi: "Patient reports pain started 24 hours ago after lifting heavy boxes. Severity 8/10. Constant aching with sharp shooting pains on movement.",
    vitals: [
        { name: "Heart Rate", value: "78", loinc_code: "8867-4", confidence: 0.98 },
        { name: "Blood Pressure", value: "135/85", loinc_code: "85354-9", confidence: 0.99 },
        { name: "Temperature", value: "36.8", loinc_code: "8310-5", confidence: 0.95 }
    ],
    physical_exam: "Tenderness over L4-L5 vertebrae. Straight leg raise positive at 45 degrees on the right.",
    diagnoses: [
        { name: "Acute Lumbar Strain", icd11_suggested: "ME84.2", icd11_validated: "ME84.2", is_primary: true, confidence: 0.92 }
    ],
    lab_orders: [
        { test_name: "X-ray Lumbar Spine", loinc_code: "24603-3", urgency: "routine" }
    ],
    medications: [
        { name: "Ibuprofen", dose: "400mg", route: "oral", frequency: "TDS", duration: "5 days", is_new: true }
    ],
    procedures: [],
    disposition: "Home with rest and follow-up in 1 week if no improvement.",
    warnings: ["Rule 7: Lumbar MRI not indicated for acute strain without neurological deficit."]
};

// Mock Audit Logs
export const MOCK_AUDIT_LOGS = [
    {
        id: "L-1",
        created_at: new Date().toISOString(),
        user_name: "Dr. Alice Smith",
        action: "USER_LOGIN_SUCCESS",
        details: "User logged in successfully from 192.168.1.5",
        entity_type: "user",
        entity_id: "u-1"
    },
    {
        id: "L-2",
        created_at: new Date(Date.now() - 1800000).toISOString(),
        user_name: "Dr. Alice Smith",
        action: "PATIENT_LOOKUP",
        details: "Viewed patient records for John Doe",
        entity_type: "patient",
        entity_id: "P-1001"
    },
    {
        id: "L-3",
        created_at: new Date(Date.now() - 3600000).toISOString(),
        user_name: "Dr. Alice Smith",
        action: "CLAIM_SCRUB_PERFORMED",
        details: "Claim scrubbed with 1 violation found",
        entity_type: "claim",
        entity_id: "cl-88921-x7"
    }
];

// Mock Users for Admin
export const MOCK_USERS = [
    { id: "u-1", email: "dr.smith@aifya.com", full_name: "Dr. Alice Smith", role: "clinician", is_active: true, license_no: "MED-12345", created_at: "2024-01-10T08:00:00Z" },
    { id: "u-2", email: "admin@aifya.com", full_name: "System Admin", role: "superadmin", is_active: true, license_no: "ADM-001", created_at: "2023-01-01T08:00:00Z" },
    { id: "u-3", email: "billing@aifya.com", full_name: "Jane Billing", role: "billing_admin", is_active: true, license_no: "BIL-999", created_at: "2024-02-15T08:00:00Z" },
];

// Mock Claims with Violations
// Helper to generate dates in the last 30 days
const daysAgo = (days: number) => new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

// Mock Claims with Violations (Expanded for Analytics)
export const MOCK_CLAIMS = [
    {
        id: "cl-88921-x7",
        encounter_id: "enc-5512",
        qafya_patient_id: "P-1001",
        amount_billed: 4500,
        scrub_status: "blocked",
        claim_status: "pending",
        scrub_violations: [
            { rule_id: "R102", rule_name: "Documentation Link", severity: "BLOCK", message: "Missing linked consultation transcript for this claim amount", suggested_fix: "Finalize and sync the clinician console note first" }
        ],
        created_at: daysAgo(0.1),
        sha_submission_ref: null,
        override_reason: null
    },
    {
        id: "cl-88922-z9",
        encounter_id: "enc-5513",
        qafya_patient_id: "P-1002",
        amount_billed: 12500,
        scrub_status: "passed",
        claim_status: "approved",
        scrub_violations: [],
        created_at: daysAgo(2),
        sha_submission_ref: "SHA-REF-99881122",
        override_reason: null
    },
    {
        id: "cl-88923-a1",
        encounter_id: "enc-5514",
        qafya_patient_id: "P-1001",
        amount_billed: 3200,
        scrub_status: "warnings_only",
        claim_status: "pending",
        scrub_violations: [
            { rule_id: "W04", rule_name: "Patient Age Check", severity: "WARN", message: "Patient age exceeds typical range for this procedure (Verify DOB)", suggested_fix: "Check patient profile for correct date of birth" }
        ],
        created_at: daysAgo(0.5),
        sha_submission_ref: null,
        override_reason: null
    },
    // Randomly generated claims for the last 30 days
    ...Array.from({ length: 27 }).map((_, i) => {
        const statuses = ["passed", "passed", "passed", "blocked", "warnings_only", "overridden"];
        const status = statuses[i % statuses.length];
        const day = Math.floor(i * 1.1);
        const amount = 500 + Math.floor(Math.random() * 15000);

        return {
            id: `cl-mock-${100 + i}`,
            encounter_id: `enc-${1000 + i}`,
            qafya_patient_id: i % 2 === 0 ? "P-1001" : "P-1002",
            amount_billed: amount,
            scrub_status: status,
            claim_status: status === "passed" ? "approved" : "pending",
            scrub_violations: status === "blocked" ? [
                { rule_id: "R201", rule_name: "Duplicate Service", severity: "BLOCK", message: "Service code already billed in recent encounter", suggested_fix: "Remove duplicate line item" }
            ] : status === "warnings_only" ? [
                { rule_id: "W11", rule_name: "Pre-auth Check", severity: "WARN", message: "Pre-authorization recommended for high-value service", suggested_fix: "Ensure pre-auth document is attached" }
            ] : [],
            created_at: daysAgo(day),
            sha_submission_ref: status === "passed" && i % 4 !== 0 ? `SHA-MOCK-${5500 + i}` : null,
            override_reason: status === "overridden" ? "Clinical necessity justified by emergency condition." : null
        };
    })
];

// Consolidated Mock Data Object
export const mockData = {
    auth: {
        login: {
            access_token: "mock_access_token",
            refresh_token: "mock_refresh_token",
            expires_in: 3600,
            user: MOCK_USER,
        },
        profile: MOCK_USER,
    },
    patients: {
        lookup: MOCK_PATIENTS[0],
        encounters: MOCK_ENCOUNTERS,
    },
    scribe: {
        process: MOCK_SOAP_NOTE,
        extract: MOCK_SOAP_NOTE,
    },
    claims: {
        list: {
            total: MOCK_CLAIMS.length,
            claims: MOCK_CLAIMS,
        },
        stats: MOCK_STATS.claims,
    },
    discharge: {
        generate: {
            id: "DS-7001",
            status: "Finalized",
        },
        get: {
            id: "DS-7001",
            patient_name: "John Doe",
            summary: "Patient John Doe was admitted for severe back pain and discharged after successful conservative management.",
            status: "Finalized",
        },
    },
    admin: {
        users: {
            total: MOCK_USERS.length,
            users: MOCK_USERS,
        },
        auditLog: {
            logs: MOCK_AUDIT_LOGS,
        },
        syncStatus: {
            qafya_connection: "connected",
            circuit_breaker_state: "closed",
            circuit_breaker_failures: 0,
            current_latency_ms: 124,
            last_success_timestamp: new Date().toISOString(),
        },
    },
    health: {
        status: "healthy",
        components: MOCK_STATS.health.components,
    },
};
