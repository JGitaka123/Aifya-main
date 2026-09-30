#!/usr/bin/env python
"""Make a legacy role/module RBAC real inside Aifya.

A hand-written RBAC often arrives as ``roles``/``modules``/``role_modules``
tables holding display names such as ``Doctor`` and ``Consultation Room``.
Aifya reads none of that. Its access model is three things instead:

1. ``staff.role`` - one snake_case role code per person, e.g. ``doctor``.
2. ``role_permissions`` - one row per role + permission + facility, holding the
   grant or the denial. ``facility_id IS NULL`` is the platform baseline every
   facility inherits (migration 029 seeds it from
   ``app.auth.permissions.ROLE_PERMISSIONS``).
3. ``staff.permissions`` - a JSONB escape hatch for one person.

So this script does not create tables. It translates: display-name role codes
on ``staff.role`` are rewritten to the codes the API actually matches on, and
the shipped baseline is verified against the code matrix. Destinations are
never granted by module name - a tab is drawn when the role owns the
destination *and* holds the tab's permission, exactly as
``apps/web/src/lib/navigation.ts`` and ``app/auth/permissions.py`` decide it.

Every statement is idempotent and goes through row-level security, so each
facility is visited with its own ``app.current_facility_id``. The default mode
is a dry run; nothing is written without ``--apply``.

Usage:
    python scripts/rbac/align_legacy_rbac.py            # report only
    python scripts/rbac/align_legacy_rbac.py --apply    # write the changes
    python scripts/rbac/align_legacy_rbac.py --env path/to/.env
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

import asyncpg

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = REPO_ROOT / "services" / "api-gateway" / ".env"


#: Legacy display names to the role code the API matches on. The right-hand
#: values are the keys of ``app.auth.permissions.ROLE_PERMISSIONS``; anything
#: not listed here is left alone and reported instead of guessed at.
LEGACY_ROLE_MAP: dict[str, str] = {
    "human resource": "hr_admin",
    "hr reception": "receptionist",
    "nurse": "nurse",
    "doctor": "doctor",
    "pharmacist": "pharmacist",
    "lab technician": "lab_tech",
    "radiologist": "radiologist",
    "theatre specialist": "specialist",
    "dental specialist": "dentist",
    "maternal doctor": "midwife",
    "accountant": "finance_admin",
}

#: Roles the API recognises, mirroring ``ROLE_PERMISSIONS`` plus the
#: administrator roles that bypass the matrix entirely.
KNOWN_ROLES: frozenset[str] = frozenset(
    {
        "super_admin",
        "admin",
        "facility_admin",
        "hospital_administrator",
        "receptionist",
        "records",
        "medical_records",
        "nurse",
        "triage_nurse",
        "ward_nurse",
        "midwife",
        "doctor",
        "clinician",
        "specialist",
        "dentist",
        "lab_tech",
        "pathologist",
        "rad_tech",
        "radiologist",
        "pharmacist",
        "cashier",
        "billing",
        "billing_clerk",
        "billing_officer",
        "finance_admin",
        "hr",
        "hr_admin",
        "hr_officer",
        "store_keeper",
        "research_coordinator",
        "principal_investigator",
        "staff",
    }
)

#: Destinations each role owns, mirroring ``DESTINATION_ROLES`` in
#: ``app/auth/permissions.py``. Reported so an operator can see what a role
#: actually unlocks, not as something this script writes.
DESTINATION_ROLES: dict[str, tuple[str, ...]] = {
    "consultation": ("nurse", "triage_nurse", "ward_nurse"),
    "clinical": ("doctor", "clinician", "nurse", "triage_nurse", "ward_nurse"),
    "pharmacy": ("pharmacist",),
    "laboratory": ("lab_tech", "pathologist"),
    "radiology": ("radiologist", "rad_tech"),
    "theatre": ("specialist",),
    "dental": ("dentist",),
    "mch": ("midwife",),
    "trials": (
        "doctor",
        "clinician",
        "nurse",
        "triage_nurse",
        "ward_nurse",
        "research_coordinator",
        "principal_investigator",
    ),
    "finance": (
        "finance_admin",
        "cashier",
        "billing",
        "billing_clerk",
        "billing_officer",
    ),
    "hr": ("hr_admin", "hr", "hr_officer"),
    "settings": ("hr_admin", "hr", "hr_officer"),
}


def read_env(path: Path) -> dict[str, str]:
    """Parse a dotenv file into a mapping.

    @param path: Path to the .env file
    @returns Key/value pairs, quotes stripped
    """
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def database_url(env_file: Path) -> str:
    """Resolve a plain-postgres URL for asyncpg.

    @param env_file: Path to the API's .env
    @returns A ``postgresql://`` DSN
    """
    raw = os.environ.get("DATABASE_URL") or read_env(env_file).get("DATABASE_URL", "")
    if not raw:
        raise SystemExit(f"DATABASE_URL not set in the environment or {env_file}")
    return re.sub(r"^postgresql\+\w+://", "postgresql://", raw)


async def use_facility(conn: "asyncpg.Connection", facility_id: str) -> None:
    """Point the session at one facility so RLS shows that tenant's rows.

    @param conn: Open connection
    @param facility_id: Facility UUID to scope the session to
    """
    await conn.execute(
        "SELECT set_config('app.current_facility_id', $1, false)", str(facility_id)
    )


async def find_legacy_roles(conn: "asyncpg.Connection", facility_id: str) -> list:
    """List staff whose role is a legacy display name rather than a role code.

    @param conn: Open connection
    @param facility_id: Facility being inspected
    @returns Rows of id, name, email and current role that need rewriting
    """
    await use_facility(conn, facility_id)
    rows = await conn.fetch(
        "SELECT id, first_name, last_name, email, role FROM staff "
        "WHERE is_deleted = false ORDER BY last_name, first_name"
    )
    stale = []
    for row in rows:
        current = (row["role"] or "").strip()
        if current in KNOWN_ROLES:
            continue
        if current.lower() in LEGACY_ROLE_MAP:
            stale.append(row)
    return stale


async def rewrite_roles(conn: "asyncpg.Connection", rows: list, apply: bool) -> int:
    """Rewrite legacy display-name roles to the codes the API matches on.

    @param conn: Open connection, already scoped to the right facility
    @param rows: Rows returned by find_legacy_roles
    @param apply: When False the change is reported but not written
    @returns How many rows were (or would be) changed
    """
    changed = 0
    for row in rows:
        target = LEGACY_ROLE_MAP[(row["role"] or "").strip().lower()]
        print(f"    {row['first_name']} {row['last_name']}: {row['role']!r} -> {target!r}")
        if apply:
            await conn.execute(
                "UPDATE staff SET role = $1, updated_at = now() WHERE id = $2",
                target,
                row["id"],
            )
        changed += 1
    return changed


async def report_facility(conn: "asyncpg.Connection", facility) -> None:
    """Print the roles and destination rooms a facility's staff resolve to.

    @param conn: Open connection
    @param facility: Row of id and name
    """
    await use_facility(conn, facility["id"])
    rows = await conn.fetch(
        "SELECT role, count(*) AS people FROM staff "
        "WHERE is_deleted = false GROUP BY role ORDER BY role"
    )
    print(f"\n  {facility['name']}")
    if not rows:
        print("    (no staff records)")
        return
    held = {row["role"] for row in rows}
    for row in rows:
        owned = sorted(
            destination
            for destination, roles in DESTINATION_ROLES.items()
            if row["role"] in roles
        )
        print(
            f"    {row['role']:22s} {row['people']} person(s)"
            f"  rooms={', '.join(owned) if owned else '-'}"
        )
    orphaned = sorted(
        destination
        for destination, roles in DESTINATION_ROLES.items()
        if not (held & set(roles))
    )
    if orphaned:
        print(f"    rooms with no owner here: {', '.join(orphaned)}")


async def audit_baseline(conn: "asyncpg.Connection") -> None:
    """Compare the global ``role_permissions`` baseline against this script.

    @param conn: Open connection
    """
    total = await conn.fetchval("SELECT count(*) FROM role_permissions")
    rows = await conn.fetch(
        "SELECT role, count(*) AS n FROM role_permissions "
        "WHERE facility_id IS NULL GROUP BY role ORDER BY role"
    )
    print(f"  baseline rows: {total}")
    print(f"  roles covered: {len(rows)}")
    missing = sorted(KNOWN_ROLES - {row["role"] for row in rows})
    if missing:
        print(f"  roles with NO baseline: {', '.join(missing)}")
    else:
        print("  every known role has a baseline")


async def main() -> int:
    """Entry point.

    @returns Process exit code
    """
    parser = argparse.ArgumentParser(description="Align a legacy RBAC with Aifya.")
    parser.add_argument("--apply", action="store_true", help="write the changes")
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV, help="path to .env")
    args = parser.parse_args()

    conn = await asyncpg.connect(database_url(args.env))
    try:
        print("== role_permissions baseline ==")
        await audit_baseline(conn)

        facilities = await conn.fetch("SELECT id, name FROM facilities ORDER BY name")
        print("\n== staff roles per facility ==")
        for facility in facilities:
            await report_facility(conn, facility)

        print("\n== legacy display-name roles ==")
        total = 0
        for facility in facilities:
            stale = await find_legacy_roles(conn, facility["id"])
            if not stale:
                continue
            print(f"\n  {facility['name']}")
            total += await rewrite_roles(conn, stale, args.apply)

        if total == 0:
            print("  none - every staff record already carries an Aifya role code")
        elif args.apply:
            print(f"\nrewrote {total} staff record(s)")
        else:
            print(f"\n{total} staff record(s) would change - re-run with --apply")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))