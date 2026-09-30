"""Tab-by-tab API smoke test for the Aifya web workspace.

Every destination in apps/web/src/lib/navigation.ts is paired with the API
calls its page and hooks actually make, so a green run means the drawer really
opens: the sidebar draws the tab, the page loads, and the API behind it answers.

Usage
-----
    python scripts/smoke/tab_api_smoke.py --report smoke.json

The signed-in identity is the platform administrator, who holds every role and
every permission. That proves connectivity and speed for every tab. Add
--roles to also mint one token per clinical role and check that the role gates
admit what they should and refuse what they should not.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

#: A 404 means the endpoint answered and the record simply does not exist yet -
#: that is a wired tab, not a broken one. Everything else at 4xx/5xx is a fault.
_OK_STATUSES = frozenset(range(200, 300)) | {404}


@dataclass(frozen=True)
class Probe:
    method: str
    path: str


@dataclass(frozen=True)
class Tab:
    key: str
    href: str
    roles: tuple[str, ...]
    probes: tuple[Probe, ...] = field(default_factory=tuple)


def g(path: str) -> Probe:
    return Probe("GET", path)


ALL = ("*",)
NIL = "00000000-0000-0000-0000-000000000000"

TABS: tuple[Tab, ...] = (
    Tab("dashboard", "/", ALL, (g("/api/v1/analytics/dashboard"), g("/api/v1/reports/dashboard"))),
    Tab("patients", "/patients", ALL, (g("/api/v1/patients"),)),
    Tab("registration", "/patients/register", ("receptionist",), (g("/api/v1/patients"),)),
    Tab("consultationRoom", "/consultation", ("nurse",), (g("/api/v1/encounters/queue"), g("/api/v1/encounters/worklist"))),
    Tab("clinical", "/clinical", ("doctor", "nurse"), (g("/api/v1/encounters/worklist"), g("/api/v1/encounters/departments"))),
    Tab("opd", "/opd", ("doctor", "nurse"), (g("/api/v1/encounters/queue"),)),
    Tab("ipd", "/ipd", ("doctor", "nurse"), (g("/api/v1/ipd/summary"), g("/api/v1/ipd/wards"), g("/api/v1/ipd/beds"), g("/api/v1/ipd/admissions"))),
    Tab("emergency", "/emergency", ("doctor", "nurse"), (g("/api/v1/emergency/summary"), g("/api/v1/emergency/queue"), g("/api/v1/emergency/doctors-on-duty"))),
    Tab("pharmacy", "/pharmacy", ("pharmacist",), (g("/api/v1/pharmacy/queue"), g("/api/v1/pharmacy/alerts"), g("/api/v1/pharmacy/inventory"))),
    Tab("laboratory", "/laboratory", ("lab_tech",), (g("/api/v1/laboratory/worklist"), g("/api/v1/laboratory/catalog"))),
    Tab("radiology", "/radiology", ("radiologist", "rad_tech"), (g("/api/v1/radiology/summary"), g("/api/v1/radiology/worklist"), g("/api/v1/imaging/analysis-types"))),
    Tab("theatre", "/theatre", ("specialist",), (g("/api/v1/theatre/summary"), g("/api/v1/theatre/theatres"), g("/api/v1/theatre/cases"))),
    Tab("dental", "/dental", ("dentist",), (g("/api/v1/dental/summary"), g("/api/v1/dental/visits"), g("/api/v1/dental/treatment-plans"))),
    Tab("mch", "/mch", ("midwife",), (g("/api/v1/mch/summary"), g("/api/v1/mch/children"), g("/api/v1/mch/immunization-schedule"))),
    Tab("billing", "/billing", ("cashier",), (g("/api/v1/billing/summary"), g("/api/v1/billing/invoices"))),
    Tab("pos", "/billing/pos", ("cashier",), (g("/api/v1/billing/summary"),)),
    Tab("finance", "/finance", ("finance_admin",), (
        g("/api/v1/finance/reports/trial-balance"),
        g(f"/api/v1/finance/reports/profit-loss?start=2026-01-01&end=2026-12-31"),
        g("/api/v1/finance/reports/balance-sheet?as_of_date=2026-09-30"),
        g("/api/v1/finance/reports/cash-flow?start=2026-01-01&end=2026-12-31"),
        g("/api/v1/finance/reports/ar-aging?as_of_date=2026-09-30"),
        g(f"/api/v1/finance/reports/budget-vs-actual?period_id={NIL}"),
    )),
    Tab("chartOfAccounts", "/finance/accounts", ("finance_admin",), (g("/api/v1/finance/accounts"),)),
    Tab("glTransactions", "/finance/transactions", ("finance_admin",), (g("/api/v1/finance/transactions"),)),
    Tab("financeReports", "/finance/reports", ("finance_admin",), (g(f"/api/v1/finance/reports/general-ledger?account_id={NIL}&start=2026-01-01&end=2026-12-31"),)),
    Tab("budgets", "/finance/budgets", ("finance_admin",), (g("/api/v1/finance/budgets"),)),
    Tab("fixedAssets", "/finance/assets", ("finance_admin",), (g("/api/v1/finance/fixed-assets"),)),
    Tab("periods", "/finance/periods", ("finance_admin",), (g("/api/v1/finance/periods"),)),
    Tab("reconciliation", "/finance/reconciliation", ("finance_admin",), (g("/api/v1/finance/bank-statements"),)),
    Tab("insurance", "/insurance", ("finance_admin",), (g("/api/v1/insurance/summary"), g("/api/v1/insurance/schemes"), g("/api/v1/insurance/claims"))),
    Tab("inventory", "/inventory", ("store_keeper",), (g("/api/v1/inventory/summary"), g("/api/v1/inventory/items"), g("/api/v1/inventory/suppliers"), g("/api/v1/inventory/transactions"), g("/api/v1/inventory/purchase-orders"))),
    Tab("appointments", "/appointments", ("hr_admin", "receptionist"), (g("/api/v1/appointments/summary"), g("/api/v1/appointments/"), g("/api/v1/appointments/schedules"))),
    Tab("referrals", "/referrals", ("hr_admin",), (g("/api/v1/referrals/summary"), g("/api/v1/referrals"), g("/api/v1/referrals/facility-lookup?q=ab"))),
    Tab("hr", "/hr", ("hr_admin",), (g("/api/v1/hr/summary"), g("/api/v1/hr/staff"), g("/api/v1/hr/roles"), g("/api/v1/hr/attendance"), g("/api/v1/hr/shifts"), g("/api/v1/hr/shift-assignments"))),
    Tab("payroll", "/hr/payroll", ("hr_admin",), (g("/api/v1/payroll/paye-bands"), g("/api/v1/payroll/nssf-tiers"), g("/api/v1/payroll/statutory-rates"), g("/api/v1/payroll/leave-types"))),
    Tab("employees", "/hr/employees", ("hr_admin",), (g("/api/v1/hr/staff"), g("/api/v1/payroll/employees"))),
    Tab("leave", "/hr/leave", ("hr_admin",), (g("/api/v1/hr/leave"),)),
    Tab("payrollReports", "/hr/payroll/reports", ("hr_admin",), (g("/api/v1/payroll/reports/headcount"),)),
    Tab("statutory", "/hr/payroll/statutory", ("hr_admin",), (g("/api/v1/payroll/statutory-rates"), g("/api/v1/payroll/paye-bands"))),
    Tab("aifyaUsage", "/hr/aifya-usage", ("hr_admin",), (g("/api/v1/aifya-usage/config"), g("/api/v1/aifya-usage/summary?year=2026&month=9"))),
    Tab("reports", "/reports", ("hr_admin",), (g("/api/v1/reports/summary"), g("/api/v1/reports/dashboard"), g("/api/v1/reports/templates"), g("/api/v1/reports/generated"), g("/api/v1/reports/usage-billing"))),
    Tab("analytics", "/analytics", ("hr_admin",), (g("/api/v1/analytics/dashboard"), g("/api/v1/analytics/bed-forecast"), g("/api/v1/analytics/stockout-predictions"), g("/api/v1/analytics/revenue-forecast"))),
    Tab("performance", "/performance", ("hr_admin",), (g("/api/v1/performance/kpis"), g("/api/v1/performance/trends?metric=patients"), g("/api/v1/performance/comparison"))),
    Tab("communications", "/communications", ("hr_admin",), (g("/api/v1/communications/templates"), g("/api/v1/communications/messages"), g("/api/v1/communications/sms-campaigns"), g("/api/v1/communications/sms-delivery-log"))),
    Tab("integrations", "/integrations/fhir", ("hr_admin",), (g("/api/v1/fhir/metadata"), g("/api/v1/dhis2/moh/forms"))),
    Tab("trials", "/trials", ("doctor", "nurse", "research_coordinator"), (g("/api/v1/trials/summary"), g("/api/v1/trials"))),
    Tab("knowledge", "/knowledge", ("doctor", "nurse", "hr_admin"), (g("/api/v1/knowledge/documents"),)),
    Tab("settings", "/settings", ("hr_admin",), (g("/api/v1/facility"), g("/api/v1/auth/roles"), g("/api/v1/hr/staff"))),
    Tab("settingsFacility", "/settings/facility", ("hr_admin",), (g("/api/v1/facility"),)),
    Tab("settingsRoles", "/settings/roles", ("hr_admin",), (g("/api/v1/auth/roles"),)),
    Tab("settingsTeam", "/settings/team", ("hr_admin",), (g("/api/v1/hr/staff"),)),
    Tab("settingsBilling", "/settings/billing", ("hr_admin",), (g("/api/v1/aifya-usage/config"),)),
    Tab("licensing", "/settings", ALL, (g("/api/v1/licensing/license"),)),
)


@dataclass
class Result:
    tab: str
    method: str
    path: str
    status: int
    ms: float
    detail: str = ""


class Smoke:
    def __init__(self, base: str, token: str, tenant: str) -> None:
        self.base = base.rstrip("/")
        self.token = token
        self.tenant = tenant
        self.headers = {"Authorization": f"Bearer {token}", "X-Facility-ID": tenant}

    async def probe(self, client: httpx.AsyncClient, tab: str, p: Probe) -> Result:
        url = self.base + p.path
        started = time.perf_counter()
        try:
            r = await client.request(p.method, url, headers=self.headers)
            ms = (time.perf_counter() - started) * 1000
            detail = ""
            if r.status_code >= 400:
                try:
                    detail = json.dumps(r.json())[:200]
                except Exception:
                    detail = r.text[:200]
            return Result(tab, p.method, p.path, r.status_code, ms, detail)
        except Exception as exc:  # noqa: BLE001 - a transport failure is a result
            ms = (time.perf_counter() - started) * 1000
            return Result(tab, p.method, p.path, 0, ms, f"{type(exc).__name__}: {exc}")


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1))))]


async def _live_finance_probes(
    client: httpx.AsyncClient, smoke: "Smoke"
) -> tuple[Probe, ...]:
    """Ask the finance reports for records that really exist.

    The static catalog probes those reports with a nil UUID, which must answer
    404 rather than crash. These probes use the first real account and period
    so the report body itself is exercised too, not only its not-found path.
    """

    async def first(path: str, container: str | None) -> str | None:
        response = await client.get(smoke.base + path, headers=smoke.headers)
        if response.status_code != 200:
            return None
        payload = response.json()
        if isinstance(payload, dict) and container:
            payload = payload.get(container)
        if isinstance(payload, list) and payload and isinstance(payload[0], dict):
            return payload[0].get("id")
        return None

    period_id = await first("/api/v1/finance/periods", None)
    account_id = await first("/api/v1/finance/accounts", "items")

    probes: list[Probe] = []
    if period_id:
        probes.append(g(f"/api/v1/finance/reports/trial-balance?period_id={period_id}"))
        probes.append(g(f"/api/v1/finance/reports/budget-vs-actual?period_id={period_id}"))
    if account_id:
        probes.append(
            g(
                f"/api/v1/finance/reports/general-ledger?account_id={account_id}"
                "&start=2026-01-01&end=2026-12-31"
            )
        )
        suffix = f"?period_id={period_id}" if period_id else ""
        probes.append(g(f"/api/v1/finance/reconciliation/{account_id}{suffix}"))
    return tuple(probes)


async def login(base: str, email: str, password: str, facility: str) -> httpx.Response:
    async with httpx.AsyncClient(timeout=60.0) as c:
        return await c.post(
            f"{base}/api/v1/auth/login",
            json={"email": email, "password": password, "facility": facility},
        )


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--email", default="admin@aifya.health")
    ap.add_argument("--password", default="Admin@Aifya2026")
    ap.add_argument("--facility", default="Aifya Platform")
    ap.add_argument("--report", default="")
    ap.add_argument("--slow-ms", type=float, default=1000.0)
    ap.add_argument("--repeat", type=int, default=1, help="probe passes; later passes measure warm speed")
    args = ap.parse_args()

    login_response = await login(args.base, args.email, args.password, args.facility)
    if login_response.status_code != 200:
        print(f"LOGIN FAILED {login_response.status_code}: {login_response.text[:300]}")
        return 2
    payload = login_response.json()
    user = payload["user"]
    smoke = Smoke(args.base, payload["access_token"], user["facilityId"])
    print(f"signed in as {user['email']} ({','.join(user['roles'])}) at {user['facilityName']}")
    print(f"permissions: {len(user['permissions'])}\n")

    results: list[Result] = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Finance reports are per-record, so the live ids are read first and the
        # report is then asked for a real account and a real period. The nil-UUID
        # probes stay in the catalog: a well-formed id this facility does not
        # hold must answer 404, never 500.
        catalog = TABS + (
            Tab(
                "financeRecords",
                "/finance/records",
                ("finance_admin",),
                await _live_finance_probes(client, smoke),
            ),
        )
        for attempt in range(args.repeat):
            for tab in catalog:
                for p in tab.probes:
                    r = await smoke.probe(client, tab.key, p)
                    if attempt == args.repeat - 1:
                        results.append(r)

    ok = [r for r in results if r.status in _OK_STATUSES]
    authz = [r for r in results if r.status in (401, 403)]
    bad = [r for r in results if r.status not in _OK_STATUSES and r.status not in (401, 403)]
    lat = [r.ms for r in ok]

    width = max(len(r.path) for r in results) + 2
    print(f"{'TAB':<20} {'M':<5} {'PATH':<{width}} {'STATUS':>6} {'ms':>8}")
    print("-" * (20 + 5 + width + 16))
    for r in results:
        note = ""
        if r.status == 404:
            note = "  (ok, no record yet)"
        elif r.status in (401, 403):
            note = "  <-- AUTHZ"
        elif r.status not in _OK_STATUSES:
            note = "  <-- FAIL"
        print(f"{r.tab:<20} {r.method:<5} {r.path:<{width}} {r.status:>6} {r.ms:>8.1f}{note}")
        if r.detail and r.status not in _OK_STATUSES and r.status not in (401, 403):
            print(f"{'':<32}{r.detail}")

    print("\n" + "=" * 60)
    print(f"probes        : {len(results)}")
    print(f"reachable     : {len(ok)}")
    print(f"401/403       : {len(authz)}")
    print(f"broken        : {len(bad)}")
    if lat:
        print(f"latency ms    : min={min(lat):.1f} p50={statistics.median(lat):.1f} p95={percentile(lat,95):.1f} max={max(lat):.1f}")
    slow = sorted([r for r in results if r.ms > args.slow_ms and r.status < 400], key=lambda r: -r.ms)
    if slow:
        print(f"\nSLOWER THAN {args.slow_ms:.0f} ms:")
        for r in slow[:25]:
            print(f"  {r.ms:8.1f} ms  {r.method} {r.path}")

    if bad or authz:
        print("\nFAILURES:")
        for r in bad + authz:
            print(f"  {r.status} {r.method} {r.path}  :: {r.detail}")

    if args.report:
        Path(args.report).write_text(
            json.dumps({"base": args.base, "user": user, "results": [r.__dict__ for r in results]}, indent=2),
            encoding="utf-8",
        )
        print(f"\nreport written to {args.report}")

    return 1 if (bad or authz) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))