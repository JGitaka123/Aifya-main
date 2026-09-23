"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import {
  FileText,
  Download,
  Printer,
  Building2,
  TrendingUp,
  Users as UsersIcon,
  CalendarCheck,
} from "lucide-react";
import {
  useP9,
  usePAYESchedule,
  useNSSFSchedule,
  useSHIFSchedule,
  useHeadcountReport,
  useLeaveUtilisation,
  useCostTrend,
  useTurnover,
} from "@/hooks/usePayroll";
import { PageHeader } from "@/components/ui/PageHeader";
import { TabGroup } from "@/components/ui/TabGroup";
import { EmployeeSelect } from "@/components/payroll/EmployeeSelect";
import { formatKES } from "@/lib/utils";

const MONTHS_EN = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

type ReportTab =
  | "p9"
  | "paye"
  | "nssf"
  | "shif"
  | "headcount"
  | "leave"
  | "trend"
  | "turnover";

/**
 * Payroll reports hub — P9, PAYE, NSSF, SHIF, headcount, leave, trends, turnover.
 *
 * @returns Reports hub page
 */
export default function PayrollReportsPage() {
  const t = useTranslations("payroll");

  const [tab, setTab] = useState<ReportTab>("p9");

  const tabs: { key: ReportTab; label: string }[] = [
    { key: "p9", label: t("p9") },
    { key: "paye", label: t("payeSchedule") },
    { key: "nssf", label: t("nssfSchedule") },
    { key: "shif", label: t("shifSchedule") },
    { key: "headcount", label: t("headcount") },
    { key: "leave", label: t("leaveUtilisation") },
    { key: "trend", label: t("costTrend") },
    { key: "turnover", label: t("turnover") },
  ];

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <PageHeader
        icon={FileText}
        title={t("reportsTitle")}
        subtitle={t("reportsSubtitle")}
        breadcrumbs={[
          { label: t("hrTitle"), href: "/hr" },
          { label: t("payroll"), href: "/hr/payroll" },
          { label: t("reports") },
        ]}
      />

      <TabGroup
        tabs={tabs}
        activeTab={tab}
        onTabChange={(k) => setTab(k as ReportTab)}
        variant="pills"
      />

      {tab === "p9" && <P9Report />}
      {tab === "paye" && <PAYEScheduleReport />}
      {tab === "nssf" && <NSSFScheduleReport />}
      {tab === "shif" && <SHIFScheduleReport />}
      {tab === "headcount" && <HeadcountSection />}
      {tab === "leave" && <LeaveUtilisationSection />}
      {tab === "trend" && <CostTrendSection />}
      {tab === "turnover" && <TurnoverSection />}
    </div>
  );
}

function P9Report() {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");
  const now = new Date();
  const [employeeId, setEmployeeId] = useState("");
  const [employeeName, setEmployeeName] = useState("");
  const [year, setYear] = useState(now.getFullYear());

  const { data, isLoading } = useP9(employeeId || undefined, year);

  const csvHref = useMemo(() => {
    if (!data) return null;
    const header = [
      "Month",
      "Basic Salary",
      "Benefits",
      "Gross Pay",
      "Retirement Contribution",
      "Affordable Housing Levy",
      "SHIF",
      "Taxable Pay",
      "PAYE",
      "Personal Relief",
      "Insurance Relief",
      "PAYE Payable",
    ];
    const rows = data.rows.map((r) => [
      MONTHS_EN[r.month - 1],
      r.basic_salary,
      r.benefits,
      r.gross_pay,
      r.defined_contribution_retirement,
      r.affordable_housing_levy,
      r.shif_contribution,
      r.taxable_pay,
      r.paye,
      r.personal_relief,
      r.insurance_relief,
      r.paye_payable,
    ]);
    const csv = [header, ...rows].map((r) => r.join(",")).join("\n");
    return `data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`;
  }, [data]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-72 flex-1">
          <label className="mb-1 block text-xs text-muted-foreground">
            {t("employee")}
          </label>
          <EmployeeSelect
            value={employeeId}
            onChange={(id, name) => {
              setEmployeeId(id);
              setEmployeeName(name);
            }}
          />
        </div>
        <label className="block">
          <span className="mb-1 block text-xs text-muted-foreground">
            {t("year")}
          </span>
          <input
            type="number"
            value={year}
            min={2020}
            max={now.getFullYear()}
            onChange={(e) => setYear(Number(e.target.value))}
            className="w-28 rounded-lg border border-border bg-card px-3 py-2 text-sm"
          />
        </label>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => window.print()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted/50"
          >
            <Printer className="h-4 w-4" />
            {t("print")}
          </button>
          <a
            href={csvHref ?? "#"}
            download={`p9-${employeeName || "employee"}-${year}.csv`}
            aria-disabled={!data}
            className={`inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted/50 ${!data ? "pointer-events-none opacity-50" : ""}`}
          >
            <Download className="h-4 w-4" />
            {t("downloadCsv")}
          </a>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        {!employeeId ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("selectEmployeeForP9")}
          </div>
        ) : isLoading ? (
          <div className="p-8 text-center text-muted-foreground">
            {tc("loading")}
          </div>
        ) : !data ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("noData")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <div className="border-b border-border p-4">
              <p className="text-sm font-semibold text-foreground">
                {data.employee_name} • {t("kraPin")}: {data.kra_pin} •{" "}
                {data.year}
              </p>
            </div>
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">{t("month")}</th>
                  <th className="px-3 py-2 text-right">{t("basicSalary")}</th>
                  <th className="px-3 py-2 text-right">{t("benefits")}</th>
                  <th className="px-3 py-2 text-right">{t("grossPay")}</th>
                  <th className="px-3 py-2 text-right">{t("nssf")}</th>
                  <th className="px-3 py-2 text-right">{t("hl")}</th>
                  <th className="px-3 py-2 text-right">{t("shif")}</th>
                  <th className="px-3 py-2 text-right">{t("taxablePay")}</th>
                  <th className="px-3 py-2 text-right">{t("paye")}</th>
                  <th className="px-3 py-2 text-right">
                    {t("personalRelief")}
                  </th>
                  <th className="px-3 py-2 text-right">
                    {t("insuranceRelief")}
                  </th>
                  <th className="px-3 py-2 text-right">{t("payePayable")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.rows.map((r) => (
                  <tr key={r.month} className="hover:bg-muted/30">
                    <td className="px-3 py-2 font-medium">
                      {MONTHS_EN[r.month - 1]}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatKES(r.basic_salary * 100)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatKES(r.benefits * 100)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatKES(r.gross_pay * 100)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatKES(r.defined_contribution_retirement * 100)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatKES(r.affordable_housing_levy * 100)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatKES(r.shif_contribution * 100)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatKES(r.taxable_pay * 100)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatKES(r.paye * 100)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatKES(r.personal_relief * 100)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {formatKES(r.insurance_relief * 100)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums font-semibold">
                      {formatKES(r.paye_payable * 100)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-border bg-muted/20 text-sm font-semibold">
                <tr>
                  <td className="px-3 py-2">{t("total")}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatKES(data.totals.basic_salary * 100)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatKES(data.totals.benefits * 100)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatKES(data.totals.gross_pay * 100)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatKES(
                      data.totals.defined_contribution_retirement * 100,
                    )}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatKES(data.totals.affordable_housing_levy * 100)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatKES(data.totals.shif_contribution * 100)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatKES(data.totals.taxable_pay * 100)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatKES(data.totals.paye * 100)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatKES(data.totals.personal_relief * 100)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatKES(data.totals.insurance_relief * 100)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatKES(data.totals.paye_payable * 100)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function MonthYearPicker({
  month,
  year,
  onChange,
}: {
  month: number;
  year: number;
  onChange: (m: number, y: number) => void;
}) {
  const t = useTranslations("payroll");
  return (
    <div className="flex flex-wrap gap-3">
      <label>
        <span className="mb-1 block text-xs text-muted-foreground">
          {t("month")}
        </span>
        <select
          value={month}
          onChange={(e) => onChange(Number(e.target.value), year)}
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
        >
          {MONTHS_EN.map((name, i) => (
            <option key={name} value={i + 1}>
              {name}
            </option>
          ))}
        </select>
      </label>
      <label>
        <span className="mb-1 block text-xs text-muted-foreground">
          {t("year")}
        </span>
        <input
          type="number"
          value={year}
          onChange={(e) => onChange(month, Number(e.target.value))}
          className="w-28 rounded-lg border border-border bg-card px-3 py-2 text-sm"
        />
      </label>
    </div>
  );
}

function PAYEScheduleReport() {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());

  const { data, isLoading } = usePAYESchedule(month, year);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <MonthYearPicker
          month={month}
          year={year}
          onChange={(m, y) => {
            setMonth(m);
            setYear(y);
          }}
        />
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted/50"
          onClick={() => window.print()}
        >
          <Download className="h-4 w-4" />
          {t("exportP10")}
        </button>
      </div>

      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">
            {tc("loading")}
          </div>
        ) : !data ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("noData")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("employee")}</th>
                  <th className="px-4 py-3">{t("kraPin")}</th>
                  <th className="px-4 py-3 text-right">{t("taxablePay")}</th>
                  <th className="px-4 py-3 text-right">{t("paye")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(data.rows ?? []).map((row) => (
                  <tr key={row.employee_id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium">
                      {row.employee_name}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {row.kra_pin}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatKES(row.taxable_pay * 100)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatKES(row.paye * 100)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-border bg-muted/20 text-sm font-semibold">
                <tr>
                  <td className="px-4 py-3" colSpan={2}>
                    {t("total")}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatKES(data.total_taxable * 100)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatKES(data.total_paye * 100)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function NSSFScheduleReport() {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());

  const { data, isLoading } = useNSSFSchedule(month, year);

  return (
    <div className="space-y-4">
      <MonthYearPicker
        month={month}
        year={year}
        onChange={(m, y) => {
          setMonth(m);
          setYear(y);
        }}
      />
      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">
            {tc("loading")}
          </div>
        ) : !data ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("noData")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("employee")}</th>
                  <th className="px-4 py-3">{t("nssfNumber")}</th>
                  <th className="px-4 py-3 text-right">
                    {t("pensionablePay")}
                  </th>
                  <th className="px-4 py-3 text-right">
                    {t("employeeContribution")}
                  </th>
                  <th className="px-4 py-3 text-right">
                    {t("employerContribution")}
                  </th>
                  <th className="px-4 py-3 text-right">{t("total")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(data.rows ?? []).map((r) => (
                  <tr key={r.employee_id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium">
                      {r.employee_name}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {r.nssf_number}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatKES(r.pensionable_pay * 100)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatKES(r.employee_contribution * 100)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatKES(r.employer_contribution * 100)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-semibold">
                      {formatKES(r.total * 100)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-border bg-muted/20 text-sm font-semibold">
                <tr>
                  <td className="px-4 py-3" colSpan={3}>
                    {t("total")}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatKES(data.total_employee * 100)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatKES(data.total_employer * 100)}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatKES(data.total * 100)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function SHIFScheduleReport() {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");
  const now = new Date();
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [year, setYear] = useState(now.getFullYear());

  const { data, isLoading } = useSHIFSchedule(month, year);

  return (
    <div className="space-y-4">
      <MonthYearPicker
        month={month}
        year={year}
        onChange={(m, y) => {
          setMonth(m);
          setYear(y);
        }}
      />
      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">
            {tc("loading")}
          </div>
        ) : !data ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("noData")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("employee")}</th>
                  <th className="px-4 py-3">{t("shifNumber")}</th>
                  <th className="px-4 py-3 text-right">{t("grossSalary")}</th>
                  <th className="px-4 py-3 text-right">{t("contribution")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(data.rows ?? []).map((r) => (
                  <tr key={r.employee_id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium">
                      {r.employee_name}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {r.shif_number}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatKES(r.gross_salary * 100)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums font-semibold">
                      {formatKES(r.contribution * 100)}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot className="border-t border-border bg-muted/20 text-sm font-semibold">
                <tr>
                  <td className="px-4 py-3" colSpan={3}>
                    {t("total")}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">
                    {formatKES(data.total * 100)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

const EMPLOYMENT_TYPE_KEYS = ["permanent", "contract", "casual", "intern"];

function HeadcountSection() {
  const t = useTranslations("payroll");
  const { data } = useHeadcountReport();

  if (!data) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
        {t("noData")}
      </div>
    );
  }

  const byEmploymentType = (data.by_employment_type ?? []).map((bucket) => ({
    ...bucket,
    label: EMPLOYMENT_TYPE_KEYS.includes(bucket.label)
      ? t(`employmentType_${bucket.label}`)
      : bucket.label,
  }));

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <ChartCard title={t("byDepartment")} icon={Building2}>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={data.by_department}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
            <XAxis dataKey="label" fontSize={12} />
            <YAxis fontSize={12} allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" fill="#3b82f6" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
      <ChartCard title={t("byEmploymentType")} icon={UsersIcon}>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={byEmploymentType}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
            <XAxis dataKey="label" fontSize={12} />
            <YAxis fontSize={12} allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" fill="#10b981" radius={[6, 6, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <p className="text-xs uppercase text-muted-foreground">
          {t("totalHeadcount")}
        </p>
        <p className="mt-2 text-4xl font-bold tabular-nums text-foreground">
          {data.total}
        </p>
      </div>
    </div>
  );
}

function LeaveUtilisationSection() {
  const t = useTranslations("payroll");
  const { data } = useLeaveUtilisation();

  const rows = data?.rows ?? [];

  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
        {t("noData")}
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
      <div className="border-b border-border px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <CalendarCheck className="h-4 w-4" />
          {t("leaveUtilisation")}
        </h2>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-3">{t("employee")}</th>
              <th className="px-4 py-3">{t("leaveType")}</th>
              <th className="px-4 py-3 text-right">{t("entitlement")}</th>
              <th className="px-4 py-3 text-right">{t("used")}</th>
              <th className="px-4 py-3 text-right">{t("remaining")}</th>
              <th className="px-4 py-3">{t("utilisation")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {rows.map((row, idx) => {
              const pct =
                row.entitlement > 0
                  ? (row.used / row.entitlement) * 100
                  : 0;
              const barColor =
                pct >= 100
                  ? "bg-red-500"
                  : pct >= 75
                    ? "bg-amber-500"
                    : pct >= 50
                      ? "bg-blue-500"
                      : "bg-emerald-500";
              return (
                <tr
                  key={`${row.employee_id}-${row.leave_type}-${idx}`}
                  className="hover:bg-muted/30"
                >
                  <td className="px-4 py-3 font-medium">
                    {row.employee_name}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {row.leave_type}
                  </td>
                  <td className="px-4 py-3 text-right">{row.entitlement}</td>
                  <td className="px-4 py-3 text-right">{row.used}</td>
                  <td className="px-4 py-3 text-right">{row.remaining}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div className="h-2 flex-1 overflow-hidden rounded-full bg-muted">
                        <div
                          className={`h-full ${barColor}`}
                          style={{ width: `${Math.min(pct, 100).toFixed(0)}%` }}
                        />
                      </div>
                      <span className="w-12 text-right text-xs tabular-nums text-muted-foreground">
                        {pct.toFixed(0)}%
                      </span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CostTrendSection() {
  const t = useTranslations("payroll");
  const { data } = useCostTrend();

  const points = data?.points ?? [];

  if (points.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
        {t("noData")}
      </div>
    );
  }

  const chartData = points.map((p) => ({
    label: p.label,
    gross: p.gross / 100,
    net: p.net / 100,
    paye: p.paye / 100,
  }));

  return (
    <ChartCard title={t("monthlyCostTrend")} icon={TrendingUp}>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
          <XAxis dataKey="label" fontSize={12} />
          <YAxis fontSize={12} />
          <Tooltip formatter={(v: number) => formatKES(v * 100)} />
          <Legend />
          <Line
            type="monotone"
            dataKey="gross"
            stroke="#10b981"
            strokeWidth={2}
            name={t("totalGross")}
          />
          <Line
            type="monotone"
            dataKey="net"
            stroke="#3b82f6"
            strokeWidth={2}
            name={t("totalNet")}
          />
          <Line
            type="monotone"
            dataKey="paye"
            stroke="#f97316"
            strokeWidth={2}
            name={t("totalPaye")}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}

function TurnoverSection() {
  const t = useTranslations("payroll");
  const { data } = useTurnover();

  const points = data?.points ?? [];

  if (points.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
        {t("noData")}
      </div>
    );
  }

  const summary = [
    { label: t("joiners"), value: data?.hires ?? 0, tone: "text-emerald-600" },
    {
      label: t("leavers"),
      value: data?.terminations ?? 0,
      tone: "text-red-600",
    },
    {
      label: t("endingHeadcount"),
      value: data?.ending_headcount ?? 0,
      tone: "text-foreground",
    },
  ];

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        {summary.map((item) => (
          <div
            key={item.label}
            className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]"
          >
            <p className="text-xs uppercase text-muted-foreground">
              {item.label}
            </p>
            <p
              className={`mt-2 text-3xl font-bold tabular-nums ${item.tone}`}
            >
              {item.value}
            </p>
          </div>
        ))}
      </div>
      <ChartCard title={t("turnover")} icon={TrendingUp}>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={points}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
            <XAxis dataKey="period" fontSize={12} />
            <YAxis fontSize={12} />
            <Tooltip />
            <Legend />
            <Bar
              dataKey="joiners"
              fill="#10b981"
              radius={[6, 6, 0, 0]}
              name={t("joiners")}
            />
            <Bar
              dataKey="leavers"
              fill="#ef4444"
              radius={[6, 6, 0, 0]}
              name={t("leavers")}
            />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}

function ChartCard({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
      <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
        <Icon className="h-4 w-4" />
        {title}
      </h3>
      {children}
    </div>
  );
}
