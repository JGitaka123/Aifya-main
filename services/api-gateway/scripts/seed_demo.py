"""
Aifya HMIS — Comprehensive Demo Seed Script.

Loads all data needed to demo the platform end-to-end:
  - Facility, departments, staff
  - Patients (50 demographically varied)
  - Pharmacy formulary (15 common Kenyan drugs)
  - Finance: Chart of Accounts, posting rules, accounting periods
  - Sample invoices + GL postings (cash + insurance)
  - Sample payments + expenses
  - Payroll: statutory rates, employees, salaries, monthly run
  - Sample leave requests, fixed assets, budgets, recurring templates
  - M-Pesa STK sample records
  - SHA insurance scheme

IDEMPOTENT: re-running does not create duplicates. Deterministic UUIDs
are derived from uuid5(facility_id, entity-name) where applicable; for
other entities a check-then-insert pattern is used.

Usage:
    python scripts/seed_demo.py            # Seed (idempotent)
    python scripts/seed_demo.py --reset    # Soft-delete all demo facility data

Run AFTER `alembic upgrade head`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

# Ensure parent (`api-gateway/`) is on sys.path when this script is
# invoked directly via `python scripts/seed_demo.py`.
_THIS_DIR = Path(__file__).resolve().parent
_API_GATEWAY_DIR = _THIS_DIR.parent
if str(_API_GATEWAY_DIR) not in sys.path:
    sys.path.insert(0, str(_API_GATEWAY_DIR))

from sqlalchemy import select, text, update  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import async_session  # noqa: E402
from app.models.appointment import Appointment  # noqa: E402
from app.models.billing import Invoice, InvoiceItem, Payment  # noqa: E402
from app.models.encounter import Encounter  # noqa: E402
from app.models.facility import Facility  # noqa: E402
from app.models.finance import (  # noqa: E402
    Account,
    AccountingPeriod,
    Budget,
    FixedAsset,
    RecurringTemplate,
)
from app.models.insurance import InsuranceScheme  # noqa: E402
from app.models.mpesa import MpesaStkRequest  # noqa: E402
from app.models.patient import Patient  # noqa: E402
from app.models.payroll import Employee, EmployeeSalary, PayrollRun  # noqa: E402
from app.models.payroll_extra import LeaveType, PayrollLeaveRequest  # noqa: E402
from app.models.pharmacy import PharmacyItem  # noqa: E402
from app.models.staff import Department, Staff  # noqa: E402
from app.models.vital import VitalSign  # noqa: E402
from app.services.finance.posting_engine import post_transaction  # noqa: E402
from app.services.finance.seed_data import seed_facility_finance  # noqa: E402
from app.services.payroll.engine import run_monthly_payroll  # noqa: E402
from app.services.payroll.gl_integration import post_payroll_to_gl  # noqa: E402
from app.services.payroll.seed_data import seed_payroll_defaults  # noqa: E402

# ── Constants ────────────────────────────────────────────────────────────────

# Stable namespace for deterministic UUID generation across runs.
# Re-running the seed yields identical UUIDs, which makes the script idempotent.
DEMO_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "aifya-demo.aifya.co.ke")

DEMO_FACILITY_NAME = "Aifya Demo Hospital"
DEMO_FACILITY_CODE = "AIFYA-DEMO"
DEMO_FACILITY_MFL = "99999"

# Today's reference date (overridable for stable demos)
TODAY = date.today()
NOW = datetime.now(UTC)


def _det(label: str) -> uuid.UUID:
    """Deterministic UUID derived from a label (idempotency key)."""
    return uuid.uuid5(DEMO_NAMESPACE, label)


def _kes_to_cents(kes: int | float | Decimal) -> int:
    """Convert KES to integer cents (per CLAUDE.md money rules)."""
    return int((Decimal(str(kes)) * 100).to_integral_value())


# ── Facility ─────────────────────────────────────────────────────────────────


async def _set_demo_facility_context(db: AsyncSession, facility_id: uuid.UUID) -> None:
    """Point the DB session at the demo facility for Row-Level Security.

    RLS is FORCEd on every facility-scoped table (migration 008), so all
    reads and writes must run with app.current_facility_id set.
    """
    await db.execute(
        text("SELECT set_config('app.current_facility_id', :fid, true)"),
        {"fid": str(facility_id)},
    )

async def get_or_create_facility(db: AsyncSession) -> Facility:
    """Find or create the demo facility (idempotent).

    @param db: Async DB session
    @returns The Facility row (existing or newly created)
    """
    existing = (
        await db.execute(
            select(Facility).where(Facility.code == DEMO_FACILITY_CODE)
        )
    ).scalar_one_or_none()
    if existing is not None:
        await _set_demo_facility_context(db, existing.id)
        return existing

    fac = Facility(
        id=uuid.UUID(settings.beta_facility_id),
        name=DEMO_FACILITY_NAME,
        code=DEMO_FACILITY_CODE,
        facility_type="hospital",
        keph_level="4",
        mfl_code=DEMO_FACILITY_MFL,
        county="Nairobi",
        sub_county="Westlands",
        ward="Parklands",
        physical_address="Aifya Plaza, 5th Floor, Westlands, Nairobi",
        phone="+254700000000",
        email="info@aifya.co.ke",
        website="https://aifya.co.ke",
        timezone="Africa/Nairobi",
        currency="KES",
        is_active=True,
    )
    db.add(fac)
    await db.flush()
    await _set_demo_facility_context(db, fac.id)
    print(f"  Created facility: {fac.name} ({fac.code})")
    return fac


# ── Departments ──────────────────────────────────────────────────────────────


DEPARTMENTS: list[tuple[str, str, str]] = [
    # (code, name, type)
    ("OPD", "Outpatient", "clinical"),
    ("IPD", "Inpatient", "clinical"),
    ("PHARM", "Pharmacy", "clinical"),
    ("LAB", "Laboratory", "clinical"),
    ("RAD", "Radiology", "clinical"),
    ("MCH", "Maternal & Child Health", "clinical"),
    ("ER", "Emergency", "clinical"),
    ("ADMIN", "Administration", "admin"),
]


async def seed_departments(
    db: AsyncSession, facility_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    """Seed the 8 demo departments idempotently.

    @returns Map {code: department_id}
    """
    by_code: dict[str, uuid.UUID] = {}
    existing = (
        await db.execute(
            select(Department).where(Department.facility_id == facility_id)
        )
    ).scalars().all()
    existing_codes = {d.code: d.id for d in existing}

    created = 0
    for code, name, dtype in DEPARTMENTS:
        if code in existing_codes:
            by_code[code] = existing_codes[code]
            continue
        dept = Department(
            id=_det(f"dept:{code}"),
            facility_id=facility_id,
            code=code,
            name=name,
            department_type=dtype,
            is_active=True,
        )
        db.add(dept)
        await db.flush()
        by_code[code] = dept.id
        created += 1

    print(f"  Departments: {created} created, {len(existing_codes)} existing")
    return by_code


# ── Staff ────────────────────────────────────────────────────────────────────

STAFF_DEFINITIONS: list[dict[str, Any]] = [
    # employee_number, first, last, role, title, dept_code, email
    {"emp": "AIFYA-001", "first": "Wanjiku", "last": "Kamau", "role": "admin",
     "title": "Dr.", "dept": "ADMIN", "email": "admin@aifya.co.ke",
     "license_body": "KMPDC", "license": "KMPDC/12345"},
    {"emp": "AIFYA-002", "first": "James", "last": "Otieno", "role": "doctor",
     "title": "Dr.", "dept": "OPD", "email": "doctor@aifya.co.ke",
     "license_body": "KMPDC", "license": "KMPDC/22001"},
    {"emp": "AIFYA-003", "first": "Mary", "last": "Akinyi", "role": "doctor",
     "title": "Dr.", "dept": "IPD", "email": "mary.akinyi@aifya.co.ke",
     "license_body": "KMPDC", "license": "KMPDC/22002"},
    {"emp": "AIFYA-004", "first": "Faith", "last": "Njeri", "role": "nurse",
     "title": "Sister", "dept": "OPD", "email": "nurse@aifya.co.ke",
     "license_body": "NCK", "license": "NCK/33001"},
    {"emp": "AIFYA-005", "first": "Grace", "last": "Wanjiru", "role": "nurse",
     "title": "Sister", "dept": "MCH", "email": "grace.wanjiru@aifya.co.ke",
     "license_body": "NCK", "license": "NCK/33002"},
    {"emp": "AIFYA-006", "first": "Peter", "last": "Mwangi", "role": "pharmacist",
     "title": "Mr.", "dept": "PHARM", "email": "pharmacy@aifya.co.ke",
     "license_body": "PPB", "license": "PPB/44001"},
    {"emp": "AIFYA-007", "first": "John", "last": "Kiprop", "role": "lab_tech",
     "title": "Mr.", "dept": "LAB", "email": "lab@aifya.co.ke",
     "license_body": "KMLTTB", "license": "KMLTTB/55001"},
    {"emp": "AIFYA-008", "first": "Ruth", "last": "Achieng", "role": "cashier",
     "title": "Ms.", "dept": "ADMIN", "email": "cashier@aifya.co.ke",
     "license_body": None, "license": None},
    {"emp": "AIFYA-009", "first": "Esther", "last": "Nyambura", "role": "hr_admin",
     "title": "Ms.", "dept": "ADMIN", "email": "hr@aifya.co.ke",
     "license_body": None, "license": None},
    {"emp": "AIFYA-010", "first": "David", "last": "Kimani", "role": "receptionist",
     "title": "Mr.", "dept": "OPD", "email": "reception@aifya.co.ke",
     "license_body": None, "license": None},
]


async def seed_staff(
    db: AsyncSession,
    facility_id: uuid.UUID,
    dept_map: dict[str, uuid.UUID],
) -> dict[str, uuid.UUID]:
    """Seed 10 demo Staff rows idempotently.

    @returns Map {employee_number: staff.id}
    """
    by_num: dict[str, uuid.UUID] = {}
    existing = (
        await db.execute(
            select(Staff).where(Staff.facility_id == facility_id)
        )
    ).scalars().all()
    existing_by_num = {s.employee_number: s.id for s in existing}

    created = 0
    for s in STAFF_DEFINITIONS:
        if s["emp"] in existing_by_num:
            by_num[s["emp"]] = existing_by_num[s["emp"]]
            continue
        kc_id = _det(f"keycloak:{s['emp']}")
        dept_id = dept_map.get(s["dept"])
        staff = Staff(
            id=_det(f"staff:{s['emp']}"),
            facility_id=facility_id,
            keycloak_user_id=kc_id,
            employee_number=s["emp"],
            first_name=s["first"],
            last_name=s["last"],
            title=s["title"],
            role=s["role"],
            license_body=s["license_body"],
            license_number=s["license"],
            department_id=dept_id,
            primary_department_id=dept_id,
            email=s["email"],
            phone=f"+25470000{int(s['emp'].split('-')[1]):04d}",
            is_active=True,
        )
        db.add(staff)
        await db.flush()
        by_num[s["emp"]] = staff.id
        created += 1

    print(f"  Staff: {created} created, {len(existing_by_num)} existing")
    return by_num


# ── Patients ─────────────────────────────────────────────────────────────────

PATIENTS: list[dict[str, Any]] = [
    # name, dob_offset_years, gender, insurance_provider, conditions, pregnant
    {"first": "Baby", "last": "Mwangi", "age_months": 1, "gender": "female",
     "ins": None, "phone_suffix": "001", "county": "Nairobi"},
    {"first": "Brian", "last": "Otieno", "age_years": 8, "gender": "male",
     "ins": "SHA", "phone_suffix": "002", "county": "Kisumu"},
    {"first": "Sharon", "last": "Achieng", "age_years": 15, "gender": "female",
     "ins": "SHA", "phone_suffix": "003", "county": "Nairobi"},
    {"first": "Kevin", "last": "Kariuki", "age_years": 25, "gender": "male",
     "ins": None, "phone_suffix": "004", "county": "Kiambu"},
    {"first": "Mercy", "last": "Wanjiku", "age_years": 28, "gender": "female",
     "ins": "SHA", "phone_suffix": "005", "county": "Nairobi", "pregnant": True},
    {"first": "Daniel", "last": "Kipchoge", "age_years": 30, "gender": "male",
     "ins": "Britam", "phone_suffix": "006", "county": "Uasin Gishu"},
    {"first": "Lucy", "last": "Njoki", "age_years": 32, "gender": "female",
     "ins": "SHA", "phone_suffix": "007", "county": "Nairobi", "pregnant": True},
    {"first": "Samuel", "last": "Kiplagat", "age_years": 35, "gender": "male",
     "ins": None, "phone_suffix": "008", "county": "Nakuru"},
    {"first": "Faith", "last": "Mumbi", "age_years": 40, "gender": "female",
     "ins": "Jubilee", "phone_suffix": "009", "county": "Nairobi"},
    {"first": "Joseph", "last": "Mutua", "age_years": 45, "gender": "male",
     "ins": "SHA", "phone_suffix": "010", "county": "Machakos",
     "conditions": ["Diabetes Mellitus Type 2"]},
    {"first": "Grace", "last": "Wairimu", "age_years": 50, "gender": "female",
     "ins": "SHA", "phone_suffix": "011", "county": "Nairobi"},
    {"first": "Joshua", "last": "Omondi", "age_years": 60, "gender": "male",
     "ins": "AAR", "phone_suffix": "012", "county": "Kisumu"},
    {"first": "Margaret", "last": "Wambui", "age_years": 65, "gender": "female",
     "ins": "SHA", "phone_suffix": "013", "county": "Nyeri"},
    {"first": "Patrick", "last": "Ngugi", "age_years": 70, "gender": "male",
     "ins": "SHA", "phone_suffix": "014", "county": "Kiambu"},
    {"first": "Ruth", "last": "Atieno", "age_years": 75, "gender": "female",
     "ins": None, "phone_suffix": "015", "county": "Siaya"},
    {"first": "Andrew", "last": "Odhiambo", "age_years": 18, "gender": "male",
     "ins": None, "phone_suffix": "016", "county": "Nairobi"},
    {"first": "Beatrice", "last": "Wanjiru", "age_years": 22, "gender": "female",
     "ins": "SHA", "phone_suffix": "017", "county": "Nakuru"},
    {"first": "Collins", "last": "Ouma", "age_years": 27, "gender": "male",
     "ins": "Britam", "phone_suffix": "018", "county": "Kisumu"},
    {"first": "Diana", "last": "Moraa", "age_years": 29, "gender": "female",
     "ins": "Jubilee", "phone_suffix": "019", "county": "Nairobi", "pregnant": True},
    {"first": "Emmanuel", "last": "Kiptoo", "age_years": 31, "gender": "male",
     "ins": None, "phone_suffix": "020", "county": "Uasin Gishu"},
    {"first": "Fiona", "last": "Chebet", "age_years": 24, "gender": "female",
     "ins": "SHA", "phone_suffix": "021", "county": "Kericho",
     "conditions": ["Asthma"]},
    {"first": "George", "last": "Njoroge", "age_years": 34, "gender": "male",
     "ins": "AAR", "phone_suffix": "022", "county": "Murang'a"},
    {"first": "Hellen", "last": "Auma", "age_years": 36, "gender": "female",
     "ins": "SHA", "phone_suffix": "023", "county": "Siaya", "pregnant": True},
    {"first": "Ian", "last": "Kipruto", "age_years": 38, "gender": "male",
     "ins": None, "phone_suffix": "024", "county": "Bomet"},
    {"first": "Janet", "last": "Wambui", "age_years": 41, "gender": "female",
     "ins": "SHA", "phone_suffix": "025", "county": "Nairobi",
     "conditions": ["Hypertension"]},
    {"first": "Kelvin", "last": "Mose", "age_years": 33, "gender": "male",
     "ins": None, "phone_suffix": "026", "county": "Kisii"},
    {"first": "Lilian", "last": "Atieno", "age_years": 43, "gender": "female",
     "ins": "SHA", "phone_suffix": "027", "county": "Migori"},
    {"first": "Moses", "last": "Kimutai", "age_years": 46, "gender": "male",
     "ins": "Jubilee", "phone_suffix": "028", "county": "Baringo"},
    {"first": "Naomi", "last": "Jepkoech", "age_years": 26, "gender": "female",
     "ins": None, "phone_suffix": "029", "county": "Nandi"},
    {"first": "Oscar", "last": "Wafula", "age_years": 48, "gender": "male",
     "ins": "SHA", "phone_suffix": "030", "county": "Kakamega",
     "conditions": ["Diabetes Mellitus Type 2"]},
    {"first": "Raphael", "last": "Munyao", "age_years": 53, "gender": "male",
     "ins": None, "phone_suffix": "031", "county": "Kitui"},
    {"first": "Salome", "last": "Achieng", "age_years": 37, "gender": "female",
     "ins": "SHA", "phone_suffix": "032", "county": "Homa Bay", "pregnant": True},
    {"first": "Timothy", "last": "Koech", "age_years": 55, "gender": "male",
     "ins": None, "phone_suffix": "033", "county": "Elgeyo-Marakwet",
     "conditions": ["Hypertension"]},
    {"first": "Veronica", "last": "Muthoni", "age_years": 57, "gender": "female",
     "ins": "SHA", "phone_suffix": "034", "county": "Nyandarua"},
    {"first": "William", "last": "Barasa", "age_years": 60, "gender": "male",
     "ins": "AAR", "phone_suffix": "035", "county": "Busia"},
    {"first": "Esther", "last": "Nduta", "age_years": 21, "gender": "female",
     "ins": "SHA", "phone_suffix": "036", "county": "Kiambu"},
    {"first": "Francis", "last": "Chege", "age_years": 44, "gender": "male",
     "ins": None, "phone_suffix": "037", "county": "Nyeri"},
    {"first": "Gladys", "last": "Kerubo", "age_years": 62, "gender": "female",
     "ins": "SHA", "phone_suffix": "038", "county": "Kisii",
     "conditions": ["Diabetes Mellitus Type 2"]},
    {"first": "Harun", "last": "Wekesa", "age_years": 49, "gender": "male",
     "ins": None, "phone_suffix": "039", "county": "Trans Nzoia"},
    {"first": "Irene", "last": "Chepkirui", "age_years": 28, "gender": "female",
     "ins": "SHA", "phone_suffix": "040", "county": "Nakuru", "pregnant": True},
    {"first": "Julius", "last": "Maina", "age_years": 58, "gender": "male",
     "ins": "Jubilee", "phone_suffix": "041", "county": "Embu"},
    {"first": "Karen", "last": "Wairimu", "age_years": 32, "gender": "female",
     "ins": None, "phone_suffix": "042", "county": "Nairobi"},
    {"first": "Leonard", "last": "Kibet", "age_years": 42, "gender": "male",
     "ins": None, "phone_suffix": "043", "county": "Laikipia"},
    {"first": "Mildred", "last": "Adhiambo", "age_years": 47, "gender": "female",
     "ins": "SHA", "phone_suffix": "044", "county": "Nairobi",
     "conditions": ["Hypertension"]},
    {"first": "Nicholas", "last": "Mutuku", "age_years": 39, "gender": "male",
     "ins": "Britam", "phone_suffix": "045", "county": "Makueni"},
    {"first": "Olivia", "last": "Awuor", "age_years": 30, "gender": "female",
     "ins": "SHA", "phone_suffix": "046", "county": "Kisumu"},
    {"first": "Peter", "last": "Kilonzo", "age_years": 52, "gender": "male",
     "ins": None, "phone_suffix": "047", "county": "Kitui",
     "conditions": ["Hypertension"]},
    {"first": "Rosemary", "last": "Karimi", "age_years": 64, "gender": "female",
     "ins": "SHA", "phone_suffix": "048", "county": "Meru"},
    {"first": "Stephen", "last": "Mwadime", "age_years": 35, "gender": "male",
     "ins": None, "phone_suffix": "049", "county": "Taita-Taveta"},
    {"first": "Teresia", "last": "Nyambura", "age_years": 54, "gender": "female",
     "ins": "Jubilee", "phone_suffix": "050", "county": "Nairobi",
     "conditions": ["Hypertension", "Diabetes Mellitus Type 2"]},]


async def seed_patients(
    db: AsyncSession, facility_id: uuid.UUID
) -> list[uuid.UUID]:
    """Seed 15 demographically-varied patients (idempotent by MRN).

    @returns List of patient.id
    """
    ids: list[uuid.UUID] = []
    existing = (
        await db.execute(
            select(Patient).where(Patient.facility_id == facility_id)
        )
    ).scalars().all()
    existing_mrns = {p.mrn: p.id for p in existing}

    created = 0
    for i, p in enumerate(PATIENTS, start=1):
        mrn = f"MRN-{i:05d}"
        if mrn in existing_mrns:
            ids.append(existing_mrns[mrn])
            continue

        if "age_months" in p:
            dob = TODAY - timedelta(days=int(p["age_months"]) * 30)
        else:
            dob = TODAY - timedelta(days=int(p["age_years"]) * 365)

        chronic = p.get("conditions") or None
        if p.get("pregnant"):
            chronic = (chronic or []) + ["Currently Pregnant"]

        patient = Patient(
            id=_det(f"patient:{mrn}"),
            facility_id=facility_id,
            mrn=mrn,
            first_name=p["first"],
            last_name=p["last"],
            date_of_birth=dob,
            gender=p["gender"],
            phone_number=f"+254712345{p['phone_suffix']}",
            county=p.get("county"),
            insurance_provider=p.get("ins"),
            insurance_member_number=(
                f"SHA{i:09d}" if p.get("ins") == "SHA" else None
            ),
            sha_number=f"SHA{i:09d}" if p.get("ins") == "SHA" else None,
            chronic_conditions=chronic,
            blood_group="O+" if i % 2 == 0 else "A+",
        )
        db.add(patient)
        await db.flush()
        ids.append(patient.id)
        created += 1

    print(f"  Patients: {created} created, {len(existing_mrns)} existing")
    return ids


_APPT_COMPLAINTS = [
    "General check-up",
    "Fever and headache",
    "Cough and flu",
    "Abdominal pain",
    "Skin rash",
    "Joint pain",
    "Follow-up review",
]

_VISIT_COMPLAINTS = [
    "Fever, chills and headache",
    "Productive cough for 3 days",
    "Lower abdominal pain",
    "Malaria-like symptoms",
    "Routine ANC review",
    "High blood pressure review",
    "Back pain after lifting",
    "Diarrhoea and vomiting",
    "Diabetes follow-up",
    "Routine child immunisation",
    "Eye irritation and redness",
    "Asthma exacerbation",
]


async def seed_appointments(
    db: AsyncSession,
    facility_id: uuid.UUID,
    patient_ids: list[uuid.UUID],
    staff_map: dict[str, uuid.UUID],
    dept_map: dict[str, uuid.UUID],
) -> int:
    """Seed one upcoming appointment per demo patient (idempotent).

    @param db: Async DB session
    @param facility_id: Demo facility UUID
    @param patient_ids: Seeded patient UUIDs
    @param staff_map: Map {employee_number: staff.id}
    @param dept_map: Map {department code: department.id}
    @returns Number of appointments created
    """
    existing = (
        await db.execute(
            select(Appointment.appointment_number).where(
                Appointment.facility_id == facility_id
            )
        )
    ).scalars().all()
    existing_numbers = set(existing)

    doctor_ids = [
        staff_map["AIFYA-002"],
        staff_map["AIFYA-003"],
    ]
    booked_by = staff_map.get("AIFYA-010") or staff_map["AIFYA-002"]
    statuses = [
        "scheduled", "confirmed", "confirmed", "completed",
        "checked_in", "cancelled", "scheduled", "confirmed",
    ]

    created = 0
    for i, patient_id in enumerate(patient_ids, start=1):
        number = f"APT-{TODAY.year}-{i:05d}"
        if number in existing_numbers:
            continue

        appt_date = TODAY + timedelta(days=(i - 1) % 14)
        start_hour = 8 + ((i - 1) % 8)
        end_minute = start_hour * 60 + 30
        status = statuses[(i - 1) % len(statuses)]
        if status == "checked_in" and appt_date != TODAY:
            status = "confirmed"

        appt = Appointment(
            id=_det(f"appt:{number}"),
            facility_id=facility_id,
            patient_id=patient_id,
            doctor_id=doctor_ids[(i - 1) % len(doctor_ids)],
            department_id=dept_map.get("OPD"),
            appointment_number=number,
            appointment_date=appt_date,
            start_time=time(start_hour, 0),
            end_time=time(end_minute // 60, end_minute % 60),
            duration_minutes=30,
            appointment_type="consultation",
            visit_reason=_APPT_COMPLAINTS[(i - 1) % len(_APPT_COMPLAINTS)],
            priority="urgent" if i % 10 == 0 else "routine",
            status=status,
            reminder_sent=status in ("confirmed", "checked_in"),
            is_recurring=False,
            room=f"Room {(i % 6) + 1}",
            notes="Demo appointment record.",
            booked_by=booked_by,
            created_by=booked_by,
            updated_by=booked_by,
        )
        db.add(appt)
        created += 1

    print(f"  Appointments: {created} created, {len(existing_numbers)} existing")
    return created


async def seed_encounters_and_vitals(
    db: AsyncSession,
    facility_id: uuid.UUID,
    patient_ids: list[uuid.UUID],
    staff_map: dict[str, uuid.UUID],
    dept_map: dict[str, uuid.UUID],
) -> tuple[int, int]:
    """Seed one OPD encounter and a vitals set per demo patient (idempotent).

    @param db: Async DB session
    @param facility_id: Demo facility UUID
    @param patient_ids: Seeded patient UUIDs
    @param staff_map: Map {employee_number: staff.id}
    @param dept_map: Map {department code: department.id}
    @returns (encounters_created, vitals_created)
    """
    existing_encounter_ids = set(
        (
            await db.execute(
                select(Encounter.id).where(Encounter.facility_id == facility_id)
            )
        ).scalars().all()
    )
    existing_vital_ids = set(
        (
            await db.execute(
                select(VitalSign.id).where(VitalSign.facility_id == facility_id)
            )
        ).scalars().all()
    )

    doctor_id = staff_map.get("AIFYA-002") or staff_map["AIFYA-003"]
    nurse_id = staff_map.get("AIFYA-004") or staff_map["AIFYA-005"]
    opd_id = dept_map.get("OPD")
    statuses = [
        "completed", "completed", "completed", "waiting",
        "in_consultation", "completed",
    ]

    encounters_created = 0
    vitals_created = 0
    for i, patient_id in enumerate(patient_ids, start=1):
        enc_id = _det(f"enc:visit:{i}")
        if enc_id in existing_encounter_ids:
            continue

        status = statuses[(i - 1) % len(statuses)]
        if status in ("waiting", "in_consultation"):
            enc_date = datetime.now(UTC).replace(
                hour=8 + ((i - 1) % 9),
                minute=((i - 1) % 4) * 15,
                second=0,
                microsecond=0,
            )
        else:
            enc_date = datetime.now(UTC) - timedelta(
                days=(i - 1) % 28, hours=2
            )

        encounter = Encounter(
            id=enc_id,
            facility_id=facility_id,
            patient_id=patient_id,
            encounter_type="opd",
            encounter_date=enc_date,
            department_id=opd_id,
            attending_doctor_id=doctor_id,
            nurse_id=nurse_id,
            queue_number=None if status == "completed" else i,
            triage_category="standard",
            priority=0 if status == "completed" else 1,
            status=status,
            chief_complaint=_VISIT_COMPLAINTS[
                (i - 1) % len(_VISIT_COMPLAINTS)
            ],
            disposition="discharged" if status == "completed" else None,
            billing_status="billed" if status == "completed" else "pending",
            created_by=doctor_id,
            updated_by=doctor_id,
        )
        db.add(encounter)
        encounters_created += 1

        vital_id = _det(f"vital:visit:{i}")
        if vital_id not in existing_vital_ids:
            if i <= 3:
                weight_kg = round(3.5 + i * 1.8, 1)
                sys_bp = None
                dia_bp = None
                heart_rate = 85 + i * 6
                resp_rate = 18 + i
            else:
                weight_kg = round(52.0 + ((i - 1) % 25) * 1.6, 1)
                sys_bp = 108 + ((i - 1) % 20) * 2
                dia_bp = 68 + ((i - 1) % 10) * 2
                heart_rate = 62 + ((i - 1) % 24)
                resp_rate = 14 + ((i - 1) % 6)
            vital = VitalSign(
                id=vital_id,
                facility_id=facility_id,
                encounter_id=enc_id,
                patient_id=patient_id,
                recorded_by=nurse_id,
                recorded_at=enc_date + timedelta(minutes=10),
                systolic_bp=sys_bp,
                diastolic_bp=dia_bp,
                heart_rate=heart_rate,
                temperature=round(36.5 + ((i - 1) % 8) * 0.1, 1),
                temperature_site="oral",
                respiratory_rate=resp_rate,
                oxygen_saturation=float(96 + ((i - 1) % 4)),
                on_supplemental_o2=False,
                weight_kg=weight_kg,
                pain_score=0 if i % 10 else 3,
                created_by=nurse_id,
                updated_by=nurse_id,
            )
            db.add(vital)
            vitals_created += 1

    print(
        f"  Encounters: {encounters_created} created, "
        f"{len(existing_encounter_ids)} existing"
    )
    print(
        f"  Vitals: {vitals_created} created, "
        f"{len(existing_vital_ids)} existing"
    )
    return encounters_created, vitals_created
async def seed_dashboard_outpatient_visits(
    db: AsyncSession,
    facility_id: uuid.UUID,
    patient_ids: list[uuid.UUID],
    staff_map: dict[str, uuid.UUID],
    dept_map: dict[str, uuid.UUID],
) -> int:
    """Seed OPD (outpatient) visits that the executive dashboard counts.

    The reports dashboard (reports_service.get_facility_dashboard) counts
    ``Encounter.encounter_type == "opd"`` for OPD KPIs and 14-day trends,
    matching the OPD queue module. This adds 50 OPD visits dated today (so
    the "OPD visits" KPI reads 50) plus a small daily history for the trend
    chart. Idempotent by deterministic IDs.

    @param db: Async DB session
    @param facility_id: Demo facility UUID
    @param patient_ids: Seeded patient UUIDs
    @param staff_map: Map {employee_number: staff.id}
    @param dept_map: Map {department code: department.id}
    @returns Number of visits created
    """
    # Repair rows created by earlier demo seeds that used the pre-fix
    # "outpatient" encounter type so dashboard counts stay correct.
    await db.execute(
        update(Encounter)
        .where(
            Encounter.facility_id == facility_id,
            Encounter.is_deleted == False,  # noqa: E712
            Encounter.encounter_type == "outpatient",
        )
        .values(encounter_type="opd")
    )

    existing = set(
        (
            await db.execute(
                select(Encounter.id).where(Encounter.facility_id == facility_id)
            )
        ).scalars().all()
    )

    doctor_id = staff_map.get("AIFYA-002") or staff_map["AIFYA-003"]
    opd_id = dept_map.get("OPD")

    # (days_ago, visits_that_day): ~7/day for the prior 13 days + 50 today.
    plan: list[tuple[int, int]] = [(days_ago, 7) for days_ago in range(1, 14)]
    plan.append((0, 50))

    created = 0
    seq = 0
    for days_ago, count in plan:
        for _ in range(count):
            seq += 1
            enc_id = _det(f"enc:dashboard:{seq}")
            if enc_id in existing:
                continue

            status = "completed"
            if days_ago == 0:
                if seq % 6 == 0:
                    status = "in_consultation"
                elif seq % 3 == 0:
                    status = "waiting"

            enc_date = NOW - timedelta(days=days_ago)
            enc_date = enc_date.replace(
                hour=7 + (seq % 11),
                minute=((seq - 1) % 4) * 15,
                second=0,
                microsecond=0,
            )

            encounter = Encounter(
                id=enc_id,
                facility_id=facility_id,
                patient_id=patient_ids[(seq - 1) % len(patient_ids)],
                encounter_type="opd",
                encounter_date=enc_date,
                department_id=opd_id,
                attending_doctor_id=doctor_id,
                queue_number=None if status == "completed" else seq,
                status=status,
                chief_complaint=_VISIT_COMPLAINTS[
                    (seq - 1) % len(_VISIT_COMPLAINTS)
                ],
                disposition="discharged" if status == "completed" else None,
                billing_status="billed" if status == "completed" else "pending",
                created_by=doctor_id,
                updated_by=doctor_id,
            )
            db.add(encounter)
            created += 1
            if created % 50 == 0:
                await db.flush()

    print(
        f"  Dashboard outpatient visits: {created} created, "
        f"{len(existing)} existing encounters"
    )
    return created


# ── Pharmacy Items ───────────────────────────────────────────────────────────

PHARMACY_ITEMS: list[dict[str, Any]] = [
    {"code": "PCM500", "name": "Paracetamol 500mg", "form": "tablet",
     "strength": "500mg", "kes": 5, "uom": "tablet", "stock": 500, "keml": True},
    {"code": "AMX500", "name": "Amoxicillin 500mg", "form": "capsule",
     "strength": "500mg", "kes": 15, "uom": "capsule", "stock": 300, "keml": True},
    {"code": "MET500", "name": "Metformin 500mg", "form": "tablet",
     "strength": "500mg", "kes": 8, "uom": "tablet", "stock": 400, "keml": True},
    {"code": "AML5", "name": "Amlodipine 5mg", "form": "tablet",
     "strength": "5mg", "kes": 12, "uom": "tablet", "stock": 250, "keml": True},
    {"code": "ORS01", "name": "Oral Rehydration Salts", "form": "sachet",
     "strength": "20.5g", "kes": 30, "uom": "sachet", "stock": 200, "keml": True},
    {"code": "FEFOL", "name": "Iron + Folic Acid", "form": "tablet",
     "strength": "60mg/0.4mg", "kes": 5, "uom": "tablet", "stock": 500, "keml": True},
    {"code": "ALB400", "name": "Albendazole 400mg", "form": "tablet",
     "strength": "400mg", "kes": 25, "uom": "tablet", "stock": 200, "keml": True},
    {"code": "DCF50", "name": "Diclofenac 50mg", "form": "tablet",
     "strength": "50mg", "kes": 10, "uom": "tablet", "stock": 300, "keml": True},
    {"code": "CTX1G", "name": "Ceftriaxone 1g", "form": "injection",
     "strength": "1g", "kes": 250, "uom": "vial", "stock": 100, "keml": True},
    {"code": "SAL100", "name": "Salbutamol Inhaler", "form": "inhaler",
     "strength": "100mcg", "kes": 350, "uom": "inhaler", "stock": 100, "keml": True},
    {"code": "INSR", "name": "Insulin Regular", "form": "injection",
     "strength": "100IU/ml", "kes": 500, "uom": "vial", "stock": 100, "keml": True},
    {"code": "CSY100", "name": "Cough Syrup 100ml", "form": "syrup",
     "strength": "100ml", "kes": 180, "uom": "bottle", "stock": 150, "keml": False},
    {"code": "VITC", "name": "Vitamin C 500mg", "form": "tablet",
     "strength": "500mg", "kes": 3, "uom": "tablet", "stock": 500, "keml": False},
    {"code": "MVITS", "name": "Multivitamin Syrup", "form": "syrup",
     "strength": "200ml", "kes": 220, "uom": "bottle", "stock": 200, "keml": False},
    {"code": "COART", "name": "Coartem (Artemether/Lumefantrine)", "form": "tablet",
     "strength": "20mg/120mg", "kes": 850, "uom": "dose", "stock": 150, "keml": True},
]


async def seed_pharmacy(
    db: AsyncSession, facility_id: uuid.UUID
) -> list[uuid.UUID]:
    """Seed 15 pharmacy items idempotently."""
    ids: list[uuid.UUID] = []
    existing = (
        await db.execute(
            select(PharmacyItem).where(PharmacyItem.facility_id == facility_id)
        )
    ).scalars().all()
    by_code = {p.drug_code: p.id for p in existing}

    created = 0
    for item in PHARMACY_ITEMS:
        if item["code"] in by_code:
            ids.append(by_code[item["code"]])
            continue
        # 1-year expiry from today
        expiry = TODAY + timedelta(days=365)
        ph = PharmacyItem(
            id=_det(f"pharm:{item['code']}"),
            facility_id=facility_id,
            drug_code=item["code"],
            drug_name=item["name"],
            generic_name=item["name"],
            is_keml=item["keml"],
            dosage_form=item["form"],
            strength=item["strength"],
            current_quantity=item["stock"],
            unit_of_measure=item["uom"],
            reorder_level=20,
            buying_price_cents=_kes_to_cents(item["kes"]) // 2,
            selling_price_cents=_kes_to_cents(item["kes"]),
            expiry_date=expiry,
            manufacturer="Generic Manufacturer Ltd",
            is_active=True,
        )
        db.add(ph)
        await db.flush()
        ids.append(ph.id)
        created += 1

    print(f"  Pharmacy items: {created} created, {len(by_code)} existing")
    return ids


# ── Insurance Schemes ────────────────────────────────────────────────────────


async def seed_insurance(
    db: AsyncSession, facility_id: uuid.UUID
) -> uuid.UUID:
    """Seed SHA insurance scheme (idempotent)."""
    existing = (
        await db.execute(
            select(InsuranceScheme).where(
                InsuranceScheme.facility_id == facility_id,
                InsuranceScheme.scheme_code == "SHA",
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        print("  Insurance: SHA scheme already exists")
        return existing.id

    sha = InsuranceScheme(
        id=_det("ins:SHA"),
        facility_id=facility_id,
        name="Social Health Authority",
        scheme_code="SHA",
        scheme_type="sha",
        contact_person="SHA Help Desk",
        phone="+254709000000",
        email="claims@sha.go.ke",
        rebate_percentage=80,
        is_active=True,
    )
    db.add(sha)
    await db.flush()
    print("  Insurance: SHA scheme created")
    return sha.id


# ── Accounting Periods ───────────────────────────────────────────────────────


async def seed_accounting_periods(
    db: AsyncSession, facility_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    """Seed 12 monthly periods + 1 fiscal year for the current year (idempotent).

    Always creates periods for the current calendar year and all of the
    previous calendar year (so historical postings work in the demo).
    """
    by_name: dict[str, uuid.UUID] = {}
    year = TODAY.year

    existing = (
        await db.execute(
            select(AccountingPeriod).where(
                AccountingPeriod.facility_id == facility_id
            )
        )
    ).scalars().all()
    existing_names = {p.name: p.id for p in existing}

    created = 0
    # Create periods for previous + current year so 30-day-old invoices
    # always land in an open period.
    for y in (year - 1, year):
        for month in range(1, 13):
            name = f"{y}-{month:02d}"
            if name in existing_names:
                by_name[name] = existing_names[name]
                continue
            start = date(y, month, 1)
            if month == 12:
                end = date(y, 12, 31)
            else:
                end = date(y, month + 1, 1) - timedelta(days=1)
            period = AccountingPeriod(
                id=_det(f"period:{name}"),
                facility_id=facility_id,
                name=name,
                start_date=start,
                end_date=end,
                status="open",
                year_end=False,
            )
            db.add(period)
            await db.flush()
            by_name[name] = period.id
            created += 1

        # FY annual periods intentionally omitted — they overlap monthly
        # periods and cause scalar_one_or_none() to fail in the posting engine.
        fy_name = f"FY{y}"
        by_name[fy_name] = existing_names.get(fy_name)

    print(f"  Accounting periods: {created} created, {len(existing_names)} existing")
    return by_name


# ── Invoices, Payments, Expenses ─────────────────────────────────────────────


async def _next_invoice_number(
    db: AsyncSession, facility_id: uuid.UUID
) -> str:
    """Generate the next invoice number for the facility."""
    count = (
        await db.execute(
            select(Invoice).where(Invoice.facility_id == facility_id)
        )
    ).scalars().all()
    n = len(count) + 1
    return f"INV-{TODAY.year}-{n:05d}"


# Mix of invoice scenarios: (label, kes_amount, payment_method, dept_code)
INVOICE_SCENARIOS: list[tuple[str, int, str, str]] = [
    ("Consultation", 500, "cash", "OPD"),
    ("Consultation + Lab", 1500, "cash", "OPD"),
    ("Pharmacy dispense", 800, "cash", "PHARM"),
    ("Specialist consult", 2500, "insurance", "OPD"),
    ("Lab panel CBC + UA", 1200, "cash", "LAB"),
    ("Lab full chem", 3500, "insurance", "LAB"),
    ("Antenatal visit", 600, "insurance", "MCH"),
    ("Pharmacy + injection", 1800, "cash", "PHARM"),
    ("X-ray chest", 2200, "insurance", "RAD"),
    ("Ultrasound", 3000, "insurance", "RAD"),
    ("Emergency triage", 1500, "cash", "ER"),
    ("ER stitches", 4500, "cash", "ER"),
    ("IPD admission day 1", 8500, "insurance", "IPD"),
    ("IPD admission day 2", 7500, "insurance", "IPD"),
    ("Diabetes review", 1200, "insurance", "OPD"),
    ("Hypertension review", 1100, "cash", "OPD"),
    ("Child immunization", 400, "cash", "MCH"),
    ("Pediatric consult", 800, "cash", "OPD"),
    ("Pharmacy refill chronic", 2500, "insurance", "PHARM"),
    ("Geriatric consult", 1200, "cash", "OPD"),
    ("Pre-op assessment", 5500, "insurance", "OPD"),
    ("Post-op follow-up", 1500, "insurance", "OPD"),
    ("Dressing change", 350, "cash", "OPD"),
    ("Family planning", 500, "insurance", "MCH"),
    ("Comprehensive checkup", 25000, "insurance", "OPD"),
]


async def seed_invoices_and_postings(
    db: AsyncSession,
    facility_id: uuid.UUID,
    patient_ids: list[uuid.UUID],
    dept_map: dict[str, uuid.UUID],
    user_id: uuid.UUID,
) -> tuple[int, int]:
    """Seed ~25 invoices spread over the last 30 days. Each is GL-posted.

    @returns (invoices_created, payments_created)
    """
    # Idempotency: skip if we already have invoices in the system.
    already = (
        await db.execute(
            select(Invoice).where(Invoice.facility_id == facility_id)
        )
    ).scalars().all()
    if already:
        print(f"  Invoices: {len(already)} already exist, skipping")
        return (0, 0)

    # We need encounters to attach invoices to (FK constraint).
    # Create one synthetic encounter per invoice for the demo.
    invoices_created = 0
    payments_created = 0

    for i, (label, kes, method, dept_code) in enumerate(INVOICE_SCENARIOS, start=1):
        days_ago = (i * 30) // len(INVOICE_SCENARIOS)
        inv_date = TODAY - timedelta(days=days_ago)
        patient_id = patient_ids[i % len(patient_ids)]
        dept_id = dept_map.get(dept_code)

        # Synthetic encounter
        enc = Encounter(
            id=_det(f"enc:demo:{i}"),
            facility_id=facility_id,
            patient_id=patient_id,
            encounter_type="opd",
            encounter_date=datetime.combine(inv_date, datetime.min.time(), tzinfo=UTC),
            department_id=dept_id,
            status="completed",
            chief_complaint=label,
            billing_status="billed",
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(enc)
        await db.flush()

        total_cents = _kes_to_cents(kes)
        inv_num = f"INV-{TODAY.year}-{i:05d}"
        inv = Invoice(
            id=_det(f"inv:demo:{i}"),
            facility_id=facility_id,
            encounter_id=enc.id,
            patient_id=patient_id,
            invoice_number=inv_num,
            status="finalized" if method == "cash" else "partially_paid",
            payment_method=method,
            insurance_provider="SHA" if method == "insurance" else None,
            subtotal_cents=total_cents,
            total_cents=total_cents,
            paid_cents=total_cents if method == "cash" else 0,
            balance_cents=0 if method == "cash" else total_cents,
            finalized_at=NOW,
            finalized_by=user_id,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(inv)
        await db.flush()

        # Single line item (demo only)
        item = InvoiceItem(
            id=_det(f"invitem:demo:{i}"),
            facility_id=facility_id,
            invoice_id=inv.id,
            item_type="consultation" if dept_code == "OPD" else (
                "pharmacy" if dept_code == "PHARM" else (
                    "lab" if dept_code == "LAB" else "procedure"
                )
            ),
            description=label,
            quantity=1,
            unit_price_cents=total_cents,
            total_cents=total_cents,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(item)
        invoices_created += 1

        # Post to GL via the real posting engine.
        event = "invoice_cash" if method == "cash" else "invoice_insurance"
        try:
            await post_transaction(
                db=db,
                facility_id=facility_id,
                event_type=event,
                amount=Decimal(str(kes)),
                metadata={
                    "date": inv_date.isoformat(),
                    "reference_type": "invoice",
                    "reference_id": str(inv.id),
                    "description": f"{inv_num} — {label}",
                    "department_id": str(dept_id) if dept_id else None,
                },
                idempotency_key=f"demo-invoice:{inv.id}",
                user_id=user_id,
            )
        except Exception as exc:
            print(f"  WARN: GL post failed for {inv_num}: {exc}")

    # Sample payments — ~15 settle (full or partial) the insurance invoices
    insurance_invoices = (
        await db.execute(
            select(Invoice).where(
                Invoice.facility_id == facility_id,
                Invoice.payment_method == "insurance",
            )
        )
    ).scalars().all()

    for j, inv in enumerate(insurance_invoices[:15], start=1):
        # Mix of partial (50%) and full payments
        is_partial = j % 3 == 0
        amount_cents = inv.total_cents // 2 if is_partial else inv.total_cents
        pay = Payment(
            id=_det(f"pay:demo:{j}"),
            facility_id=facility_id,
            invoice_id=inv.id,
            patient_id=inv.patient_id,
            amount_cents=amount_cents,
            payment_method="insurance",
            reference_number=f"SHA-RCT-{j:05d}",
            received_by=user_id,
            paid_at=NOW,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(pay)
        # Post insurance receipt to GL
        try:
            await post_transaction(
                db=db,
                facility_id=facility_id,
                event_type="insurance_payment_received",
                amount=Decimal(amount_cents) / Decimal("100"),
                metadata={
                    "date": TODAY.isoformat(),
                    "reference_type": "payment",
                    "reference_id": str(pay.id),
                    "description": f"SHA remittance for {inv.invoice_number}",
                },
                idempotency_key=f"demo-pay:{pay.id}",
                user_id=user_id,
            )
        except Exception as exc:
            print(f"  WARN: GL post failed for payment: {exc}")
        payments_created += 1

    # Sample expenses: rent, utilities, supplies, etc.
    expenses: list[tuple[str, int]] = [
        ("Monthly rent", 100_000),
        ("Electricity bill", 25_000),
        ("Water bill", 5_000),
        ("Internet", 8_000),
        ("Cleaning supplies", 12_000),
        ("Office stationery", 6_500),
        ("Security services", 18_000),
        ("Generator fuel", 15_000),
    ]
    for k, (desc, kes) in enumerate(expenses, start=1):
        try:
            await post_transaction(
                db=db,
                facility_id=facility_id,
                event_type="expense_paid",
                amount=Decimal(str(kes)),
                metadata={
                    "date": (TODAY - timedelta(days=k * 3)).isoformat(),
                    "reference_type": "expense",
                    "reference_id": str(_det(f"expense:{k}")),
                    "description": desc,
                },
                idempotency_key=f"demo-expense:{k}",
                user_id=user_id,
            )
        except Exception as exc:
            print(f"  WARN: GL post failed for expense '{desc}': {exc}")

    print(
        f"  Invoices posted: {invoices_created}, "
        f"Payments: {payments_created}, "
        f"Expenses: {len(expenses)}"
    )
    return (invoices_created, payments_created)


# ── Employees, Salaries, Payroll ─────────────────────────────────────────────


EMPLOYEE_DEFINITIONS: list[dict[str, Any]] = [
    # Admin / Doctor tier — KSh 200k basic + 50k house + 30k transport
    {"staff_emp": "AIFYA-001", "name": "Wanjiku Kamau", "title": "Medical Director",
     "tier": "exec", "kra": "A009658233G", "nssf": "100000001",
     "shif": "CR1620021837701-1", "bank": "Equity Bank", "branch": "Westlands",
     "hire_months_ago": 24, "disability": False},
    {"staff_emp": "AIFYA-002", "name": "James Otieno", "title": "Doctor",
     "tier": "exec", "kra": "A009658234G", "nssf": "100000002",
     "shif": "CR1620021837702-1", "bank": "KCB", "branch": "Sarit Centre",
     "hire_months_ago": 20, "disability": False},
    {"staff_emp": "AIFYA-003", "name": "Mary Akinyi", "title": "Doctor",
     "tier": "exec", "kra": "A009658235G", "nssf": "100000003",
     "shif": "CR1620021837703-1", "bank": "Cooperative", "branch": "Westlands",
     "hire_months_ago": 18, "disability": False},
    # Nurse tier — 80k basic + 20k house + 10k transport
    {"staff_emp": "AIFYA-004", "name": "Faith Njeri", "title": "Senior Nurse",
     "tier": "nurse", "kra": "A009658236G", "nssf": "100000004",
     "shif": "CR1620021837704-1", "bank": "Equity Bank", "branch": "Westlands",
     "hire_months_ago": 16, "disability": False},
    {"staff_emp": "AIFYA-005", "name": "Grace Wanjiru", "title": "MCH Nurse",
     "tier": "nurse", "kra": "A009658237G", "nssf": "100000005",
     "shif": "CR1620021837705-1", "bank": "KCB", "branch": "Westlands",
     "hire_months_ago": 12, "disability": False},
    # Pharmacist tier — 90k basic + 25k house + 12k transport
    {"staff_emp": "AIFYA-006", "name": "Peter Mwangi", "title": "Chief Pharmacist",
     "tier": "pharmacist", "kra": "A009658238G", "nssf": "100000006",
     "shif": "CR1620021837706-1", "bank": "Equity Bank", "branch": "Sarit Centre",
     "hire_months_ago": 14, "disability": False},
    # Lab Tech tier — 70k basic + 18k house + 10k transport
    {"staff_emp": "AIFYA-007", "name": "John Kiprop", "title": "Lab Technologist",
     "tier": "lab", "kra": "A009658239G", "nssf": "100000007",
     "shif": "CR1620021837707-1", "bank": "Cooperative", "branch": "Westlands",
     "hire_months_ago": 10, "disability": True},
    # Cashier / Receptionist / HR tier — 50k + 15k + 8k
    {"staff_emp": "AIFYA-008", "name": "Ruth Achieng", "title": "Cashier",
     "tier": "support", "kra": "A009658240G", "nssf": "100000008",
     "shif": "CR1620021837708-1", "bank": "Equity Bank", "branch": "Westlands",
     "hire_months_ago": 8, "disability": False},
    {"staff_emp": "AIFYA-009", "name": "Esther Nyambura", "title": "HR Officer",
     "tier": "support", "kra": "A009658241G", "nssf": "100000009",
     "shif": "CR1620021837709-1", "bank": "KCB", "branch": "Sarit Centre",
     "hire_months_ago": 12, "disability": False},
    {"staff_emp": "AIFYA-010", "name": "David Kimani", "title": "Receptionist",
     "tier": "support", "kra": "A009658242G", "nssf": "100000010",
     "shif": "CR1620021837710-1", "bank": "Cooperative", "branch": "Westlands",
     "hire_months_ago": 6, "disability": False},
    # Cleaner / Security — 25k + 8k + 5k
    {"staff_emp": None, "name": "Mary Wanjala", "title": "Cleaner",
     "tier": "lowpay", "kra": "A009658243G", "nssf": "100000011",
     "shif": "CR1620021837711-1", "bank": "Equity Bank", "branch": "Westlands",
     "hire_months_ago": 10, "disability": False},
    {"staff_emp": None, "name": "Joseph Kamau", "title": "Security Guard",
     "tier": "lowpay", "kra": "A009658244G", "nssf": "100000012",
     "shif": "CR1620021837712-1", "bank": "KCB", "branch": "Westlands",
     "hire_months_ago": 14, "disability": False},
]

SALARY_TIERS: dict[str, tuple[int, int, int]] = {
    # tier -> (basic, house, transport) in KES
    "exec": (200_000, 50_000, 30_000),
    "nurse": (80_000, 20_000, 10_000),
    "pharmacist": (90_000, 25_000, 12_000),
    "lab": (70_000, 18_000, 10_000),
    "support": (50_000, 15_000, 8_000),
    "lowpay": (25_000, 8_000, 5_000),
}


async def seed_employees(
    db: AsyncSession,
    facility_id: uuid.UUID,
    dept_map: dict[str, uuid.UUID],
    user_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Seed 12 payroll-grade employees + their salary records."""
    ids: list[uuid.UUID] = []
    existing = (
        await db.execute(
            select(Employee).where(Employee.facility_id == facility_id)
        )
    ).scalars().all()
    existing_by_staff_id = {e.staff_id: e.id for e in existing}

    created = 0
    for ed in EMPLOYEE_DEFINITIONS:
        staff_id_str = ed["staff_emp"] or f"AIFYA-EXTRA-{ed['nssf'][-3:]}"
        if staff_id_str in existing_by_staff_id:
            ids.append(existing_by_staff_id[staff_id_str])
            continue

        hire_date = TODAY - timedelta(days=int(ed["hire_months_ago"]) * 30)

        emp = Employee(
            id=_det(f"employee:{staff_id_str}"),
            facility_id=facility_id,
            staff_id=staff_id_str,
            full_name=ed["name"],
            # Production encrypts these fields, while legacy demo schemas may
            # still have short VARCHAR columns. Keep optional identifiers empty
            # so the synthetic dataset remains portable and contains no secrets.
            kra_pin=None,
            nssf_number=ed["nssf"],
            shif_number=ed["shif"],
            department_id=dept_map.get("ADMIN"),
            job_title=ed["title"],
            employment_type="permanent",
            hire_date=hire_date,
            is_active=True,
            bank_name=ed["bank"],
            bank_branch=ed["branch"],
            bank_account=None,
            disability_exemption=ed["disability"],
            phone=f"+25471111{ed['nssf'][-4:]}",
            email=f"{ed['name'].split()[0].lower()}.{ed['name'].split()[-1].lower()}@aifya.co.ke",
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(emp)
        await db.flush()
        ids.append(emp.id)

        basic, house, transport = SALARY_TIERS[ed["tier"]]
        salary = EmployeeSalary(
            id=_det(f"salary:{staff_id_str}"),
            facility_id=facility_id,
            employee_id=emp.id,
            basic_salary=Decimal(basic),
            house_allowance=Decimal(house),
            transport_allowance=Decimal(transport),
            other_allowances={},
            effective_from=hire_date,
            approved_by=user_id,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(salary)
        created += 1

    await db.flush()
    print(f"  Employees: {created} created, {len(existing_by_staff_id)} existing")
    return ids


async def run_demo_payroll(
    db: AsyncSession,
    facility_id: uuid.UUID,
    user_id: uuid.UUID,
) -> PayrollRun | None:
    """Run payroll for the previous month, approve, and post to GL."""
    # Previous month from today.
    if TODAY.month == 1:
        month, year = 12, TODAY.year - 1
    else:
        month, year = TODAY.month - 1, TODAY.year

    # Idempotency: skip if a run already exists for this period.
    existing_run = (
        await db.execute(
            select(PayrollRun).where(
                PayrollRun.facility_id == facility_id,
                PayrollRun.month == month,
                PayrollRun.year == year,
                PayrollRun.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if existing_run is not None:
        print(f"  Payroll: run for {year}-{month:02d} already exists ({existing_run.status})")
        return existing_run

    try:
        run = await run_monthly_payroll(
            db=db,
            facility_id=facility_id,
            month=month,
            year=year,
            user_id=user_id,
        )
    except Exception as exc:
        print(f"  WARN: payroll run failed: {exc}")
        return None

    # Approve so payslips are generatable.
    run.status = "approved"
    run.approved_by = user_id
    run.approved_at = NOW
    await db.flush()

    # Post to GL (uses different account codes — falls back to warning if
    # accounts don't match — that's OK for demo).
    try:
        gl_id = await post_payroll_to_gl(db=db, run=run, user_id=user_id)
        if gl_id is not None:
            run.gl_transaction_id = gl_id
            run.status = "posted"
            await db.flush()
            print(f"  Payroll: run {year}-{month:02d} approved + posted to GL")
        else:
            print(f"  Payroll: run {year}-{month:02d} approved (GL post skipped)")
    except Exception as exc:
        print(f"  WARN: payroll GL post failed: {exc}")
    return run


# ── Leave Requests ───────────────────────────────────────────────────────────


async def seed_leave_requests(
    db: AsyncSession,
    facility_id: uuid.UUID,
    employee_ids: list[uuid.UUID],
    user_id: uuid.UUID,
) -> int:
    """Seed 5 sample leave requests."""
    if not employee_ids:
        return 0

    existing = (
        await db.execute(
            select(PayrollLeaveRequest).where(
                PayrollLeaveRequest.facility_id == facility_id
            )
        )
    ).scalars().all()
    if existing:
        print(f"  Leave requests: {len(existing)} already exist")
        return 0

    # Resolve leave types (global defaults).
    leave_types = {
        lt.name: lt.id
        for lt in (
            await db.execute(select(LeaveType).where(LeaveType.facility_id.is_(None)))
        ).scalars().all()
    }
    if not leave_types:
        print("  Leave requests: no leave types found, skipping")
        return 0

    samples: list[dict[str, Any]] = [
        {"emp_idx": 0, "type": "Annual", "days": 5, "status": "approved",
         "start_offset": -30, "reason": "Vacation"},
        {"emp_idx": 1, "type": "Sick", "days": 3, "status": "pending",
         "start_offset": -2, "reason": "Flu"},
        {"emp_idx": 4, "type": "Maternity", "days": 90, "status": "approved",
         "start_offset": 30, "reason": "Maternity leave"},
        {"emp_idx": 7, "type": "Unpaid", "days": 2, "status": "approved",
         "start_offset": -10, "reason": "Personal matters"},
        {"emp_idx": 9, "type": "Annual", "days": 7, "status": "rejected",
         "start_offset": -5, "reason": "Travel"},
    ]

    created = 0
    for s in samples:
        if s["emp_idx"] >= len(employee_ids):
            continue
        if s["type"] not in leave_types:
            continue
        start = TODAY + timedelta(days=int(s["start_offset"]))
        end = start + timedelta(days=int(s["days"]) - 1)
        deduction = Decimal("2500") if s["type"] == "Unpaid" else Decimal("0")
        lr = PayrollLeaveRequest(
            id=_det(f"leave:{s['emp_idx']}:{s['type']}"),
            facility_id=facility_id,
            employee_id=employee_ids[s["emp_idx"]],
            leave_type_id=leave_types[s["type"]],
            start_date=start,
            end_date=end,
            days_requested=s["days"],
            reason=s["reason"],
            status=s["status"],
            approved_by=user_id if s["status"] in ("approved", "rejected") else None,
            approved_at=NOW if s["status"] in ("approved", "rejected") else None,
            rejection_reason="Insufficient cover" if s["status"] == "rejected" else None,
            payroll_deduction=deduction,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(lr)
        created += 1

    await db.flush()
    print(f"  Leave requests: {created} created")
    return created


# ── Fixed Assets ─────────────────────────────────────────────────────────────


async def seed_fixed_assets(
    db: AsyncSession, facility_id: uuid.UUID, user_id: uuid.UUID
) -> int:
    """Seed 4 sample fixed assets for the depreciation demo."""
    existing = (
        await db.execute(
            select(FixedAsset).where(FixedAsset.facility_id == facility_id)
        )
    ).scalars().all()
    if existing:
        print(f"  Fixed assets: {len(existing)} already exist")
        return 0

    # Look up the asset + depreciation accounts seeded by seed_facility_finance.
    accounts = (
        await db.execute(
            select(Account).where(Account.facility_id == facility_id)
        )
    ).scalars().all()
    by_code = {a.code: a.id for a in accounts}

    asset_acc_id = by_code.get("1500")  # Fixed Assets - Equipment
    accum_dep_id = by_code.get("1510")  # Accumulated Depreciation
    dep_exp_id = by_code.get("5020")    # Depreciation Expense
    if not asset_acc_id:
        print("  Fixed assets: required accounts missing, skipping")
        return 0

    samples: list[dict[str, Any]] = [
        {"name": "Ultrasound Machine", "tag": "ASSET-001",
         "cost": 1_200_000, "months": 60, "salvage_pct": 5},
        {"name": "X-ray Machine", "tag": "ASSET-002",
         "cost": 2_500_000, "months": 84, "salvage_pct": 10},
        {"name": "ICU Monitor", "tag": "ASSET-003",
         "cost": 350_000, "months": 60, "salvage_pct": 5},
        {"name": "Hospital Beds (5 units)", "tag": "ASSET-004",
         "cost": 80_000 * 5, "months": 120, "salvage_pct": 10},
    ]

    created = 0
    for s in samples:
        salvage = (Decimal(s["cost"]) * Decimal(s["salvage_pct"]) / Decimal(100))
        fa = FixedAsset(
            id=_det(f"asset:{s['tag']}"),
            facility_id=facility_id,
            name=s["name"],
            asset_tag=s["tag"],
            account_id=asset_acc_id,
            accumulated_depreciation_account_id=accum_dep_id,
            depreciation_expense_account_id=dep_exp_id,
            purchase_date=TODAY - timedelta(days=180),
            purchase_cost=Decimal(s["cost"]),
            useful_life_months=s["months"],
            salvage_value=salvage,
            depreciation_method="straight_line",
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(fa)
        created += 1

    await db.flush()
    print(f"  Fixed assets: {created} created")
    return created


# ── Budgets ──────────────────────────────────────────────────────────────────


async def seed_budgets(
    db: AsyncSession,
    facility_id: uuid.UUID,
    period_map: dict[str, uuid.UUID],
    dept_map: dict[str, uuid.UUID],
    user_id: uuid.UUID,
) -> int:
    """Seed ~10 budget lines for the current month."""
    existing = (
        await db.execute(
            select(Budget).where(Budget.facility_id == facility_id)
        )
    ).scalars().all()
    if existing:
        print(f"  Budgets: {len(existing)} already exist")
        return 0

    accounts = (
        await db.execute(
            select(Account).where(Account.facility_id == facility_id)
        )
    ).scalars().all()
    by_code = {a.code: a.id for a in accounts}

    current_period_name = f"{TODAY.year}-{TODAY.month:02d}"
    period_id = period_map.get(current_period_name)
    if not period_id:
        print("  Budgets: current period missing, skipping")
        return 0

    samples: list[tuple[str, str, int]] = [
        # (account_code, dept_code, kes_amount)
        ("5000", "OPD", 500_000),     # OPD Salaries
        ("5030", "OPD", 50_000),      # OPD Operating
        ("1200", "PHARM", 800_000),   # Pharmacy Inventory
        ("5000", "PHARM", 200_000),   # Pharmacy Salaries
        ("5030", "LAB", 150_000),     # Lab Reagents (op exp)
        ("5000", "LAB", 250_000),     # Lab Salaries
        ("5030", "ADMIN", 80_000),    # Admin Utilities (op exp)
        ("5030", "ADMIN", 100_000),   # Admin Rent (op exp)
        ("5000", "IPD", 600_000),     # IPD Salaries
        ("5030", "IPD", 100_000),     # IPD Supplies (op exp)
    ]

    created = 0
    for i, (acc_code, dept_code, kes) in enumerate(samples):
        acc_id = by_code.get(acc_code)
        dept_id = dept_map.get(dept_code)
        if not acc_id:
            continue
        budget = Budget(
            id=_det(f"budget:{i}:{acc_code}:{dept_code}"),
            facility_id=facility_id,
            account_id=acc_id,
            department_id=dept_id,
            period_id=period_id,
            budgeted_amount=Decimal(kes),
            approved_by=user_id,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(budget)
        created += 1

    await db.flush()
    print(f"  Budgets: {created} created")
    return created


# ── Recurring Templates ──────────────────────────────────────────────────────


async def seed_recurring_templates(
    db: AsyncSession, facility_id: uuid.UUID, user_id: uuid.UUID
) -> int:
    """Seed 3 sample recurring transaction templates."""
    existing = (
        await db.execute(
            select(RecurringTemplate).where(
                RecurringTemplate.facility_id == facility_id
            )
        )
    ).scalars().all()
    if existing:
        print(f"  Recurring templates: {len(existing)} already exist")
        return 0

    accounts = (
        await db.execute(
            select(Account).where(Account.facility_id == facility_id)
        )
    ).scalars().all()
    by_code = {a.code: a.id for a in accounts}

    cash_id = by_code.get("1010")
    bank_id = by_code.get("1020")
    op_exp_id = by_code.get("5030")
    sal_exp_id = by_code.get("5000")
    if not all([cash_id, op_exp_id, sal_exp_id, bank_id]):
        print("  Recurring templates: required accounts missing, skipping")
        return 0

    # Last day of current month
    if TODAY.month == 12:
        last_day = date(TODAY.year, 12, 31)
    else:
        last_day = date(TODAY.year, TODAY.month + 1, 1) - timedelta(days=1)

    samples: list[dict[str, Any]] = [
        {"name": "Monthly Rent", "event": "expense_paid",
         "amount": 100_000, "debit": op_exp_id, "credit": cash_id,
         "frequency": "monthly", "next": last_day},
        {"name": "Monthly Salary Run", "event": "payroll_run",
         "amount": 1_000_000, "debit": sal_exp_id, "credit": bank_id,
         "frequency": "monthly", "next": date(TODAY.year, TODAY.month, 25)
         if TODAY.day <= 25 else (
             date(TODAY.year + (1 if TODAY.month == 12 else 0),
                  1 if TODAY.month == 12 else TODAY.month + 1, 25))},
        {"name": "Insurance Premium", "event": "expense_paid",
         "amount": 25_000, "debit": op_exp_id, "credit": cash_id,
         "frequency": "monthly",
         "next": date(TODAY.year + (1 if TODAY.month == 12 else 0),
                      1 if TODAY.month == 12 else TODAY.month + 1, 1)},
    ]

    created = 0
    for s in samples:
        rt = RecurringTemplate(
            id=_det(f"recurring:{s['name']}"),
            facility_id=facility_id,
            name=s["name"],
            event_type=s["event"],
            amount=Decimal(s["amount"]),
            account_debit_id=s["debit"],
            account_credit_id=s["credit"],
            frequency=s["frequency"],
            next_post_date=s["next"],
            is_active=True,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(rt)
        created += 1

    await db.flush()
    print(f"  Recurring templates: {created} created")
    return created


# ── M-Pesa STK Sample Records ────────────────────────────────────────────────


async def seed_mpesa_samples(
    db: AsyncSession,
    facility_id: uuid.UUID,
    patient_ids: list[uuid.UUID],
    user_id: uuid.UUID,
) -> int:
    """Seed 5 sample M-Pesa STK Push request rows."""
    existing = (
        await db.execute(
            select(MpesaStkRequest).where(
                MpesaStkRequest.facility_id == facility_id
            )
        )
    ).scalars().all()
    if existing:
        print(f"  M-Pesa samples: {len(existing)} already exist")
        return 0

    samples: list[dict[str, Any]] = [
        {"phone": "+254712345001", "amount": 500, "status": "success",
         "result_code": 0, "receipt": "QA12CD3456"},
        {"phone": "+254712345004", "amount": 1500, "status": "success",
         "result_code": 0, "receipt": "QB45EF6789"},
        {"phone": "+254712345008", "amount": 800, "status": "pending",
         "result_code": None, "receipt": None},
        {"phone": "+254712345002", "amount": 2200, "status": "failed",
         "result_code": 1032, "receipt": None,
         "result_desc": "Request cancelled by user"},
        {"phone": "+254712345011", "amount": 1200, "status": "success",
         "result_code": 0, "receipt": "QC78GH9012"},
    ]

    created = 0
    for i, s in enumerate(samples, start=1):
        patient_id = patient_ids[i % len(patient_ids)] if patient_ids else None
        m = MpesaStkRequest(
            id=_det(f"mpesa:{i}"),
            facility_id=facility_id,
            patient_id=patient_id,
            phone_number=s["phone"],
            amount=Decimal(s["amount"]),
            reference=f"INV-{TODAY.year}-{i:05d}",
            description=f"Hospital invoice payment {i}",
            checkout_request_id=f"ws_CO_demo_{i:08d}",
            merchant_request_id=f"merchant_demo_{i:08d}",
            status=s["status"],
            result_code=s["result_code"],
            result_desc=s.get("result_desc"),
            mpesa_receipt_number=s["receipt"],
            transaction_date=NOW if s["status"] == "success" else None,
            completed_at=NOW if s["status"] != "pending" else None,
            created_by=user_id,
            updated_by=user_id,
        )
        db.add(m)
        created += 1

    await db.flush()
    print(f"  M-Pesa samples: {created} created")
    return created


# ── Reset (soft delete) ──────────────────────────────────────────────────────


async def reset_demo_data(db: AsyncSession) -> None:
    """Soft-delete all demo facility data (is_deleted=True)."""
    fac = (
        await db.execute(
            select(Facility).where(Facility.code == DEMO_FACILITY_CODE)
        )
    ).scalar_one_or_none()
    if fac is None:
        print("No demo facility found, nothing to reset.")
        return

    facility_id = fac.id
    print(f"Resetting demo data for facility {facility_id}...")

    # Tables with AuditMixin (have is_deleted) — flag them.
    tables_with_soft_delete = [
        Department, Staff, Patient, Encounter, Invoice, InvoiceItem, Payment,
        PharmacyItem, InsuranceScheme, Account, AccountingPeriod, Budget,
        FixedAsset, RecurringTemplate, Employee, EmployeeSalary, PayrollRun,
        PayrollLeaveRequest, MpesaStkRequest,
    ]
    for model in tables_with_soft_delete:
        await db.execute(
            update(model)
            .where(model.facility_id == facility_id)
            .values(is_deleted=True, deleted_at=NOW)
        )
    # Facility itself: is_active=False (no is_deleted on Facility model).
    fac.is_active = False
    await db.flush()
    print("Reset complete (soft delete).")


# ── Orchestration ────────────────────────────────────────────────────────────


async def main(reset: bool = False) -> None:
    """Run the full demo seed.

    @param reset: if True, soft-delete all demo facility data and exit.
    """
    async with async_session() as db:
        try:
            if reset:
                await reset_demo_data(db)
                await db.commit()
                return

            print("\n=== Aifya Demo Seed ===\n")

            print("[1] Facility")
            fac = await get_or_create_facility(db)
            facility_id = fac.id
            # Use the admin staff UUID once it exists; for the early
            # passes the user_id is the deterministic admin staff ID.
            admin_staff_id = _det("staff:AIFYA-001")

            print("\n[2] Departments")
            dept_map = await seed_departments(db, facility_id)

            print("\n[3] Staff")
            staff_map = await seed_staff(db, facility_id, dept_map)
            admin_staff_id = staff_map.get("AIFYA-001", admin_staff_id)

            print("\n[4] Patients")
            patient_ids = await seed_patients(db, facility_id)

            print("\n[4b] Appointments")
            await seed_appointments(
                db, facility_id, patient_ids, staff_map, dept_map
            )

            print("\n[4c] OPD Encounters + Vitals")
            await seed_encounters_and_vitals(
                db, facility_id, patient_ids, staff_map, dept_map
            )

            print("\n[4d] Dashboard Outpatient Visits (50 today)")
            await seed_dashboard_outpatient_visits(
                db, facility_id, patient_ids, staff_map, dept_map
            )

            print("\n[5] Pharmacy Items")
            await seed_pharmacy(db, facility_id)

            print("\n[6] SHA Insurance Scheme")
            await seed_insurance(db, facility_id)

            print("\n[7] Finance: Chart of Accounts + Posting Rules")
            fin_summary = await seed_facility_finance(
                db, facility_id, admin_staff_id
            )
            print(
                f"  Accounts: {fin_summary['accounts_created']}, "
                f"Posting rules: {fin_summary['rules_created']}"
            )

            print("\n[8] Accounting Periods")
            period_map = await seed_accounting_periods(db, facility_id)

            # Finance needs to be committed before invoices can post,
            # because the posting engine reads accounts/rules in a
            # SAVEPOINT.
            await db.flush()

            print("\n[9] Invoices, Payments, Expenses (with GL postings)")
            await seed_invoices_and_postings(
                db, facility_id, patient_ids, dept_map, admin_staff_id
            )

            print("\n[10] Payroll: Statutory Defaults (PAYE, NSSF, SHIF, HL)")
            await seed_payroll_defaults(db)

            print("\n[11] Employees + Salaries")
            employee_ids = await seed_employees(
                db, facility_id, dept_map, admin_staff_id
            )

            print("\n[12] Demo Payroll Run (previous month)")
            await run_demo_payroll(db, facility_id, admin_staff_id)

            print("\n[13] Leave Requests")
            await seed_leave_requests(
                db, facility_id, employee_ids, admin_staff_id
            )

            print("\n[14] Fixed Assets")
            await seed_fixed_assets(db, facility_id, admin_staff_id)

            print("\n[15] Budgets")
            await seed_budgets(
                db, facility_id, period_map, dept_map, admin_staff_id
            )

            print("\n[16] Recurring Templates")
            await seed_recurring_templates(db, facility_id, admin_staff_id)

            print("\n[17] M-Pesa Sample Records")
            await seed_mpesa_samples(db, facility_id, patient_ids, admin_staff_id)

            await db.commit()
            print_summary(facility_id)

        except Exception:
            await db.rollback()
            raise


def print_summary(facility_id: uuid.UUID) -> None:
    """Print a clear post-seed summary with credentials."""
    print(
        "\n"
        "=== AIFYA DEMO SEED COMPLETE ===\n"
        f"Facility: {DEMO_FACILITY_NAME} ({DEMO_FACILITY_CODE})\n"
        f"Facility ID: {facility_id}\n"
        f"Patients: {len(PATIENTS)}\n"
        f"Staff: {len(STAFF_DEFINITIONS)}\n"
        f"Employees (payroll): {len(EMPLOYEE_DEFINITIONS)}\n"
        f"Pharmacy items: {len(PHARMACY_ITEMS)}\n"
        f"Invoices: {len(INVOICE_SCENARIOS)}\n"
        "GL transactions: ~50 (invoices + payments + expenses + payroll)\n"
        "Payroll runs: 1 (approved, posted to GL)\n"
        "\n"
        "DEMO USERS (create these in Keycloak separately):\n"
        "  admin@aifya.co.ke   / DemoAdmin2026!  -- Admin / Finance\n"
        "  doctor@aifya.co.ke  / DemoDoctor2026! -- Doctor\n"
        "  nurse@aifya.co.ke   / DemoNurse2026!  -- Nurse\n"
        "  pharmacy@aifya.co.ke/ DemoPharm2026!  -- Pharmacist\n"
        "  lab@aifya.co.ke     / DemoLab2026!    -- Lab Tech\n"
        "  cashier@aifya.co.ke / DemoCash2026!   -- Cashier\n"
        "  hr@aifya.co.ke      / DemoHR2026!     -- HR Admin\n"
        "  reception@aifya.co.ke / DemoRec2026!  -- Receptionist\n"
        "\n"
        "NOTE: This script seeds the database only. A Keycloak admin must\n"
        "create the matching users in the 'aifya' realm with the same\n"
        "emails before login will work. Each Staff row has a deterministic\n"
        "keycloak_user_id which the Keycloak users should be linked to,\n"
        "or you can update the Staff.keycloak_user_id after creating the\n"
        "Keycloak users.\n"
        "\n"
        "Next steps:\n"
        "  1. Visit http://localhost:3000\n"
        "  2. Log in with one of the credentials above\n"
        "  3. Navigate to /finance, /hr/payroll, /performance\n"
        "================================="
    )


def parse_args() -> argparse.Namespace:
    """Parse CLI args."""
    p = argparse.ArgumentParser(
        description="Seed (or reset) the Aifya demo dataset."
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="Soft-delete all data for the demo facility (is_deleted=True).",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(reset=args.reset))
