"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Scan,
  ArrowLeft,
  AlertCircle,
  FileText,
  CheckCircle,
  Calendar,
  Clock,
  Shield,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useImagingOrderDetail,
  useScheduleOrder,
  usePerformStudy,
  useEnterReport,
  useVerifyReport,
  useNotifyCriticalImaging,
} from "@/hooks/useRadiology";
import { useStaffDirectory } from "@/hooks/useHR";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

/** Urgency badge styling. */
const URGENCY_STYLES: Record<string, string> = {
  normal: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  abnormal: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  critical: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  incidental: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
};

/**
 * Imaging order detail page — shows order info, scheduling, performance,
 * radiology report entry, verification, and critical finding notification.
 *
 * @returns Imaging order detail page
 */
export default function ImagingOrderDetailPage() {
  const params = useParams();
  const orderId = params.orderId as string;
  const t = useTranslations("radiology");
  const tc = useTranslations("common");

  const { data: detail, isLoading } = useImagingOrderDetail(orderId);
  const scheduleOrder = useScheduleOrder();
  const performStudy = usePerformStudy();
  const enterReport = useEnterReport();
  const verifyReport = useVerifyReport();
  const notifyCritical = useNotifyCriticalImaging();

  // Clinicians that can be notified about a critical finding
  const { data: staffDirectory } = useStaffDirectory("doctor");
  const clinicians = staffDirectory?.items.filter((staff) => staff.is_active) ?? [];

  // Schedule form state
  const [scheduleDate, setScheduleDate] = useState("");
  const [scheduleRoom, setScheduleRoom] = useState("");

  // Perform form state
  const [accessionNumber, setAccessionNumber] = useState("");

  // Report form state
  const [findings, setFindings] = useState("");
  const [impression, setImpression] = useState("");
  const [recommendations, setRecommendations] = useState("");
  const [technique, setTechnique] = useState("");
  const [comparison, setComparison] = useState("");
  const [urgency, setUrgency] = useState("normal");
  const [isCritical, setIsCritical] = useState(false);
  const [reportNotes, setReportNotes] = useState("");

  // Verify form state
  const [verifyNotes, setVerifyNotes] = useState("");

  // Critical notify state
  const [notifyTo, setNotifyTo] = useState("");

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        {tc("loading")}
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
        <p>{t("orderNotFound")}</p>
        <Link href="/radiology" className="mt-4 text-primary hover:underline">
          {t("backToWorklist")}
        </Link>
      </div>
    );
  }

  const { order, result } = detail;

  /**
   * Handle scheduling form submission.
   */
  const handleSchedule = () => {
    if (!scheduleDate) return;
    scheduleOrder.mutate({
      orderId: order.id,
      scheduled_at: new Date(scheduleDate).toISOString(),
      room: scheduleRoom || null,
    });
  };

  /**
   * Handle perform study form submission.
   */
  const handlePerform = () => {
    performStudy.mutate({
      orderId: order.id,
      accession_number: accessionNumber || null,
    });
  };

  /**
   * Handle report entry form submission.
   */
  const handleReport = () => {
    if (!result) return;
    enterReport.mutate({
      resultId: result.id,
      findings: findings || null,
      impression: impression || null,
      recommendations: recommendations || null,
      technique: technique || null,
      comparison: comparison || null,
      urgency: urgency as "normal" | "abnormal" | "critical" | "incidental",
      is_critical: isCritical,
      notes: reportNotes || null,
    });
  };

  /**
   * Handle report verification.
   */
  const handleVerify = () => {
    if (!result) return;
    verifyReport.mutate({
      resultId: result.id,
      notes: verifyNotes || null,
    });
  };

  /**
   * Handle critical finding notification.
   */
  const handleNotifyCritical = () => {
    if (!result || !notifyTo) return;
    notifyCritical.mutate({
      resultId: result.id,
      notified_to: notifyTo,
    });
  };

  return (
    <div className="mx-auto max-w-4xl animate-[fade-in_0.3s_ease-out] p-6 lg:p-8">
      {/* Back link */}
      <Link
        href="/radiology"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("backToWorklist")}
      </Link>

      {/* Order header */}
      <div className="mb-6 rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
        <div className="flex items-center gap-3">
          <Scan className="h-6 w-6 text-primary" />
          <h1 className="text-xl font-bold text-foreground">
            {order.order_number}
          </h1>
          <span
            className={cn(
              "rounded-full px-2.5 py-0.5 text-xs font-medium uppercase",
              order.priority === "stat"
                ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200"
                : order.priority === "urgent"
                  ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200"
                  : "bg-muted text-muted-foreground"
            )}
          >
            {t(order.priority as "stat" | "urgent" | "routine")}
          </span>
        </div>

        {/* Patient info */}
        <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-muted-foreground">{t("patient")}:</span>{" "}
            <span className="font-medium text-foreground">
              {detail.patient_name ?? "—"}
            </span>
            {detail.patient_mrn && (
              <span className="ml-2 font-mono text-xs text-muted-foreground">
                {detail.patient_mrn}
              </span>
            )}
          </div>
          <div>
            <span className="text-muted-foreground">{t("modality")}:</span>{" "}
            <span className="font-medium text-foreground">
              {order.modality.toUpperCase()}
            </span>
          </div>
          <div>
            <span className="text-muted-foreground">{t("bodyPart")}:</span>{" "}
            <span className="font-medium text-foreground">{order.body_part}</span>
            {order.laterality && order.laterality !== "na" && (
              <span className="ml-1 text-muted-foreground">
                ({t(order.laterality as "left" | "right" | "bilateral")})
              </span>
            )}
          </div>
          <div>
            <span className="text-muted-foreground">{t("study")}:</span>{" "}
            <span className="font-medium text-foreground">
              {order.study_description}
            </span>
          </div>
          {order.views_requested && (
            <div>
              <span className="text-muted-foreground">{t("views")}:</span>{" "}
              <span className="text-foreground">{order.views_requested}</span>
            </div>
          )}
          {order.clinical_indication && (
            <div className="col-span-2">
              <span className="text-muted-foreground">{t("indication")}:</span>{" "}
              <span className="text-foreground">{order.clinical_indication}</span>
            </div>
          )}
          {order.contrast_required && (
            <div>
              <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                {t("contrastRequired")}
              </span>
            </div>
          )}
          {order.pregnancy_status && order.pregnancy_status !== "na" && (
            <div>
              <Shield className="mr-1 inline h-3 w-3 text-amber-500" />
              <span className="text-xs text-amber-700 dark:text-amber-300">
                {t(`pregnancy_${order.pregnancy_status}` as "pregnancy_not_pregnant" | "pregnancy_pregnant" | "pregnancy_unknown")}
              </span>
            </div>
          )}
        </div>

        {/* Status and timestamps */}
        <div className="mt-4 flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
            {t("ordered")}: {formatDateTime(order.created_at)}
          </span>
          {order.scheduled_at && (
            <span className="flex items-center gap-1">
              <Calendar className="h-3 w-3" />
              {t("scheduled")}: {formatDateTime(order.scheduled_at)}
              {order.room && ` — ${order.room}`}
            </span>
          )}
          {order.performed_at && (
            <span className="flex items-center gap-1">
              <CheckCircle className="h-3 w-3" />
              {t("performed")}: {formatDateTime(order.performed_at)}
            </span>
          )}
        </div>
      </div>

      {/* Schedule form — show only if ordered */}
      {order.status === "ordered" && (
        <div className="mb-6 rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-3 flex items-center gap-2 font-semibold text-foreground">
            <Calendar className="h-5 w-5 text-purple-500" />
            {t("scheduleStudy")}
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">
                {t("scheduledDateTime")}
              </label>
              <input
                type="datetime-local"
                value={scheduleDate}
                onChange={(e) => setScheduleDate(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">
                {t("room")}
              </label>
              <input
                type="text"
                value={scheduleRoom}
                onChange={(e) => setScheduleRoom(e.target.value)}
                placeholder={t("roomPlaceholder")}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
          </div>
          <button
            onClick={handleSchedule}
            disabled={!scheduleDate || scheduleOrder.isPending}
            className="mt-4 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-700 disabled:opacity-50"
          >
            {scheduleOrder.isPending ? tc("saving") : t("schedule")}
          </button>
        </div>
      )}

      {/* Perform study form — show if ordered or scheduled */}
      {(order.status === "ordered" || order.status === "scheduled") && (
        <div className="mb-6 rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-3 flex items-center gap-2 font-semibold text-foreground">
            <Scan className="h-5 w-5 text-blue-500" />
            {t("performStudy")}
          </h2>
          <div>
            <label className="mb-1 block text-sm text-muted-foreground">
              {t("accessionNumber")}
            </label>
            <input
              type="text"
              value={accessionNumber}
              onChange={(e) => setAccessionNumber(e.target.value)}
              placeholder={t("accessionPlaceholder")}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
            />
          </div>
          <button
            onClick={handlePerform}
            disabled={performStudy.isPending}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {performStudy.isPending ? tc("saving") : t("markPerformed")}
          </button>
        </div>
      )}

      {/* Report section */}
      {result && (
        <div className="mb-6 rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-3 flex items-center gap-2 font-semibold text-foreground">
            <FileText className="h-5 w-5 text-indigo-500" />
            {t("radiologyReport")}
            {result.status && (
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-xs font-medium",
                  result.status === "final"
                    ? "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200"
                    : result.status === "preliminary"
                      ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200"
                      : "bg-muted text-muted-foreground"
                )}
              >
                {t(`report${result.status.charAt(0).toUpperCase()}${result.status.slice(1)}` as "reportDraft" | "reportPreliminary" | "reportFinal")}
              </span>
            )}
          </h2>

          {/* Show existing report if final or preliminary */}
          {result.status !== "draft" && (
            <div className="mb-4 space-y-3">
              {result.technique && (
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground">{t("technique")}</h3>
                  <p className="text-sm text-foreground">{result.technique}</p>
                </div>
              )}
              {result.comparison && (
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground">{t("comparison")}</h3>
                  <p className="text-sm text-foreground">{result.comparison}</p>
                </div>
              )}
              {result.findings && (
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground">{t("findings")}</h3>
                  <p className="whitespace-pre-wrap text-sm text-foreground">{result.findings}</p>
                </div>
              )}
              {result.impression && (
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground">{t("impression")}</h3>
                  <p className="whitespace-pre-wrap text-sm text-foreground">{result.impression}</p>
                </div>
              )}
              {result.recommendations && (
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground">{t("recommendations")}</h3>
                  <p className="text-sm text-foreground">{result.recommendations}</p>
                </div>
              )}

              {/* Urgency badge */}
              <div className="flex items-center gap-2">
                <span className="text-sm text-muted-foreground">{t("urgency")}:</span>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-xs font-medium",
                    URGENCY_STYLES[result.urgency] ?? URGENCY_STYLES.normal
                  )}
                >
                  {t(result.urgency as "normal" | "abnormal" | "critical" | "incidental")}
                </span>
                {result.is_critical && (
                  <AlertCircle className="h-4 w-4 text-red-500" />
                )}
              </div>

              {/* Timestamps */}
              <div className="flex gap-4 text-xs text-muted-foreground">
                {result.reported_at && (
                  <span>{t("reportedAt")}: {formatDateTime(result.reported_at)}</span>
                )}
                {result.verified_at && (
                  <span>{t("verifiedAt")}: {formatDateTime(result.verified_at)}</span>
                )}
              </div>
            </div>
          )}

          {/* Report entry form — show if draft or preliminary (not final) */}
          {result.status !== "final" && (
            <div className="space-y-3 border-t border-border pt-4">
              <h3 className="text-sm font-medium text-foreground">
                {result.status === "draft" ? t("enterReport") : t("updateReport")}
              </h3>
              <div>
                <label className="mb-1 block text-sm text-muted-foreground">{t("technique")}</label>
                <textarea
                  value={technique}
                  onChange={(e) => setTechnique(e.target.value)}
                  rows={2}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                  placeholder={t("techniquePlaceholder")}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-muted-foreground">{t("comparison")}</label>
                <input
                  type="text"
                  value={comparison}
                  onChange={(e) => setComparison(e.target.value)}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                  placeholder={t("comparisonPlaceholder")}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-muted-foreground">{t("findings")}</label>
                <textarea
                  value={findings}
                  onChange={(e) => setFindings(e.target.value)}
                  rows={4}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                  placeholder={t("findingsPlaceholder")}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-muted-foreground">{t("impression")}</label>
                <textarea
                  value={impression}
                  onChange={(e) => setImpression(e.target.value)}
                  rows={3}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                  placeholder={t("impressionPlaceholder")}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm text-muted-foreground">{t("recommendations")}</label>
                <textarea
                  value={recommendations}
                  onChange={(e) => setRecommendations(e.target.value)}
                  rows={2}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                  placeholder={t("recommendationsPlaceholder")}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="mb-1 block text-sm text-muted-foreground">{t("urgency")}</label>
                  <select
                    value={urgency}
                    onChange={(e) => setUrgency(e.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                  >
                    <option value="normal">{t("normal")}</option>
                    <option value="abnormal">{t("abnormal")}</option>
                    <option value="critical">{t("critical")}</option>
                    <option value="incidental">{t("incidental")}</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-2 text-sm text-foreground">
                    <input
                      type="checkbox"
                      checked={isCritical}
                      onChange={(e) => setIsCritical(e.target.checked)}
                      className="h-4 w-4 rounded border-input"
                    />
                    {t("markCritical")}
                  </label>
                </div>
              </div>
              <div>
                <label className="mb-1 block text-sm text-muted-foreground">{tc("notes")}</label>
                <textarea
                  value={reportNotes}
                  onChange={(e) => setReportNotes(e.target.value)}
                  rows={2}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                />
              </div>
              <button
                onClick={handleReport}
                disabled={enterReport.isPending}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {enterReport.isPending ? tc("saving") : t("saveReport")}
              </button>
            </div>
          )}

          {/* Verify button — show if preliminary */}
          {result.status === "preliminary" && (
            <div className="mt-4 border-t border-border pt-4">
              <h3 className="mb-2 text-sm font-medium text-foreground">{t("verifyReport")}</h3>
              <div className="mb-3">
                <label className="mb-1 block text-sm text-muted-foreground">{t("verificationNotes")}</label>
                <textarea
                  value={verifyNotes}
                  onChange={(e) => setVerifyNotes(e.target.value)}
                  rows={2}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                />
              </div>
              <button
                onClick={handleVerify}
                disabled={verifyReport.isPending}
                className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
              >
                {verifyReport.isPending ? tc("saving") : t("verifyAndFinalise")}
              </button>
            </div>
          )}

          {/* Critical notification — show if critical and not notified */}
          {result.is_critical && !result.critical_notified && (
            <div className="mt-4 rounded-lg border border-red-300 bg-red-50 p-4 dark:border-red-800 dark:bg-red-950">
              <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-red-700 dark:text-red-300">
                <AlertCircle className="h-4 w-4" />
                {t("criticalFindingAlert")}
              </h3>
              <p className="mb-3 text-xs text-red-600 dark:text-red-400">
                {t("criticalFindingDescription")}
              </p>
              <div className="mb-3">
                <label className="mb-1 block text-sm text-muted-foreground">
                  {t("notifiedClinician")}
                </label>
                <select
                  value={notifyTo}
                  onChange={(e) => setNotifyTo(e.target.value)}
                  className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground"
                >
                  <option value="">{t("selectClinician")}</option>
                  {clinicians.map((clinician) => (
                    <option key={clinician.id} value={clinician.id}>
                      {clinician.title ? `${clinician.title} ` : ""}
                      {clinician.first_name} {clinician.last_name}
                    </option>
                  ))}
                </select>
              </div>
              <button
                onClick={handleNotifyCritical}
                disabled={!notifyTo || notifyCritical.isPending}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
              >
                {notifyCritical.isPending ? tc("saving") : t("recordNotification")}
              </button>
            </div>
          )}

          {/* Critical notified confirmation */}
          {result.is_critical && result.critical_notified && (
            <div className="mt-4 rounded-lg border border-green-300 bg-green-50 p-4 dark:border-green-800 dark:bg-green-950">
              <p className="flex items-center gap-2 text-sm text-green-700 dark:text-green-300">
                <CheckCircle className="h-4 w-4" />
                {t("criticalNotified")} — {formatDateTime(result.critical_notified_at ?? "")}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
