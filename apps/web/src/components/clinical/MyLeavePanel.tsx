"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  CalendarDays,
  CheckCircle2,
  Loader2,
  Send,
} from "lucide-react";
import {
  useLeaveRequests,
  useLeaveTypes,
  useMyLeaveBalance,
  useSubmitLeaveRequest,
  type LeaveRequestStatus,
} from "@/hooks/usePayroll";
import { useAuth } from "@/components/providers/AuthProvider";
import { TabGroup } from "@/components/ui/TabGroup";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmptyState } from "@/components/ui/EmptyState";
import { cn, formatDate } from "@/lib/utils";

/** The three halves of My Leave, in the order a clinician works through them. */
type LeaveTab = "request" | "balance" | "requests";

/** Badge look for each leave status, matching the HR Leave page. */
const STATUS_VARIANT: Record<
  LeaveRequestStatus,
  "warning" | "success" | "error" | "default"
> = {
  pending: "warning",
  approved: "success",
  rejected: "error",
  cancelled: "default",
};

/** Per-bucket card colours, matching the HR & Staff balance cards. */
const BUCKET_STYLE: Record<string, string> = {
  annual: "bg-blue-50 dark:bg-blue-950/30",
  sick: "bg-orange-50 dark:bg-orange-950/30",
  maternity: "bg-pink-50 dark:bg-pink-950/30",
  paternity: "bg-indigo-50 dark:bg-indigo-950/30",
};

const BUCKET_TEXT: Record<string, string> = {
  annual: "text-blue-800 dark:text-blue-200",
  sick: "text-orange-800 dark:text-orange-200",
  maternity: "text-pink-800 dark:text-pink-200",
  paternity: "text-indigo-800 dark:text-indigo-200",
};

const BUCKET_LABEL_KEYS: Record<string, string> = {
  annual: "annualLeave",
  sick: "sickLeave",
  maternity: "maternityLeave",
  paternity: "paternityLeave",
};

/**
 * My Leave - a clinician's own leave, inside the Clinical workspace.
 *
 * A doctor should not have to open HR to ask for a day off, so the same payroll
 * leave register HR uses is offered here in three parts: request leave, read the
 * balance that is left, and look back at the requests already filed. The API
 * resolves the caller's own payroll employee row, so nothing filed here can land
 * on a colleague.
 *
 * @returns The My Leave request, balance and history panel
 */
export function MyLeavePanel() {
  const t = useTranslations("clinical");
  const tp = useTranslations("payroll");
  const tc = useTranslations("common");
  const { user } = useAuth();

  const [tab, setTab] = useState<LeaveTab>("request");
  const [leaveTypeId, setLeaveTypeId] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const { data: mine, isLoading: mineLoading } = useLeaveRequests({
    employee_id: user?.id,
  });
  const { data: leaveTypes } = useLeaveTypes();
  const {
    data: balance,
    isLoading: balanceLoading,
    isError: balanceFailed,
  } = useMyLeaveBalance();
  const submit = useSubmitLeaveRequest();

  const requests = mine?.items ?? [];
  const types = Array.isArray(leaveTypes) ? leaveTypes : [];

  /** File the request against the signed-in user; the API enforces it too. */
  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setSaved(false);

    if (!user?.id) {
      setError(t("leaveNoAccount"));
      return;
    }
    if (!leaveTypeId) {
      setError(t("leaveTypeRequired"));
      return;
    }
    const startMs = new Date(`${startDate}T00:00:00`).getTime();
    const endMs = new Date(`${endDate}T00:00:00`).getTime();
    if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs < startMs) {
      setError(tp("leaveDateInvalid"));
      return;
    }
    const daysRequested = Math.round((endMs - startMs) / 86_400_000) + 1;

    submit.mutate(
      {
        employee_id: user.id,
        leave_type_id: leaveTypeId,
        start_date: startDate,
        end_date: endDate,
        days_requested: daysRequested,
        reason: reason.trim() || undefined,
      },
      {
        onSuccess: () => {
          setSaved(true);
          setLeaveTypeId("");
          setStartDate("");
          setEndDate("");
          setReason("");
        },
        onError: (err: Error) =>
          setError(err.message || tp("leaveCreateFailed")),
      },
    );
  };

  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
      <h2 className="flex items-center gap-2 font-semibold text-foreground">
        <CalendarDays className="h-5 w-5 text-primary" />
        {t("myLeave")}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">{t("myLeaveHint")}</p>

      <div className="mt-4">
        <TabGroup
          tabs={[
            { key: "request", label: t("leaveTabRequest") },
            { key: "balance", label: t("leaveTabBalance") },
            {
              key: "requests",
              label: t("leaveTabRequests"),
              count: requests.length,
            },
          ]}
          activeTab={tab}
          onTabChange={(key) => setTab(key as LeaveTab)}
          variant="underline"
        />
      </div>

      {tab === "request" && (
        <form onSubmit={onSubmit} className="mt-5 max-w-2xl space-y-4">
          {types.length === 0 && (
            <p className="text-sm text-muted-foreground">{t("leaveNoTypes")}</p>
          )}

          <label className="block text-sm">
            <span className="mb-1 block text-muted-foreground">
              {tp("leaveType")}
            </span>
            <select
              value={leaveTypeId}
              onChange={(event) => setLeaveTypeId(event.target.value)}
              className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
            >
              <option value="">{tc("select")}</option>
              {types.map((type) => (
                <option key={type.id} value={type.id}>
                  {type.name}
                </option>
              ))}
            </select>
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">
                {tp("startDate")}
              </span>
              <input
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
              />
            </label>
            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">
                {tp("endDate")}
              </span>
              <input
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
              />
            </label>
          </div>

          <label className="block text-sm">
            <span className="mb-1 block text-muted-foreground">
              {tp("reason")}
            </span>
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              rows={3}
              className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
            />
          </label>

          {error && (
            <p className="text-xs text-red-600 dark:text-red-400">{error}</p>
          )}
          {saved && (
            <p className="flex items-center gap-1.5 text-xs text-green-700 dark:text-green-400">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {t("leaveRequestedOk")}
            </p>
          )}

          <button
            type="submit"
            disabled={submit.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {submit.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            {t("leaveSubmit")}
          </button>
        </form>
      )}

      {tab === "balance" && (
        <div className="mt-5">
          {balanceFailed ? (
            <div className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 dark:border-amber-800 dark:bg-amber-950">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <p className="text-sm text-amber-800 dark:text-amber-200">
                {t("leaveBalanceUnavailable")}
              </p>
            </div>
          ) : balanceLoading ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {tc("loading")}
            </p>
          ) : (
            <>
              <p className="mb-3 text-sm text-muted-foreground">
                {t("leaveBalanceHint")}
              </p>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                {(balance?.buckets ?? []).map((bucket) => (
                  <div
                    key={bucket.key}
                    className={cn("rounded-lg p-4", BUCKET_STYLE[bucket.key])}
                  >
                    <p
                      className={cn(
                        "text-2xl font-bold",
                        BUCKET_TEXT[bucket.key],
                      )}
                    >
                      {bucket.remaining_days}
                    </p>
                    <p
                      className={cn(
                        "text-xs font-medium",
                        BUCKET_TEXT[bucket.key],
                      )}
                    >
                      {tp(BUCKET_LABEL_KEYS[bucket.key])}
                    </p>
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {tp("used")} {bucket.taken_days} / {tp("entitlement")}{" "}
                      {bucket.entitled_days}
                    </p>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}

      {tab === "requests" && (
        <div className="mt-5">
          {mineLoading ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              {tc("loading")}
            </p>
          ) : requests.length === 0 ? (
            <EmptyState
              icon={CalendarDays}
              title={t("leaveRequestsEmpty")}
              description={t("leaveRequestsEmptyHint")}
            />
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">{tp("leaveType")}</th>
                    <th className="px-4 py-3">{tp("dates")}</th>
                    <th className="px-4 py-3">{tp("days")}</th>
                    <th className="px-4 py-3">{tp("status")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {requests.map((request) => (
                    <tr key={request.id} className="hover:bg-muted/30">
                      <td className="px-4 py-3 font-medium">
                        {request.leave_type_name ?? "\u2014"}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {formatDate(request.start_date)} {"\u2014"}{" "}
                        {formatDate(request.end_date)}
                      </td>
                      <td className="px-4 py-3">{request.days_requested}</td>
                      <td className="px-4 py-3">
                        <StatusBadge
                          variant={STATUS_VARIANT[request.status]}
                          size="sm"
                          dot
                        >
                          {tp(`leaveStatus_${request.status}`)}
                        </StatusBadge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
