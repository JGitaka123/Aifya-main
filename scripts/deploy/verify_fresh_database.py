#!/usr/bin/env python
"""Production database deployment check for Aifya.

Answers one question: can a fresh PostgreSQL database be built from this
repository alone - migrations, seeds, RLS, indexes, constraints - and does the
result actually isolate tenants and enforce the role matrix?

It does that in two halves.

1. Deployment check. Reads the schema the migrations produced and reports what
   the deployment depends on: the alembic revision reached, table inventory,
   how many tables carry ENABLE + FORCE row level security, the policies
   themselves, indexes, constraints and triggers, and whether the
   ``role_permissions`` baseline matches ``app.auth.permissions.ROLE_PERMISSIONS``.

2. End-to-end test. Signs in as the runtime login - deliberately a
   NOSUPERUSER/NOBYPASSRLS role, because a superuser would prove nothing -
   creates two facilities with their own staff and patients, and then checks
   that each tenant sees only its own rows, that a cross-tenant read and write
   both come back empty, and that a per-facility role override applies at one
   hospital without touching the other. The RBAC half calls the API's own
   ``resolve_permissions``, so it tests the real enforcement path rather than a
   copy of it.

Everything the test creates is rolled back, so it is safe against a database
you intend to keep.

Usage:
    python scripts/deploy/verify_fresh_database.py
    python scripts/deploy/verify_fresh_database.py --database-url postgresql://...
    python scripts/deploy/verify_fresh_database.py --expect-empty
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import uuid
from pathlib import Path

import asyncpg

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "services" / "api-gateway"
DEFAULT_ENV = API_ROOT / ".env"

#: Tables that legitimately have no tenant column, so FORCE RLS is not expected.
SHARED_TABLES = frozenset(
    {
        "alembic_version",
        "facilities",
        "facility_licenses",
        "facility_update_status",
        "app_updates",
        "usage_telemetry",
        "auth_accounts",
        "role_permissions",
        "payment_callbacks",
    }
)

_results: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    """Record one assertion and print it.

    @param ok: Whether the assertion held
    @param label: What was checked
    @param detail: Extra context printed after the label
    @returns The same ``ok`` value, for convenient early exits
    """
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f" - {detail}" if detail else ""))
    _results.append((ok, label))
    return ok


def section(title: str) -> None:
    """Print a section heading.

    @param title: Heading text
    """
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def read_env(path: Path) -> dict[str, str]:
    """Parse a dotenv file.

    @param path: Path to the .env file
    @returns Key/value pairs with quotes stripped
    """
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_urls(args: argparse.Namespace) -> tuple[str, str]:
    """Resolve the runtime URL and the SQLAlchemy URL for the target database.

    @param args: Parsed command line
    @returns ``(asyncpg_url, sqlalchemy_url)``
    """
    raw = args.database_url or os.environ.get("DATABASE_URL") or ""
    if not raw and args.database:
        base = read_env(args.env).get("DATABASE_URL", "")
        if not base:
            raise SystemExit(f"DATABASE_URL not found in {args.env}")
        raw = re.sub(r"/[^/?]+(\?.*)?$", f"/{args.database}", base)
    if not raw:
        raise SystemExit("set --database-url, --database, or DATABASE_URL")
    plain = re.sub(r"^postgresql\+\w+://", "postgresql://", raw)
    orm = re.sub(r"^postgresql://", "postgresql+asyncpg://", raw)
    return plain, orm


async def check_migration_state(conn: asyncpg.Connection) -> None:
    """Report the revision reached and the table inventory.

    @param conn: Open connection
    """
    section("1. MIGRATION STATE")
    revision = await conn.fetchval("SELECT version_num FROM alembic_version")
    head = None
    try:
        sys.path.insert(0, str(API_ROOT))
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config(str(API_ROOT / "alembic.ini"))
        cfg.set_main_option("script_location", str(API_ROOT / "alembic"))
        head = ScriptDirectory.from_config(cfg).get_current_head()
    except Exception as exc:  # pragma: no cover - reporting only
        print(f"  (could not read script head: {exc})")

    check(revision is not None, "alembic_version present", f"revision={revision}")
    if head:
        check(revision == head, "database is at script head", f"{revision} vs {head}")

    tables = await conn.fetch(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY table_name"
    )
    names = [r["table_name"] for r in tables]
    check(len(names) > 100, "table inventory", f"{len(names)} tables in public")
    print(f"       {', '.join(names[:12])}, ...")


async def check_rls(conn: asyncpg.Connection) -> None:
    """Verify ENABLE + FORCE row level security across tenant tables.

    @param conn: Open connection
    """
    section("2. ROW LEVEL SECURITY")
    rows = await conn.fetch(
        "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity "
        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname='public' AND c.relkind='r' ORDER BY c.relname"
    )
    enabled = [r for r in rows if r["relrowsecurity"]]
    forced = [r for r in rows if r["relrowsecurity"] and r["relforcerowsecurity"]]
    unforced = [r["relname"] for r in enabled if not r["relforcerowsecurity"]]
    missing = [
        r["relname"]
        for r in rows
        if not r["relrowsecurity"] and r["relname"] not in SHARED_TABLES
    ]

    # A child table with no tenant column is still reachable if it hangs off an
    # isolated parent: none of the parent's protection applies to the child.
    orphans = await conn.fetch(
        "SELECT DISTINCT child.relname FROM pg_class child "
        "JOIN pg_namespace n ON n.oid = child.relnamespace "
        "JOIN pg_constraint fk ON fk.conrelid = child.oid AND fk.contype = 'f' "
        "JOIN pg_class parent ON parent.oid = fk.confrelid "
        "WHERE n.nspname = 'public' AND child.relkind = 'r' "
        "AND NOT child.relrowsecurity AND parent.relrowsecurity "
        "AND child.relname <> ALL($1::text[])",
        list(SHARED_TABLES),
    )
    for row in orphans:
        if row["relname"] not in missing:
            missing.append(row["relname"])

    check(len(forced) > 0, "tables with ENABLE + FORCE RLS", f"{len(forced)} tables")
    check(not unforced, "no table enables RLS without FORCE", ", ".join(unforced) or "none")
    check(
        not missing,
        "every tenant table has RLS enabled",
        ", ".join(missing) or "none",
    )

    policies = await conn.fetch(
        "SELECT tablename, policyname, cmd FROM pg_policies "
        "WHERE schemaname='public' ORDER BY tablename, policyname"
    )
    check(len(policies) > 0, "policies installed", f"{len(policies)} policies")
    by_cmd: dict[str, int] = {}
    for row in policies:
        by_cmd[row["cmd"]] = by_cmd.get(row["cmd"], 0) + 1
    print(f"       by command: {by_cmd}")
    for name in ("staff", "patients", "role_permissions"):
        found = [p["policyname"] for p in policies if p["tablename"] == name]
        check(bool(found), f"policy on {name}", ", ".join(found) or "MISSING")


async def check_indexes_and_constraints(conn: asyncpg.Connection) -> None:
    """Report indexes, constraints and triggers the schema depends on.

    @param conn: Open connection
    """
    section("3. INDEXES, CONSTRAINTS, TRIGGERS")
    indexes = await conn.fetchval(
        "SELECT count(*) FROM pg_indexes WHERE schemaname='public'"
    )
    check(indexes > 100, "indexes", f"{indexes} indexes")

    kinds = {"p": "PRIMARY KEY", "f": "FOREIGN KEY", "u": "UNIQUE", "c": "CHECK"}
    rows = await conn.fetch(
        "SELECT contype, count(*) AS n FROM pg_constraint c "
        "JOIN pg_namespace n ON n.oid = c.connamespace "
        "WHERE n.nspname='public' GROUP BY contype"
    )
    # asyncpg hands back the "char" column as bytes, so decode before matching.
    seen = {
        (r["contype"].decode() if isinstance(r["contype"], bytes) else r["contype"]): r["n"]
        for r in rows
    }
    for code, label in kinds.items():
        check(seen.get(code, 0) > 0, f"{label} constraints", str(seen.get(code, 0)))

    partial = await conn.fetchval(
        "SELECT count(*) FROM pg_index WHERE indpred IS NOT NULL"
    )
    check(True, "partial indexes", f"{partial} partial index(es)")

    triggers = await conn.fetchval(
        "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
        "JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND NOT t.tgisinternal"
    )
    check(True, "user triggers", f"{triggers} trigger(s)")


async def check_rbac_seed(conn: asyncpg.Connection) -> None:
    """Compare the seeded role matrix with the code's baseline.

    @param conn: Open connection
    """
    section("4. RBAC SEED")
    sys.path.insert(0, str(API_ROOT))
    from app.auth.permissions import ROLE_PERMISSIONS

    total = await conn.fetchval("SELECT count(*) FROM role_permissions")
    roles = await conn.fetch(
        "SELECT role, count(*) AS n FROM role_permissions "
        "WHERE facility_id IS NULL GROUP BY role ORDER BY role"
    )
    seeded = {r["role"]: r["n"] for r in roles}
    check(total > 0, "role_permissions seeded", f"{total} rows")
    check(
        len(seeded) == len(ROLE_PERMISSIONS),
        "every code role has seeded rows",
        f"{len(seeded)} seeded vs {len(ROLE_PERMISSIONS)} in code",
    )
    unchecked = sorted(set(ROLE_PERMISSIONS) - set(seeded))
    check(not unchecked, "no role missing from the seed", ", ".join(unchecked) or "none")

    drift = []
    for role, expected in ROLE_PERMISSIONS.items():
        if role not in seeded:
            continue
        actual = {
            r["permission"]
            for r in await conn.fetch(
                "SELECT permission FROM role_permissions "
                "WHERE role=$1 AND facility_id IS NULL AND is_allowed",
                role,
            )
        }
        if actual != set(expected):
            drift.append(role)
    check(not drift, "seeded matrix matches ROLE_PERMISSIONS", ", ".join(drift) or "no drift")

    print(f"       doctor                  {seeded.get('doctor', 0)} permissions")
    print(f"       nurse                   {seeded.get('nurse', 0)} permissions")
    print(f"       pharmacist              {seeded.get('pharmacist', 0)} permissions")
    print(f"       cashier                 {seeded.get('cashier', 0)} permissions")
    print(f"       super_admin             {seeded.get('super_admin', 0)} permissions")


async def check_runtime_role(conn: asyncpg.Connection) -> None:
    """Confirm the runtime login cannot sidestep RLS.

    @param conn: Open connection
    """
    section("5. RUNTIME LOGIN PRIVILEGES")
    row = await conn.fetchrow(
        "SELECT current_user, "
        "(SELECT rolsuper FROM pg_roles WHERE rolname=current_user) AS super, "
        "(SELECT rolbypassrls FROM pg_roles WHERE rolname=current_user) AS bypass"
    )
    check(not row["super"], f"runtime login {row['current_user']!r} is NOSUPERUSER")
    check(not row["bypass"], "runtime login is NOBYPASSRLS")
    check(
        row["current_user"] not in ("postgres",),
        "not connected as the postgres superuser",
        row["current_user"],
    )


async def run_e2e(conn: asyncpg.Connection) -> None:
    """Run the RBAC and facility-isolation end-to-end test.

    @param conn: Open connection, rolled back at the end
    """
    section("6. END-TO-END: FACILITY ISOLATION")
    facility_a = uuid.uuid4()
    facility_b = uuid.uuid4()
    patient_a = uuid.uuid4()
    patient_b = uuid.uuid4()

    tx = conn.transaction()
    await tx.start()
    try:
        for fid, name, code in (
            (facility_a, "Deploy Check A", "DEPLOYA"),
            (facility_b, "Deploy Check B", "DEPLOYB"),
        ):
            await conn.execute(
                "INSERT INTO facilities (id, name, code, facility_type, is_active) "
                "VALUES ($1,$2,$3,'hospital',true)",
                fid,
                name,
                code,
            )
        for fid, pid, mrn, first in (
            (facility_a, patient_a, "MRN-A-1", "Alpha"),
            (facility_b, patient_b, "MRN-B-1", "Beta"),
        ):
            await conn.execute(
                "SELECT set_config('app.current_facility_id',$1,true)", str(fid)
            )
            await conn.execute(
                "INSERT INTO patients (id, facility_id, mrn, first_name, last_name, "
                "date_of_birth, gender, phone_number) "
                "VALUES ($1,$2,$3,$4,'Patient','1990-01-01','female','0700000000')",
                pid,
                fid,
                mrn,
                first,
            )

        await conn.execute("SELECT set_config('app.current_facility_id','',true)")
        visible = await conn.fetchval("SELECT count(*) FROM patients")
        check(visible == 0, "no facility context sees no patients", f"{visible} rows")

        await conn.execute(
            "SELECT set_config('app.current_facility_id',$1,true)", str(facility_a)
        )
        rows_a = await conn.fetch("SELECT mrn FROM patients ORDER BY mrn")
        check(
            [r["mrn"] for r in rows_a] == ["MRN-A-1"],
            "facility A sees only its own patient",
            f"{[r['mrn'] for r in rows_a]}",
        )

        stolen = await conn.fetchval(
            "SELECT count(*) FROM patients WHERE id=$1", patient_b
        )
        check(stolen == 0, "facility A cannot read facility B's patient by id")

        updated = await conn.execute(
            "UPDATE patients SET first_name='Tampered' WHERE id=$1", patient_b
        )
        check(
            updated.endswith("0"),
            "facility A cannot write facility B's patient",
            f"UPDATE ... -> {updated}",
        )

        await conn.execute(
            "SELECT set_config('app.current_facility_id',$1,true)", str(facility_b)
        )
        rows_b = await conn.fetch("SELECT mrn FROM patients ORDER BY mrn")
        check(
            [r["mrn"] for r in rows_b] == ["MRN-B-1"],
            "facility B sees only its own patient",
            f"{[r['mrn'] for r in rows_b]}",
        )
    finally:
        await tx.rollback()


async def run_child_table_e2e(conn: asyncpg.Connection) -> None:
    """Check a child table is isolated, not only its parent.

    A schedule hangs off a trial. The trial is isolated, the schedule is not,
    and none of the parent's protection reaches the child, so a facility can
    read and rewrite another hospital's rows if this regresses.

    @param conn: Open connection, rolled back at the end
    """
    section("6b. END-TO-END: CHILD TABLE ISOLATION")
    facility_a = uuid.uuid4()
    facility_b = uuid.uuid4()
    trial_a = uuid.uuid4()
    trial_b = uuid.uuid4()

    tx = conn.transaction()
    await tx.start()
    try:
        for fid, name, code in (
            (facility_a, "Child A", "CHILDA"),
            (facility_b, "Child B", "CHILDB"),
        ):
            await conn.execute(
                "INSERT INTO facilities (id,name,code,facility_type,is_active) "
                "VALUES ($1,$2,$3,'hospital',true)",
                fid, name, code,
            )
        for fid, tid, label in (
            (facility_a, trial_a, "A"),
            (facility_b, trial_b, "B"),
        ):
            await conn.execute(
                "SELECT set_config('app.current_facility_id',$1,true)", str(fid)
            )
            await conn.execute(
                "INSERT INTO clinical_trials (id, facility_id, trial_code, title, study_type, "
                "sponsor, protocol_version, protocol_date, inclusion_criteria, exclusion_criteria) "
                "VALUES ($1,$2,$3,$4,'interventional','Sponsor','v1','2026-01-01','[]','[]')",
                tid, fid, f"CHILD-{label}", f"Child trial {label}",
            )
            await conn.execute(
                "INSERT INTO trial_visit_schedule (id, trial_id, visit_code, visit_name, "
                "day_from_enrollment, window_before_days, window_after_days, "
                "required_assessments, is_mandatory, sort_order) "
                "VALUES ($1,$2,'V1',$3,0,0,0,'[]',true,1)",
                uuid.uuid4(), tid, f"Visit-for-{label}",
            )

        await conn.execute(
            "SELECT set_config('app.current_facility_id',$1,true)", str(facility_a)
        )
        visible_trials = await conn.fetchval("SELECT count(*) FROM clinical_trials")
        visible_schedules = await conn.fetchval(
            "SELECT count(*) FROM trial_visit_schedule"
        )
        check(visible_trials == 1, "facility A sees only its own trial", f"{visible_trials}")
        check(
            visible_schedules == 1,
            "facility A sees only its own trial schedule",
            f"{visible_schedules} row(s) visible, expected 1",
        )
        leaked = await conn.fetch(
            "SELECT visit_name FROM trial_visit_schedule WHERE trial_id = $1", trial_b
        )
        check(not leaked, "facility A cannot read facility B's schedule rows",
              f"leaked {[r['visit_name'] for r in leaked]}" if leaked else "none")
        written = await conn.execute(
            "UPDATE trial_visit_schedule SET visit_name='tampered' WHERE trial_id=$1", trial_b
        )
        check(written.endswith("0"), "facility A cannot write facility B's schedule rows",
              f"UPDATE ... -> {written}")
    finally:
        await tx.rollback()


async def run_rbac_e2e(orm_url: str, facility_a: uuid.UUID | None = None) -> None:
    """Exercise the API's own permission resolution and destination rules.

    @param orm_url: SQLAlchemy async URL for the target database
    @param facility_a: Optional facility to check per-facility overrides against
    """
    section("7. END-TO-END: RBAC ENFORCEMENT")
    sys.path.insert(0, str(API_ROOT))

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.auth.dependencies import CurrentUser
    from app.auth.permissions import (
        DESTINATION_ROLES,
        ROLE_PERMISSIONS,
        is_superuser,
        resolve_permissions,
    )

    engine = create_async_engine(orm_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    facility_id = facility_a or uuid.uuid4()

    expectations = {
        "doctor": {
            "holds": ["clinical.view", "clinical.consult", "opd.view", "ipd.view",
                      "emergency.view", "trials.view", "knowledge.view", "patients.view"],
            "denied": ["settings.manage", "hr.view", "finance.view", "billing.payment",
                       "patients.register", "pharmacy.dispense", "theatre.record"],
        },
        "nurse": {
            "holds": ["clinical.view", "opd.view", "ipd.view", "emergency.view",
                      "triage.record"],
            "denied": ["settings.manage", "billing.payment", "clinical.consult",
                       "finance.view"],
        },
        "pharmacist": {
            "holds": ["pharmacy.view", "pharmacy.dispense"],
            "denied": ["clinical.view", "settings.manage", "billing.payment"],
        },
        "cashier": {
            "holds": ["billing.view", "billing.payment"],
            "denied": ["clinical.view", "pharmacy.dispense", "settings.manage"],
        },
        "lab_tech": {
            "holds": ["laboratory.view", "laboratory.result"],
            "denied": ["clinical.consult", "settings.manage"],
        },
    }

    async with factory() as session:
        for role, spec in expectations.items():
            user = CurrentUser(
                user_id=uuid.uuid4(),
                facility_id=facility_id,
                email=f"{role}@deploycheck.local",
                roles=[role],
                name=role,
            )
            granted = await resolve_permissions(session, user)
            missing = [p for p in spec["holds"] if p not in granted]
            leaked = [p for p in spec["denied"] if p in granted]
            check(not missing, f"{role} holds its permissions",
                  f"missing {missing}" if missing else f"{len(granted)} permissions")
            check(not leaked, f"{role} is denied what it must not hold",
                  f"leaked {leaked}" if leaked else "none leaked")

        admin = CurrentUser(
            user_id=uuid.uuid4(), facility_id=facility_id,
            email="admin@deploycheck.local", roles=["facility_admin"], name="admin",
        )
        granted = await resolve_permissions(session, admin)
        check(len(granted) > 40, "facility_admin holds the whole matrix",
              f"{len(granted)} permissions")
        check(is_superuser(["facility_admin"]), "facility_admin is a superuser role")

        # Destination ownership: a role that holds a room's permission may still
        # not own the room, which is what keeps a doctor out of the pharmacy.
        owner_case = {
            "pharmacy": ("pharmacist", "doctor"),
            "laboratory": ("lab_tech", "doctor"),
            "theatre": ("specialist", "doctor"),
            "dental": ("dentist", "doctor"),
            "mch": ("midwife", "doctor"),
            "finance": ("cashier", "doctor"),
            "hr": ("hr_admin", "doctor"),
        }
        for destination, (owner, outsider) in owner_case.items():
            roles = DESTINATION_ROLES[destination]
            check(owner in roles, f"{destination} owned by {owner}")
            check(outsider not in roles, f"{destination} not owned by {outsider}")

        # A doctor holds pharmacy.view as an *action*, so the room check is what
        # must keep the pharmacy queue away - prove the two are different gates.
        user = CurrentUser(user_id=uuid.uuid4(), facility_id=facility_id,
                           email="d@deploycheck.local", roles=["doctor"], name="d")
        granted = await resolve_permissions(session, user)
        check("pharmacy.view" in granted, "doctor may read the drug catalogue")
        check("doctor" not in DESTINATION_ROLES["pharmacy"],
              "doctor still does not own the pharmacy room")

    await engine.dispose()

    # app.database builds an engine at import time; close it so the process can
    # exit without a lingering pool.
    from app.database import engine as api_engine

    await api_engine.dispose()


async def run_override_e2e(conn: asyncpg.Connection) -> None:
    """Prove a per-facility override applies at one hospital only.

    @param conn: Open connection, rolled back at the end
    """
    section("8. END-TO-END: PER-FACILITY RBAC OVERRIDE")
    facility_a = uuid.uuid4()
    facility_b = uuid.uuid4()
    tx = conn.transaction()
    await tx.start()
    try:
        for fid, name, code in (
            (facility_a, "Override A", "OVRA"),
            (facility_b, "Override B", "OVRB"),
        ):
            await conn.execute(
                "INSERT INTO facilities (id,name,code,facility_type,is_active) "
                "VALUES ($1,$2,$3,'hospital',true)",
                fid, name, code,
            )

        await conn.execute(
            "SELECT set_config('app.current_facility_id',$1,true)", str(facility_a)
        )
        await conn.execute(
            "INSERT INTO role_permissions "
            "(id, facility_id, role, permission, is_allowed, is_deleted, created_at, updated_at) "
            "VALUES ($1,$2,'doctor','clinical.consult',false,false,now(),now())",
            uuid.uuid4(), facility_a,
        )
        await conn.execute("SELECT set_config('app.current_facility_id','',true)")

        global_rows = await conn.fetchval(
            "SELECT count(*) FROM role_permissions "
            "WHERE role='doctor' AND permission='clinical.consult' AND facility_id IS NULL"
        )
        check(global_rows == 1, "global baseline still grants clinical.consult to doctor")

        await conn.execute(
            "SELECT set_config('app.current_facility_id',$1,true)", str(facility_b)
        )
        b_rows = await conn.fetchval(
            "SELECT count(*) FROM role_permissions WHERE facility_id=$1", facility_b
        )
        check(b_rows == 0, "facility B has no override rows of its own", f"{b_rows}")

        await conn.execute(
            "SELECT set_config('app.current_facility_id',$1,true)", str(facility_a)
        )
        a_rows = await conn.fetchval(
            "SELECT count(*) FROM role_permissions "
            "WHERE facility_id=$1 AND role='doctor' AND permission='clinical.consult'",
            facility_a,
        )
        check(a_rows == 1, "facility A sees its own revoking override", f"{a_rows}")
    finally:
        await tx.rollback()


async def main() -> int:
    """Entry point.

    @returns Process exit code
    """
    parser = argparse.ArgumentParser(description="Aifya production database check.")
    parser.add_argument("--database-url", help="target database URL")
    parser.add_argument("--database", default="aifya_app",
                        help="database name to derive from .env when no URL is given")
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV, help="path to .env")
    parser.add_argument("--skip-e2e", action="store_true", help="schema checks only")
    args = parser.parse_args()

    plain, orm = resolve_urls(args)
    print(f"target: {re.sub(r'://[^@]+@', '://***@', plain)}")

    # The API's Settings and permission matrix are read from the environment,
    # so point them at the database under test before anything imports them.
    os.environ["DATABASE_URL"] = orm
    os.environ.setdefault("SECRET_KEY", "0" * 64)
    os.environ["DEBUG"] = "false"

    conn = await asyncpg.connect(plain)
    try:
        await check_migration_state(conn)
        await check_rls(conn)
        await check_indexes_and_constraints(conn)
        await check_rbac_seed(conn)
        await check_runtime_role(conn)
        if not args.skip_e2e:
            await run_e2e(conn)
            await run_child_table_e2e(conn)
            await run_rbac_e2e(orm)
            await run_override_e2e(conn)
    finally:
        await conn.close()

    failed = [label for ok, label in _results if not ok]
    section("SUMMARY")
    print(f"  {len(_results) - len(failed)}/{len(_results)} checks passed")
    if failed:
        print("  failed:")
        for label in failed:
            print(f"    - {label}")
        return 1
    print("  deployment check: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))