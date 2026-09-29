"""What a signed-in user may do, once the hospital has said who they are.

A role alone is too blunt a key.  ``doctor`` staffs every speciality, so the
role can say "may consult" but never "may consult *here*" - the department on
the staff record answers that (see ``app/services/clinical_workspace.py``).
What the role *can* answer is which parts of Aifya a person may open at all: a
cashier has no business reading a doctor's consultation notes, and a
receptionist has no business approving a prescription.

This module is that second answer, in three layers:

1. ``ROLE_PERMISSIONS`` - the permission set each role holds by default.  It is
   the shipped baseline and the fallback when the ``role_permissions`` table
   has not been seeded, so a facility that never touches the table still gets
   sane access control.
2. ``role_permissions`` (migration 029) - per-facility overrides of that
   baseline.  A hospital that wants its nurses to prescribe can grant it
   without a code release.  A global row (``facility_id IS NULL``) applies to
   every facility; a facility row overrides the global one.
3. ``staff.permissions`` - a JSONB map of per-person grants and denials, e.g.
   ``{"clinical.consult": true}``.  This is the escape hatch for the one
   locum who needs more than the role carries.

The layers compose in that order, so the most specific statement wins.
Administrator roles are deliberately outside the chain: ``admin`` and
``facility_admin`` always hold every permission, otherwise a bad override row
could lock a hospital out of its own system.

The API is the authority.  The web app mirrors these strings to hide what it
knows is forbidden, but every endpoint enforces them again server-side.
"""

from __future__ import annotations

import uuid
from enum import StrEnum

from fastapi import Depends, HTTPException, status
from sqlalchemy import case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, current_user_dependency
from app.database import get_db
from app.models.role_permission import RolePermission
from app.models.staff import Staff


class Permission(StrEnum):
    """Every action in Aifya that can be granted or withheld independently."""

    # Records and registration
    PATIENTS_VIEW = "patients.view"
    PATIENTS_REGISTER = "patients.register"
    PATIENTS_UPDATE = "patients.update"
    ENCOUNTERS_CREATE = "encounters.create"

    # Clinical workspace - the doctor's own queue, notes, orders
    CLINICAL_VIEW = "clinical.view"
    CLINICAL_CONSULT = "clinical.consult"

    # Nursing and assessment
    TRIAGE_RECORD = "triage.record"

    # Destinations a patient can be routed to
    OPD_VIEW = "opd.view"
    OPD_MANAGE = "opd.manage"
    IPD_VIEW = "ipd.view"
    IPD_RECORD = "ipd.record"
    EMERGENCY_VIEW = "emergency.view"
    EMERGENCY_RECORD = "emergency.record"
    DENTAL_VIEW = "dental.view"
    DENTAL_RECORD = "dental.record"
    MCH_VIEW = "mch.view"
    MCH_RECORD = "mch.record"
    THEATRE_VIEW = "theatre.view"
    THEATRE_RECORD = "theatre.record"

    # Support departments
    PHARMACY_VIEW = "pharmacy.view"
    PHARMACY_DISPENSE = "pharmacy.dispense"
    LABORATORY_VIEW = "laboratory.view"
    LABORATORY_RESULT = "laboratory.result"
    RADIOLOGY_VIEW = "radiology.view"
    RADIOLOGY_RESULT = "radiology.result"

    # Money
    BILLING_VIEW = "billing.view"
    BILLING_CHARGE = "billing.charge"
    BILLING_PAYMENT = "billing.payment"
    INSURANCE_VIEW = "insurance.view"
    INSURANCE_MANAGE = "insurance.manage"
    FINANCE_VIEW = "finance.view"
    FINANCE_MANAGE = "finance.manage"

    # Back office
    INVENTORY_VIEW = "inventory.view"
    INVENTORY_MANAGE = "inventory.manage"
    HR_VIEW = "hr.view"
    HR_MANAGE = "hr.manage"

    # Journey
    APPOINTMENTS_VIEW = "appointments.view"
    APPOINTMENTS_MANAGE = "appointments.manage"
    REFERRALS_VIEW = "referrals.view"
    REFERRALS_MANAGE = "referrals.manage"

    # Insight and system
    REPORTS_VIEW = "reports.view"
    ANALYTICS_VIEW = "analytics.view"
    COMMUNICATIONS_VIEW = "communications.view"
    TRIALS_VIEW = "trials.view"
    KNOWLEDGE_VIEW = "knowledge.view"
    SETTINGS_MANAGE = "settings.manage"


ALL_PERMISSIONS: frozenset[str] = frozenset(permission.value for permission in Permission)

# Roles that hold everything and cannot be narrowed by an override row.  A
# facility administrator who loses ``settings.manage`` to a stray row has no
# way back in, so they sit outside the override chain entirely.
SUPERUSER_ROLES: frozenset[str] = frozenset(
    {"super_admin", "admin", "facility_admin", "hospital_administrator"}
)

# --- Baseline sets -------------------------------------------------------

# Front desk: identifies the patient, opens the encounter, routes them, and
# takes the consultation fee.  Deliberately has no ``clinical.*`` permission -
# the front desk registers the visit, it does not read the consultation.
_FRONT_DESK = frozenset(
    {
        Permission.PATIENTS_VIEW,
        Permission.PATIENTS_REGISTER,
        Permission.PATIENTS_UPDATE,
        Permission.ENCOUNTERS_CREATE,
        Permission.TRIAGE_RECORD,
        Permission.OPD_VIEW,
        Permission.OPD_MANAGE,
        Permission.APPOINTMENTS_VIEW,
        Permission.APPOINTMENTS_MANAGE,
        Permission.BILLING_VIEW,
        Permission.BILLING_CHARGE,
        Permission.BILLING_PAYMENT,
        Permission.INSURANCE_VIEW,
        Permission.INSURANCE_MANAGE,
        Permission.REFERRALS_VIEW,
        Permission.REFERRALS_MANAGE,
        Permission.KNOWLEDGE_VIEW,
    }
)

# Nursing: triage, vitals, the ward. See the queue, prepare the patient, and
# hand over - but prescribing and diagnosing stay with the clinician.
_NURSING = frozenset(
    {
        Permission.PATIENTS_VIEW,
        Permission.PATIENTS_UPDATE,
        Permission.TRIAGE_RECORD,
        Permission.CLINICAL_VIEW,
        Permission.OPD_VIEW,
        Permission.IPD_VIEW,
        Permission.IPD_RECORD,
        Permission.EMERGENCY_VIEW,
        Permission.EMERGENCY_RECORD,
        Permission.MCH_VIEW,
        Permission.MCH_RECORD,
        Permission.LABORATORY_VIEW,
        Permission.RADIOLOGY_VIEW,
        Permission.PHARMACY_VIEW,
        Permission.APPOINTMENTS_VIEW,
        Permission.REFERRALS_VIEW,
        Permission.KNOWLEDGE_VIEW,
    }
)

# The clinician: clinical workspace, diagnoses, prescriptions and orders.  The
# *department* decides which patients this reaches, not the role.
_CLINICIAN = frozenset(
    {
        Permission.PATIENTS_VIEW,
        Permission.PATIENTS_UPDATE,
        Permission.CLINICAL_VIEW,
        Permission.CLINICAL_CONSULT,
        Permission.TRIAGE_RECORD,
        Permission.OPD_VIEW,
        Permission.OPD_MANAGE,
        Permission.IPD_VIEW,
        Permission.IPD_RECORD,
        Permission.EMERGENCY_VIEW,
        Permission.EMERGENCY_RECORD,
        Permission.MCH_VIEW,
        Permission.MCH_RECORD,
        Permission.DENTAL_VIEW,
        Permission.LABORATORY_VIEW,
        Permission.RADIOLOGY_VIEW,
        Permission.PHARMACY_VIEW,
        Permission.APPOINTMENTS_VIEW,
        Permission.REFERRALS_VIEW,
        Permission.REFERRALS_MANAGE,
        Permission.REPORTS_VIEW,
        Permission.KNOWLEDGE_VIEW,
    }
)

_LABORATORY = frozenset(
    {
        Permission.PATIENTS_VIEW,
        Permission.LABORATORY_VIEW,
        Permission.LABORATORY_RESULT,
        Permission.KNOWLEDGE_VIEW,
    }
)

_RADIOLOGY = frozenset(
    {
        Permission.PATIENTS_VIEW,
        Permission.RADIOLOGY_VIEW,
        Permission.RADIOLOGY_RESULT,
        Permission.KNOWLEDGE_VIEW,
    }
)

_PHARMACY = frozenset(
    {
        Permission.PATIENTS_VIEW,
        Permission.PHARMACY_VIEW,
        Permission.PHARMACY_DISPENSE,
        Permission.INVENTORY_VIEW,
        Permission.BILLING_VIEW,
        Permission.KNOWLEDGE_VIEW,
    }
)

# The money desk. Finance and inventory view are here because the sidebar
# groups Billing, Finance, GL Transactions, Budgets and Inventory under one
# "Accountant" destination set: a cashier who could see the Finance tab but
# was refused by /api/v1/finance would read as a broken build rather than as
# a deliberate boundary.
_CASHIER = frozenset(
    {
        Permission.PATIENTS_VIEW,
        Permission.BILLING_VIEW,
        Permission.BILLING_CHARGE,
        Permission.BILLING_PAYMENT,
        Permission.INSURANCE_VIEW,
        Permission.INSURANCE_MANAGE,
        Permission.FINANCE_VIEW,
        Permission.INVENTORY_VIEW,
        Permission.REPORTS_VIEW,
        Permission.KNOWLEDGE_VIEW,
    }
)

_FINANCE = frozenset(
    {
        Permission.PATIENTS_VIEW,
        Permission.BILLING_VIEW,
        Permission.BILLING_CHARGE,
        Permission.BILLING_PAYMENT,
        Permission.INSURANCE_VIEW,
        Permission.INSURANCE_MANAGE,
        Permission.FINANCE_VIEW,
        Permission.FINANCE_MANAGE,
        Permission.INVENTORY_VIEW,
        Permission.REPORTS_VIEW,
        Permission.ANALYTICS_VIEW,
        Permission.KNOWLEDGE_VIEW,
    }
)

# The HR desk owns the facility's day book as well as its staff file: the
# appointment book, the referral queue, the analytics dashboards and the
# communications centre are all HR destinations in the navigation, and a
# destination is only useful if the API behind it answers.
_HR = frozenset(
    {
        Permission.HR_VIEW,
        Permission.HR_MANAGE,
        Permission.REPORTS_VIEW,
        Permission.KNOWLEDGE_VIEW,
        Permission.APPOINTMENTS_VIEW,
        Permission.REFERRALS_VIEW,
        Permission.ANALYTICS_VIEW,
        Permission.COMMUNICATIONS_VIEW,
    }
)

# The HR administrator is the person who issues access: they add the employee,
# choose the role, set the password and switch the account on or off. Setting a
# colleague's password is the same act as creating their account, so it sits
# here rather than in an administrator-only set - and it also needs the facility
# profile, because the hospital's own name and contacts are HR's to keep right.
# Only the HR administrator carries it. The Setting and Integrations
# destinations are the facility's own configuration, so an HR officer keeps the
# staff records, the appointment book and the payroll without gaining the power
# to rewrite the hospital's settings or the integration keys behind them.
_HR_ADMIN = _HR | {Permission.SETTINGS_MANAGE}

_STORES = frozenset(
    {
        Permission.INVENTORY_VIEW,
        Permission.INVENTORY_MANAGE,
        Permission.PHARMACY_VIEW,
        Permission.KNOWLEDGE_VIEW,
    }
)

_RESEARCH = frozenset(
    {
        Permission.PATIENTS_VIEW,
        Permission.CLINICAL_VIEW,
        Permission.TRIALS_VIEW,
        Permission.REPORTS_VIEW,
        Permission.ANALYTICS_VIEW,
        Permission.COMMUNICATIONS_VIEW,
        Permission.KNOWLEDGE_VIEW,
    }
)

# The residual bucket. The employee sync maps an unrecognised job title to the
# role ``staff``, so this is what a cook, a driver or an unclassified
# administrator holds. It must not be empty: an account with no permissions at
# all gets a sidebar with one link and a wall of 403s, which reads as a broken
# system rather than as a missing role assignment.
_UNCLASSIFIED = frozenset(
    {
        Permission.PATIENTS_VIEW,
        Permission.KNOWLEDGE_VIEW,
    }
)


def _as_strings(permissions: frozenset[Permission]) -> frozenset[str]:
    """
    Widen a baseline set from enum members to plain permission strings.

    @param permissions: Permissions as enum members
    @returns The same permissions as ``permission.value`` strings
    """
    return frozenset(permission.value for permission in permissions)


#: The permission set each ``staff.role`` holds before overrides.  Keys are the
#: role values the codebase actually stores, plus the aliases hospitals commonly
#: type in the same field (``triage_nurse``, ``ward_nurse``, ``clinician``,
#: ...) so a near-miss spelling is still gated sensibly rather than silently
#: dropped to zero permissions.
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "super_admin": ALL_PERMISSIONS,
    "admin": ALL_PERMISSIONS,
    "facility_admin": ALL_PERMISSIONS,
    "hospital_administrator": ALL_PERMISSIONS,
    "receptionist": _as_strings(_FRONT_DESK),
    "records": _as_strings(_FRONT_DESK),
    "medical_records": _as_strings(_FRONT_DESK),
    "nurse": _as_strings(_NURSING | {Permission.TRIALS_VIEW}),
    "triage_nurse": _as_strings(_NURSING | {Permission.TRIALS_VIEW}),
    "ward_nurse": _as_strings(_NURSING | {Permission.TRIALS_VIEW}),
    "midwife": _as_strings(_NURSING | {Permission.MCH_RECORD}),
    "doctor": _as_strings(_CLINICIAN | {Permission.TRIALS_VIEW}),
    "clinician": _as_strings(_CLINICIAN | {Permission.TRIALS_VIEW}),
    "specialist": _as_strings(_CLINICIAN | {Permission.THEATRE_VIEW}),
    "dentist": _as_strings(_CLINICIAN | {Permission.DENTAL_RECORD}),
    "lab_tech": _as_strings(_LABORATORY),
    "pathologist": _as_strings(_LABORATORY),
    "rad_tech": _as_strings(_RADIOLOGY),
    "radiologist": _as_strings(_RADIOLOGY),
    "pharmacist": _as_strings(_PHARMACY),
    "cashier": _as_strings(_CASHIER),
    "billing": _as_strings(_CASHIER),
    "billing_clerk": _as_strings(_CASHIER),
    "billing_officer": _as_strings(_CASHIER | {Permission.REPORTS_VIEW}),
    "finance_admin": _as_strings(_FINANCE),
    "hr": _as_strings(_HR),
    "hr_admin": _as_strings(_HR_ADMIN),
    "hr_officer": _as_strings(_HR),
    "store_keeper": _as_strings(_STORES),
    "research_coordinator": _as_strings(_RESEARCH),
    "principal_investigator": _as_strings(_RESEARCH),
    "staff": _as_strings(_UNCLASSIFIED),
}

#: What an account holds when *none* of its roles appear in the matrix. Never
#: empty, for the same reason ``staff`` is never empty: a role nobody has
#: taught the system about should still leave a working - if narrow - app.
UNCLASSIFIED_PERMISSIONS: frozenset[str] = _as_strings(_UNCLASSIFIED)


#: The roles HR may write onto a staff record, in the order the Role picker
#: shows them. Each entry is ``(stored role, picker label, one-line purpose)``.
#:
#: This tuple is the whole of "an employee cannot create their own role": the
#: HR screens only ever offer these strings and the endpoints reject anything
#: else, so ``staff.role`` can only hold a value the matrix above already
#: understands. Administrator roles are deliberately absent - an HR officer who
#: could mint a facility_admin could grant themselves every permission in the
#: system - so the first administrator is created by facility onboarding
#: instead, and everything after that is an explicit, auditable choice.
ASSIGNABLE_ROLES: tuple[tuple[str, str, str], ...] = (
    (
        "doctor",
        "Doctor",
        "Consultations, clinical workspace, OPD, IPD and emergency care",
    ),
    ("specialist", "Specialist / Consultant", "Doctor access plus theatre"),
    ("dentist", "Dentist", "Doctor access plus the dental clinic"),
    ("nurse", "Nurse", "Triage and nursing care across OPD, IPD and emergency"),
    ("midwife", "Midwife", "Nurse access plus maternal and child health"),
    ("pharmacist", "Pharmacist", "Pharmacy dispensing and stock"),
    ("lab_tech", "Laboratory Technician", "Laboratory requests and results"),
    (
        "radiologist",
        "Radiologist / Radiographer",
        "Radiology requests and reports",
    ),
    ("receptionist", "Receptionist", "Registration, appointments and routing"),
    ("records", "Medical Records", "Registration and patient records"),
    ("cashier", "Cashier / Billing", "Billing, payments and insurance"),
    (
        "finance_admin",
        "Accountant / Finance",
        "Billing, finance, inventory and reports",
    ),
    (
        "hr_admin",
        "HR Administrator",
        "Staff records, payroll, HR reports and facility settings",
    ),
    ("store_keeper", "Store Keeper", "Inventory and pharmacy stock"),
    (
        "research_coordinator",
        "Research Coordinator",
        "Clinical trials, reports and analytics",
    ),
    (
        "staff",
        "Other / Support Staff",
        "Records view only - no clinical or financial access",
    ),
)

_ASSIGNABLE_ROLE_NAMES: frozenset[str] = frozenset(
    role for role, _label, _purpose in ASSIGNABLE_ROLES
)


def normalise_role(role: str) -> str:
    """
    Normalise a role string for matrix lookup.

    @param role: Role as stored on the staff record or carried in the token
    @returns Lower-case, trimmed role
    """
    return role.strip().lower()


def is_superuser(roles: list[str]) -> bool:
    """
    Whether any of these roles always holds every permission.

    @param roles: Roles from the access token or staff record
    @returns True when the caller is an administrator role
    """
    return any(normalise_role(role) in SUPERUSER_ROLES for role in roles)


def is_assignable_role(role: str | None) -> bool:
    """
    Whether HR is allowed to write this role onto a staff record.

    The HR screens send a role name; this is the check that turns "an employee
    may not choose their own access" into a rule the API enforces rather than a
    convention the interface follows. It compares on the normalised name so
    ``Lab_Tech`` and ``lab_tech`` are the same role.

    @param role: Role name from the request body
    @returns True when the role is one HR may assign
    """
    if not role:
        return False
    return normalise_role(role) in _ASSIGNABLE_ROLE_NAMES


def assignable_roles() -> list[dict[str, str]]:
    """
    The role catalogue for the HR picker, with each role's baseline access.

    The permission list is the shipped baseline (not the facility's overrides)
    so the picker can be built from a single synchronous call. The Settings ->
    Roles screen still shows the resolved, facility-specific matrix.

    @returns One dict per assignable role: role, label, description, permissions
    """
    options: list[dict[str, str]] = []
    for role, label, description in ASSIGNABLE_ROLES:
        options.append(
            {
                "role": role,
                "label": label,
                "description": description,
                "permissions": sorted(
                    ROLE_PERMISSIONS.get(role, UNCLASSIFIED_PERMISSIONS)
                ),
            }
        )
    return options


def permissions_for_roles(roles: list[str]) -> frozenset[str]:
    """
    Union the baseline permission sets of every role a user holds.

    @param roles: Roles from the access token or staff record
    @returns Permission strings granted by those roles, never empty
    """
    granted: set[str] = set()
    matched = False
    for role in roles:
        permissions = ROLE_PERMISSIONS.get(normalise_role(role))
        if permissions is None:
            continue
        matched = True
        granted.update(permissions)
    if not matched:
        return UNCLASSIFIED_PERMISSIONS
    return frozenset(granted)


def is_allowed(
    granted: frozenset[str] | set[str],
    required: tuple[str, ...],
    *,
    any_of: bool = False,
) -> bool:
    """
    Whether a granted permission set satisfies a requirement.

    @param granted: Permission strings the caller holds
    @param required: Permission strings the endpoint demands
    @param any_of: When True one match is enough, otherwise all are needed
    @returns True when the requirement is satisfied
    """
    if not required:
        return True
    if any_of:
        return any(permission in granted for permission in required)
    return all(permission in granted for permission in required)


async def _facility_overrides(
    db: AsyncSession, facility_id: uuid.UUID, roles: list[str]
) -> list[tuple[str, bool]]:
    """
    Read the ``role_permissions`` rows that apply to these roles.

    Global rows (``facility_id IS NULL``) come first and facility rows last, so
    a facility's own statement is applied on top of the shared default.

    @param db: Database session
    @param facility_id: Facility the caller is signed in to
    @param roles: Roles to look up
    @returns ``(permission, is_allowed)`` pairs in application order
    """
    statement = (
        select(RolePermission.permission, RolePermission.is_allowed)
        .where(
            RolePermission.role.in_([normalise_role(role) for role in roles]),
            RolePermission.is_deleted == False,  # noqa: E712
            or_(
                RolePermission.facility_id.is_(None),
                RolePermission.facility_id == facility_id,
            ),
        )
        # Global rows first, this facility's rows last, so the facility's own
        # statement is the one left standing. A CASE keeps the ordering
        # portable rather than depending on NULLS FIRST.
        .order_by(
            case((RolePermission.facility_id.is_(None), 0), else_=1),
            RolePermission.created_at.asc(),
        )
    )
    rows = (await db.execute(statement)).all()
    return [(str(permission), bool(is_allowed)) for permission, is_allowed in rows]


async def _staff_overrides(
    db: AsyncSession, staff_id: uuid.UUID
) -> dict[str, bool]:
    """
    Read the per-person grant/deny map from ``staff.permissions``.

    @param db: Database session
    @param staff_id: Staff UUID from the token subject
    @returns Permission name to allowed flag, ignoring unknown names
    """
    permissions = (
        await db.execute(select(Staff.permissions).where(Staff.id == staff_id))
    ).scalar_one_or_none()
    if not isinstance(permissions, dict):
        return {}
    return {
        str(key): bool(value)
        for key, value in permissions.items()
        if str(key) in ALL_PERMISSIONS
    }


async def resolve_permissions(
    db: AsyncSession, current_user: CurrentUser
) -> frozenset[str]:
    """
    Work out everything this caller may do, overriding as it goes.

    @param db: Database session
    @param current_user: Authenticated user from the token
    @returns The effective permission set
    """
    if is_superuser(current_user.roles):
        return ALL_PERMISSIONS

    granted = set(permissions_for_roles(current_user.roles))

    for permission, allowed in await _facility_overrides(
        db, current_user.facility_id, current_user.roles
    ):
        if allowed:
            granted.add(permission)
        else:
            granted.discard(permission)

    for permission, allowed in (
        await _staff_overrides(db, current_user.user_id)
    ).items():
        if allowed:
            granted.add(permission)
        else:
            granted.discard(permission)

    return frozenset(granted)


async def effective_role_permissions(
    db: AsyncSession, facility_id: uuid.UUID, role: str
) -> frozenset[str]:
    """
    Work out what one role may do at one facility, overrides included.

    Unlike :func:`resolve_permissions`, this takes a role name rather than a
    signed-in user, so the Settings -> Roles screen can show the whole matrix
    instead of only the caller's own access.

    @param db: Database session
    @param facility_id: Facility whose overrides apply
    @param role: Role name to resolve
    @returns The effective permission set for that role
    """
    normalised = normalise_role(role)
    if normalised in SUPERUSER_ROLES:
        return ALL_PERMISSIONS

    granted = set(ROLE_PERMISSIONS.get(normalised, UNCLASSIFIED_PERMISSIONS))

    for permission, allowed in await _facility_overrides(db, facility_id, [normalised]):
        if allowed:
            granted.add(permission)
        else:
            granted.discard(permission)

    return frozenset(granted)


def require_permission(*required: str, any_of: bool = False):
    """
    Build a dependency that admits only callers holding the permission.

    ``@param``-style docs do not fit a dependency factory, so in short: pass
    the permission strings the endpoint needs, and ``any_of=True`` when holding
    any one of them is enough.

    @param required: Permission strings the endpoint demands
    @param any_of: When True one match is enough, otherwise all are needed
    @returns A FastAPI dependency returning the authenticated user
    """

    async def permission_checker(
        current_user: CurrentUser = current_user_dependency,
        db: AsyncSession = Depends(get_db),
    ) -> CurrentUser:
        granted = await resolve_permissions(db, current_user)
        if not is_allowed(granted, required, any_of=any_of):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Requires permission: " + ", ".join(required),
            )
        return current_user

    return permission_checker

# --- Destinations ---------------------------------------------------------

#: The roles that own each navigation destination, mirroring the ``roles`` list
#: on ``apps/web/src/lib/navigation.ts``. The sidebar reads it to decide which
#: tabs to draw; ``require_destination`` reads it to decide which calls to
#: answer, so a tab no worker can see is also a room no other worker can open.
#:
#: This answers a different question from ``require_permission``. A doctor holds
#: ``pharmacy.view`` because the consultation screen reads the drug catalogue -
#: that is an action inside the doctor's own room. The pharmacy dispensing queue
#: is not an action, it is a room, and it belongs to the pharmacist.
#:
#: Destinations that are not listed here are not role-owned: patients, the
#: dashboard and the user guide stay open to any signed-in employee.
DESTINATION_ROLES: dict[str, frozenset[str]] = {
    "consultation": frozenset({"nurse", "triage_nurse", "ward_nurse", "midwife"}),
    "clinical": frozenset(
        {"doctor", "clinician", "nurse", "triage_nurse", "ward_nurse", "midwife"}
    ),
    "pharmacy": frozenset({"pharmacist"}),
    "laboratory": frozenset({"lab_tech", "pathologist"}),
    "radiology": frozenset({"radiologist", "rad_tech"}),
    "theatre": frozenset({"specialist"}),
    "dental": frozenset({"dentist"}),
    "mch": frozenset({"midwife"}),
    "trials": frozenset(
        {
            "doctor",
            "clinician",
            "nurse",
            "triage_nurse",
            "ward_nurse",
            "research_coordinator",
            "principal_investigator",
        }
    ),
    "finance": frozenset(
        {"finance_admin", "cashier", "billing", "billing_clerk", "billing_officer"}
    ),
    "hr": frozenset({"hr_admin", "hr", "hr_officer"}),
    "settings": frozenset({"hr_admin"}),
}


def require_destination(*destinations: str):
    """
    Build a dependency that admits only the roles a destination belongs to.

    Administrator roles always pass, so a facility that has narrowed a role can
    never lock itself out of a module it owns.

    @param destinations: Destination keys from ``DESTINATION_ROLES``
    @returns A FastAPI dependency returning the authenticated user
    @raises ValueError: When a key is not a known destination
    @raises HTTPException 403: When none of the caller's roles own the room
    """
    for destination in destinations:
        if destination not in DESTINATION_ROLES:
            raise ValueError(f"unknown destination: {destination}")

    async def destination_checker(
        current_user: CurrentUser = current_user_dependency,
    ) -> CurrentUser:
        if is_superuser(current_user.roles):
            return current_user

        allowed: set[str] = set()
        for destination in destinations:
            allowed |= DESTINATION_ROLES[destination]

        held = {normalise_role(role) for role in current_user.roles}
        if not (held & allowed):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "This part of Aifya belongs to another role. "
                    "Ask HR/Admin if you need access."
                ),
            )
        return current_user

    return destination_checker
