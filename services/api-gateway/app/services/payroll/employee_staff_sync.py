"""Keep payroll employees mirrored into the clinical staff directory.

The duty roster, the emergency "Assign doctor" panel and the appointments
doctor lists all read from the clinical ``staff`` table. Registering a doctor
through HR -> Employees -> Add Employee only writes a payroll ``employees``
row, so this module mirrors the employee into ``staff`` (with the correct
clinical role such as ``doctor``) straight from the API. That makes a doctor
registered here appear in the doctor dropdowns even when the database-level
``sync_employee_to_staff()`` trigger is missing or outdated.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hr import StaffProfile
from app.models.staff import Staff

# Specialty/role words that identify a clinician as a doctor. They are matched
# against the lower-cased job title AFTER the midwife/nurse checks so titles
# such as "Paediatric Nurse" stay nurses while "General Practitioner",
# "Medical Officer" or "Consultant Surgeon" become doctors.
_DOCTOR_KEYWORDS = (
    "doctor",
    "physician",
    "medical officer",
    "consultant",
    "general practitioner",
    "medical practitioner",
    "family practitioner",
    "medical specialist",
    "registrar",
    "surgeon",
    "pediatric",
    "paediatric",
    "gynecolog",
    "gynaecolog",
    "obstetric",
    "dermatolog",
    "cardiolog",
    "neurolog",
    "psychiatr",
    "anesthes",
    "anaesthet",
    "ophthalmolog",
    "otolaryng",
    "orthoped",
    "orthopaed",
    "gastroenterolog",
    "urolog",
    "endocrinolog",
    "nephrolog",
    "pulmonolog",
    "rheumatolog",
    "oncolog",
    "hematolog",
    "haematolog",
    "internist",
    "family medicine",
    "emergency medicine",
)


def map_role_from_job_title(job_title: str | None) -> str:
    """Map a payroll job title to the matching staff directory role."""
    if not job_title:
        return "staff"
    title = job_title.lower()
    if "midwife" in title:
        return "midwife"
    if "nurse" in title:
        return "nurse"
    if any(keyword in title for keyword in _DOCTOR_KEYWORDS):
        return "doctor"
    if "pharmac" in title:
        return "pharmacist"
    if "laborat" in title or title.startswith("lab"):
        return "lab_tech"
    if "radiolog" in title:
        return "radiologist"
    if "cashier" in title:
        return "cashier"
    if "reception" in title:
        return "receptionist"
    if "record" in title:
        return "records"
    return "staff"


def _split_name(full_name: str) -> tuple[str, str]:
    """Split a full name into first and last names like the DB trigger does."""
    parts = full_name.strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


async def sync_employee_to_staff(
    db: AsyncSession,
    *,
    facility_id: uuid.UUID,
    employee: object,
    actor_id: uuid.UUID | None,
) -> Staff | None:
    """Create or refresh the clinical staff row for a payroll employee."""
    employee_number = (getattr(employee, "staff_id") or "").strip()
    full_name = (getattr(employee, "full_name") or "").strip()
    if not employee_number or not full_name:
        return None

    first_name, last_name = _split_name(full_name)
    role = map_role_from_job_title(getattr(employee, "job_title", None))
    employee_email = (getattr(employee, "email") or "").strip()
    email = employee_email or f"{employee_number}@aifya.co.ke"
    phone = (getattr(employee, "phone") or "").strip() or None

    result = await db.execute(
        select(Staff).where(
            Staff.facility_id == facility_id,
            Staff.employee_number == employee_number,
            Staff.is_deleted == False,  # noqa: E712
        )
    )
    staff = result.scalars().first()

    if staff is None:
        staff = Staff(
            facility_id=facility_id,
            keycloak_user_id=uuid.uuid4(),
            employee_number=employee_number,
            first_name=first_name,
            last_name=last_name,
            role=role,
            email=email,
            phone=phone,
            is_active=bool(getattr(employee, "is_active", True)),
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(staff)
        await db.flush()
        await _ensure_staff_profile(db, staff, employee, actor_id)
    else:
        staff.first_name = first_name
        staff.last_name = last_name
        staff.role = role
        if employee_email:
            staff.email = employee_email
        if phone:
            staff.phone = phone
        staff.is_active = bool(getattr(employee, "is_active", True))
        staff.updated_by = actor_id

    return staff


async def _ensure_staff_profile(
    db: AsyncSession,
    staff: Staff,
    employee: object,
    actor_id: uuid.UUID | None,
) -> None:
    """Create the matching staff_profile row when a staff row is created."""
    existing = await db.execute(
        select(StaffProfile.id).where(
            StaffProfile.facility_id == staff.facility_id,
            StaffProfile.staff_id == staff.id,
            StaffProfile.is_deleted == False,  # noqa: E712
        )
    )
    if existing.scalar_one_or_none() is not None:
        return
    profile = StaffProfile(
        facility_id=staff.facility_id,
        staff_id=staff.id,
        employment_type=getattr(employee, "employment_type") or "permanent",
        employment_date=getattr(employee, "hire_date", None),
        nssf_number=getattr(employee, "nssf_number", None),
        created_by=actor_id,
        updated_by=actor_id,
    )
    db.add(profile)
    await db.flush()