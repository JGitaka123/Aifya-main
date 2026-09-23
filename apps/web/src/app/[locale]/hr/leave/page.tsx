"use client";

import { useState, useMemo } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CalendarDays, Plus, X, Check, Ban } from "lucide-react";
import {
  useLeaveRequests,
  useLeaveTypes,
  useCreateLeaveType,
  useSubmitLeaveRequest,
  useApproveLeaveRequest,
  type LeaveRequest,
  type LeaveRequestStatus,
} from "@/hooks/usePayroll";
import { useAuth } from "@/components/providers/AuthProvider";
import { PageHeader } from "@/components/ui/PageHeader";
import { TabGroup } from "@/components/ui/TabGroup";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { EmployeeSelect } from "@/components/payroll/EmployeeSelect";
import { formatDate } from "@/lib/utils";

const leaveSchema = z.object({
  employee_id: z.string().min(1),
  leave_type_id: z.string().min(1),
  start_date: z.string().min(1),
  end_date: z.string().min(1),
  reason: z.string().optional(),
});

type LeaveForm = z.infer<typeof leaveSchema>;

type Tab = "mine" | "pending" | "calendar";

/**
 * Leave management — employee requests, manager approvals, calendar view.
 *
 * @returns Leave management page
 */
export default function LeaveManagementPage() {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");
  const { user } = useAuth();

  const [activeTab, setActiveTab] = useState<Tab>("mine");
  const [showRequest, setShowRequest] = useState(false);
  const [newLeaveType, setNewLeaveType] = useState("");
  const [leaveFormError, setLeaveFormError] = useState<string | null>(null);

  const isManager = useMemo(
    () =>
      (user?.roles ?? []).some((r) =>
        ["manager", "hr_admin", "admin", "super_admin"].includes(r),
      ),
    [user],
  );

  const { data: myLeave } = useLeaveRequests({ employee_id: user?.id });
  const { data: pending } = useLeaveRequests({ status: "pending" });
  const { data: leaveTypes } = useLeaveTypes();

  const submit = useSubmitLeaveRequest();
  const createLeaveType = useCreateLeaveType();

  const form = useForm<LeaveForm>({
    resolver: zodResolver(leaveSchema),
    defaultValues: {
      employee_id: user?.id ?? "",
      leave_type_id: "",
      start_date: "",
      end_date: "",
      reason: "",
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    const startMs = new Date(values.start_date + "T00:00:00").getTime();
    const endMs = new Date(values.end_date + "T00:00:00").getTime();
    if (Number.isNaN(startMs) || Number.isNaN(endMs) || endMs < startMs) {
      setLeaveFormError(t("leaveDateInvalid"));
      return;
    }
    const daysRequested =
      Math.round((endMs - startMs) / (24 * 60 * 60 * 1000)) + 1;

    let leaveTypeId = values.leave_type_id;
    try {
      if (leaveTypeId === "__new__") {
        const name = newLeaveType.trim();
        if (!name) {
          setLeaveFormError(t("newLeaveTypeNameRequired"));
          return;
        }
        const created = await createLeaveType.mutateAsync({ name });
        leaveTypeId = created.id;
      }
      setLeaveFormError(null);
      submit.mutate(
        { ...values, leave_type_id: leaveTypeId, days_requested: daysRequested },
        {
          onSuccess: () => {
            form.reset();
            setShowRequest(false);
            setNewLeaveType("");
          },
          onError: (err) => {
            const detail = (err as { message?: unknown } | undefined)
              ?.message;
            setLeaveFormError(
              typeof detail === "string" ? detail : t("leaveCreateFailed"),
            );
          },
        },
      );
    } catch {
      setLeaveFormError(t("leaveCreateFailed"));
    }
  });

  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: "mine", label: t("myRequests"), count: Array.isArray(myLeave?.items) ? myLeave.items.length : 0 },
    ...(isManager
      ? [
          {
            key: "pending" as const,
            label: t("pendingApprovals"),
            count: Array.isArray(pending?.items) ? pending.items.length : 0,
          },
        ]
      : []),
    { key: "calendar", label: t("calendar") },
  ];

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <PageHeader
        icon={CalendarDays}
        title={t("leaveTitle")}
        subtitle={t("leaveSubtitle")}
        breadcrumbs={[
          { label: t("hrTitle"), href: "/hr" },
          { label: t("leave") },
        ]}
        actions={
          <button
            type="button"
            onClick={() => setShowRequest(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            {t("requestLeave")}
          </button>
        }
      />

      <TabGroup
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={(k) => setActiveTab(k as Tab)}
        variant="underline"
      />

      {activeTab === "mine" && (
        <LeaveTable items={myLeave?.items ?? []} />
      )}

      {activeTab === "pending" && isManager && (
        <PendingApprovals items={pending?.items ?? []} />
      )}

      {activeTab === "calendar" && (
        <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
          {t("calendarComingSoon")}
        </div>
      )}

      {showRequest && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setShowRequest(false)}
          role="presentation"
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={onSubmit}
            role="dialog"
            aria-modal="true"
            aria-labelledby="leave-dialog-title"
            className="w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-xl"
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 id="leave-dialog-title" className="text-lg font-semibold text-foreground">
                {t("requestLeave")}
              </h2>
              <button
                type="button"
                onClick={() => setShowRequest(false)}
                aria-label={tc("cancel")}
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted/50"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-4">
              <label className="block text-sm">
                <span className="mb-1 block text-muted-foreground">
                  {t("employee")}
                </span>
                <EmployeeSelect
                  value={form.watch("employee_id")}
                  onChange={(id) => form.setValue("employee_id", id)}
                />
                {form.formState.errors.employee_id && (
                  <span className="mt-1 block text-xs text-red-600 dark:text-red-400">
                    {form.formState.errors.employee_id.message}
                  </span>
                )}
              </label>

              <label className="block text-sm">
                <span className="mb-1 block text-muted-foreground">
                  {t("leaveType")}
                </span>
                <select
                  value={form.watch("leave_type_id")}
                  onChange={(e) => {
                    form.setValue("leave_type_id", e.target.value, {
                      shouldValidate: true,
                    });
                    if (e.target.value !== "__new__") setNewLeaveType("");
                  }}
                  className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
                >
                  <option value="">{tc("select")}</option>
                  {Array.isArray(leaveTypes) && leaveTypes.map((lt) => (
                    <option key={lt.id} value={lt.id}>
                      {lt.name}
                    </option>
                  ))}
                  <option value="__new__">{t("newLeaveType")}</option>
                </select>
                {form.watch("leave_type_id") === "__new__" && (
                  <input
                    value={newLeaveType}
                    onChange={(e) => setNewLeaveType(e.target.value)}
                    placeholder={t("newLeaveTypePlaceholder")}
                    className="mt-2 w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
                    autoFocus
                  />
                )}
                {form.formState.errors.leave_type_id && (
                  <span className="mt-1 block text-xs text-red-600 dark:text-red-400">
                    {form.formState.errors.leave_type_id.message}
                  </span>
                )}
              </label>

              <div className="grid grid-cols-2 gap-3">
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
                <label className="block text-sm">
                  <span className="mb-1 block text-muted-foreground">
                    {t("endDate")}
                  </span>
                  <input
                    type="date"
                    {...form.register("end_date")}
                    className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
                  />
                </label>
              </div>

              <label className="block text-sm">
                <span className="mb-1 block text-muted-foreground">
                  {t("reason")}
                </span>
                <textarea
                  {...form.register("reason")}
                  rows={3}
                  className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
                />
              </label>
            </div>

            {leaveFormError && (
              <p className="text-xs text-red-600 dark:text-red-400">
                {leaveFormError}
              </p>
            )}

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setShowRequest(false)}
                className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted/50"
              >
                {tc("cancel")}
              </button>
              <button
                type="submit"
                disabled={submit.isPending || createLeaveType.isPending}
                className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {tc("submit")}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

const STATUS_VARIANT: Record<
  LeaveRequestStatus,
  "default" | "success" | "warning" | "error"
> = {
  pending: "warning",
  approved: "success",
  rejected: "error",
  cancelled: "default",
};

function LeaveTable({ items }: { items: LeaveRequest[] }) {
  const t = useTranslations("payroll");
  if (!items.length) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
        {t("noLeaveRequests")}
      </div>
    );
  }
  return (
    <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-3">{t("leaveType")}</th>
              <th className="px-4 py-3">{t("dates")}</th>
              <th className="px-4 py-3">{t("days")}</th>
              <th className="px-4 py-3">{t("status")}</th>
              <th className="px-4 py-3">{t("reason")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((lr) => (
              <tr key={lr.id} className="hover:bg-muted/30">
                <td className="px-4 py-3 font-medium">
                  {lr.leave_type_name ?? "-"}
                </td>
                <td className="px-4 py-3 text-muted-foreground">
                  {formatDate(lr.start_date)} — {formatDate(lr.end_date)}
                </td>
                <td className="px-4 py-3">{lr.days_requested}</td>
                <td className="px-4 py-3">
                  <StatusBadge variant={STATUS_VARIANT[lr.status]}>
                    {t(`leaveStatus_${lr.status}`)}
                  </StatusBadge>
                </td>
                <td className="px-4 py-3 max-w-xs truncate text-muted-foreground">
                  {lr.reason ?? "-"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PendingApprovals({ items }: { items: LeaveRequest[] }) {
  const t = useTranslations("payroll");
  if (!items.length) {
    return (
      <div className="rounded-xl border border-border bg-card p-8 text-center text-muted-foreground">
        {t("noPendingLeave")}
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {items.map((lr) => (
        <PendingRow key={lr.id} request={lr} />
      ))}
    </div>
  );
}

function PendingRow({ request }: { request: LeaveRequest }) {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");
  const approve = useApproveLeaveRequest(request.id);

  const decide = (decision: "approve" | "reject") => {
    approve.mutate({ action: decision });
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
      <div>
        <p className="text-sm font-medium text-foreground">
          {request.employee_name ?? request.employee_id}
        </p>
        <p className="text-xs text-muted-foreground">
          {request.leave_type_name} • {formatDate(request.start_date)} —{" "}
          {formatDate(request.end_date)} ({request.days_requested} {t("days")})
        </p>
        {request.reason && (
          <p className="mt-1 text-xs text-muted-foreground">
            {request.reason}
          </p>
        )}
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => decide("reject")}
          disabled={approve.isPending}
          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-sm font-medium text-foreground hover:bg-muted/50 disabled:opacity-50"
        >
          <Ban className="h-4 w-4" />
          {tc("reject")}
        </button>
        <button
          type="button"
          onClick={() => decide("approve")}
          disabled={approve.isPending}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
        >
          <Check className="h-4 w-4" />
          {tc("approve")}
        </button>
      </div>
    </div>
  );
}
