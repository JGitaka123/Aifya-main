"use client";

import { useState, useMemo } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  ArrowLeft,
  User,
  Wallet,
  FileText,
  CalendarDays,
  Award,
  Edit,
  X,
  Plus,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useEmployee,
  useUpdateEmployee,
  useEmployeeSalaries,
  useEmployeeSalaryChange,
  useEmployeePayslips,
  useLeaveRequests,
  useLeaveTypes,
} from "@/hooks/usePayroll";
import { useAuth } from "@/components/providers/AuthProvider";
import { TabGroup } from "@/components/ui/TabGroup";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { PayrollStatusBadge } from "@/components/payroll/PayrollStatusBadge";
import { formatKES, formatDate } from "@/lib/utils";

const profileSchema = z.object({
  full_name: z.string().min(2),
  job_title: z.string().min(2),
  bank_name: z.string().min(2),
  bank_branch: z.string().min(2),
  bank_account: z.string().min(5),
});

type ProfileForm = z.infer<typeof profileSchema>;

const salarySchema = z.object({
  effective_from: z.string().min(1),
  basic_salary: z.coerce.number().min(0),
  house_allowance: z.coerce.number().min(0),
  transport_allowance: z.coerce.number().min(0),
  other_allowances: z.coerce.number().min(0),
  approved_by: z.string().min(1),
  notes: z.string().optional(),
});

type SalaryForm = z.infer<typeof salarySchema>;

type Tab = "profile" | "salary" | "payslips" | "leave" | "performance";

/**
 * Employee detail page — tabbed view: profile, salary history, payslips, leave, performance.
 *
 * @returns Employee detail page
 */
export default function EmployeeDetailPage() {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");
  const params = useParams();
  const searchParams = useSearchParams();
  const employeeId = params.employeeId as string;

  const { user } = useAuth();
  const isHRAdmin = useMemo(
    () =>
      (user?.roles ?? []).some((r) =>
        ["hr_admin", "admin", "super_admin"].includes(r),
      ),
    [user],
  );

  const [activeTab, setActiveTab] = useState<Tab>("profile");
  const [editing, setEditing] = useState(searchParams.get("edit") === "1");
  const [salaryModal, setSalaryModal] = useState(false);

  const { data: employee, isLoading } = useEmployee(employeeId);
  const update = useUpdateEmployee(employeeId);
  const { data: salaryHistory } = useEmployeeSalaries(employeeId);
  const { data: payslips } = useEmployeePayslips(employeeId);
  const { data: leaveTypes } = useLeaveTypes();
  const { data: leaveRequests } = useLeaveRequests({
    employee_id: employeeId,
  });
  const salaryMut = useEmployeeSalaryChange(employeeId);

  const profileForm = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    values: employee
      ? {
          full_name: employee.full_name,
          job_title: employee.job_title,
          bank_name: employee.bank_name,
          bank_branch: employee.bank_branch,
          bank_account: employee.bank_account,
        }
      : undefined,
  });

  const salaryForm = useForm<SalaryForm>({
    resolver: zodResolver(salarySchema),
    defaultValues: {
      effective_from: new Date().toISOString().split("T")[0],
      basic_salary: 0,
      house_allowance: 0,
      transport_allowance: 0,
      other_allowances: 0,
      approved_by: user?.id ?? "",
      notes: "",
    },
  });

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        {tc("loading")}
      </div>
    );
  }

  if (!employee) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        {t("employeeNotFound")}
      </div>
    );
  }

  const onSaveProfile = profileForm.handleSubmit((values) => {
    update.mutate(values, { onSuccess: () => setEditing(false) });
  });

  const onSubmitSalary = salaryForm.handleSubmit((values) => {
    salaryMut.mutate(values, { onSuccess: () => setSalaryModal(false) });
  });

  const tabs: { key: Tab; label: string }[] = [
    { key: "profile", label: t("profile") },
    { key: "salary", label: t("salary") },
    { key: "payslips", label: t("payslips") },
    { key: "leave", label: t("leave") },
    { key: "performance", label: t("performance") },
  ];

  const currentSalary = salaryHistory?.[0];

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-4">
        <Link
          href="/hr/employees"
          className="rounded-lg p-2 hover:bg-muted/50"
        >
          <ArrowLeft className="h-5 w-5 text-muted-foreground" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-foreground">
            {employee.full_name}
          </h1>
          <p className="text-sm text-muted-foreground">
            {employee.staff_id} • {employee.job_title}
          </p>
        </div>
        <StatusBadge variant={employee.is_active ? "success" : "default"}>
          {employee.is_active ? t("active") : t("inactive")}
        </StatusBadge>
      </div>

      <TabGroup
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={(k) => setActiveTab(k as Tab)}
        variant="underline"
      />

      {/* Profile tab */}
      {activeTab === "profile" && (
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
              <User className="h-5 w-5" />
              {t("profile")}
            </h2>
            {isHRAdmin && !editing && (
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-sm font-medium hover:bg-muted/50"
              >
                <Edit className="h-3.5 w-3.5" />
                {tc("edit")}
              </button>
            )}
          </div>

          {editing ? (
            <form onSubmit={onSaveProfile} className="grid gap-4 sm:grid-cols-2">
              <FormField
                label={t("fullName")}
                error={profileForm.formState.errors.full_name?.message}
                {...profileForm.register("full_name")}
              />
              <div>
                <FormField
                  label={t("jobTitle")}
                  error={profileForm.formState.errors.job_title?.message}
                  {...profileForm.register("job_title")}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  {t("jobTitleHint")}
                </p>
              </div>
              <FormField
                label={t("bankName")}
                error={profileForm.formState.errors.bank_name?.message}
                {...profileForm.register("bank_name")}
              />
              <FormField
                label={t("bankBranch")}
                error={profileForm.formState.errors.bank_branch?.message}
                {...profileForm.register("bank_branch")}
              />
              <FormField
                label={t("bankAccount")}
                error={profileForm.formState.errors.bank_account?.message}
                {...profileForm.register("bank_account")}
              />
              <div className="col-span-full mt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setEditing(false)}
                  className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted/50"
                >
                  {tc("cancel")}
                </button>
                <button
                  type="submit"
                  disabled={update.isPending}
                  className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
                >
                  {tc("save")}
                </button>
              </div>
            </form>
          ) : (
            <dl className="grid gap-4 sm:grid-cols-2">
              <Info label={t("staffId")} value={employee.staff_id} />
              <Info label={t("idNumber")} value={employee.id_number} />
              <Info label={t("kraPin")} value={employee.kra_pin} />
              <Info label={t("nssfNumber")} value={employee.nssf_number} />
              <Info label={t("shifNumber")} value={employee.shif_number} />
              <Info
                label={t("employmentType")}
                value={t(`employmentType_${employee.employment_type}`)}
              />
              <Info
                label={t("hireDate")}
                value={formatDate(employee.hire_date)}
              />
              <Info
                label={t("disabilityExemption")}
                value={employee.disability_exemption ? tc("yes") : tc("no")}
              />
              <Info label={t("bankName")} value={employee.bank_name} />
              <Info label={t("bankBranch")} value={employee.bank_branch} />
              <Info label={t("bankAccount")} value={employee.bank_account} />
              {employee.termination_date && (
                <Info
                  label={t("terminationDate")}
                  value={formatDate(employee.termination_date)}
                />
              )}
            </dl>
          )}
        </div>
      )}

      {/* Salary tab */}
      {activeTab === "salary" && (
        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
                <Wallet className="h-5 w-5" />
                {t("currentSalary")}
              </h2>
              {isHRAdmin && (
                <button
                  type="button"
                  onClick={() => setSalaryModal(true)}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90"
                >
                  <Plus className="h-3.5 w-3.5" />
                  {t("changeSalary")}
                </button>
              )}
            </div>

            {currentSalary ? (
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <SalaryStat
                  label={t("basicSalary")}
                  value={currentSalary.basic_salary}
                />
                <SalaryStat
                  label={t("houseAllowance")}
                  value={currentSalary.house_allowance}
                />
                <SalaryStat
                  label={t("transportAllowance")}
                  value={currentSalary.transport_allowance}
                />
                <SalaryStat
                  label={t("otherAllowances")}
                  value={currentSalary.other_allowances}
                />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                {t("noSalaryRecord")}
              </p>
            )}
          </div>

          <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
            <div className="border-b border-border px-4 py-3">
              <h3 className="text-sm font-semibold text-foreground">
                {t("salaryHistory")}
              </h3>
            </div>
            {!salaryHistory?.length ? (
              <div className="p-8 text-center text-muted-foreground">
                {t("noSalaryHistory")}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-4 py-3">{t("effectiveFrom")}</th>
                      <th className="px-4 py-3 text-right">
                        {t("basicSalary")}
                      </th>
                      <th className="px-4 py-3 text-right">
                        {t("houseAllowance")}
                      </th>
                      <th className="px-4 py-3 text-right">
                        {t("transportAllowance")}
                      </th>
                      <th className="px-4 py-3 text-right">
                        {t("otherAllowances")}
                      </th>
                      <th className="px-4 py-3 text-right">{t("total")}</th>
                      <th className="px-4 py-3">{t("approvedBy")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {salaryHistory.map((s) => {
                      const total =
                        s.basic_salary +
                        s.house_allowance +
                        s.transport_allowance +
                        s.other_allowances;
                      return (
                        <tr key={s.id} className="hover:bg-muted/30">
                          <td className="px-4 py-3 font-medium">
                            {formatDate(s.effective_from)}
                          </td>
                          <td className="px-4 py-3 text-right tabular-nums">
                            {formatKES(s.basic_salary * 100)}
                          </td>
                          <td className="px-4 py-3 text-right tabular-nums">
                            {formatKES(s.house_allowance * 100)}
                          </td>
                          <td className="px-4 py-3 text-right tabular-nums">
                            {formatKES(s.transport_allowance * 100)}
                          </td>
                          <td className="px-4 py-3 text-right tabular-nums">
                            {formatKES(s.other_allowances * 100)}
                          </td>
                          <td className="px-4 py-3 text-right tabular-nums font-semibold">
                            {formatKES(total * 100)}
                          </td>
                          <td className="px-4 py-3 text-muted-foreground">
                            {s.approved_by ?? "-"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Payslips tab */}
      {activeTab === "payslips" && (
        <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <FileText className="h-4 w-4" />
              {t("payslips")}
            </h2>
            <Link
              href={`/hr/employees/${employeeId}/payslips`}
              className="text-xs font-medium text-primary hover:underline"
            >
              {t("openSelfService")}
            </Link>
          </div>
          {!payslips?.length ? (
            <div className="p-8 text-center text-muted-foreground">
              {t("noPayslips")}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">{t("period")}</th>
                    <th className="px-4 py-3">{t("status")}</th>
                    <th className="px-4 py-3 text-right">{t("gross")}</th>
                    <th className="px-4 py-3 text-right">{t("net")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {payslips.map((p) => (
                    <tr key={p.id} className="hover:bg-muted/30">
                      <td className="px-4 py-3 font-medium">
                        {p.month}/{p.year}
                      </td>
                      <td className="px-4 py-3">
                        <PayrollStatusBadge status={p.status} />
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {formatKES(p.gross_salary * 100)}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums font-semibold">
                        {formatKES(p.net_salary * 100)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Leave tab */}
      {activeTab === "leave" && (
        <div className="space-y-4">
          {leaveTypes && leaveTypes.length > 0 && (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {leaveTypes.map((lt) => (
                <div
                  key={lt.id}
                  className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]"
                >
                  <p className="text-xs font-medium text-muted-foreground">
                    {lt.name}
                  </p>
                  <p className="mt-1 text-2xl font-bold tabular-nums text-foreground">
                    {lt.days_entitlement}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {t("daysEntitlement")}
                  </p>
                </div>
              ))}
            </div>
          )}

          <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
            <div className="border-b border-border px-4 py-3">
              <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <CalendarDays className="h-4 w-4" />
                {t("leaveHistory")}
              </h2>
            </div>
            {!leaveRequests?.items?.length ? (
              <div className="p-8 text-center text-muted-foreground">
                {t("noLeaveHistory")}
              </div>
            ) : (
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
                    {leaveRequests.items.map((lr) => (
                      <tr key={lr.id} className="hover:bg-muted/30">
                        <td className="px-4 py-3 font-medium">
                          {lr.leave_type_name ?? "-"}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {formatDate(lr.start_date)} —{" "}
                          {formatDate(lr.end_date)}
                        </td>
                        <td className="px-4 py-3">{lr.days_requested}</td>
                        <td className="px-4 py-3">
                          <StatusBadge
                            variant={
                              lr.status === "approved"
                                ? "success"
                                : lr.status === "rejected"
                                  ? "error"
                                  : lr.status === "cancelled"
                                    ? "default"
                                    : "warning"
                            }
                          >
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
            )}
          </div>
        </div>
      )}

      {/* Performance tab */}
      {activeTab === "performance" && (
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
            <Award className="h-5 w-5" />
            {t("performance")}
          </h2>
          <p className="text-sm text-muted-foreground">
            {t("performanceComingSoon")}
          </p>
        </div>
      )}

      {/* Salary change modal */}
      {salaryModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setSalaryModal(false)}
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={onSubmitSalary}
            className="w-full max-w-2xl rounded-xl border border-border bg-card p-6 shadow-xl"
          >
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-foreground">
                {t("changeSalary")}
              </h2>
              <button
                type="button"
                onClick={() => setSalaryModal(false)}
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted/50"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <FormField
                label={t("effectiveFrom")}
                type="date"
                error={salaryForm.formState.errors.effective_from?.message}
                {...salaryForm.register("effective_from")}
              />
              <FormField
                label={t("approverField")}
                error={salaryForm.formState.errors.approved_by?.message}
                {...salaryForm.register("approved_by")}
              />
              <FormField
                label={t("basicSalary")}
                type="number"
                error={salaryForm.formState.errors.basic_salary?.message}
                {...salaryForm.register("basic_salary")}
              />
              <FormField
                label={t("houseAllowance")}
                type="number"
                error={salaryForm.formState.errors.house_allowance?.message}
                {...salaryForm.register("house_allowance")}
              />
              <FormField
                label={t("transportAllowance")}
                type="number"
                error={
                  salaryForm.formState.errors.transport_allowance?.message
                }
                {...salaryForm.register("transport_allowance")}
              />
              <FormField
                label={t("otherAllowances")}
                type="number"
                error={salaryForm.formState.errors.other_allowances?.message}
                {...salaryForm.register("other_allowances")}
              />
              <label className="col-span-full block text-sm">
                <span className="mb-1 block text-muted-foreground">
                  {t("notes")}
                </span>
                <textarea
                  {...salaryForm.register("notes")}
                  rows={2}
                  className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
                />
              </label>
            </div>

            <div className="mt-6 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setSalaryModal(false)}
                className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium hover:bg-muted/50"
              >
                {tc("cancel")}
              </button>
              <button
                type="submit"
                disabled={salaryMut.isPending}
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

const Info = ({ label, value }: { label: string; value: string }) => (
  <div>
    <dt className="text-xs uppercase text-muted-foreground">{label}</dt>
    <dd className="font-medium text-foreground">{value}</dd>
  </div>
);

const SalaryStat = ({ label, value }: { label: string; value: number }) => (
  <div className="rounded-lg bg-muted/30 p-3">
    <p className="text-xs text-muted-foreground">{label}</p>
    <p className="mt-1 text-lg font-bold tabular-nums text-foreground">
      {formatKES(value * 100)}
    </p>
  </div>
);

interface FormFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

const FormField = ({ label, error, ...rest }: FormFieldProps) => (
  <label className="block text-sm">
    <span className="mb-1 block text-muted-foreground">{label}</span>
    <input
      {...rest}
      className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
    />
    {error && (
      <span className="mt-1 block text-xs text-red-600 dark:text-red-400">
        {error}
      </span>
    )}
  </label>
);
