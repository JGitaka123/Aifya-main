"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowDownLeft, ArrowUpRight, CheckCircle, Clock, FileText, Printer, Send } from "lucide-react";
import { useReferralSummary, useReferralList } from "@/hooks/useReferrals";
import { NewReferralForm } from "@/components/referrals/NewReferralForm";
import { ReferralStatusActions } from "@/components/referrals/ReferralStatusActions";
import { cn } from "@/lib/utils";

const URGENCY_STYLES: Record<string, string> = {
  emergency: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  urgent: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200",
  routine: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
};

const STATUS_STYLES: Record<string, string> = {
  draft: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200",
  sent: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  received: "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200",
  accepted: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  declined: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  completed: "bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200",
  cancelled: "bg-muted text-muted-foreground",
};

export default function ReferralsPage() {
  const t = useTranslations("referrals");
  const [tab, setTab] = useState<"outgoing" | "incoming">("outgoing");
  const [showNewReferral, setShowNewReferral] = useState(false);

  const { data: summary, isLoading: summaryLoading } = useReferralSummary();
  const { data: referrals, isLoading } = useReferralList(tab);

  const summaryCards = [
    { label: t("totalReferrals"), value: summary?.total_referrals ?? 0, icon: FileText, color: "text-blue-600 dark:text-blue-400" },
    { label: t("outgoing"), value: summary?.outgoing ?? 0, icon: ArrowUpRight, color: "text-purple-600 dark:text-purple-400" },
    { label: t("incoming"), value: summary?.incoming ?? 0, icon: ArrowDownLeft, color: "text-cyan-600 dark:text-cyan-400" },
    { label: t("pending"), value: summary?.pending ?? 0, icon: Clock, color: "text-amber-600 dark:text-amber-400" },
    { label: t("accepted"), value: summary?.accepted ?? 0, icon: Send, color: "text-green-600 dark:text-green-400" },
    { label: t("completed"), value: summary?.completed ?? 0, icon: CheckCircle, color: "text-teal-600 dark:text-teal-400" },
  ];

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <button
          type="button"
          onClick={() => setShowNewReferral((open) => !open)}
          className="inline-flex items-center gap-2 self-start rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 sm:self-auto"
        >
          <ArrowUpRight className="h-4 w-4" />
          {t("newReferral")}
        </button>
      </div>

      {showNewReferral && <NewReferralForm onClose={() => setShowNewReferral(false)} />}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {summaryCards.map((card) => (
          <div key={card.label} className="rounded-xl border border-border bg-card p-3 shadow-[var(--shadow-card)]">
            <div className="flex items-center gap-2">
              <card.icon className={cn("h-4 w-4", card.color)} />
              <span className="text-xs text-muted-foreground">{card.label}</span>
            </div>
            <p className="mt-1 text-xl font-bold text-foreground">
              {summaryLoading ? "—" : card.value}
            </p>
          </div>
        ))}
      </div>

      <div className="flex gap-2 border-b border-border">
        {(["outgoing", "incoming"] as const).map((t_) => (
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

      <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
        <table className="w-full text-left text-sm">
          <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-3">{t("referralNumber")}</th>
              <th className="px-4 py-3">{t("patient")}</th>
              <th className="px-4 py-3">{tab === "outgoing" ? t("referredTo") : t("referredFrom")}</th>
              <th className="px-4 py-3">{t("reason")}</th>
              <th className="px-4 py-3">{t("urgency")}</th>
              <th className="px-4 py-3">{t("date")}</th>
              <th className="px-4 py-3">{t("statusLabel")}</th>
              <th className="px-4 py-3 text-right">{t("actions")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {isLoading ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-muted-foreground/70">{t("loading")}</td></tr>
            ) : !referrals?.items.length ? (
              <tr><td colSpan={8} className="px-4 py-8 text-center text-muted-foreground/70">{t("noReferrals")}</td></tr>
            ) : (
              referrals.items.map((r) => (
                <tr key={r.id} className="bg-card hover:bg-muted/50">
                  <td className="px-4 py-3 font-medium text-blue-600 dark:text-blue-400">
                    <div className="flex items-center gap-2">
                      <span>{r.referral_number}</span>
                      {r.emergency_visit_id && (
                        <span
                          title={t("fromEmergencyTitle")}
                          className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-red-700 dark:bg-red-950 dark:text-red-300"
                        >
                          {t("fromEmergency")}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-medium text-foreground">{r.patient_name || "—"}</td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {tab === "outgoing" ? r.receiving_facility_name : r.referring_facility_name || "—"}
                  </td>
                  <td className="max-w-[200px] truncate px-4 py-3 text-foreground">{r.reason}</td>
                  <td className="px-4 py-3">
                    <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", URGENCY_STYLES[r.urgency])}>
                      {t(`urgencyType.${r.urgency}`)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{new Date(r.referral_date).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", STATUS_STYLES[r.status])}>
                      {t(`status.${r.status}`)}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <ReferralStatusActions referralId={r.id} status={r.status} />
                      <button
                        type="button"
                        onClick={async () => {
                          const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
                          const res = await fetch(
                            `${apiBase}/api/v1/referrals/${r.id}/pdf-note`,
                            { credentials: "include" },
                          );
                          if (!res.ok) {
                            alert(t("pdfError"));
                            return;
                          }
                          const blob = await res.blob();
                          const url = URL.createObjectURL(blob);
                          window.open(url, "_blank", "noopener");
                          setTimeout(() => URL.revokeObjectURL(url), 60_000);
                        }}
                        className="inline-flex items-center gap-1 rounded-md border border-input px-2 py-1 text-xs font-medium transition-colors hover:bg-muted"
                      >
                        <Printer className="h-3 w-3" />
                        {t("generateNote")}
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
