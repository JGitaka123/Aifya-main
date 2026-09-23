"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Heart,
  Baby,
  AlertTriangle,
  Calendar,
  ChevronDown,
  ChevronUp,
  Clock,
  Plus,
  Syringe,
  Users,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import type { ChildRecordResponse, Patient } from "@aifya/shared";
import {
  useMCHSummary,
  useANCProfiles,
  useChildRecords,
} from "@/hooks/useMCH";
import {
  ScheduledAppointments,
  type RegisterWorklistItem,
} from "@/components/appointments/ScheduledAppointments";
import { ChildImmunizationPanel } from "@/components/mch/ChildImmunizationPanel";
import { NewANCProfileForm } from "@/components/mch/NewANCProfileForm";
import { NewChildRecordForm } from "@/components/mch/NewChildRecordForm";
import { PatientPrefill } from "@/components/mch/PatientPrefill";
import { cn, formatDate } from "@/lib/utils";

/** Risk level badge styling. */
const RISK_STYLES: Record<string, string> = {
  low: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  moderate: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  high: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

/** ANC status badge styling. */
const STATUS_STYLES: Record<string, string> = {
  active: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  delivered: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  postnatal: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  closed: "bg-muted text-muted-foreground",
  transferred: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200",
};

/**
 * MCH Dashboard — shows ANC profiles, child health records, and summary stats.
 * Combines maternal and child health tracking.
 *
 * @returns MCH dashboard page
 */
export default function MCHDashboardPage() {
  const t = useTranslations("mch");
  const tc = useTranslations("common");
  const [tab, setTab] = useState<"anc" | "children">("anc");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [showANCForm, setShowANCForm] = useState(false);
  const [showChildForm, setShowChildForm] = useState(false);
  const [expandedChildId, setExpandedChildId] = useState<string | null>(null);
  const [ancPrefill, setAncPrefill] = useState<Patient | null>(null);
  const [childPrefill, setChildPrefill] = useState<Patient | null>(null);
  const [prefill, setPrefill] = useState<{
    patientId: string;
    kind: "anc" | "child";
  } | null>(null);

  const {
    data: summary,
    isError: summaryError,
    refetch: refetchSummary,
  } = useMCHSummary();
  const {
    data: ancProfiles,
    isLoading: ancLoading,
    isError: ancError,
    refetch: refetchAnc,
  } = useANCProfiles(tab === "anc" ? statusFilter || undefined : undefined);
  const {
    data: children,
    isLoading: childrenLoading,
    isError: childrenError,
    refetch: refetchChildren,
  } = useChildRecords();

  const rowActionClass =
    "inline-flex items-center gap-1 whitespace-nowrap rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-foreground shadow-sm hover:bg-muted";

  // MCH follow-ups are register-driven: a pregnancy or a child card schedules
  // the next contact, so the department panel has to show the register rather
  // than only the booked appointment book.
  const ancWorklist: RegisterWorklistItem[] = (ancProfiles?.items ?? [])
    .filter((profile) => profile.status === "active")
    .map((profile) => ({
      id: profile.id,
      patientName: profile.patient_name,
      patientMrn: profile.patient_mrn,
      reference: profile.anc_number,
      detail: `G${profile.gravida}P${profile.parity}${
        profile.gestation_weeks != null && profile.gestation_weeks >= 0
          ? ` · ${profile.gestation_weeks} ${t("weeks")}`
          : ""
      }`,
      due: profile.expected_delivery_date
        ? `${t("edd")} ${formatDate(profile.expected_delivery_date)}`
        : "—",
      tone: profile.risk_level === "high" ? "overdue" : "due",
      action: (
        <Link href={`/mch/${profile.id}`} className={rowActionClass}>
          {tc("open")}
        </Link>
      ),
    }));

  const childWorklist: RegisterWorklistItem[] = (children?.items ?? []).map(
    (child) => ({
      id: child.id,
      patientName: child.patient_name,
      reference: child.child_number,
      detail: `${child.age_months ?? 0} ${t("months")} · ${child.immunization_count} ${t("doses")}`,
      due: child.next_immunization ?? t("upToDate"),
      tone: child.next_immunization ? "due" : "ok",
      action: (
        <button
          type="button"
          onClick={() =>
            setExpandedChildId(expandedChildId === child.id ? null : child.id)
          }
          className={rowActionClass}
        >
          {tc("open")}
        </button>
      ),
    })
  );

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] p-5 sm:p-6 lg:p-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Heart className="h-7 w-7 text-pink-500" />
          <h1 className="text-2xl font-bold text-foreground">{t("title")}</h1>
        </div>
        <div className="flex items-center gap-3">
          {tab === "anc" && (
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background"
            >
              <option value="">{t("filterAll")}</option>
              <option value="active">{t("statusActive")}</option>
              <option value="delivered">{t("statusDelivered")}</option>
              <option value="postnatal">{t("statusPostnatal")}</option>
              <option value="closed">{t("statusClosed")}</option>
            </select>
          )}
        </div>
      </div>

      {/* Summary cards */}
      {summary ? (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          <SummaryCard
            icon={<Heart className="h-5 w-5 text-pink-500" />}
            label={t("activeANC")}
            value={String(summary.active_anc_profiles)}
          />
          <SummaryCard
            icon={<AlertTriangle className="h-5 w-5 text-red-500" />}
            label={t("highRisk")}
            value={String(summary.high_risk_pregnancies)}
            highlight={summary.high_risk_pregnancies > 0}
          />
          <SummaryCard
            icon={<Baby className="h-5 w-5 text-blue-500" />}
            label={t("deliveriesMonth")}
            value={String(summary.deliveries_this_month)}
          />
          <SummaryCard
            icon={<Baby className="h-5 w-5 text-green-500" />}
            label={t("liveBirths")}
            value={String(summary.live_births_this_month)}
          />
          <SummaryCard
            icon={<Users className="h-5 w-5 text-purple-500" />}
            label={t("activeChildren")}
            value={String(summary.active_children)}
          />
          <SummaryCard
            icon={<Syringe className="h-5 w-5 text-amber-500" />}
            label={t("overdueImmunizations")}
            value={String(summary.overdue_immunizations)}
            highlight={summary.overdue_immunizations > 0}
          />
        </div>
      ) : summaryError ? (
        <div className="mb-6">
          <LoadError onRetry={() => void refetchSummary()} />
        </div>
      ) : null}

      {prefill && (
        <PatientPrefill
          patientId={prefill.patientId}
          onLoaded={(patient) => {
            if (prefill.kind === "anc") {
              setAncPrefill(patient);
              setShowANCForm(true);
            } else {
              setChildPrefill(patient);
              setShowChildForm(true);
            }
            setPrefill(null);
          }}
        />
      )}

      {/* Tabs */}
      <div className="mb-4 flex border-b border-border">
        <button
          onClick={() => setTab("anc")}
          className={cn(
            "px-4 py-2 text-sm font-medium transition-colors",
            tab === "anc"
              ? "border-b-2 border-pink-500 text-pink-600 dark:text-pink-400"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {t("antenatalCare")}
        </button>
        <button
          onClick={() => setTab("children")}
          className={cn(
            "px-4 py-2 text-sm font-medium transition-colors",
            tab === "children"
              ? "border-b-2 border-blue-500 text-blue-600 dark:text-blue-400"
              : "text-muted-foreground hover:text-foreground"
          )}
        >
          {t("childHealth")}
        </button>
      </div>

      {/* ANC Profiles tab */}
      {tab === "anc" && (
        <>
          <div className="mb-6">
            <ScheduledAppointments
              appointmentType="anc"
              registerTitle={t("antenatalCare")}
              registerItems={ancWorklist}
              renderAction={(appointment) => (
                <button
                  type="button"
                  onClick={() =>
                    setPrefill({
                      patientId: appointment.patient_id,
                      kind: "anc",
                    })
                  }
                  className="inline-flex items-center gap-1 whitespace-nowrap rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-foreground shadow-sm hover:bg-muted"
                >
                  <Plus className="h-3.5 w-3.5" />
                  {t("registerPregnancy")}
                </button>
              )}
            />
          </div>

          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">
              {t("antenatalCare")}
            </h2>
            <button
              type="button"
              onClick={() => setShowANCForm((open) => !open)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90"
            >
              <Plus className="h-4 w-4" />
              {showANCForm ? tc("cancel") : t("newANCProfile")}
            </button>
          </div>

          {showANCForm && (
            <div className="mb-4">
              <NewANCProfileForm
                patient={ancPrefill}
                onDone={() => {
                  setShowANCForm(false);
                  setAncPrefill(null);
                }}
              />
            </div>
          )}

          {ancError ? (
            <LoadError onRetry={() => void refetchAnc()} />
          ) : ancLoading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              {tc("loading")}
            </div>
          ) : !ancProfiles?.items.length ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Heart className="mb-3 h-12 w-12 opacity-40" />
              <p className="text-lg">{t("noANCProfiles")}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {ancProfiles.items.map((profile) => (
                <Link
                  key={profile.id}
                  href={`/mch/${profile.id}`}
                  className={cn(
                    "flex items-center gap-4 rounded-lg border border-border bg-card p-4 shadow-[var(--shadow-card)] transition-colors hover:shadow-md",
                    profile.risk_level === "high" && "border-red-400 dark:border-red-700"
                  )}
                >
                  {/* Icon */}
                  <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-pink-100 text-pink-700 dark:bg-pink-950 dark:text-pink-300">
                    <Heart className="h-5 w-5" />
                  </div>

                  {/* Patient & ANC info */}
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-semibold text-foreground">
                        {profile.patient_name ?? "—"}
                      </span>
                      {profile.patient_mrn && (
                        <span className="font-mono text-xs text-muted-foreground">
                          {profile.patient_mrn}
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 flex items-center gap-3 text-sm text-muted-foreground">
                      <span className="font-mono">{profile.anc_number}</span>
                      <span>
                        G{profile.gravida}P{profile.parity}
                      </span>
                      {profile.gestation_weeks != null && (
                        <span>
                          {profile.gestation_weeks} {t("weeks")}
                        </span>
                      )}
                      <span>
                        {profile.visit_count} {t("visits")}
                      </span>
                    </div>
                  </div>

                  {/* EDD */}
                  {profile.expected_delivery_date && (
                    <div className="hidden flex-shrink-0 text-center sm:block">
                      <Calendar className="mx-auto h-4 w-4 text-muted-foreground" />
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {t("edd")}: {profile.expected_delivery_date}
                      </div>
                    </div>
                  )}

                  {/* Risk badge */}
                  <span
                    className={cn(
                      "flex-shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium",
                      RISK_STYLES[profile.risk_level] ?? RISK_STYLES.low
                    )}
                  >
                    {t(`risk_${profile.risk_level}` as "risk_low" | "risk_moderate" | "risk_high")}
                  </span>

                  {/* Status badge */}
                  <span
                    className={cn(
                      "flex-shrink-0 rounded-full px-2.5 py-0.5 text-xs font-medium",
                      STATUS_STYLES[profile.status] ?? STATUS_STYLES.active
                    )}
                  >
                    {t(`status_${profile.status}` as "status_active" | "status_delivered" | "status_postnatal" | "status_closed")}
                  </span>
                </Link>
              ))}
            </div>
          )}
        </>
      )}

      {/* Child Health tab */}
      {tab === "children" && (
        <>
          <div className="mb-6">
            <ScheduledAppointments
              appointmentType="vaccination"
              registerTitle={t("childHealth")}
              registerItems={childWorklist}
              renderAction={(appointment) => (
                <button
                  type="button"
                  onClick={() =>
                    setPrefill({
                      patientId: appointment.patient_id,
                      kind: "child",
                    })
                  }
                  className="inline-flex items-center gap-1 whitespace-nowrap rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-foreground shadow-sm hover:bg-muted"
                >
                  <Plus className="h-3.5 w-3.5" />
                  {t("registerChild")}
                </button>
              )}
            />
          </div>

          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-foreground">
              {t("childHealth")}
            </h2>
            <button
              type="button"
              onClick={() => setShowChildForm((open) => !open)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90"
            >
              <Plus className="h-4 w-4" />
              {showChildForm ? tc("cancel") : t("newChildRecord")}
            </button>
          </div>

          {showChildForm && (
            <div className="mb-4">
              <NewChildRecordForm
                patient={childPrefill}
                onDone={() => {
                  setShowChildForm(false);
                  setChildPrefill(null);
                }}
                onCreated={(created: ChildRecordResponse) =>
                  setExpandedChildId(created.id)
                }
              />
            </div>
          )}

          {childrenError ? (
            <LoadError onRetry={() => void refetchChildren()} />
          ) : childrenLoading ? (
            <div className="flex items-center justify-center py-12 text-muted-foreground">
              {tc("loading")}
            </div>
          ) : !children?.items.length ? (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <Baby className="mb-3 h-12 w-12 opacity-40" />
              <p className="text-lg">{t("noChildren")}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {children.items.map((child) => {
                const expanded = expandedChildId === child.id;
                return (
                  <div
                    key={child.id}
                    className="overflow-hidden rounded-lg border border-border bg-card shadow-[var(--shadow-card)]"
                  >
                    <button
                      type="button"
                      onClick={() => setExpandedChildId(expanded ? null : child.id)}
                      className="flex w-full items-center gap-4 p-4 text-left"
                    >
                    {/* Icon */}
                    <div
                      className={cn(
                        "flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full",
                        child.sex === "male"
                          ? "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                          : "bg-pink-100 text-pink-700 dark:bg-pink-950 dark:text-pink-300"
                      )}
                    >
                      <Baby className="h-5 w-5" />
                    </div>

                    {/* Child info */}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="truncate font-semibold text-foreground">
                          {child.patient_name ?? "—"}
                        </span>
                        <span className="font-mono text-xs text-muted-foreground">
                          {child.child_number}
                        </span>
                      </div>
                      <div className="mt-0.5 flex items-center gap-3 text-sm text-muted-foreground">
                        <span>{t(child.sex as "male" | "female")}</span>
                        {child.age_months != null && (
                          <span>
                            {child.age_months} {t("months")}
                          </span>
                        )}
                        <span className="flex items-center gap-1">
                          <Syringe className="h-3 w-3" />
                          {child.immunization_count} {t("doses")}
                        </span>
                        {child.hiv_exposed && (
                          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                            {t("hivExposed")}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* DOB */}
                    <div className="hidden items-center gap-1 text-xs text-muted-foreground lg:flex">
                      <Clock className="h-3 w-3" />
                      {t("dob")}: {child.date_of_birth}
                    </div>

                      {expanded ? (
                        <ChevronUp className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                      )}
                    </button>

                    {expanded && <ChildImmunizationPanel child={child} />}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/**
 * Error state for a failed MCH query.
 *
 * Without this, an unreachable API renders the same empty state as a register
 * with no records, so the ANC and Child Health tabs look dormant rather than
 * broken.
 *
 * @param props - Retry handler
 * @returns Retry panel
 */
function LoadError({ onRetry }: { onRetry: () => void }) {
  const t = useTranslations("mch");
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-red-300 bg-red-50 px-4 py-10 text-center dark:border-red-900 dark:bg-red-950">
      <AlertTriangle className="h-6 w-6 text-red-600 dark:text-red-400" />
      <p className="text-sm text-red-700 dark:text-red-300">
        {t("apiUnreachable")}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-lg border border-red-300 bg-background px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted dark:border-red-900"
      >
        {t("retry")}
      </button>
    </div>
  );
}

/**
 * Summary card for dashboard stats.
 *
 * @param props - Card props
 * @returns Summary card component
 */
function SummaryCard({
  icon,
  label,
  value,
  highlight = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]",
        highlight && "border-amber-300 dark:border-amber-800"
      )}
    >
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <p
        className={cn(
          "mt-1 text-xl font-bold",
          highlight ? "text-amber-700 dark:text-amber-400" : "text-foreground"
        )}
      >
        {value}
      </p>
    </div>
  );
}
