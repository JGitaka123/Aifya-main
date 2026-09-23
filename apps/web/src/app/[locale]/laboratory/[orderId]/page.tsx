"use client";

import { use, useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  ArrowLeft,
  FlaskConical,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Beaker,
  ShieldAlert,
  Bell,
  User,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useLabOrderDetail,
  useCollectSpecimen,
  useEnterResult,
  useVerifyResult,
  useNotifyCritical,
} from "@/hooks/useLaboratory";
import { useStaffDirectory } from "@/hooks/useHR";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";
import type { LabResultDetail, StaffDirectoryItem } from "@aifya/shared";

import {
  resultEntrySchema,
  type ResultEntryFormData,
} from "@/lib/validations/labResult";

/** Result status badge styling. */
const RESULT_STATUS_STYLES: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  preliminary: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  final: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  cancelled: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
};

/**
 * Lab order detail page — view results, enter results, verify, and notify critical.
 * Shows specimen collection, result entry forms, and verification actions.
 *
 * @returns Lab order detail page
 */
export default function LabOrderDetailPage({
  params,
}: {
  params: Promise<{ orderId: string }>;
}) {
  const { orderId } = use(params);
  const t = useTranslations("lab");
  const tc = useTranslations("common");
  const [activeResultId, setActiveResultId] = useState<string | null>(null);
  const [specimenId, setSpecimenId] = useState("");
  const [verifyNotes, setVerifyNotes] = useState("");
  const [notifyResultId, setNotifyResultId] = useState<string | null>(null);
  const [notifyToId, setNotifyToId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data, isLoading } = useLabOrderDetail(orderId);
  const collectSpecimen = useCollectSpecimen();
  const enterResult = useEnterResult();
  const verifyResult = useVerifyResult();
  const notifyCritical = useNotifyCritical();
  const { data: staffDirectory } = useStaffDirectory("doctor");

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors: formErrors },
  } = useForm<ResultEntryFormData>({
    resolver: zodResolver(resultEntrySchema),
    defaultValues: { is_abnormal: false },
  });

  const handleCollectSpecimen = () => {
    setError(null);
    collectSpecimen.mutate(
      { order_id: orderId, specimen_id: specimenId || undefined },
      {
        onSuccess: () => setSpecimenId(""),
        onError: (err) => setError(err.message),
      }
    );
  };

  const handleEnterResult = (resultId: string) => (formData: ResultEntryFormData) => {
    setError(null);
    enterResult.mutate(
      { result_id: resultId, ...formData },
      {
        onSuccess: () => {
          setActiveResultId(null);
          reset();
          window.location.reload();
        },
        onError: (err) => setError(err.message),
      }
    );
  };

  const handleVerify = (resultId: string) => {
    setError(null);
    verifyResult.mutate(
      { result_id: resultId, notes: verifyNotes || undefined },
      {
        onSuccess: () => setVerifyNotes(""),
        onError: (err) => setError(err.message),
      }
    );
  };

  const handleNotifyCritical = (resultId: string) => {
    if (!notifyToId.trim()) return;
    setError(null);
    notifyCritical.mutate(
      { result_id: resultId, notified_to: notifyToId },
      {
        onSuccess: () => {
          setNotifyResultId(null);
          setNotifyToId("");
        },
        onError: (err) => setError(err.message),
      }
    );
  };

  if (isLoading || !data) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <Link
          href="/laboratory"
          className="flex items-center gap-1 text-sm text-primary hover:underline"
        >
          <ArrowLeft className="h-4 w-4" />
          {tc("back")}
        </Link>
        <p className="mt-4 text-muted-foreground">{tc("loading")}</p>
      </div>
    );
  }

  const order = data.order;
  const results = data.results;
  const allFinal = results.length > 0 && results.every((r) => r.status === "final");
  const hasUnnotified = results.some((r) => r.is_critical && !r.critical_notified);

  return (
    <div className="mx-auto max-w-4xl animate-[fade-in_0.3s_ease-out] p-6 lg:p-8">
      {/* Back link */}
      <Link
        href="/laboratory"
        className="mb-4 inline-flex items-center gap-1 text-sm text-primary hover:underline"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("worklist")}
      </Link>

      {/* Header */}
      <div className="mb-6 flex items-center gap-3">
        <FlaskConical className="h-6 w-6 text-primary" />
        <h1 className="text-xl font-bold text-foreground">{t("orderDetail")}</h1>
        <span className="font-mono text-sm text-muted-foreground">
          {order.order_number}
        </span>
        {allFinal && (
          <span className="flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800 dark:bg-green-950 dark:text-green-200">
            <CheckCircle2 className="h-3 w-3" />
            {t("orderComplete")}
          </span>
        )}
      </div>

      {/* Critical alert banner */}
      {hasUnnotified && (
        <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 p-4 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
          <ShieldAlert className="mt-0.5 h-5 w-5 flex-shrink-0" />
          <div>
            <p className="font-semibold">{t("criticalValue")}</p>
            <p>{t("criticalAlert")}</p>
          </div>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-800 dark:bg-red-950 dark:text-red-200">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          <p>{error}</p>
        </div>
      )}

      {/* Patient & order info */}
      <div className="mb-6 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
        <h2 className="mb-2 text-sm font-medium text-muted-foreground">
          {t("patientInfo")}
        </h2>
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <div className="flex items-center gap-1">
            <User className="h-4 w-4 text-muted-foreground" />
            <span className="font-semibold text-foreground">
              {data.patient_name ?? "—"}
            </span>
          </div>
          {data.patient_mrn && (
            <span className="font-mono text-muted-foreground">{data.patient_mrn}</span>
          )}
          <span className="text-muted-foreground">
            {t("priority")}:{" "}
            <span className="font-medium uppercase">{order.priority}</span>
          </span>
          {order.specimen_type && (
            <span className="text-muted-foreground">
              {t("specimenType")}: {order.specimen_type}
            </span>
          )}
          {order.fasting && (
            <span className="text-amber-600 dark:text-amber-400">
              {t("fastingRequired")}
            </span>
          )}
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Clock className="h-3 w-3" />
            {formatDateTime(order.created_at)}
          </span>
        </div>
        {order.clinical_info && (
          <p className="mt-2 text-sm italic text-muted-foreground">
            {order.clinical_info}
          </p>
        )}
      </div>

      {/* Specimen collection (if not yet collected) */}
      {order.status === "ordered" && (
        <div className="mb-6 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 font-semibold text-foreground">
            {t("collectSpecimen")}
          </h3>
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="mb-1 block text-sm font-medium text-foreground">
                {t("specimenId")}
              </label>
              <input
                type="text"
                value={specimenId}
                onChange={(e) => setSpecimenId(e.target.value)}
                placeholder="SPEC-001..."
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
            <button
              onClick={handleCollectSpecimen}
              disabled={collectSpecimen.isPending}
              className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-50"
            >
              <Beaker className="h-4 w-4" />
              {collectSpecimen.isPending ? t("collecting") : t("collectSpecimen")}
            </button>
          </div>
        </div>
      )}

      {order.specimen_collected_at && (
        <div className="mb-6 flex items-center gap-2 text-sm text-green-700 dark:text-green-400">
          <CheckCircle2 className="h-4 w-4" />
          {t("specimenCollected")} — {formatDateTime(order.specimen_collected_at)}
        </div>
      )}

      {/* Results table */}
      <div className="mb-6">
        <h3 className="mb-3 font-semibold text-foreground">{t("results")}</h3>
        <div className="space-y-3">
          {results.map((result) => (
            <ResultCard
              key={result.id}
              result={result}
              t={t}
              tc={tc}
              isActiveEntry={activeResultId === result.id}
              onStartEntry={() => {
                setActiveResultId(result.id);
                reset();
              }}
              onCancelEntry={() => setActiveResultId(null)}
              onSubmitEntry={handleSubmit(handleEnterResult(result.id), () =>
                setError(t("fixFormErrors"))
              )}
              register={register}
              formErrors={formErrors}
              enterPending={enterResult.isPending}
              onVerify={() => handleVerify(result.id)}
              verifyPending={verifyResult.isPending}
              verifyNotes={verifyNotes}
              onVerifyNotesChange={setVerifyNotes}
              isNotifyOpen={notifyResultId === result.id}
              onOpenNotify={() => setNotifyResultId(result.id)}
              onCloseNotify={() => setNotifyResultId(null)}
              notifyToId={notifyToId}
              onNotifyToIdChange={setNotifyToId}
              onNotifyCritical={() => handleNotifyCritical(result.id)}
              notifyPending={notifyCritical.isPending}
              clinicians={staffDirectory?.items.filter((staff) => staff.is_active) ?? []}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Result Card Component ────────────────────────────────────────────────────

interface ResultCardProps {
  result: LabResultDetail;
  t: ReturnType<typeof useTranslations<"lab">>;
  tc: ReturnType<typeof useTranslations<"common">>;
  isActiveEntry: boolean;
  onStartEntry: () => void;
  onCancelEntry: () => void;
  onSubmitEntry: () => void;
  register: ReturnType<typeof useForm<ResultEntryFormData>>["register"];
  formErrors: ReturnType<typeof useForm<ResultEntryFormData>>["formState"]["errors"];
  enterPending: boolean;
  onVerify: () => void;
  verifyPending: boolean;
  verifyNotes: string;
  onVerifyNotesChange: (v: string) => void;
  isNotifyOpen: boolean;
  onOpenNotify: () => void;
  onCloseNotify: () => void;
  notifyToId: string;
  onNotifyToIdChange: (v: string) => void;
  onNotifyCritical: () => void;
  notifyPending: boolean;
  clinicians: StaffDirectoryItem[];
}

/**
 * Individual result card with entry form, verification, and critical notification.
 *
 * @param props - Result card props
 * @returns Result card component
 */
function ResultCard({
  result,
  t,
  tc,
  isActiveEntry,
  onStartEntry,
  onCancelEntry,
  onSubmitEntry,
  register,
  formErrors,
  enterPending,
  onVerify,
  verifyPending,
  verifyNotes,
  onVerifyNotesChange,
  isNotifyOpen,
  onOpenNotify,
  onCloseNotify,
  notifyToId,
  onNotifyToIdChange,
  onNotifyCritical,
  notifyPending,
  clinicians,
}: ResultCardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border p-4",
        result.is_critical
          ? "border-red-300 bg-red-50/50 dark:border-red-800 dark:bg-red-950/30"
          : "border-border bg-card shadow-[var(--shadow-card)]"
      )}
    >
      {/* Test header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-foreground">{result.test_name}</span>
          <span className="font-mono text-xs text-muted-foreground">
            {result.test_code}
          </span>
          {result.panel_name && (
            <span className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground">
              {result.panel_name}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {result.is_critical && (
            <span className="flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-bold text-red-800 dark:bg-red-950 dark:text-red-200">
              <AlertTriangle className="h-3 w-3" />
              {t("critical")}
            </span>
          )}
          {result.is_abnormal && !result.is_critical && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950 dark:text-amber-200">
              {t("abnormal")}
            </span>
          )}
          <span
            className={cn(
              "rounded-full px-2.5 py-0.5 text-xs font-medium",
              RESULT_STATUS_STYLES[result.status] ?? RESULT_STATUS_STYLES.pending
            )}
          >
            {t(result.status as "pending" | "preliminary" | "final")}
          </span>
        </div>
      </div>

      {/* Existing result display */}
      {result.result_value && (
        <div className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1 text-sm sm:grid-cols-4">
          <div>
            <span className="text-xs text-muted-foreground">{t("resultValue")}</span>
            <p
              className={cn(
                "font-semibold",
                result.is_critical
                  ? "text-red-700 dark:text-red-400"
                  : result.is_abnormal
                    ? "text-amber-700 dark:text-amber-400"
                    : "text-foreground"
              )}
            >
              {result.result_value} {result.result_unit ?? ""}
            </p>
          </div>
          {result.reference_range && (
            <div>
              <span className="text-xs text-muted-foreground">
                {t("referenceRange")}
              </span>
              <p className="text-foreground">{result.reference_range}</p>
            </div>
          )}
          {result.interpretation && (
            <div>
              <span className="text-xs text-muted-foreground">
                {t("interpretation")}
              </span>
              <p className="capitalize text-foreground">{result.interpretation}</p>
            </div>
          )}
          {result.method && (
            <div>
              <span className="text-xs text-muted-foreground">{t("method")}</span>
              <p className="text-foreground">{result.method}</p>
            </div>
          )}
        </div>
      )}

      {/* Timestamps */}
      {(result.resulted_at || result.verified_at) && (
        <div className="mt-2 flex flex-wrap gap-4 text-xs text-muted-foreground">
          {result.resulted_at && (
            <span>
              {t("resultedAt")}: {formatDateTime(result.resulted_at)}
            </span>
          )}
          {result.verified_at && (
            <span className="flex items-center gap-1">
              <CheckCircle2 className="h-3 w-3 text-green-500" />
              {t("verifiedAt")}: {formatDateTime(result.verified_at)}
            </span>
          )}
        </div>
      )}

      {result.notes && (
        <p className="mt-2 text-sm italic text-muted-foreground">{result.notes}</p>
      )}

      {/* Critical notification status */}
      {result.is_critical && (
        <div className="mt-3 flex items-center gap-2">
          {result.critical_notified ? (
            <span className="flex items-center gap-1 text-xs text-green-700 dark:text-green-400">
              <Bell className="h-3.5 w-3.5" />
              {t("notified")}
              {result.critical_notified_at && (
                <span> — {formatDateTime(result.critical_notified_at)}</span>
              )}
            </span>
          ) : (
            <>
              {isNotifyOpen ? (
                <div className="flex items-center gap-2">
                  <select
                    value={notifyToId}
                    onChange={(e) => onNotifyToIdChange(e.target.value)}
                    className="rounded-md border border-input bg-background px-2 py-1 text-xs text-foreground"
                  >
                    <option value="">{t("selectClinician")}</option>
                    {clinicians.map((clinician) => (
                      <option key={clinician.id} value={clinician.id}>
                        {clinician.title ? `${clinician.title} ` : ""}
                        {clinician.first_name} {clinician.last_name}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={onNotifyCritical}
                    disabled={notifyPending || !notifyToId.trim()}
                    className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                  >
                    {notifyPending ? t("notifying") : t("confirm" as "notifyClinician")}
                  </button>
                  <button
                    onClick={onCloseNotify}
                    className="text-xs text-muted-foreground hover:underline"
                  >
                    {t("cancel" as "notifyClinician")}
                  </button>
                </div>
              ) : (
                <button
                  onClick={onOpenNotify}
                  className="flex items-center gap-1 rounded bg-red-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-red-700"
                >
                  <Bell className="h-3.5 w-3.5" />
                  {t("notifyClinician")}
                </button>
              )}
            </>
          )}
        </div>
      )}

      {/* Action buttons */}
      <div className="mt-3 flex items-center gap-2">
        {/* Enter result (pending only) */}
        {result.status === "pending" && !isActiveEntry && (
          <button
            onClick={onStartEntry}
            className="flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground shadow hover:bg-primary/90"
          >
            <Beaker className="h-3.5 w-3.5" />
            {t("resultEntry")}
          </button>
        )}

        {/* Verify (preliminary only) */}
        {result.status === "preliminary" && (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={verifyNotes}
              onChange={(e) => onVerifyNotesChange(e.target.value)}
              placeholder={t("verificationNotes")}
              className="rounded-md border border-input bg-background px-2 py-1 text-xs text-foreground"
            />
            <button
              onClick={onVerify}
              disabled={verifyPending}
              className="flex items-center gap-1 rounded-lg bg-green-600 px-3 py-1.5 text-xs font-medium text-white shadow hover:bg-green-700 disabled:opacity-50"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              {verifyPending ? t("verifying") : t("verify")}
            </button>
          </div>
        )}
      </div>

      {/* Result entry form (expanded) */}
      {isActiveEntry && (
        <form onSubmit={onSubmitEntry} className="mt-4 space-y-3 border-t border-border pt-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div className="col-span-2">
              <label className="mb-1 block text-xs font-medium text-foreground">
                {t("resultValue")} *
              </label>
              <input
                {...register("result_value")}
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
              />
              {formErrors.result_value && (
                <p className="mt-0.5 text-xs text-red-500">
                  {formErrors.result_value.message}
                </p>
              )}
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-foreground">
                {t("resultNumeric")}
              </label>
              <input
                type="number"
                step="any"
                {...register("result_numeric")}
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-foreground">
                {t("resultUnit")}
              </label>
              <input
                {...register("result_unit")}
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-foreground">
                {t("referenceRange")}
              </label>
              <input
                {...register("reference_range")}
                placeholder="e.g. 4.5-11.0"
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-foreground">
                {t("interpretation")}
              </label>
              <select
                {...register("interpretation")}
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
              >
                <option value="">—</option>
                <option value="normal">{t("normal")}</option>
                <option value="abnormal">{t("abnormal")}</option>
                <option value="critical">{t("critical")}</option>
                <option value="inconclusive">{t("inconclusive")}</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-foreground">
                {t("method")}
              </label>
              <input
                {...register("method")}
                className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
              />
            </div>
            <div className="flex items-end">
              <label className="flex items-center gap-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  {...register("is_abnormal")}
                  className="rounded border-input text-primary"
                />
                {t("abnormal")}
              </label>
            </div>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-foreground">
              {t("resultNotes")}
            </label>
            <textarea
              {...register("notes")}
              rows={2}
              className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground"
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={enterPending}
              className="flex items-center gap-1 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-50"
            >
              {enterPending ? t("enteringResult") : t("resultEntry")}
            </button>
            <button
              type="button"
              onClick={onCancelEntry}
              className="rounded-lg border border-input px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
            >
              {tc("cancel")}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
