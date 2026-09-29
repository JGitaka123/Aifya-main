"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Shield, Plus, X } from "lucide-react";
import {
  usePAYEBands,
  useNSSFTiers,
  useStatutoryRates,
  useCreateStatutoryRate,
  useEmployees,
  useInsuranceUtilisation,
  useEmployeeDeductions,
  useCreateEmployeeDeduction,
  useDeleteEmployeeDeduction,
  type StatutoryRate,
} from "@/hooks/usePayroll";
import { useAuth } from "@/components/providers/AuthProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { TabGroup } from "@/components/ui/TabGroup";
import { formatKES, formatDate, todayISO } from "@/lib/utils";

type Tab = "paye" | "nssf" | "other" | "insurance";

const RATE_CATEGORIES = [
  "shif",
  "housing_levy",
  "relief",
  "insurance",
  "nssf",
  "paye",
] as const;

const rateSchema = z.object({
  name: z.string().min(1),
  category: z.string().min(1),
  effective_from: z.string().min(1),
  rate: z.coerce.number().optional(),
  fixed_amount: z.coerce.number().optional(),
});

type RateForm = z.infer<typeof rateSchema>;

/**
 * Statutory rates configuration page — read-only history view, admin can add new effective records.
 *
 * @returns Statutory rates page
 */
export default function StatutoryRatesPage() {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");
  const { user } = useAuth();

  const [tab, setTab] = useState<Tab>("paye");
  const [showAdd, setShowAdd] = useState(false);

  const isAdmin = useMemo(
    () =>
      (user?.roles ?? []).some((r) =>
        ["finance_admin", "facility_admin", "admin", "super_admin"].includes(r),
      ),
    [user],
  );

  const { data: bands } = usePAYEBands();
  const { data: tiers } = useNSSFTiers();
  const { data: rates } = useStatutoryRates();
  const create = useCreateStatutoryRate();

  const form = useForm<RateForm>({
    resolver: zodResolver(rateSchema),
    defaultValues: {
      name: "",
      category: "shif",
      effective_from: new Date().toISOString().split("T")[0],
    },
  });

  const onSubmit = form.handleSubmit((values) => {
    create.mutate(values, {
      onSuccess: () => {
        form.reset();
        setShowAdd(false);
      },
    });
  });

  const tabs: { key: Tab; label: string }[] = [
    { key: "paye", label: t("payeBands") },
    { key: "nssf", label: t("nssfTiers") },
    { key: "other", label: t("otherRates") },
    { key: "insurance", label: t("insurance") },
  ];

  const openAdd = (category: string) => {
    form.setValue("category", category);
    setShowAdd(true);
  };

  const allRates = Array.isArray(rates) ? rates : [];
  const otherRates = allRates.filter((r) => r.category !== "insurance");
  const insuranceRates = allRates.filter((r) => r.category === "insurance");

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <PageHeader
        icon={Shield}
        title={t("statutoryTitle")}
        subtitle={t("statutorySubtitle")}
        breadcrumbs={[
          { label: t("hrTitle"), href: "/hr" },
          { label: t("payroll"), href: "/hr/payroll" },
          { label: t("statutory") },
        ]}
        actions={
          isAdmin ? (
            <button
              type="button"
              onClick={() => setShowAdd(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              <Plus className="h-4 w-4" />
              {t("addNewRate")}
            </button>
          ) : null
        }
      />

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
        {t("ratesReadonlyNotice")}
      </div>

      <TabGroup
        tabs={tabs}
        activeTab={tab}
        onTabChange={(k) => setTab(k as Tab)}
        variant="underline"
      />

      {/* PAYE Bands */}
      {tab === "paye" && (
        <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold text-foreground">
              {t("payeBands")}
            </h2>
          </div>
          {!Array.isArray(bands) || !bands.length ? (
            <div className="p-8 text-center text-muted-foreground">
              {t("noData")}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">{t("band")}</th>
                    <th className="px-4 py-3">{t("effectiveFrom")}</th>
                    <th className="px-4 py-3 text-right">{t("lowerLimit")}</th>
                    <th className="px-4 py-3 text-right">{t("upperLimit")}</th>
                    <th className="px-4 py-3 text-right">{t("ratePct")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {bands.map((b, index) => (
                    <tr key={b.id} className="hover:bg-muted/30">
                      <td className="px-4 py-3 font-medium">
                        {t("bandN", { n: index + 1 })}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {formatDate(b.effective_from)}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {formatKES(Number(b.lower_limit) * 100)}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {b.upper_limit !== null && b.upper_limit !== undefined
                          ? formatKES(Number(b.upper_limit) * 100)
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {b.rate != null
                          ? `${(Number(b.rate) * 100).toFixed(2)}%`
                          : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* NSSF Tiers */}
      {tab === "nssf" && (
        <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold text-foreground">
              {t("nssfTiers")}
            </h2>
          </div>
          {!Array.isArray(tiers) || !tiers.length ? (
            <div className="p-8 text-center text-muted-foreground">
              {t("noData")}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">{t("tier")}</th>
                    <th className="px-4 py-3">{t("effectiveFrom")}</th>
                    <th className="px-4 py-3 text-right">{t("lowerLimit")}</th>
                    <th className="px-4 py-3 text-right">{t("upperLimit")}</th>
                    <th className="px-4 py-3 text-right">
                      {t("employeeRate")}
                    </th>
                    <th className="px-4 py-3 text-right">
                      {t("employerRate")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {tiers.map((tier) => (
                    <tr key={tier.id} className="hover:bg-muted/30">
                      <td className="px-4 py-3 font-medium">{tier.tier}</td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {formatDate(tier.effective_from)}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {formatKES(Number(tier.lower_limit) * 100)}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {formatKES(Number(tier.upper_limit) * 100)}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {(Number(tier.employee_rate) * 100).toFixed(2)}%
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {(Number(tier.employer_rate) * 100).toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Other rates */}
      {tab === "other" && (
        <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold text-foreground">
              {t("otherRates")}
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              SHIF (2.75%) • {t("housingLevy")} (1.5%) • {t("personalRelief")}{" "}
              (KSh 2,400) • {t("insuranceRelief")}
            </p>
          </div>
          {!otherRates.length ? (
            <div className="p-8 text-center text-muted-foreground">
              {t("noData")}
            </div>
          ) : (
            <RateTable rates={otherRates} />
          )}
        </div>
      )}

      {/* Insurance products + how they are used */}
      {tab === "insurance" && (
        <InsurancePanel
          isAdmin={isAdmin}
          rates={insuranceRates}
          onAddProduct={() => openAdd("insurance")}
        />
      )}

      {/* Add new rate modal */}
      {showAdd && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setShowAdd(false)}
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={onSubmit}
            className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl"
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">
                {t("addNewRate")}
              </h2>
              <button
                type="button"
                onClick={() => setShowAdd(false)}
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted/50"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-4">
              <label className="block text-sm">
                <span className="mb-1 block text-muted-foreground">
                  {t("name")}
                </span>
                <input
                  type="text"
                  {...form.register("name")}
                  className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
                />
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-muted-foreground">
                  {t("category")}
                </span>
                <select
                  {...form.register("category")}
                  className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
                >
                  {RATE_CATEGORIES.map((category) => (
                    <option key={category} value={category}>
                      {category}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                <span className="mb-1 block text-muted-foreground">
                  {t("effectiveFrom")}
                </span>
                <input
                  type="date"
                  {...form.register("effective_from")}
                  className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
                />
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-sm">
                  <span className="mb-1 block text-muted-foreground">
                    {t("ratePct")}
                  </span>
                  <input
                    type="number"
                    step="0.0001"
                    {...form.register("rate")}
                    className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
                  />
                </label>
                <label className="block text-sm">
                  <span className="mb-1 block text-muted-foreground">
                    {t("amount")} (KES)
                  </span>
                  <input
                    type="number"
                    {...form.register("fixed_amount")}
                    className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
                  />
                </label>
              </div>
              <p className="text-xs text-muted-foreground">
                {t("rateDecimalHint")}
              </p>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowAdd(false)}
                className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted/50"
              >
                {tc("cancel")}
              </button>
              <button
                type="submit"
                disabled={create.isPending}
                className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {tc("save")}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

function RateTable({ rates }: { rates: StatutoryRate[] }) {
  const t = useTranslations("payroll");
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
          <tr>
            <th className="px-4 py-3">{t("name")}</th>
            <th className="px-4 py-3">{t("category")}</th>
            <th className="px-4 py-3">{t("effectiveFrom")}</th>
            <th className="px-4 py-3">{t("effectiveTo")}</th>
            <th className="px-4 py-3 text-right">{t("ratePct")}</th>
            <th className="px-4 py-3 text-right">{t("amount")}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rates.map((r) => (
            <tr key={r.id} className="hover:bg-muted/30">
              <td className="px-4 py-3 font-medium">{r.name}</td>
              <td className="px-4 py-3 text-muted-foreground">{r.category}</td>
              <td className="px-4 py-3 text-muted-foreground">
                {formatDate(r.effective_from)}
              </td>
              <td className="px-4 py-3 text-muted-foreground">
                {r.effective_to ? formatDate(r.effective_to) : t("current")}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {r.rate !== null && r.rate !== undefined
                  ? `${(Number(r.rate) * 100).toFixed(2)}%`
                  : "—"}
              </td>
              <td className="px-4 py-3 text-right tabular-nums">
                {r.fixed_amount !== null && r.fixed_amount !== undefined
                  ? formatKES(Number(r.fixed_amount) * 100)
                  : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
      <p className="text-xs uppercase text-muted-foreground">{label}</p>
      <p className="mt-1 text-lg font-semibold tabular-nums text-foreground">
        {value}
      </p>
    </div>
  );
}

const premiumSchema = z.object({
  employee_id: z.string().min(1),
  name: z.string().min(1),
  amount: z.coerce.number().positive(),
  frequency: z.enum(["monthly", "one_time"]),
  start_date: z.string().min(1),
});

type PremiumForm = z.infer<typeof premiumSchema>;

const YEAR_WINDOW = 5;

/**
 * Insurance products plus how payroll has actually used them.
 *
 * A product is a `statutory_rates` row in the `insurance` category. A premium
 * is an `employee_deductions` row whose name matches a product, which is what
 * makes the payroll engine grant insurance relief on it.
 *
 * @param isAdmin - Whether the caller may configure products and premiums
 * @param rates - Configured insurance products
 * @param onAddProduct - Opens the statutory-rate modal preset to insurance
 * @returns Insurance configuration and usage tracking
 */
function InsurancePanel({
  isAdmin,
  rates,
  onAddProduct,
}: {
  isAdmin: boolean;
  rates: StatutoryRate[];
  onAddProduct: () => void;
}) {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");
  const thisYear = new Date().getFullYear();
  const [year, setYear] = useState(thisYear);

  const { data: report, isLoading } = useInsuranceUtilisation(year);
  const { data: employees } = useEmployees({ is_active: true, page_size: 200 });
  const { data: deductions } = useEmployeeDeductions();
  const createDeduction = useCreateEmployeeDeduction();
  const removeDeduction = useDeleteEmployeeDeduction();

  const form = useForm<PremiumForm>({
    resolver: zodResolver(premiumSchema),
    defaultValues: {
      employee_id: "",
      name: "",
      amount: 0,
      frequency: "monthly",
      start_date: todayISO(),
    },
  });

  const onRecord = form.handleSubmit((values) => {
    createDeduction.mutate(values, {
      onSuccess: () => {
        form.reset({
          employee_id: "",
          name: "",
          amount: 0,
          frequency: "monthly",
          start_date: todayISO(),
        });
      },
    });
  });

  const years = Array.from({ length: YEAR_WINDOW }, (_, i) => thisYear - i);
  const employeeOptions = employees?.items ?? [];
  const premiumRows = Array.isArray(deductions) ? deductions : [];
  const periods = report?.periods ?? [];
  const coverage = report?.coverage ?? [];
  const productNames = (report?.products ?? []).map((p) => p.name);

  const nameOf = (employeeId: string) =>
    employeeOptions.find((e) => e.id === employeeId)?.full_name ??
    employeeId.slice(0, 8);

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3">
          <div>
            <h2 className="text-sm font-semibold text-foreground">
              {t("insuranceProducts")}
            </h2>
            <p className="mt-1 max-w-3xl text-xs text-muted-foreground">
              {t("insuranceProductsHint")}
            </p>
          </div>
          {isAdmin ? (
            <button
              type="button"
              onClick={onAddProduct}
              className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted/50"
            >
              <Plus className="h-4 w-4" />
              {t("addInsuranceProduct")}
            </button>
          ) : null}
        </div>
        {!rates.length ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("noInsuranceProducts")}
          </div>
        ) : (
          <RateTable rates={rates} />
        )}
      </div>

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-foreground">
            {t("insuranceTracking")}
          </h2>
          <p className="mt-1 max-w-3xl text-xs text-muted-foreground">
            {t("insuranceTrackingHint")}
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">{t("year")}</span>
          <select
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
            className="rounded-lg border border-border bg-card px-3 py-1.5 text-sm"
          >
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        </label>
      </div>

      {isLoading ? (
        <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
          {tc("loading")}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Stat
            label={t("insuranceCovered")}
            value={String(report?.covered_employees ?? 0)}
          />
          <Stat
            label={t("insurancePremium")}
            value={formatKES(Number(report?.monthly_premium ?? 0) * 100)}
          />
          <Stat
            label={t("insurancePremiumYtd", { year })}
            value={formatKES(Number(report?.total_premium ?? 0) * 100)}
          />
          <Stat
            label={t("insuranceReliefYtd", { year })}
            value={formatKES(Number(report?.total_relief ?? 0) * 100)}
          />
        </div>
      )}

      <p className="rounded-xl border border-border bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
        {t("insuranceReliefRule", {
          rate: Number((Number(report?.relief_rate ?? 0) * 100).toFixed(2)),
          cap: formatKES(Number(report?.relief_cap ?? 0) * 100),
        })}
      </p>

      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        <div className="border-b border-border px-4 py-3">
          <h3 className="text-sm font-semibold text-foreground">
            {t("insuranceUsageByPeriod")}
          </h3>
        </div>
        {!periods.length ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("noInsuranceUsage")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("period")}</th>
                  <th className="px-4 py-3">{t("status")}</th>
                  <th className="px-4 py-3 text-right">
                    {t("insuranceCovered")}
                  </th>
                  <th className="px-4 py-3 text-right">
                    {t("insurancePremium")}
                  </th>
                  <th className="px-4 py-3 text-right">
                    {t("insuranceRelief")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {periods.map((p) => (
                  <tr key={`${p.year}-${p.month}`} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium">
                      {p.label} {p.year}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {p.run_status ? t(`runStatus_${p.run_status}`) : "—"}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {p.covered_employees}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatKES(Number(p.premium) * 100)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatKES(Number(p.relief) * 100)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        <div className="border-b border-border px-4 py-3">
          <h3 className="text-sm font-semibold text-foreground">
            {t("insuranceCoverage")}
          </h3>
        </div>
        {!coverage.length ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("noInsuranceUsage")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("employee")}</th>
                  <th className="px-4 py-3">{t("product")}</th>
                  <th className="px-4 py-3 text-right">
                    {t("insurancePremium")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {coverage.map((c) => (
                  <tr key={c.employee_id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium">
                      {c.employee_name}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {c.products.join(", ")}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatKES(Number(c.monthly_premium) * 100)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        <div className="border-b border-border px-4 py-3">
          <h3 className="text-sm font-semibold text-foreground">
            {t("recordPremium")}
          </h3>
          <p className="mt-1 max-w-3xl text-xs text-muted-foreground">
            {t("recordPremiumHint")}
          </p>
        </div>

        {isAdmin ? (
          <form
            onSubmit={onRecord}
            className="grid gap-3 border-b border-border px-4 py-4 md:grid-cols-6"
          >
            <label className="block text-sm md:col-span-2">
              <span className="mb-1 block text-muted-foreground">
                {t("employee")}
              </span>
              <select
                {...form.register("employee_id")}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
              >
                <option value="">{tc("select")}</option>
                {employeeOptions.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.full_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">
                {t("product")}
              </span>
              <input
                list="insurance-product-names"
                {...form.register("name")}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
              />
              <datalist id="insurance-product-names">
                {productNames.map((name) => (
                  <option key={name} value={name} />
                ))}
              </datalist>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">
                {t("amount")} (KES)
              </span>
              <input
                type="number"
                step="0.01"
                {...form.register("amount")}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">
                {t("frequency")}
              </span>
              <select
                {...form.register("frequency")}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
              >
                <option value="monthly">{t("frequency_monthly")}</option>
                <option value="one_time">{t("frequency_one_time")}</option>
              </select>
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">
                {t("startDate")}
              </span>
              <input
                type="date"
                {...form.register("start_date")}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
              />
            </label>
            <div className="flex items-center justify-between gap-3 md:col-span-6">
              <p className="text-xs text-muted-foreground">
                {t("productNameHint")}
              </p>
              <button
                type="submit"
                disabled={createDeduction.isPending}
                className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {t("recordPremium")}
              </button>
            </div>
          </form>
        ) : null}

        <div className="border-b border-border px-4 py-3">
          <h4 className="text-xs font-semibold uppercase text-muted-foreground">
            {t("premiums")}
          </h4>
        </div>
        {!premiumRows.length ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("noInsuranceUsage")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("employee")}</th>
                  <th className="px-4 py-3">{t("product")}</th>
                  <th className="px-4 py-3 text-right">{t("amount")}</th>
                  <th className="px-4 py-3">{t("frequency")}</th>
                  <th className="px-4 py-3">{t("startDate")}</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {premiumRows.map((d) => (
                  <tr key={d.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium">
                      {nameOf(d.employee_id)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{d.name}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {formatKES(Number(d.amount) * 100)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {d.frequency === "one_time"
                        ? t("frequency_one_time")
                        : t("frequency_monthly")}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDate(d.start_date)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {isAdmin ? (
                        <button
                          type="button"
                          onClick={() =>
                            removeDeduction.mutate({ deductionId: d.id })
                          }
                          disabled={removeDeduction.isPending}
                          className="rounded-lg border border-border px-2 py-1 text-xs font-medium text-muted-foreground hover:bg-muted/50 disabled:opacity-50"
                        >
                          {tc("remove")}
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
