"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  CheckCircle,
  Clock,
  DollarSign,
  FileText,
  Send,
  Shield,
  XCircle,
} from "lucide-react";
import { useInsuranceSummary, useInsuranceClaims, useInsuranceSchemes } from "@/hooks/useInsurance";
import { cn } from "@/lib/utils";

const CLAIM_STYLES: Record<string, string> = {
  draft: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200",
  submitted: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  processing: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  approved: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  partially_approved: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  rejected: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  paid: "bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200",
};

function formatKES(cents: number): string {
  return `KES ${(cents / 100).toLocaleString("en-KE", { minimumFractionDigits: 2 })}`;
}

export default function InsurancePage() {
  const t = useTranslations("insurance");
  const [tab, setTab] = useState<"claims" | "schemes">("claims");

  const { data: summary, isLoading: summaryLoading } = useInsuranceSummary();
  const { data: claims, isLoading: claimsLoading } = useInsuranceClaims();
  const { data: schemes } = useInsuranceSchemes();

  const summaryCards = [
    { label: t("totalClaims"), value: summary?.total_claims ?? 0, icon: FileText, color: "text-blue-600 dark:text-blue-400" },
    { label: t("pendingClaims"), value: summary?.pending_claims ?? 0, icon: Clock, color: "text-amber-600 dark:text-amber-400" },
    { label: t("submittedClaims"), value: summary?.submitted_claims ?? 0, icon: Send, color: "text-indigo-600 dark:text-indigo-400" },
    { label: t("approvedClaims"), value: summary?.approved_claims ?? 0, icon: CheckCircle, color: "text-green-600 dark:text-green-400" },
    { label: t("rejectedClaims"), value: summary?.rejected_claims ?? 0, icon: XCircle, color: "text-red-600 dark:text-red-400" },
    { label: t("totalClaimValue"), value: summary ? formatKES(summary.total_claim_value) : "—", icon: DollarSign, color: "text-purple-600 dark:text-purple-400" },
    { label: t("activeSchemes"), value: summary?.active_schemes ?? 0, icon: Shield, color: "text-cyan-600 dark:text-cyan-400" },
    { label: t("preAuthPending"), value: summary?.preauth_pending ?? 0, icon: AlertTriangle, color: "text-orange-600 dark:text-orange-400" },
  ];

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-8">
        {summaryCards.map((card) => (
          <div key={card.label} className="rounded-xl border border-border bg-card p-3 shadow-[var(--shadow-card)]">
            <div className="flex items-center gap-2">
              <card.icon className={cn("h-4 w-4", card.color)} />
              <span className="text-xs text-muted-foreground">{card.label}</span>
            </div>
            <p className="mt-1 text-lg font-bold text-foreground">
              {summaryLoading ? "—" : card.value}
            </p>
          </div>
        ))}
      </div>

      <div className="flex gap-2 border-b border-border">
        {(["claims", "schemes"] as const).map((t_) => (
          <button
            key={t_}
            onClick={() => setTab(t_)}
            className={cn(
              "px-4 py-2 text-sm font-medium transition-colors",
              tab === t_
                ? "border-b-2 border-blue-600 text-blue-600 dark:border-blue-400 dark:text-blue-400"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {t(`tab.${t_}`)}
          </button>
        ))}
      </div>

      {tab === "claims" && (
        <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("claimNumber")}</th>
                <th className="px-4 py-3">{t("patient")}</th>
                <th className="px-4 py-3">{t("scheme")}</th>
                <th className="px-4 py-3">{t("memberNumber")}</th>
                <th className="px-4 py-3">{t("amount")}</th>
                <th className="px-4 py-3">{t("date")}</th>
                <th className="px-4 py-3">{t("statusLabel")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {claimsLoading ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground/70">{t("loading")}</td></tr>
              ) : !claims?.items.length ? (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-muted-foreground/70">{t("noClaims")}</td></tr>
              ) : (
                claims.items.map((c) => (
                  <tr key={c.id} className="bg-card hover:bg-muted/50">
                    <td className="px-4 py-3 font-medium text-blue-600 dark:text-blue-400">{c.claim_number}</td>
                    <td className="px-4 py-3 font-medium text-foreground">{c.patient_name || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{c.scheme_name || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{c.member_number}</td>
                    <td className="px-4 py-3 font-medium">{formatKES(c.claim_amount)}</td>
                    <td className="px-4 py-3 text-muted-foreground">{new Date(c.claim_date).toLocaleDateString()}</td>
                    <td className="px-4 py-3">
                      <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", CLAIM_STYLES[c.status])}>
                        {t(`claimStatus.${c.status}`)}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "schemes" && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {schemes?.items.map((s) => (
            <div key={s.id} className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-foreground">{s.name}</h3>
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800 dark:bg-blue-950 dark:text-blue-200">
                  {t(`schemeType.${s.scheme_type}`)}
                </span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">{s.scheme_code}</p>
              {s.contact_person && <p className="text-xs text-muted-foreground/70">{s.contact_person} — {s.phone}</p>}
            </div>
          ))}
          {!schemes?.items.length && (
            <p className="col-span-full py-8 text-center text-muted-foreground/70">{t("noSchemes")}</p>
          )}
        </div>
      )}
    </div>
  );
}
