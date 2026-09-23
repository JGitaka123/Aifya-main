-- backend/database/seed_data.sql
-- Mock data for Aifya Health Platform

-- 1. Create External EMR Tables (Mocking Q-Afya)
CREATE TABLE IF NOT EXISTS patient_registration (
    national_id VARCHAR(50) PRIMARY KEY,
    insurance_no VARCHAR(50),
    insurance_status VARCHAR(50),
    insurance_package VARCHAR(50),
    max_benefit_cap NUMERIC(12, 2),
    full_name VARCHAR(255),
    gender VARCHAR(10),
    date_of_birth DATE
);

CREATE TABLE IF NOT EXISTS patient_encounters (
    encounter_id VARCHAR(50) PRIMARY KEY,
    patient_id VARCHAR(50) REFERENCES patient_registration(national_id),
    encounter_date TIMESTAMPTZ DEFAULT NOW(),
    clinical_notes TEXT,
    diagnosis_code VARCHAR(50),
    last_modified_by VARCHAR(100),
    last_modified_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lab_results (
    id SERIAL PRIMARY KEY,
    encounter_id VARCHAR(50) REFERENCES patient_encounters(encounter_id),
    test_name VARCHAR(255),
    result_value VARCHAR(255),
    loinc_code VARCHAR(50),
    result_date TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS prescriptions (
    id SERIAL PRIMARY KEY,
    encounter_id VARCHAR(50) REFERENCES patient_encounters(encounter_id),
    drug_name VARCHAR(255),
    dose VARCHAR(50),
    route VARCHAR(50),
    frequency VARCHAR(50),
    duration VARCHAR(50),
    is_new BOOLEAN DEFAULT TRUE,
    prescription_date TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Insert Mock Data
-- Default Facility
INSERT INTO facility_config (facility_name, facility_level, sha_facility_code)
VALUES ('Mary Help Hospital', 'Level 4', 'MHH-001')
ON CONFLICT (sha_facility_code) DO NOTHING;

-- Mock Patients
INSERT INTO patient_registration (national_id, insurance_no, insurance_status, insurance_package, max_benefit_cap, full_name, gender, date_of_birth)
VALUES 
('12345678', 'SHA-1001', 'active', 'SHIF', 500000.00, 'John Kamau Doe', 'M', '1985-05-15'),
('87654321', 'SHA-1002', 'active', 'SHIF', 250000.00, 'Mary Atieno Anyango', 'F', '1992-08-22'),
('11223344', 'SHA-1003', 'inactive', 'SHIF', 0.00, 'Peter Njoroge', 'M', '1970-01-10')
ON CONFLICT (national_id) DO NOTHING;

-- Mock Encounters
INSERT INTO patient_encounters (encounter_id, patient_id, encounter_date, clinical_notes, diagnosis_code, last_modified_by)
VALUES 
('ENC-2026-001', '12345678', NOW() - INTERVAL '2 days', 'Patient complains of persistent headache and fever.', 'BA00', 'DR_SMITH'),
('ENC-2026-002', '87654321', NOW() - INTERVAL '1 day', 'Routine antenatal checkup. All vitals normal.', 'Z34.9', 'DR_MUSA')
ON CONFLICT (encounter_id) DO NOTHING;

-- Mock Labs
INSERT INTO lab_results (encounter_id, test_name, result_value, loinc_code)
VALUES 
('ENC-2026-001', 'Malaria RDT', 'Positive', '32700-7'),
('ENC-2026-001', 'Hemoglobin', '12.5 g/dL', '718-7')
ON CONFLICT DO NOTHING;

-- Mock Prescriptions
INSERT INTO prescriptions (encounter_id, drug_name, dose, route, frequency, duration)
VALUES 
('ENC-2026-001', 'Artemether/Lumefantrine', '80/480mg', 'Oral', 'BD', '3 days'),
('ENC-2026-001', 'Paracetamol', '1g', 'Oral', 'TDS', '3 days')
ON CONFLICT DO NOTHING;
