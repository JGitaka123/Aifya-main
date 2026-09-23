"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Calendar, CheckCircle, Clock, Plus, Users } from "lucide-react";
import { useDentalSummary, useDentalVisits, useDentalTreatmentPlans } from "@/hooks/useDental";
import { ScheduledAppointments } from "@/components/appointments/ScheduledAppointments";
import { StartDentalVisitButton } from "@/components/dental/StartDentalVisitButton";
import { DentistSchedulesPanel } from "@/components/dental/DentistSchedulesPanel";
import { NewTreatmentPlanForm } from "@/components/dental/NewTreatmentPlanForm";
import { TreatmentPlanActions } from "@/components/dental/TreatmentPlanActions";
import { cn, formatKES } from "@/lib/utils";

const STATUS_STYLES: Record<string, string> = {
  scheduled: "bg-muted text-muted-foreground",
  in_progress: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  completed: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  cancelled: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  draft: "bg-muted text-muted-foreground",
  approved: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
};

export default function DentalPage() {
  const t = useTranslations("dental");
  const tc = useTranslations("common");
  const [tab, setTab] = useState<"visits" | "treatments" | "dentists">("visits");
  const [showPlanForm, setShowPlanForm] = useState(false);

  const { data: summary, isLoading: summaryLoading } = useDentalSummary();
  const { data: visits, isLoading: visitsLoading } = useDentalVisits();
  const { data: plans } = useDentalTreatmentPlans();

  const summaryCards = [
    { label: t("totalPatients"), value: summary?.total_patients ?? 0, icon: Users, color: "text-blue-600 dark:text-blue-400" },
    { label: t("todayVisits"), value: summary?.today_visits ?? 0, icon: Calendar, color: "text-purple-600 dark:text-purple-400" },
    { label: t("pendingTreatments"), value: summary?.pending_treatments ?? 0, icon: Clock, color: "text-amber-600 dark:text-amber-400" },
    { label: t("completedToday"), value: summary?.completed_today ?? 0, icon: CheckCircle, color: "text-green-600 dark:text-green-400" },
  ];

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <div>
        <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {summaryCards.map((card) => (
          <div key={card.label} className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
            <div className="flex items-center gap-2">
              <card.icon className={cn("h-5 w-5", card.color)} />
              <span className="text-sm text-muted-foreground">{card.label}</span>
            </div>
            <p className="mt-2 text-2xl font-bold text-foreground">
              {summaryLoading ? "—" : card.value}
            </p>
          </div>
        ))}
      </div>

      <ScheduledAppointments
        appointmentType="dental"
        renderAction={(appointment) => (
          <StartDentalVisitButton appointment={appointment} />
        )}
      />

      <div className="flex gap-2 border-b border-border">
        {(["visits", "treatments", "dentists"] as const).map((t_) => (
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

      {tab === "visits" && (
        <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("visitNumber")}</th>
                <th className="px-4 py-3">{t("patient")}</th>
                <th className="px-4 py-3">{t("dentist")}</th>
                <th className="px-4 py-3">{t("date")}</th>
                <th className="px-4 py-3">{t("procedure")}</th>
                <th className="px-4 py-3">{t("statusLabel")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {visitsLoading ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground/70">{t("loading")}</td></tr>
              ) : !visits?.items.length ? (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-muted-foreground/70">{t("noRecords")}</td></tr>
              ) : (
                visits.items.map((v) => (
                  <tr key={v.id} className="bg-card hover:bg-muted/50">
                    <td className="px-4 py-3 font-medium text-blue-600 dark:text-blue-400">{v.visit_number}</td>
                    <td className="px-4 py-3 font-medium text-foreground">{v.patient_name || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{v.dentist_name || "—"}</td>
                    <td className="px-4 py-3 text-muted-foreground">{new Date(v.visit_date).toLocaleDateString()}</td>
                    <td className="max-w-[200px] truncate px-4 py-3 text-foreground">{v.chief_complaint || "—"}</td>
                    <td className="px-4 py-3">
                      <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", STATUS_STYLES[v.status])}>
                        {t(`status.${v.status}`)}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "treatments" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">
              {t("tab.treatments")}
            </h2>
            <button
              type="button"
              onClick={() => setShowPlanForm((open) => !open)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90"
            >
              <Plus className="h-4 w-4" />
              {showPlanForm ? tc("cancel") : t("newTreatmentPlan")}
            </button>
          </div>

          {showPlanForm && (
            <NewTreatmentPlanForm onDone={() => setShowPlanForm(false)} />
          )}

          <div className="overflow-x-auto rounded-xl border border-border shadow-[var(--shadow-card)]">
            <table className="w-full text-left text-sm">
              <thead className="bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("planNumber")}</th>
                  <th className="px-4 py-3">{t("patient")}</th>
                  <th className="px-4 py-3">{t("diagnosis")}</th>
                  <th className="px-4 py-3">{t("planItems")}</th>
                  <th className="px-4 py-3">{t("estimatedCost")}</th>
                  <th className="px-4 py-3">{t("dentist")}</th>
                  <th className="px-4 py-3">{t("statusLabel")}</th>
                  <th className="px-4 py-3">{tc("actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {!plans?.items.length ? (
                  <tr>
                    <td colSpan={8} className="px-4 py-8 text-center text-muted-foreground/70">
                      {t("noPlans")}
                    </td>
                  </tr>
                ) : (
                  plans.items.map((p) => (
                    <tr key={p.id} className="bg-card hover:bg-muted/50">
                      <td className="px-4 py-3 font-medium text-blue-600 dark:text-blue-400">
                        {p.plan_number}
                      </td>
                      <td className="px-4 py-3 text-foreground">
                        {p.patient_name ?? p.patient_id}
                        {p.patient_mrn && (
                          <span className="block text-xs text-muted-foreground">
                            {p.patient_mrn}
                          </span>
                        )}
                      </td>
                      <td className="max-w-[220px] truncate px-4 py-3 text-foreground">
                        {p.diagnosis || "—"}
                      </td>
                      <td className="px-4 py-3 text-foreground">
                        {p.plan_items?.length ?? 0}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-foreground">
                        {formatKES(p.total_estimated_cost)}
                      </td>
                      <td className="px-4 py-3 text-foreground">
                        {p.dentist_name ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-xs font-medium",
                            STATUS_STYLES[p.status]
                          )}
                        >
                          {t("status." + p.status)}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <TreatmentPlanActions plan={p} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "dentists" && <DentistSchedulesPanel />}
    </div>
  );
}
