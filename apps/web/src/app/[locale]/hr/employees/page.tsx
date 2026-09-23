"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Users, Plus, Search, X, Eye, Edit, FileText } from "lucide-react";
import { Link } from "@/i18n/routing";
import { apiClient } from "@/lib/api-client";
import { generateId } from "@/lib/utils";
import {
  useEmployees,
  useCreateEmployee,
  useDepartments,
  useCreateDepartment,
  type DepartmentType,
  type EmploymentType,
} from "@/hooks/usePayroll";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { HelpTooltip } from "@/components/help/HelpTooltip";

const EMPLOYMENT_TYPES: EmploymentType[] = [
  "permanent",
  "contract",
  "casual",
  "intern",
];

const DEPARTMENT_TYPES: DepartmentType[] = ["clinical", "support", "admin"];

const employeeSchema = z.object({
  staff_id: z.string().min(1),
  full_name: z.string().min(2),
  id_number: z.string().min(5).optional(),
  kra_pin: z.string().min(5).optional(),
  nssf_number: z.string().min(2).optional(),
  shif_number: z.string().min(2).optional(),
  job_title: z.string().min(2).optional(),
  employment_type: z.enum([
    "permanent",
    "contract",
    "casual",
    "intern",
  ]),
  department_id: z.string().optional(),
  hire_date: z.string().min(1),
  email: z.string().email().optional().or(z.literal("")),
  phone: z.string().optional(),
  bank_name: z.string().min(2).optional(),
  bank_branch: z.string().min(2).optional(),
  bank_account: z.string().min(5).optional(),
  disability_exemption: z.boolean().default(false),
  basic_salary: z.coerce.number().min(0),
  house_allowance: z.coerce.number().min(0),
  transport_allowance: z.coerce.number().min(0),
  other_allowances: z.coerce.number().min(0),
});

type EmployeeForm = z.infer<typeof employeeSchema>;

/**
 * Employee Master List — searchable, filterable, with multi-section create modal.
 *
 * @returns Employee list page
 */
export default function EmployeesListPage() {
  const t = useTranslations("payroll");
  const tc = useTranslations("common");

  const [search, setSearch] = useState("");
  const [employmentTypeFilter, setEmploymentTypeFilter] = useState<
    EmploymentType | ""
  >("");
  const [activeFilter, setActiveFilter] = useState<"all" | "active" | "inactive">(
    "active",
  );
  const [showCreate, setShowCreate] = useState(false);

  const { data, isLoading } = useEmployees({
    search: search || undefined,
    employment_type: employmentTypeFilter || undefined,
    is_active:
      activeFilter === "all"
        ? undefined
        : activeFilter === "active"
          ? true
          : false,
  });

  const create = useCreateEmployee();
  const { data: departments } = useDepartments();
  const createDepartment = useCreateDepartment();
  const [createError, setCreateError] = useState<string | null>(null);
  const [showNewDept, setShowNewDept] = useState(false);
  const [newDeptName, setNewDeptName] = useState("");
  const [newDeptType, setNewDeptType] = useState<DepartmentType>("clinical");
  const [deptError, setDeptError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<EmployeeForm>({
    resolver: zodResolver(employeeSchema),
    defaultValues: {
      employment_type: "permanent",
      disability_exemption: false,
      basic_salary: 0,
      house_allowance: 0,
      transport_allowance: 0,
      other_allowances: 0,
    },
  });

  const handleCreateDepartment = async () => {
    setDeptError(null);
    const name = newDeptName.trim();
    const code =
      name.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 12) || "DEPT";
    if (!name) {
      setDeptError(t("departmentNameRequired"));
      return;
    }
    try {
      const created = await createDepartment.mutateAsync({
        code,
        name,
        department_type: newDeptType,
      });
      setValue("department_id", created.id);
      setShowNewDept(false);
      setNewDeptName("");
      setNewDeptType("clinical");
    } catch (err) {
      setDeptError(
        err instanceof Error ? err.message : t("departmentCreateFailed"),
      );
    }
  };

  const onSubmit = handleSubmit(async (values) => {
    setCreateError(null);
    const opt = (value?: string) => (value && value.trim() ? value.trim() : undefined);
    const payload = {
      staff_id: values.staff_id.trim(),
      full_name: values.full_name.trim(),
      employment_type: values.employment_type,
      hire_date: values.hire_date,
      disability_exemption: values.disability_exemption,
      id_number: opt(values.id_number),
      kra_pin: opt(values.kra_pin),
      nssf_number: opt(values.nssf_number),
      shif_number: opt(values.shif_number),
      job_title: opt(values.job_title),
      department_id: values.department_id || undefined,
      email: values.email || undefined,
      phone: values.phone || undefined,
      bank_name: opt(values.bank_name),
      bank_branch: opt(values.bank_branch),
      bank_account: opt(values.bank_account),
      basic_salary: values.basic_salary ?? 0,
      house_allowance: values.house_allowance ?? 0,
      transport_allowance: values.transport_allowance ?? 0,
      other_allowances: values.other_allowances ?? 0,
    };
    try {
      const employee = await create.mutateAsync(payload);
      const hasSalary =
        (values.basic_salary ?? 0) > 0 ||
        (values.house_allowance ?? 0) > 0 ||
        (values.transport_allowance ?? 0) > 0 ||
        (values.other_allowances ?? 0) > 0;
      if (hasSalary && employee?.id) {
        await apiClient.post(
          `/payroll/employees/${employee.id}/salaries`,
          {
            effective_from: employee.hire_date || values.hire_date,
            basic_salary: values.basic_salary ?? 0,
            house_allowance: values.house_allowance ?? 0,
            transport_allowance: values.transport_allowance ?? 0,
            other_allowances: {},
          },
          generateId()
        );
      }
      reset();
      setShowCreate(false);
      setCreateError(null);
    } catch (err) {
      setCreateError(
        err instanceof Error ? err.message : "Failed to add the employee."
      );
    }
  });

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      <PageHeader
        icon={Users}
        title={t("employeesTitle")}
        subtitle={t("employeesSubtitle")}
        breadcrumbs={[
          { label: t("hrTitle"), href: "/hr" },
          { label: t("employees") },
        ]}
        actions={
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
          >
            <Plus className="h-4 w-4" />
            {t("addEmployee")}
          </button>
        }
      />

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-60">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t("searchEmployee")}
            className="w-full rounded-lg border border-border bg-card py-2 pl-9 pr-3 text-sm"
          />
        </div>
        <select
          value={employmentTypeFilter}
          onChange={(e) =>
            setEmploymentTypeFilter(e.target.value as EmploymentType | "")
          }
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
        >
          <option value="">{t("allEmploymentTypes")}</option>
          {EMPLOYMENT_TYPES.map((et) => (
            <option key={et} value={et}>
              {t(`employmentType_${et}`)}
            </option>
          ))}
        </select>
        <select
          value={activeFilter}
          onChange={(e) =>
            setActiveFilter(e.target.value as "all" | "active" | "inactive")
          }
          className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
        >
          <option value="active">{t("activeOnly")}</option>
          <option value="inactive">{t("inactiveOnly")}</option>
          <option value="all">{tc("all")}</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
        {isLoading ? (
          <div className="p-8 text-center text-muted-foreground">
            {tc("loading")}
          </div>
        ) : !Array.isArray(data?.items) || !data.items.length ? (
          <div className="p-8 text-center text-muted-foreground">
            {t("noEmployees")}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                <tr>
                  <th className="px-4 py-3">{t("staffId")}</th>
                  <th className="px-4 py-3">{t("name")}</th>
                  <th className="px-4 py-3">{t("jobTitle")}</th>
                  <th className="px-4 py-3">{t("department")}</th>
                  <th className="px-4 py-3">{t("employmentType")}</th>
                  <th className="px-4 py-3">{t("status")}</th>
                  <th className="px-4 py-3 text-right">{tc("actions")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.items.map((emp) => (
                  <tr key={emp.id} className="hover:bg-muted/30">
                    <td className="px-4 py-3 font-medium text-foreground">
                      <Link
                        href={`/hr/employees/${emp.id}`}
                        className="text-primary hover:underline"
                      >
                        {emp.staff_id}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-foreground">
                      {emp.full_name}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {emp.job_title}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {emp.department_name ?? "-"}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge variant="info">
                        {t(`employmentType_${emp.employment_type}`)}
                      </StatusBadge>
                    </td>
                    <td className="px-4 py-3">
                      {emp.is_active ? (
                        <StatusBadge variant="success">
                          {t("active")}
                        </StatusBadge>
                      ) : (
                        <StatusBadge variant="default">
                          {t("inactive")}
                        </StatusBadge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          href={`/hr/employees/${emp.id}`}
                          className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-2 py-1 text-xs font-medium hover:bg-muted/50"
                        >
                          <Eye className="h-3 w-3" />
                          {tc("view")}
                        </Link>
                        <Link
                          href={`/hr/employees/${emp.id}?edit=1`}
                          className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-2 py-1 text-xs font-medium hover:bg-muted/50"
                        >
                          <Edit className="h-3 w-3" />
                          {tc("edit")}
                        </Link>
                        <Link
                          href={`/hr/employees/${emp.id}/payslips`}
                          className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-2 py-1 text-xs font-medium hover:bg-muted/50"
                        >
                          <FileText className="h-3 w-3" />
                          {t("payslips")}
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {data && Array.isArray(data.items) && (
          <div className="border-t border-border px-4 py-3 text-xs text-muted-foreground">
            {t("totalEmployees", { count: data.total })}
          </div>
        )}
      </div>

      {/* Create modal */}
      {showCreate && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
          onClick={() => setShowCreate(false)}
          role="presentation"
        >
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={onSubmit}
            role="dialog"
            aria-modal="true"
            aria-labelledby="employee-dialog-title"
            className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-border bg-card shadow-xl"
          >
            <div className="flex items-center justify-between border-b border-border p-4">
              <h2 id="employee-dialog-title" className="text-lg font-semibold text-foreground">
                {t("addEmployee")}
              </h2>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                aria-label={tc("cancel")}
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted/50"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-6 overflow-y-auto p-6">
              {createError && (
                <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm font-medium text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-400">
                  {createError}
                </div>
              )}
              {/* Personal */}
              <section>
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("personal")}
                </h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field
                    label={t("staffId")}
                    error={errors.staff_id?.message}
                    {...register("staff_id")}
                  />
                  <Field
                    label={t("fullName")}
                    error={errors.full_name?.message}
                    {...register("full_name")}
                  />
                  <Field
                    label={t("idNumber")}
                    error={errors.id_number?.message}
                    {...register("id_number")}
                  />
                  <Field
                    label={t("hireDate")}
                    type="date"
                    error={errors.hire_date?.message}
                    {...register("hire_date")}
                  />
                  <Field
                    label="Email"
                    type="email"
                    placeholder="samuel.mutua@aifya.co.ke"
                    {...register("email")}
                  />
                  <Field
                    label="Phone"
                    placeholder="+254700000013"
                    {...register("phone")}
                  />
                </div>
              </section>

              {/* Statutory */}
              <section>
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("statutoryIds")}
                </h3>
                <div className="grid gap-4 sm:grid-cols-3">
                  <Field
                    label={t("kraPin")}
                    error={errors.kra_pin?.message}
                    help={t("help.kraPin")}
                    placeholder="A009658233G"
                    {...register("kra_pin")}
                  />
                  <Field
                    label={t("nssfNumber")}
                    error={errors.nssf_number?.message}
                    help={t("help.nssfNumber")}
                    placeholder="2017197738"
                    {...register("nssf_number")}
                  />
                  <Field
                    label={t("shifNumber")}
                    error={errors.shif_number?.message}
                    help={t("help.shifNumber")}
                    placeholder="CR1620021837701-1"
                    {...register("shif_number")}
                  />
                </div>
                <label className="mt-3 flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    {...register("disability_exemption")}
                    className="rounded border-border"
                  />
                  <span className="text-foreground inline-flex items-center">
                    {t("disabilityExemption")}
                    <HelpTooltip content={t("help.disabilityExemption")} />
                  </span>
                </label>
              </section>

              {/* Employment */}
              <section>
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("employment")}
                </h3>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div>
                    <Field
                      label={t("jobTitle")}
                      error={errors.job_title?.message}
                      {...register("job_title")}
                    />
                    <p className="mt-1 text-xs text-muted-foreground">
                      {t("jobTitleHint")}
                    </p>
                  </div>
                  <label className="block text-sm">
                    <span className="mb-1 block text-muted-foreground">
                      {t("employmentType")}
                    </span>
                    <select
                      {...register("employment_type")}
                      className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
                    >
                      {EMPLOYMENT_TYPES.map((et) => (
                        <option key={et} value={et}>
                          {t(`employmentType_${et}`)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div>
                    <label className="block text-sm">
                      <span className="mb-1 block text-muted-foreground">
                        {t("department")}
                      </span>
                      <select
                        {...register("department_id")}
                        className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
                      >
                        <option value="">{t("selectDepartment")}</option>
                        {(departments ?? []).map((dept) => (
                          <option key={dept.id} value={dept.id}>
                            {dept.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      onClick={() => setShowNewDept((v) => !v)}
                      className="mt-1 text-xs font-medium text-primary hover:underline"
                    >
                      {showNewDept ? tc("cancel") : t("createDepartment")}
                    </button>
                  </div>
                </div>

                {showNewDept && (
                  <div className="mt-3 grid gap-3 rounded-lg border border-dashed border-border bg-muted/20 p-3 sm:grid-cols-[1fr_auto_auto]">
                    <input
                      type="text"
                      value={newDeptName}
                      onChange={(e) => setNewDeptName(e.target.value)}
                      placeholder={t("departmentName")}
                      className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
                    />
                    <select
                      value={newDeptType}
                      onChange={(e) =>
                        setNewDeptType(e.target.value as DepartmentType)
                      }
                      className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
                    >
                      {DEPARTMENT_TYPES.map((dt) => (
                        <option key={dt} value={dt}>
                          {t(`departmentType_${dt}`)}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={handleCreateDepartment}
                      disabled={createDepartment.isPending}
                      className="rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
                    >
                      {tc("save")}
                    </button>
                    {deptError && (
                      <p className="text-xs text-red-600 dark:text-red-400 sm:col-span-3">
                        {deptError}
                      </p>
                    )}
                  </div>
                )}
              </section>

              {/* Bank */}
              <section>
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("bankDetails")}
                </h3>
                <div className="grid gap-4 sm:grid-cols-3">
                  <Field
                    label={t("bankName")}
                    error={errors.bank_name?.message}
                    {...register("bank_name")}
                  />
                  <Field
                    label={t("bankBranch")}
                    error={errors.bank_branch?.message}
                    {...register("bank_branch")}
                  />
                  <Field
                    label={t("bankAccount")}
                    error={errors.bank_account?.message}
                    {...register("bank_account")}
                  />
                </div>
              </section>

              {/* Salary */}
              <section>
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  {t("salaryStructure")} (KES)
                </h3>
                <div className="grid gap-4 sm:grid-cols-4">
                  <Field
                    label={t("basicSalary")}
                    type="number"
                    error={errors.basic_salary?.message}
                    {...register("basic_salary")}
                  />
                  <Field
                    label={t("houseAllowance")}
                    type="number"
                    error={errors.house_allowance?.message}
                    {...register("house_allowance")}
                  />
                  <Field
                    label={t("transportAllowance")}
                    type="number"
                    error={errors.transport_allowance?.message}
                    {...register("transport_allowance")}
                  />
                  <Field
                    label={t("otherAllowances")}
                    type="number"
                    error={errors.other_allowances?.message}
                    {...register("other_allowances")}
                  />
                </div>
              </section>
            </div>

            <div className="flex justify-end gap-2 border-t border-border bg-muted/20 p-4">
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
              >
                {tc("cancel")}
              </button>
              <button
                type="submit"
                disabled={create.isPending}
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {create.isPending && (
                  <span
                    aria-hidden
                    className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-current border-t-transparent"
                  />
                )}
                {tc("save")}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

interface FieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  /** Optional contextual help shown via a `?` tooltip next to the label. */
  help?: React.ReactNode;
}

const Field = ({ label, error, help, ...rest }: FieldProps) => (
  <label className="block text-sm">
    <span className="mb-1 block text-muted-foreground">
      <span className="inline-flex items-center">
        {label}
        {help && <HelpTooltip content={help} />}
      </span>
    </span>
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
