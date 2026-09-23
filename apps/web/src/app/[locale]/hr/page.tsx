"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import {
  Users,
  Stethoscope,
  Heart,
  Clock,
  CalendarOff,
  AlertTriangle,
  FileText,
  Search,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useHRSummary,
  useStaffDirectory,
  useLeaveRequests,
  useShiftAssignments,
} from "@/hooks/useHR";
import { cn } from "@/lib/utils";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { TabGroup } from "@/components/ui/TabGroup";
import { DutyRosterManager } from "@/components/emergency/DutyRosterManager";

/** Role badge styling. */
const ROLE_STYLES: Record<string, string> = {
  doctor: "bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200",
  nurse: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  pharmacist: "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-200",
  lab_tech: "bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200",
  radiologist: "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200",
  admin: "bg-muted text-foreground",
  cashier: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  records: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200",
  receptionist: "bg-pink-100 text-pink-800 dark:bg-pink-950 dark:text-pink-200",
  midwife: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200",
};

/** Leave status styling. */
const LEAVE_STATUS_STYLES: Record<string, string> = {
  pending: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  approved: "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200",
  rejected: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
  cancelled: "bg-muted text-muted-foreground",
};

/**
 * HR Dashboard — staff directory, leave requests, shift roster, summary KPIs.
 *
 * @returns HR dashboard page
 */
export default function HRDashboardPage() {
  const t = useTranslations("hr");
  const tc = useTranslations("common");
  const today = new Date().toISOString().split("T")[0];

  const [activeTab, setActiveTab] = useState<"directory" | "leave" | "shifts">("directory");
  const [roleFilter, setRoleFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [leaveStatusFilter, setLeaveStatusFilter] = useState("");

  const { data: summary } = useHRSummary();
  const { data: directory, isLoading: dirLoading } = useStaffDirectory(
    roleFilter || undefined,
    undefined,
    searchQuery || undefined
  );
  const { data: leaveList } = useLeaveRequests(undefined, leaveStatusFilter || undefined);
  const { data: shifts } = useShiftAssignments(today);

  const summaryCards = [
    { label: t("totalStaff"), value: summary?.total_staff ?? 0, icon: Users, color: "blue" as const },
    { label: t("activeStaff"), value: summary?.active_staff ?? 0, icon: Users, color: "green" as const },
    { label: t("doctors"), value: summary?.doctors ?? 0, icon: Stethoscope, color: "indigo" as const },
    { label: t("nurses"), value: summary?.nurses ?? 0, icon: Heart, color: "pink" as const },
    { label: t("onDutyToday"), value: summary?.on_duty_today ?? 0, icon: Clock, color: "cyan" as const },
    { label: t("onLeaveToday"), value: summary?.on_leave_today ?? 0, icon: CalendarOff, color: "amber" as const },
    { label: t("pendingLeave"), value: summary?.pending_leave_requests ?? 0, icon: FileText, color: "orange" as const },
    { label: t("expiringContracts"), value: summary?.expiring_contracts ?? 0, icon: AlertTriangle, color: "red" as const },
  ];

  const tabs = [
    { key: "directory" as const, label: t("staffDirectory") },
    { key: "leave" as const, label: t("leaveRequests") },
    { key: "shifts" as const, label: t("shiftRoster") },
  ];

  return (
    <div className="mx-auto max-w-[1500px] animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      {/* Header */}
      <PageHeader
        icon={Users}
        title={t("title")}
        breadcrumbs={[{ label: t("title") }]}
      />

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 lg:grid-cols-8">
        {summaryCards.map((card) => (
          <StatCard
            key={card.label}
            icon={card.icon}
            label={card.label}
            value={card.value}
            color={card.color}
          />
        ))}
      </div>

      {/* Tabs */}
      <TabGroup
        tabs={tabs.map((t) => ({ key: t.key, label: t.label }))}
        activeTab={activeTab}
        onTabChange={setActiveTab as (key: string) => void}
        variant="underline"
      />

      {/* Staff Directory Tab */}
      {activeTab === "directory" && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t("searchStaff")}
                className="w-full rounded-lg border border-border bg-card py-2 pl-9 pr-3 text-sm"
              />
            </div>
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
            >
              <option value="">{t("allRoles")}</option>
              <option value="doctor">{t("roleDoctor")}</option>
              <option value="nurse">{t("roleNurse")}</option>
              <option value="pharmacist">{t("rolePharmacist")}</option>
              <option value="lab_tech">{t("roleLabTech")}</option>
              <option value="radiologist">{t("roleRadiologist")}</option>
              <option value="admin">{t("roleAdmin")}</option>
              <option value="receptionist">{t("roleReceptionist")}</option>
              <option value="midwife">{t("roleMidwife")}</option>
            </select>
          </div>

          <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
            {dirLoading ? (
              <div className="p-8 text-center text-muted-foreground">{tc("loading")}</div>
            ) : !Array.isArray(directory?.items) || !directory.items.length ? (
              <div className="p-8 text-center text-muted-foreground">{t("noStaff")}</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-4 py-3">{t("employeeNo")}</th>
                      <th className="px-4 py-3">{t("name")}</th>
                      <th className="px-4 py-3">{t("role")}</th>
                      <th className="px-4 py-3">{t("department")}</th>
                      <th className="px-4 py-3">{t("specialization")}</th>
                      <th className="px-4 py-3">{t("phone")}</th>
                      <th className="px-4 py-3">{t("license")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {directory.items.map((staff) => (
                      <tr key={staff.id} className="hover:bg-muted/50">
                        <td className="px-4 py-3">
                          <Link
                            href={`/hr/${staff.id}`}
                            className="font-medium text-blue-600 hover:underline dark:text-blue-400"
                          >
                            {staff.employee_number}
                          </Link>
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-medium text-foreground">
                            {staff.title ? `${staff.title} ` : ""}
                            {staff.first_name} {staff.last_name}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {staff.email}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
                              ROLE_STYLES[staff.role] ?? ROLE_STYLES.admin
                            )}
                          >
                            {staff.role?.replace(/_/g, " ") ?? staff.role}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-foreground">
                          {staff.department_name ?? "-"}
                        </td>
                        <td className="px-4 py-3 text-foreground">
                          {staff.specialization ?? "-"}
                        </td>
                        <td className="px-4 py-3 text-foreground">
                          {staff.phone ?? "-"}
                        </td>
                        <td className="px-4 py-3 text-muted-foreground">
                          {staff.license_number ?? "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {directory && (
              <div className="border-t border-border px-4 py-3 text-sm text-muted-foreground">
                {t("totalCount", { count: directory.total })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Leave Requests Tab */}
      {activeTab === "leave" && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <select
              value={leaveStatusFilter}
              onChange={(e) => setLeaveStatusFilter(e.target.value)}
              className="rounded-lg border border-border bg-card px-3 py-2 text-sm"
            >
              <option value="">{t("allStatuses")}</option>
              <option value="pending">{t("leavePending")}</option>
              <option value="approved">{t("leaveApproved")}</option>
              <option value="rejected">{t("leaveRejected")}</option>
            </select>
          </div>

          <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
            {!Array.isArray(leaveList?.items) || !leaveList.items.length ? (
              <div className="p-8 text-center text-muted-foreground">
                {t("noLeaveRequests")}
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="px-4 py-3">{t("staffMember")}</th>
                      <th className="px-4 py-3">{t("leaveType")}</th>
                      <th className="px-4 py-3">{t("dates")}</th>
                      <th className="px-4 py-3">{t("days")}</th>
                      <th className="px-4 py-3">{t("status")}</th>
                      <th className="px-4 py-3">{t("reason")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {leaveList.items.map((leave) => (
                      <tr key={leave.id} className="hover:bg-muted/50">
                        <td className="px-4 py-3 font-medium text-foreground">
                          {leave.staff_name ?? "-"}
                        </td>
                        <td className="px-4 py-3 text-foreground">
                          {t(`leaveType_${leave.leave_type}`)}
                        </td>
                        <td className="px-4 py-3 text-foreground">
                          {leave.start_date} — {leave.end_date}
                        </td>
                        <td className="px-4 py-3 text-foreground">
                          {leave.days_requested}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={cn(
                              "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
                              LEAVE_STATUS_STYLES[leave.status] ?? LEAVE_STATUS_STYLES.pending
                            )}
                          >
                            {t(`leaveStatus_${leave.status}`)}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-muted-foreground max-w-xs truncate">
                          {leave.reason ?? "-"}
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

      {/* Shift Roster Tab */}
      {activeTab === "shifts" && (
        <>
          <DutyRosterManager />
        <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
          {!Array.isArray(shifts?.items) || !shifts.items.length ? (
            <div className="p-8 text-center text-muted-foreground">
              {t("noShiftsToday")}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border bg-muted/30 text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-4 py-3">{t("staffMember")}</th>
                    <th className="px-4 py-3">{t("shift")}</th>
                    <th className="px-4 py-3">{t("date")}</th>
                    <th className="px-4 py-3">{t("status")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {shifts.items.map((sa) => (
                    <tr key={sa.id} className="hover:bg-muted/50">
                      <td className="px-4 py-3 font-medium text-foreground">
                        {sa.staff_name ?? "-"}
                      </td>
                      <td className="px-4 py-3 text-foreground">
                        {sa.shift_name ?? "-"}
                      </td>
                      <td className="px-4 py-3 text-foreground">
                        {sa.assignment_date}
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-block rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800 dark:bg-blue-950 dark:text-blue-200">
                          {sa.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        </>
      )}
    </div>
  );
}
