"""Check, over HTTP, which modules each role can actually reach.

This is the answer to "hiding the tab was not a control". It loads the real
application, signs in a synthetic user with one role at a time, and calls one
representative endpoint per module. A 403 means the role gate refused the call;
anything else means the request reached the route (404 and 422 included - the
point is that the door opened).

Run it from the service root, or from anywhere:

    python scripts/check_role_access.py

It needs the local database that ``.env`` points at, because the permission
checks read the ``role_permissions`` overrides. The exit code is the number of
spot-check failures, so it can gate a deployment.
"""

import asyncio
import logging
import os
import pathlib
import re
import sys
import uuid

SERVICE_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

for line in (SERVICE_ROOT / ".env").read_text(encoding="utf-8", errors="replace").splitlines():
    match = re.match(r"\s*DATABASE_URL\s*=\s*(.+?)\s*$", line)
    if match:
        os.environ["DATABASE_URL"] = match.group(1).strip().strip('"').strip("'")
        break
os.environ["DEBUG"] = "false"
os.environ["MPESA_CALLBACK_IP_ENFORCE"] = "false"

from app.auth import license_check  # noqa: E402
from app.schemas.licensing import TIER_ENTITLEMENTS  # noqa: E402


async def _no_redis():
    return None


async def _entitlements(facility_id, db):
    """Hand back an enterprise licence so the tier check never answers 403."""
    entitlements = TIER_ENTITLEMENTS["enterprise"]
    return {
        "tier": "enterprise",
        "enabled_modules": entitlements["enabled_modules"],
        "feature_flags": entitlements["feature_flags"],
        "max_users": entitlements["max_users"],
        "max_patients": entitlements["max_patients"],
        "is_valid": True,
        "in_grace_period": False,
    }


license_check._get_redis = _no_redis
license_check._get_entitlements = _entitlements

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.auth.dependencies import CurrentUser, get_current_user  # noqa: E402
from app.main import app  # noqa: E402

logging.disable(logging.WARNING)

_roles: list[str] = []


async def _user() -> CurrentUser:
    """Stand in for the signed-in employee, with whatever role is being probed."""
    return CurrentUser(
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        facility_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        email="probe@aifya.health",
        roles=list(_roles),
        name="Probe",
    )


app.dependency_overrides[get_current_user] = _user

#: One representative endpoint per module.
MODULES = [
    ("patients", "GET", "/api/v1/patients"),
    ("encounters", "GET", "/api/v1/encounters/departments"),
    ("ipd", "GET", "/api/v1/ipd/wards"),
    ("emergency", "GET", "/api/v1/emergency/queue"),
    ("pharmacy", "GET", "/api/v1/pharmacy/inventory"),
    ("laboratory", "GET", "/api/v1/laboratory/catalog"),
    ("radiology", "GET", "/api/v1/radiology/worklist"),
    ("theatre", "GET", "/api/v1/theatre/theatres"),
    ("dental", "GET", "/api/v1/dental/summary"),
    ("mch", "GET", "/api/v1/mch/summary"),
    ("billing", "GET", "/api/v1/billing/summary"),
    ("finance", "GET", "/api/v1/finance/accounts"),
    ("insurance", "GET", "/api/v1/insurance/summary"),
    ("inventory", "GET", "/api/v1/inventory/items"),
    ("appointments", "GET", "/api/v1/appointments/summary"),
    ("referrals", "GET", "/api/v1/referrals/summary"),
    ("hr", "GET", "/api/v1/hr/summary"),
    ("payroll", "GET", "/api/v1/payroll/departments"),
    ("reports", "GET", "/api/v1/reports/summary"),
    ("analytics", "GET", "/api/v1/analytics/dashboard"),
    ("communications", "GET", "/api/v1/communications/templates"),
    ("trials", "GET", "/api/v1/trials"),
    ("imaging", "GET", "/api/v1/imaging/analysis-types"),
    ("agents", "GET", "/api/v1/agents/types"),
    ("dhis2", "GET", "/api/v1/dhis2/moh/forms"),
    ("federated", "GET", "/api/v1/federated/surveillance"),
    ("performance", "GET", "/api/v1/performance/kpis"),
    ("fhir", "GET", "/api/v1/fhir/metadata"),
    ("knowledge", "GET", "/api/v1/knowledge/documents"),
    ("icd10", "GET", "/api/v1/icd10/search?q=malaria"),
    ("facility", "GET", "/api/v1/facility"),
    ("mpesa", "GET", "/api/v1/mpesa/status"),
    ("licensing", "GET", "/api/v1/licensing/license"),
    ("self-service clock-in", "POST", "/api/v1/hr/attendance/clock-in"),
    ("self-service leave", "POST", "/api/v1/payroll/leave-requests"),
]

ROLES = [
    "doctor",
    "clinician",
    "nurse",
    "triage_nurse",
    "ward_nurse",
    "midwife",
    "dentist",
    "specialist",
    "pharmacist",
    "lab_tech",
    "pathologist",
    "radiologist",
    "rad_tech",
    "receptionist",
    "records",
    "store_keeper",
    "finance_admin",
    "cashier",
    "billing",
    "hr",
    "hr_admin",
    "hr_officer",
    "research_coordinator",
    "principal_investigator",
    "staff",
    "admin",
    "facility_admin",
    "super_admin",
    "hospital_administrator",
]

#: ``(label, role, method, url, expected)``. ``expected=403`` means the call must
#: be refused; ``None`` means it must not be. These are the claims the gate is
#: built to make, stated as assertions so a regression fails loudly.
SPOT = [
    ("nurse cannot read the staff file", "nurse", "GET", "/api/v1/hr/staff", 403),
    ("nurse cannot read payroll", "nurse", "GET", "/api/v1/payroll/employees", 403),
    ("nurse cannot read the ledger", "nurse", "GET", "/api/v1/finance/accounts", 403),
    ("receptionist cannot read payroll", "receptionist", "GET", "/api/v1/payroll/employees", 403),
    ("pharmacist cannot read the ledger", "pharmacist", "GET", "/api/v1/finance/accounts", 403),
    ("doctor cannot read payroll", "doctor", "GET", "/api/v1/payroll/employees", 403),
    ("doctor cannot read the staff file", "doctor", "GET", "/api/v1/hr/staff", 403),
    ("midwife cannot read the ledger", "midwife", "GET", "/api/v1/finance/accounts", 403),
    ("lab tech cannot read the ledger", "lab_tech", "GET", "/api/v1/finance/accounts", 403),
    ("store keeper cannot read the staff file", "store_keeper", "GET", "/api/v1/hr/staff", 403),
    ("staff cannot read the ledger", "staff", "GET", "/api/v1/finance/accounts", 403),
    ("hr may read the staff file", "hr", "GET", "/api/v1/hr/staff", None),
    ("hr_officer may read payroll", "hr_officer", "GET", "/api/v1/payroll/employees", None),
    ("hr may add an employee", "hr", "POST", "/api/v1/payroll/employees", None),
    ("hr_officer may add an employee", "hr_officer", "POST", "/api/v1/payroll/employees", None),
    ("hr may create a department", "hr", "POST", "/api/v1/payroll/departments", None),
    ("hr may add a leave type", "hr", "POST", "/api/v1/payroll/leave-types", None),
    ("a nurse still may not add an employee", "nurse", "POST", "/api/v1/payroll/employees", 403),
    ("accountant may read the ledger", "finance_admin", "GET", "/api/v1/finance/accounts", None),
    ("super_admin may read the staff file", "super_admin", "GET", "/api/v1/hr/staff", None),
    ("super_admin may read payroll", "super_admin", "GET", "/api/v1/payroll/employees", None),
    ("super_admin may read the ledger", "super_admin", "GET", "/api/v1/finance/accounts", None),
    ("hospital_administrator may read payroll", "hospital_administrator", "GET", "/api/v1/payroll/employees", None),
    ("facility_admin may not issue platform licences", "facility_admin", "POST", "/api/v1/licensing/admin/licenses", 403),
    ("admin may not issue platform licences", "admin", "POST", "/api/v1/licensing/admin/licenses", 403),
    ("super_admin may issue platform licences", "super_admin", "POST", "/api/v1/licensing/admin/licenses", None),
    ("a nurse may still clock in", "nurse", "POST", "/api/v1/hr/attendance/clock-in", None),
    ("a nurse may still file their own leave", "nurse", "POST", "/api/v1/payroll/leave-requests", None),
    ("facility_admin may not approve other facilities", "facility_admin", "GET", "/api/v1/onboarding/pending", 403),
    ("admin may approve facilities", "admin", "GET", "/api/v1/onboarding/pending", None),
    ("super_admin may approve facilities", "super_admin", "GET", "/api/v1/onboarding/pending", None),
]


async def main() -> int:
    """
    Run the module sweep and the spot checks.

    @returns Number of spot-check failures, for the process exit code
    """
    transport = ASGITransport(app=app)
    admins = {"admin", "facility_admin", "super_admin", "hospital_administrator"}
    matrix: dict[str, dict[str, int]] = {}

    async with AsyncClient(transport=transport, base_url="http://probe") as client:
        for role in ROLES:
            _roles[:] = [role]
            row: dict[str, int] = {}
            for name, method, url in MODULES:
                request = client.get(url) if method == "GET" else client.post(url, json={})
                row[name] = (await request).status_code
            matrix[role] = row

        print("=== Reached past the role gate, per module (non-admin roles) ===")
        for name, _, _ in MODULES:
            allowed = [r for r in ROLES if r not in admins and matrix[r][name] != 403]
            refused_admins = [r for r in admins if matrix[r][name] == 403]
            flag = f"   !! ADMIN REFUSED: {refused_admins}" if refused_admins else ""
            print(f"{name:24} {', '.join(allowed) or '(nobody but admins)'}{flag}")

        print("\n=== Spot checks ===")
        failures = 0
        for label, role, method, url, expected in SPOT:
            _roles[:] = [role]
            request = client.get(url) if method == "GET" else client.post(url, json={})
            status = (await request).status_code
            passed = status == 403 if expected == 403 else status != 403
            failures += 0 if passed else 1
            print(f"  [{'PASS' if passed else 'FAIL'}] {label}  ({role} -> {status})")

    print(f"\nspot-check failures: {failures}")
    return failures


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
