"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  Calendar,
  CheckCircle,
  Crosshair,
  MonitorCheck,
  Scissors,
  XCircle,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useTheatreSummary, useSurgicalCases, useTheatres } from "@/hooks/useTheatre";
import { cn } from "@/lib/utils";

const PRIORITY_STYLES: Record<string, string> = {
  emergency: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  urgent: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200",
  elective: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
};

const STATUS_STYLES: Record<string, string> = {
  scheduled: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200",
  preop: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  in_progress: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  in_recovery: "bg-cyan-100 text-cyan-800 dark:bg-cyan-950 dark:text-cyan-200",
  completed: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  cancelled: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  postponed: "bg-muted text-muted-foreground",
};

const THEATRE_STATUS_STYLES: Record<string, string> = {
  available: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  in_use: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  cleaning: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  maintenance: "bg-muted text-muted-foreground",
  closed: "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200",
};

export default function TheatrePage() {
  const t = useTranslations("theatre");
  const [tab, setTab] = useState<"schedule" | "theatres">("schedule");
  const [dateFilter, setDateFilter] = useState(new Date().toISOString().split("T")[0]);

  const { data: summary, isLoading: summaryLoading } = useTheatreSummary();
  const { data: cases, isLoading: casesLoading } = useSurgicalCases(dateFilter);
  const { data: theatres } = useTheatres();

  const summaryCards = [
    { label: t("totalTheatres"), value: summary?.total_theatres ?? 0, icon: MonitorCheck, color: "text-blue-600 dark:text-blue-400" },
    { label: t("available"), value: summary?.available_theatres ?? 0, icon: CheckCircle, color: "text-green-600 dark:text-green-400" },
    { label: t("inUse"), value: summary?.in_use_theatres ?? 0, icon: Scissors, color: "text-red-600 dark:text-red-400" },
    { label: t("scheduledToday"), value: summary?.scheduled_today ?? 0, icon: Calendar, color: "text-purple-600 dark:text-purple-400" },
    { label: t("completedToday"), value: summary?.completed_today ?? 0, icon: Crosshair, color: "text-teal-600 dark:text-teal-400" },
    { label: t("emergencyCases"), value: summary?.emergency_cases ?? 0, icon: AlertTriangle, color: "text-orange-600 dark:text-orange-400" },
    { label: t("cancelledToday"), value: summary?.cancelled_today ?? 0, icon: XCircle, color: "text-muted-foreground" },
  ];

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-7">
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

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        {(["schedule", "theatres"] as const).map((t_) => (
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

      {/* Schedule Tab */}
      {tab === "schedule" && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <input
              type="date"
              value={dateFilter}
              onChange={(e) => setDateFilter(e.target.value)}
              className="rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground"
            />
          </div>

          <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("caseNumber")}</th>
                  <th className="px-4 py-3">{t("time")}</th>
                  <th className="px-4 py-3">{t("patient")}</th>
                  <th className="px-4 py-3">{t("procedure")}</th>
                  <th className="px-4 py-3">{t("theatreLabel")}</th>
                  <th className="px-4 py-3">{t("surgeon")}</th>
                  <th className="px-4 py-3">{t("priority")}</th>
                  <th className="px-4 py-3">{t("statusLabel")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {casesLoading ? (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-muted-foreground/70">{t("loading")}</td></tr>
                ) : !cases?.items.length ? (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-muted-foreground/70">{t("noCases")}</td></tr>
                ) : (
                  cases.items.map((c) => (
                    <tr key={c.id} className="bg-card hover:bg-muted/50">
                      <td className="px-4 py-3">
                        <Link href={`/theatre/${c.id}`} className="font-medium text-blue-600 hover:underline dark:text-blue-400">
                          {c.case_number}
                        </Link>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-muted-foreground">
                        {new Date(c.scheduled_date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </td>
                      <td className="px-4 py-3 font-medium text-foreground">{c.patient_name || "—"}</td>
                      <td className="max-w-[200px] truncate px-4 py-3 text-foreground">{c.procedure_name}</td>
                      <td className="px-4 py-3 text-muted-foreground">{c.theatre_name || "—"}</td>
                      <td className="px-4 py-3 text-muted-foreground">{c.lead_surgeon_name || "—"}</td>
                      <td className="px-4 py-3">
                        <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", PRIORITY_STYLES[c.priority])}>
                          {t(`priorityType.${c.priority}`)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", STATUS_STYLES[c.status])}>
                          {t(`status.${c.status}`)}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Theatres Tab */}
      {tab === "theatres" && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {theatres?.map((th) => (
            <div key={th.id} className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-foreground">{th.name}</h3>
                <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", THEATRE_STATUS_STYLES[th.status])}>
                  {t(`theatreStatus.${th.status}`)}
                </span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">{th.code} — {t(`theatreType.${th.theatre_type}`)}</p>
              {th.floor && <p className="text-xs text-muted-foreground/70">{t("floor")}: {th.floor}</p>}
            </div>
          ))}
          {!theatres?.length && (
            <p className="col-span-full py-8 text-center text-muted-foreground/70">{t("noTheatres")}</p>
          )}
        </div>
      )}
    </div>
  );
}
