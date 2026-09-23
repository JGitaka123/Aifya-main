"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { useOfflineMutation } from "@/hooks/useOfflineMutation";
import { generateId } from "@/lib/utils";

const API_URL = "/api/v1";

// ── Types ─────────────────────────────────────────────────────────────────

export type EmploymentType =
  | "permanent"
  | "contract"
  | "casual"
  | "intern";
export type PayrollRunStatus = "draft" | "approved" | "posted" | "locked";

export type LeaveRequestStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "cancelled";

export interface Employee {
  id: string;
  staff_id: string;
  full_name: string;
  id_number: string;
  kra_pin: string;
  nssf_number: string;
  shif_number: string;
  department_id: string | null;
  department_name?: string | null;
  job_title: string;
  employment_type: EmploymentType;
  hire_date: string;
  termination_date?: string | null;
  is_active: boolean;
  bank_name: string;
  bank_branch: string;
  bank_account: string;
  disability_exemption: boolean;
}

export interface EmployeeListResponse {
  items: Employee[];
  total: number;
}

export interface EmployeeFilters {
  department_id?: string;
  employment_type?: EmploymentType;
  is_active?: boolean;
  search?: string;
  page?: number;
  page_size?: number;
}

export interface EmployeeCreate {
  staff_id: string;
  full_name: string;
  id_number?: string;
  kra_pin?: string;
  nssf_number?: string;
  shif_number?: string;
  department_id?: string | null;
  job_title?: string;
  employment_type: EmploymentType;
  hire_date: string;
  bank_name?: string;
  bank_branch?: string;
  bank_account?: string;
  disability_exemption?: boolean;
  basic_salary?: number;
  house_allowance?: number;
  transport_allowance?: number;
  other_allowances?: number;
}

export interface EmployeeUpdate {
  full_name?: string;
  job_title?: string;
  employment_type?: EmploymentType;
  department_id?: string | null;
  bank_name?: string;
  bank_branch?: string;
  bank_account?: string;
  disability_exemption?: boolean;
  termination_date?: string | null;
  is_active?: boolean;
}

export interface SalaryRecord {
  id: string;
  employee_id: string;
  effective_from: string;
  basic_salary: number;
  house_allowance: number;
  transport_allowance: number;
  other_allowances: number;
  approved_by?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface SalaryChange {
  effective_from: string;
  basic_salary: number;
  house_allowance: number;
  transport_allowance: number;
  other_allowances: number;
  approved_by: string;
  notes?: string;
}

export interface PayrollRun {
  id: string;
  month: number;
  year: number;
  status: PayrollRunStatus;
  run_date: string;
  approved_by?: string | null;
  approved_at?: string | null;
  gl_transaction_id?: string | null;
  total_gross: number;
  total_paye: number;
  total_nssf: number;
  total_shif: number;
  total_hl: number;
  total_net: number;
}

export interface PayrollRunListResponse {
  items: PayrollRun[];
  total: number;
}

export interface PayrollLineItem {
  id: string;
  employee_id: string;
  employee_name: string;
  staff_id?: string;
  department_name?: string | null;
  basic_salary: number;
  house_allowance: number;
  transport_allowance: number;
  other_allowances: number;
  gross_salary: number;
  nssf_employee: number;
  shif: number;
  housing_levy: number;
  taxable_pay: number;
  paye_gross: number;
  personal_relief: number;
  paye: number;
  other_deductions: number;
  total_deductions: number;
  net_salary: number;
}

export interface PayrollRunDetail extends PayrollRun {
  line_items: PayrollLineItem[];
}

export interface PayrollRunCreate {
  month: number;
  year: number;
}

export interface EmployeePayslipSummary {
  id: string;
  run_id: string;
  month: number;
  year: number;
  gross_salary: number;
  net_salary: number;
  total_deductions: number;
  paye: number;
  status: PayrollRunStatus;
}

export interface P9MonthRow {
  month: number;
  basic_salary: number;
  benefits: number;
  gross_pay: number;
  defined_contribution_retirement: number;
  affordable_housing_levy: number;
  shif_contribution: number;
  taxable_pay: number;
  paye: number;
  personal_relief: number;
  insurance_relief: number;
  paye_payable: number;
}

export interface P9Report {
  employee_id: string;
  employee_name: string;
  kra_pin: string;
  year: number;
  rows: P9MonthRow[];
  totals: P9MonthRow;
}

export interface PAYEScheduleRow {
  employee_id: string;
  employee_name: string;
  kra_pin: string;
  taxable_pay: number;
  paye: number;
}

export interface PAYESchedule {
  month: number;
  year: number;
  rows: PAYEScheduleRow[];
  total_taxable: number;
  total_paye: number;
}

export interface NSSFScheduleRow {
  employee_id: string;
  employee_name: string;
  nssf_number: string;
  pensionable_pay: number;
  employee_contribution: number;
  employer_contribution: number;
  total: number;
}

export interface NSSFSchedule {
  month: number;
  year: number;
  rows: NSSFScheduleRow[];
  total_employee: number;
  total_employer: number;
  total: number;
}

export interface SHIFScheduleRow {
  employee_id: string;
  employee_name: string;
  shif_number: string;
  gross_salary: number;
  contribution: number;
}

export interface SHIFSchedule {
  month: number;
  year: number;
  rows: SHIFScheduleRow[];
  total: number;
}

export interface HeadcountBucket {
  label: string;
  count: number;
}

export interface HeadcountReport {
  as_of: string;
  total: number;
  by_department: HeadcountBucket[];
  by_employment_type: HeadcountBucket[];
}

export interface LeaveUtilisationRow {
  employee_id: string;
  employee_name: string;
  leave_type: string;
  entitlement: number;
  used: number;
  remaining: number;
}

export interface LeaveUtilisationReport {
  rows: LeaveUtilisationRow[];
}

export interface CostTrendPoint {
  month: number;
  year: number;
  label: string;
  gross: number;
  net: number;
  paye: number;
  statutory: number;
}

export interface CostTrendReport {
  year: number;
  points: CostTrendPoint[];
}

export interface TurnoverPoint {
  period: string;
  joiners: number;
  leavers: number;
}

export interface TurnoverReport {
  period_start: string;
  period_end: string;
  hires: number;
  terminations: number;
  ending_headcount: number;
  points: TurnoverPoint[];
}

export interface StatutoryRate {
  id: string;
  facility_id?: string | null;
  name: string;
  category: string;
  rate?: number | null;
  fixed_amount?: number | null;
  fixed_cap?: number | null;
  effective_from: string;
  effective_to?: string | null;
  approved_by?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface StatutoryRateCreate {
  name: string;
  category: string;
  rate?: number | null;
  fixed_amount?: number | null;
  fixed_cap?: number | null;
  effective_from: string;
  effective_to?: string | null;
  notes?: string;
}

export interface PAYEBand {
  id: string;
  facility_id?: string | null;
  lower_limit: number;
  upper_limit?: number | null;
  rate: number;
  effective_from: string;
  effective_to?: string | null;
}

export interface NSSFTier {
  id: string;
  facility_id?: string | null;
  tier: string;
  lower_limit: number;
  upper_limit: number;
  employee_rate: number;
  employer_rate: number;
  effective_from: string;
  effective_to?: string | null;
}

export interface LeaveType {
  id: string;
  name: string;
  days_entitlement: number;
  paid: boolean;
  carries_over: boolean;
  max_carryover?: number | null;
}

export interface LeaveRequest {
  id: string;
  employee_id: string;
  employee_name?: string;
  leave_type_id: string;
  leave_type_name?: string;
  start_date: string;
  end_date: string;
  days_requested: number;
  reason?: string | null;
  status: LeaveRequestStatus;
  approved_by?: string | null;
  approved_at?: string | null;
  created_at: string;
}

export interface LeaveRequestListResponse {
  items: LeaveRequest[];
  total: number;
}

export interface LeaveRequestCreate {
  employee_id: string;
  leave_type_id: string;
  start_date: string;
  end_date: string;
  days_requested: number;
  reason?: string;
}

export interface LeaveApproval {
  action: "approve" | "reject";
  rejection_reason?: string | null;
}

export type DepartmentType = "clinical" | "support" | "admin";

export interface Department {
  id: string;
  code: string;
  name: string;
  description?: string | null;
  department_type: DepartmentType;
  parent_id?: string | null;
  head_of_department_id?: string | null;
  is_active: boolean;
}

export interface DepartmentCreate {
  code: string;
  name: string;
  description?: string;
  department_type?: DepartmentType;
  parent_id?: string | null;
  head_of_department_id?: string | null;
  is_active?: boolean;
}

// ── Departments ───────────────────────────────────────────────────────────

/**
 * Fetch the facility's departments (the cost centres payroll groups by).
 *
 * @param includeInactive - Include deactivated departments
 * @returns Query result with departments ordered by name
 */
export function useDepartments(includeInactive = false) {
  return useOfflineQuery<Department[]>({
    queryKey: ["payroll", "departments", includeInactive],
    queryFn: () =>
      apiClient.get<Department[]>(
        `/payroll/departments${includeInactive ? "?include_inactive=true" : ""}`,
      ),
  });
}

/**
 * Create a department.
 *
 * @returns Mutation for creating a department
 */
export function useCreateDepartment() {
  const qc = useQueryClient();
  return useOfflineMutation<Department, DepartmentCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<Department>("/payroll/departments", data, generateId()),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["payroll", "departments"] });
      },
    },
    { url: `${API_URL}/payroll/departments`, method: "POST" },
  );
}

// ── Employees ─────────────────────────────────────────────────────────────

/**
 * Fetch employees with filtering.
 *
 * @param filters - Optional filters for the employee list
 * @returns Query result with list of employees
 */
export function useEmployees(filters: EmployeeFilters = {}) {
  const params: Record<string, string> = {};
  if (filters.department_id) params.department_id = filters.department_id;
  if (filters.employment_type) params.employment_type = filters.employment_type;
  if (filters.is_active !== undefined) params.is_active = String(filters.is_active);
  if (filters.search) params.search = filters.search;
  if (filters.page) params.page = String(filters.page);
  if (filters.page_size) params.page_size = String(filters.page_size);

  const qs = new URLSearchParams(params).toString();

  return useOfflineQuery<EmployeeListResponse>({
    queryKey: ["payroll", "employees", filters],
    queryFn: () =>
      apiClient.get<EmployeeListResponse>(
        `/payroll/employees${qs ? `?${qs}` : ""}`,
      ),
  });
}

/**
 * Fetch a single employee by ID.
 *
 * @param employeeId - Employee UUID
 * @returns Query result with employee detail
 */
export function useEmployee(employeeId?: string) {
  return useOfflineQuery<Employee>({
    queryKey: ["payroll", "employee", employeeId],
    queryFn: () =>
      apiClient.get<Employee>(`/payroll/employees/${employeeId}`),
    enabled: !!employeeId,
  });
}

/**
 * Create a new employee record.
 *
 * @returns Mutation for creating an employee
 */
export function useCreateEmployee() {
  const qc = useQueryClient();
  return useOfflineMutation<Employee, EmployeeCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<Employee>("/payroll/employees", data, generateId()),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["payroll", "employees"] });
      },
    },
    { url: `${API_URL}/payroll/employees`, method: "POST" },
  );
}

/**
 * Update an existing employee.
 *
 * @param employeeId - Employee UUID to update
 * @returns Mutation for updating employee profile
 */
export function useUpdateEmployee(employeeId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<Employee, EmployeeUpdate>(
    {
      mutationFn: (data) =>
        apiClient.patch<Employee>(
          `/payroll/employees/${employeeId}`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["payroll", "employees"] });
        qc.invalidateQueries({
          queryKey: ["payroll", "employee", employeeId],
        });
      },
    },
    {
      url: `${API_URL}/payroll/employees/${employeeId}`,
      method: "PATCH",
    },
  );
}

/**
 * Submit a new salary record (HR admin only).
 *
 * @param employeeId - Employee UUID
 * @returns Mutation for changing the salary
 */
export function useEmployeeSalaryChange(employeeId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<SalaryRecord, SalaryChange>(
    {
      mutationFn: (data) =>
        apiClient.post<SalaryRecord>(
          `/payroll/employees/${employeeId}/salaries`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({
          queryKey: ["payroll", "employee", employeeId],
        });
        qc.invalidateQueries({
          queryKey: ["payroll", "employee", employeeId, "salaries"],
        });
      },
    },
    {
      url: `${API_URL}/payroll/employees/${employeeId}/salaries`,
      method: "POST",
    },
  );
}

/**
 * Fetch salary history for an employee.
 *
 * @param employeeId - Employee UUID
 * @returns Query result with salary records
 */
export function useEmployeeSalaries(employeeId?: string) {
  return useOfflineQuery<SalaryRecord[]>({
    queryKey: ["payroll", "employee", employeeId, "salaries"],
    queryFn: () =>
      apiClient.get<SalaryRecord[]>(
        `/payroll/employees/${employeeId}/salaries`,
      ),
    enabled: !!employeeId,
  });
}

/**
 * Fetch payslips for a single employee (self-service view).
 *
 * @param employeeId - Employee UUID
 * @returns Query result with payslip summaries
 */
export function useEmployeePayslips(employeeId?: string) {
  return useOfflineQuery<EmployeePayslipSummary[]>({
    queryKey: ["payroll", "employee", employeeId, "payslips"],
    queryFn: () =>
      apiClient.get<EmployeePayslipSummary[]>(
        `/payroll/employees/${employeeId}/payslips`,
      ),
    enabled: !!employeeId,
  });
}

// ── Payroll Runs ──────────────────────────────────────────────────────────

/**
 * Fetch payroll runs filtered by year/month.
 *
 * @param filters - Optional year and month filters
 * @returns Query result with runs
 */
export function usePayrollRuns(filters: { year?: number; month?: number } = {}) {
  const params: Record<string, string> = {};
  if (filters.year) params.year = String(filters.year);
  if (filters.month) params.month = String(filters.month);
  const qs = new URLSearchParams(params).toString();

  return useOfflineQuery<PayrollRunListResponse>({
    queryKey: ["payroll", "runs", filters],
    queryFn: () =>
      apiClient.get<PayrollRunListResponse>(
        `/payroll/runs${qs ? `?${qs}` : ""}`,
      ),
    refetchInterval: 30_000,
  });
}

/**
 * Fetch a single payroll run with line items.
 *
 * @param runId - Payroll run UUID
 * @returns Query result with the run and its line items
 */
export function usePayrollRun(runId?: string) {
  return useOfflineQuery<PayrollRunDetail>({
    queryKey: ["payroll", "run", runId],
    queryFn: () =>
      apiClient.get<PayrollRunDetail>(`/payroll/runs/${runId}`),
    enabled: !!runId,
  });
}

/**
 * Create a draft payroll run.
 *
 * @returns Mutation for creating a new run
 */
export function useCreatePayrollRun() {
  const qc = useQueryClient();
  return useOfflineMutation<PayrollRun, PayrollRunCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<PayrollRun>("/payroll/runs", data, generateId()),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["payroll", "runs"] });
      },
    },
    { url: `${API_URL}/payroll/runs`, method: "POST" },
  );
}

/**
 * Approve a draft payroll run (finance admin only).
 *
 * @param runId - Payroll run UUID
 * @returns Mutation for approving the run
 */
export function useApprovePayrollRun(runId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<PayrollRun, { approved_by: string }>(
    {
      mutationFn: (data) =>
        apiClient.post<PayrollRun>(
          `/payroll/runs/${runId}/approve`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["payroll", "runs"] });
        qc.invalidateQueries({ queryKey: ["payroll", "run", runId] });
      },
    },
    { url: `${API_URL}/payroll/runs/${runId}/approve`, method: "POST" },
  );
}

/**
 * Recalculate a draft payroll run (re-runs the engine on draft).
 *
 * @param runId - Payroll run UUID
 * @returns Mutation for recalculating the run
 */
export function useRecalculatePayrollRun(runId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<PayrollRun, void>(
    {
      mutationFn: () =>
        apiClient.post<PayrollRun>(
          `/payroll/runs/${runId}/recalculate`,
          {},
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["payroll", "run", runId] });
      },
    },
    {
      url: `${API_URL}/payroll/runs/${runId}/recalculate`,
      method: "POST",
    },
  );
}

/**
 * Fetch a payslip PDF and return an object URL for inline display/download.
 * The blob is fetched lazily; the URL is revoked on unmount.
 *
 * @param runId - Payroll run UUID
 * @param employeeId - Employee UUID
 * @returns Object URL string and lifecycle helpers
 */
export function usePayslipPDF(runId?: string, employeeId?: string) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!runId || !employeeId) {
      return;
    }

    let cancelled = false;
    let createdUrl: string | null = null;
    setIsLoading(true);
    setError(null);

    fetch(
      `${API_URL}/payroll/runs/${runId}/payslip/${employeeId}`,
      { credentials: "include" },
    )
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Failed to fetch payslip: ${response.statusText}`);
        }
        const blob = await response.blob();
        if (cancelled) return;
        createdUrl = window.URL.createObjectURL(blob);
        setObjectUrl(createdUrl);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoading(false);
        }
      });

    return () => {
      cancelled = true;
      if (createdUrl) {
        window.URL.revokeObjectURL(createdUrl);
      }
    };
  }, [runId, employeeId]);

  return { objectUrl, isLoading, error };
}

// ── Reports ───────────────────────────────────────────────────────────────

/**
 * Fetch the annual P9 return for an employee.
 *
 * @param employeeId - Employee UUID
 * @param year - Year (4-digit)
 * @returns Query result with P9 report
 */
export function useP9(employeeId?: string, year?: number) {
  return useOfflineQuery<P9Report>({
    queryKey: ["payroll", "p9", employeeId, year],
    queryFn: () =>
      apiClient.get<P9Report>(
        `/payroll/reports/p9/${employeeId}?year=${year}`,
      ),
    enabled: !!employeeId && !!year,
  });
}

/**
 * Fetch the monthly PAYE schedule.
 *
 * @param month - Month (1-12)
 * @param year - Year (4-digit)
 * @returns Query result with PAYE schedule
 */
export function usePAYESchedule(month?: number, year?: number) {
  return useOfflineQuery<PAYESchedule>({
    queryKey: ["payroll", "paye-schedule", month, year],
    queryFn: () =>
      apiClient.get<PAYESchedule>(
        `/payroll/reports/paye-schedule?month=${month}&year=${year}`,
      ),
    enabled: !!month && !!year,
  });
}

/**
 * Fetch the monthly NSSF schedule.
 *
 * @param month - Month (1-12)
 * @param year - Year (4-digit)
 * @returns Query result with NSSF schedule
 */
export function useNSSFSchedule(month?: number, year?: number) {
  return useOfflineQuery<NSSFSchedule>({
    queryKey: ["payroll", "nssf-schedule", month, year],
    queryFn: () =>
      apiClient.get<NSSFSchedule>(
        `/payroll/reports/nssf-schedule?month=${month}&year=${year}`,
      ),
    enabled: !!month && !!year,
  });
}

/**
 * Fetch the monthly SHIF schedule.
 *
 * @param month - Month (1-12)
 * @param year - Year (4-digit)
 * @returns Query result with SHIF schedule
 */
export function useSHIFSchedule(month?: number, year?: number) {
  return useOfflineQuery<SHIFSchedule>({
    queryKey: ["payroll", "shif-schedule", month, year],
    queryFn: () =>
      apiClient.get<SHIFSchedule>(
        `/payroll/reports/shif-schedule?month=${month}&year=${year}`,
      ),
    enabled: !!month && !!year,
  });
}

/**
 * Fetch the headcount report (by department, employment type, gender).
 *
 * @returns Query result with headcount report
 */
export function useHeadcountReport() {
  return useOfflineQuery<HeadcountReport>({
    queryKey: ["payroll", "report", "headcount"],
    queryFn: () =>
      apiClient.get<HeadcountReport>("/payroll/reports/headcount"),
  });
}

/**
 * Fetch leave utilisation per employee.
 *
 * @returns Query result with leave utilisation
 */
export function useLeaveUtilisation() {
  return useOfflineQuery<LeaveUtilisationReport>({
    queryKey: ["payroll", "report", "leave-utilisation"],
    queryFn: () =>
      apiClient.get<LeaveUtilisationReport>(
        `/payroll/reports/leave-utilisation?year=${new Date().getFullYear()}`,
      ),
  });
}

/**
 * Fetch monthly payroll cost trend (rolling).
 *
 * @returns Query result with cost trend points
 */
export function useCostTrend() {
  return useOfflineQuery<CostTrendReport>({
    queryKey: ["payroll", "report", "cost-trend"],
    queryFn: () =>
      apiClient.get<CostTrendReport>(`/payroll/reports/cost-trend?year=${new Date().getFullYear()}`),
  });
}

/**
 * Fetch the joiners/leavers turnover trend.
 *
 * @param year - Optional calendar year; defaults to the current year
 * @returns Query result with turnover summary and points
 */
export function useTurnover(year?: number) {
  return useOfflineQuery<TurnoverReport>({
    queryKey: ["payroll", "report", "turnover", year],
    queryFn: () =>
      apiClient.get<TurnoverReport>(
        `/payroll/reports/turnover${year ? `?year=${year}` : ""}`,
      ),
  });
}

// ── Statutory Configuration ──────────────────────────────────────────────

/**
 * Fetch all statutory rates (current + history).
 *
 * @returns Query result with statutory rates
 */
export function useStatutoryRates() {
  return useOfflineQuery<StatutoryRate[]>({
    queryKey: ["payroll", "statutory-rates"],
    queryFn: () =>
      apiClient.get<StatutoryRate[]>("/payroll/statutory-rates"),
  });
}

/**
 * Add a new statutory rate (creates a new effective_from record; never mutates history).
 *
 * @returns Mutation for creating a statutory rate
 */
export function useCreateStatutoryRate() {
  const qc = useQueryClient();
  return useOfflineMutation<StatutoryRate, StatutoryRateCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<StatutoryRate>(
          "/payroll/statutory-rates",
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["payroll", "statutory-rates"] });
        qc.invalidateQueries({ queryKey: ["payroll", "paye-bands"] });
      },
    },
    { url: `${API_URL}/payroll/statutory-rates`, method: "POST" },
  );
}

/**
 * Fetch active PAYE bands.
 *
 * @returns Query result with PAYE bands
 */
export function usePAYEBands() {
  return useOfflineQuery<PAYEBand[]>({
    queryKey: ["payroll", "paye-bands"],
    queryFn: () => apiClient.get<PAYEBand[]>("/payroll/paye-bands"),
  });
}

/**
 * Fetch the active NSSF tiers (Tier I and Tier II).
 *
 * @returns Query result with NSSF tiers
 */
export function useNSSFTiers() {
  return useOfflineQuery<NSSFTier[]>({
    queryKey: ["payroll", "nssf-tiers"],
    queryFn: () => apiClient.get<NSSFTier[]>("/payroll/nssf-tiers"),
  });
}

// ── Leave ────────────────────────────────────────────────────────────────

/**
 * Fetch leave types configured for the facility.
 *
 * @returns Query result with leave types
 */
export function useLeaveTypes() {
  return useOfflineQuery<LeaveType[]>({
    queryKey: ["payroll", "leave-types"],
    queryFn: () => apiClient.get<LeaveType[]>("/payroll/leave-types"),
  });
}

/**
 * Create a new leave type (e.g. typed on the fly from the Leave tab).
 *
 * @returns Mutation for creating a leave type
 */
export function useCreateLeaveType() {
  const qc = useQueryClient();
  return useOfflineMutation<LeaveType, { name: string }>(
    {
      mutationFn: (data) =>
        apiClient.post<LeaveType>("/payroll/leave-types", data, generateId()),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["payroll", "leave-types"] });
      },
    },
    { url: "/api/v1/payroll/leave-types", method: "POST" },
  );
}

/**
 * Fetch payroll module leave requests.
 *
 * @param filters - Optional filters (employee, status)
 * @returns Query result with leave requests
 */
export function useLeaveRequests(
  filters: { employee_id?: string; status?: LeaveRequestStatus } = {},
) {
  const params: Record<string, string> = {};
  if (filters.employee_id) params.employee_id = filters.employee_id;
  if (filters.status) params.status = filters.status;
  const qs = new URLSearchParams(params).toString();

  return useOfflineQuery<LeaveRequestListResponse>({
    queryKey: ["payroll", "leave-requests", filters],
    queryFn: () =>
      apiClient.get<LeaveRequestListResponse>(
        `/payroll/leave-requests${qs ? `?${qs}` : ""}`,
      ),
    refetchInterval: 30_000,
  });
}

/**
 * Submit a leave request.
 *
 * @returns Mutation for submitting leave
 */
export function useSubmitLeaveRequest() {
  const qc = useQueryClient();
  return useOfflineMutation<LeaveRequest, LeaveRequestCreate>(
    {
      mutationFn: (data) =>
        apiClient.post<LeaveRequest>(
          "/payroll/leave-requests",
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["payroll", "leave-requests"] });
      },
    },
    { url: `${API_URL}/payroll/leave-requests`, method: "POST" },
  );
}

/**
 * Approve or reject a leave request.
 *
 * @param leaveId - Leave request UUID
 * @returns Mutation for processing leave decision
 */
export function useApproveLeaveRequest(leaveId: string) {
  const qc = useQueryClient();
  return useOfflineMutation<LeaveRequest, LeaveApproval>(
    {
      mutationFn: (data) =>
        apiClient.post<LeaveRequest>(
          `/payroll/leave-requests/${leaveId}/approve`,
          data,
          generateId(),
        ),
      onSuccess: () => {
        qc.invalidateQueries({ queryKey: ["payroll", "leave-requests"] });
      },
    },
    {
      url: `${API_URL}/payroll/leave-requests/${leaveId}/approve`,
      method: "POST",
    },
  );
}
