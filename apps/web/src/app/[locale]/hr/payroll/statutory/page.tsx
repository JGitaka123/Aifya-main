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
  type StatutoryRate,
} from "@/hooks/usePayroll";
import { useAuth } from "@/components/providers/AuthProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { TabGroup } from "@/components/ui/TabGroup";
import { formatKES, formatDate } from "@/lib/utils";

type Tab = "paye" | "nssf" | "other";

const RATE_CATEGORIES = [
  "shif",
  "housing_levy",
  "relief",
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
        ["finance_admin", "admin", "super_admin"].includes(r),
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
  ];

  const otherRates = Array.isArray(rates) ? rates : [];

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
