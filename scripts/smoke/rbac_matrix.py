"""Role-by-role API access matrix for the Aifya workspace.

The sidebar hides a tab a role does not own, but hiding is not a control. This
script mints one session per role and asks the API directly, so it reports what
a hand-typed URL would actually get.

It creates a staff row per role inside an existing facility, runs the matrix,
and deletes those rows again - it writes no clinical data and changes nothing
that already exists.

The role lists below are copied one-for-one from
``apps/web/src/lib/navigation.ts``, which is the sidebar's own answer to who
owns which room.

Usage
-----
    python scripts/smoke/rbac_matrix.py            # print the matrix
    python scripts/smoke/rbac_matrix.py --assert   # exit 1 when a role cannot
                                                   # open a tab the sidebar
                                                   # draws for it
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

import asyncpg
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services" / "api-gateway"))

from app.auth.internal_tokens import issue_access_token  # noqa: E402

DB = dict(
    host="localhost",
    port=5432,
    user="aifya_user",
    password="aifya_dev_password",
    database="AIFYA-MAIN",
)

DOCTORS = ("doctor", "clinician")
NURSES = ("nurse", "triage_nurse", "ward_nurse")
SPECIALISTS = ("specialist",)
DENTISTS = ("dentist",)
MIDWIVES = ("midwife",)
PHARMACISTS = ("pharmacist",)
LABORATORY = ("lab_tech", "pathologist")
RADIOLOGY = ("radiologist", "rad_tech")
FRONT_DESK = ("receptionist", "records", "medical_records")
HR_TEAM = ("hr_admin", "hr", "hr_officer")
ACCOUNTANTS = ("finance_admin", "cashier", "billing", "billing_clerk", "billing_officer")
STORES = ("store_keeper",)
RESEARCH = ("research_coordinator", "principal_investigator")
CLINICAL = DOCTORS + NURSES
TRIALS = CLINICAL + RESEARCH
KNOWLEDGE = HR_TEAM + DOCTORS + NURSES

#: Every destination the sidebar declares, and the roles it declares for it.
TAB_ROLES: dict[str, tuple[str, ...]] = {
    "patients": (*DOCTORS, *NURSES, *SPECIALISTS, *DENTISTS, *MIDWIVES,
                 *PHARMACISTS, *LABORATORY, *RADIOLOGY, *FRONT_DESK, *HR_TEAM,
                 *ACCOUNTANTS, *STORES, *RESEARCH),
    "registration": FRONT_DESK,
    "consultationRoom": NURSES,
    "clinical": CLINICAL,
    "opd": CLINICAL,
    "ipd": CLINICAL,
    "emergency": CLINICAL,
    "pharmacy": PHARMACISTS,
    "laboratory": LABORATORY,
    "radiology": RADIOLOGY,
    "theatre": SPECIALISTS,
    "dental": DENTISTS,
    "mch": MIDWIVES,
    "billing": ACCOUNTANTS,
    "pos": ACCOUNTANTS,
    "finance": ACCOUNTANTS,
    "insurance": ACCOUNTANTS,
    "inventory": ACCOUNTANTS + STORES,
    "appointments": HR_TEAM,
    "referrals": HR_TEAM,
    "hr": HR_TEAM,
    "payroll": HR_TEAM,
    "employees": HR_TEAM,
    "leave": HR_TEAM,
    "payrollReports": HR_TEAM,
    "statutory": HR_TEAM,
    "aifyaUsage": HR_TEAM,
    "reports": HR_TEAM,
    "analytics": HR_TEAM,
    "performance": HR_TEAM,
    "communications": HR_TEAM,
    "integrations": HR_TEAM,
    "trials": TRIALS,
    "knowledge": KNOWLEDGE,
    "settings": HR_TEAM,
}

#: The one request that decides whether a tab's own room opens.
TAB_PROBES: dict[str, tuple[str, str]] = {
    "patients": ("GET", "/api/v1/patients"),
    "registration": ("POST", "/api/v1/patients"),
    "consultationRoom": ("GET", "/api/v1/encounters/queue"),
    "clinical": ("GET", "/api/v1/encounters/worklist"),
    "opd": ("GET", "/api/v1/encounters/queue"),
    "ipd": ("GET", "/api/v1/ipd/summary"),
    "emergency": ("GET", "/api/v1/emergency/summary"),
    "pharmacy": ("GET", "/api/v1/pharmacy/queue"),
    "laboratory": ("GET", "/api/v1/laboratory/worklist"),
    "radiology": ("GET", "/api/v1/radiology/summary"),
    "theatre": ("GET", "/api/v1/theatre/summary"),
    "dental": ("GET", "/api/v1/dental/summary"),
    "mch": ("GET", "/api/v1/mch/summary"),
    "billing": ("GET", "/api/v1/billing/summary"),
    "pos": ("GET", "/api/v1/billing/summary"),
    "finance": ("GET", "/api/v1/finance/accounts"),
    "insurance": ("GET", "/api/v1/insurance/summary"),
    "inventory": ("GET", "/api/v1/inventory/summary"),
    "appointments": ("GET", "/api/v1/appointments/summary"),
    "referrals": ("GET", "/api/v1/referrals/summary"),
    "hr": ("GET", "/api/v1/hr/summary"),
    "payroll": ("GET", "/api/v1/payroll/paye-bands"),
    "employees": ("GET", "/api/v1/hr/staff"),
    "leave": ("GET", "/api/v1/hr/leave"),
    "payrollReports": ("GET", "/api/v1/payroll/reports/headcount"),
    "statutory": ("GET", "/api/v1/payroll/statutory-rates"),
    "aifyaUsage": ("GET", "/api/v1/aifya-usage/config"),
    "reports": ("GET", "/api/v1/reports/summary"),
    "analytics": ("GET", "/api/v1/analytics/dashboard"),
    "performance": ("GET", "/api/v1/performance/kpis"),
    "communications": ("GET", "/api/v1/communications/templates"),
    "integrations": ("GET", "/api/v1/fhir/metadata"),
    "trials": ("GET", "/api/v1/trials/summary"),
    "knowledge": ("GET", "/api/v1/knowledge/documents"),
    "settings": ("GET", "/api/v1/facility"),
}

ROLES = sorted({role for roles in TAB_ROLES.values() for role in roles})

#: A refused request is 401/403; anything else means the door opened, including
#: 422 (the room answered and rejected the empty body).
def is_open(status: int) -> bool:
    return status not in (0, 401, 403)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--facility-code", default="PLATFORM")
    ap.add_argument("--assert", dest="do_assert", action="store_true")
    args = ap.parse_args()

    conn = await asyncpg.connect(**DB)
    facility_id = await conn.fetchval(
        "select id from facilities where code = $1", args.facility_code
    )
    if facility_id is None:
        print(f"facility {args.facility_code} not found")
        await conn.close()
        return 2

    await conn.execute(
        "select set_config('app.current_facility_id', $1, false)", str(facility_id)
    )
    await conn.execute("delete from staff where email like 'smoke+%@aifya.test'")

    created: list[uuid.UUID] = []
    tokens: dict[str, str] = {}
    try:
        for role in ROLES:
            staff_id = uuid.uuid4()
            await conn.execute(
                """
                insert into staff (id, facility_id, keycloak_user_id,
                                   employee_number, first_name, last_name,
                                   role, email, is_active, is_deleted,
                                   created_at, updated_at)
                values ($1, $2, $3, $4, $5, $6, $7, $8, true, false, now(), now())
                """,
                staff_id,
                facility_id,
                uuid.uuid4(),
                f"SMOKE-{role}",
                "Smoke",
                role.replace("_", " ").title(),
                role,
                f"smoke+{role}@aifya.test",
            )
            created.append(staff_id)
            tokens[role] = issue_access_token(
                subject=staff_id,
                facility_id=facility_id,
                email=f"smoke+{role}@aifya.test",
                name=f"Smoke {role}",
                roles=[role],
            )

        lookup: dict[tuple[str, str], int] = {}
        async with httpx.AsyncClient(timeout=60.0) as client:
            for role, token in tokens.items():
                headers = {
                    "Authorization": f"Bearer {token}",
                    "X-Facility-ID": str(facility_id),
                }
                for tab, (method, path) in TAB_PROBES.items():
                    body = {} if method == "POST" else None
                    try:
                        response = await client.request(
                            method, args.base + path, headers=headers, json=body
                        )
                        lookup[(role, tab)] = response.status_code
                    except Exception:
                        lookup[(role, tab)] = 0
    finally:
        await conn.execute("delete from staff where email like 'smoke+%@aifya.test'")
        await conn.close()

    print(f"{'TAB':<18}" + "".join(f"{i:>6}" for i in range(len(ROLES))))
    print("-" * (18 + 6 * len(ROLES)))
    for tab in TAB_PROBES:
        row = "".join(
            f"{('.' if is_open(lookup.get((r, tab), 0)) else 'X'):>6}" for r in ROLES
        )
        print(f"{tab:<18}{row}")
    print("\n'.' = the API answered   'X' = the API refused (401/403)")
    print("roles: " + ", ".join(f"{i}:{r}" for i, r in enumerate(ROLES)))

    lockouts = [
        f"{role:22} cannot open {tab:18} (got {lookup.get((role, tab), 0)})"
        for role in ROLES
        for tab, roles in TAB_ROLES.items()
        if role in roles and not is_open(lookup.get((role, tab), 0))
    ]
    leaks = [
        f"{role:22} reaches {tab:18} ({lookup.get((role, tab))}) though the sidebar hides it"
        for role in ROLES
        for tab, roles in TAB_ROLES.items()
        if role not in roles and is_open(lookup.get((role, tab), 0))
    ]

    if lockouts:
        print("\nROLE CANNOT OPEN A TAB THE SIDEBAR DRAWS FOR IT:")
        for line in lockouts:
            print("  " + line)
    if leaks:
        print(f"\nROLE REACHES A TAB THE SIDEBAR HIDES ({len(leaks)}):")
        for line in leaks[:40]:
            print("  " + line)

    return 1 if (args.do_assert and lockouts) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))