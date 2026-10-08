"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  ArrowLeft,
  User,
  MapPin,
  Shield,
  Calendar,
  CalendarCheck,
  Briefcase,
  Heart,
  GraduationCap,
  ShieldCheck,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import { useStaffDirectory, useStaffProfile } from "@/hooks/useHR";
import { useEmployees, useLeaveRequests } from "@/hooks/usePayroll";
import { StaffAccessDialog } from "@/components/hr/StaffAccessDialog";
import { StaffAvailabilityPanel } from "@/components/hr/StaffAvailabilityPanel";
import type { StaffDirectoryItem } from "@aifya/shared";
import { formatDate } from "@/lib/utils";

/**
 * Staff Detail Page — extended profile with employment, qualifications,
 * leave balances, emergency contact, and statutory info.
 *
 * @returns Staff detail page
 */
export default function StaffDetailPage() {
  const t = useTranslations("hr");
  const tc = useTranslations("common");
  const params = useParams();
  const staffId = params.staffId as string;

  const { data: profile, isLoading } = useStaffProfile(staffId);

  // Leave is recorded against the payroll employee row, which is linked to the
  // staff register through employees.staff_id === staff.employee_number.
  //
  // Deactivated staff are included: this is the page HR lands on to switch an
  // account back on, so the row has to be here even when access is off.
  const { data: directory } = useStaffDirectory(
    undefined,
    undefined,
    undefined,
    true
  );
  const member: StaffDirectoryItem | undefined = useMemo(
    () => directory?.items?.find((item) => item.id === staffId),
    [directory, staffId],
  );
  const employeeNumber = member?.employee_number;
  const [accessOpen, setAccessOpen] = useState(false);
  const { data: employees } = useEmployees({ page_size: 200 });
  const employeeId = useMemo(
    () => employees?.items?.find((e) => e.staff_id === employeeNumber)?.id,
    [employees, employeeNumber],
  );
  const { data: staffLeave } = useLeaveRequests(
    employeeId ? { employee_id: employeeId } : {},
    Boolean(employeeId),
  );

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        {tc("loading")}
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        {t("profileNotFound")}
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6 lg:p-8 animate-[fade-in_0.3s_ease-out]">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/hr"
          className="rounded-lg p-2 hover:bg-muted/50"
        >
          <ArrowLeft className="h-5 w-5 text-muted-foreground" />
        </Link>
        <h1 className="text-2xl font-bold text-foreground">
          {t("staffProfile")}
        </h1>
        {member && (
          <button
            type="button"
            onClick={() => setAccessOpen(true)}
            className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
          >
            <ShieldCheck className="h-4 w-4" />
            {t("systemAccess")}
          </button>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Personal Info */}
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
            <User className="h-5 w-5" />
            {t("personalInfo")}
          </h2>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            {profile.date_of_birth && (
              <div>
                <dt className="text-muted-foreground">{t("dateOfBirth")}</dt>
                <dd className="font-medium text-foreground">{profile.date_of_birth}</dd>
              </div>
            )}
            {profile.gender && (
              <div>
                <dt className="text-muted-foreground">{t("gender")}</dt>
                <dd className="font-medium text-foreground capitalize">{profile.gender}</dd>
              </div>
            )}
            {profile.national_id && (
              <div>
                <dt className="text-muted-foreground">{t("nationalId")}</dt>
                <dd className="font-medium text-foreground">{profile.national_id}</dd>
              </div>
            )}
            {profile.address && (
              <div className="col-span-2">
                <dt className="flex items-center gap-1 text-muted-foreground">
                  <MapPin className="h-3.5 w-3.5" />
                  {t("address")}
                </dt>
                <dd className="font-medium text-foreground">
                  {profile.address}
                  {profile.sub_county && `, ${profile.sub_county}`}
                  {profile.county && `, ${profile.county}`}
                </dd>
              </div>
            )}
          </dl>
        </div>

        {/* Employment */}
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
            <Briefcase className="h-5 w-5" />
            {t("employmentInfo")}
          </h2>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-muted-foreground">{t("employmentType")}</dt>
              <dd className="font-medium text-foreground capitalize">
                {profile.employment_type}
              </dd>
            </div>
            {profile.employment_date && (
              <div>
                <dt className="text-muted-foreground">{t("employmentDate")}</dt>
                <dd className="font-medium text-foreground">{profile.employment_date}</dd>
              </div>
            )}
            {profile.contract_end_date && (
              <div>
                <dt className="text-muted-foreground">{t("contractEnd")}</dt>
                <dd className="font-medium text-foreground">{profile.contract_end_date}</dd>
              </div>
            )}
            {profile.probation_end_date && (
              <div>
                <dt className="text-muted-foreground">{t("probationEnd")}</dt>
                <dd className="font-medium text-foreground">{profile.probation_end_date}</dd>
              </div>
            )}
          </dl>
        </div>

        {/* Statutory Info */}
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
            <Shield className="h-5 w-5" />
            {t("statutoryInfo")}
          </h2>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            {profile.kra_pin && (
              <div>
                <dt className="text-muted-foreground">{t("kraPin")}</dt>
                <dd className="font-medium text-foreground">{profile.kra_pin}</dd>
              </div>
            )}
            {profile.nhif_number && (
              <div>
                <dt className="text-muted-foreground">{t("nhif")}</dt>
                <dd className="font-medium text-foreground">{profile.nhif_number}</dd>
              </div>
            )}
            {profile.nssf_number && (
              <div>
                <dt className="text-muted-foreground">{t("nssf")}</dt>
                <dd className="font-medium text-foreground">{profile.nssf_number}</dd>
              </div>
            )}
          </dl>
        </div>

        {/* Leave Balances */}
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
            <Calendar className="h-5 w-5" />
            {t("leaveBalances")}
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div className="rounded-lg bg-blue-50 p-3 dark:bg-blue-950/30">
              <p className="text-xl font-bold text-blue-800 dark:text-blue-200">
                {profile.annual_leave_balance}
              </p>
              <p className="text-xs text-blue-600 dark:text-blue-400">{t("annualLeave")}</p>
            </div>
            <div className="rounded-lg bg-orange-50 p-3 dark:bg-orange-950/30">
              <p className="text-xl font-bold text-orange-800 dark:text-orange-200">
                {profile.sick_leave_balance}
              </p>
              <p className="text-xs text-orange-600 dark:text-orange-400">{t("sickLeave")}</p>
            </div>
            <div className="rounded-lg bg-pink-50 p-3 dark:bg-pink-950/30">
              <p className="text-xl font-bold text-pink-800 dark:text-pink-200">
                {profile.maternity_leave_balance}
              </p>
              <p className="text-xs text-pink-600 dark:text-pink-400">{t("maternityLeave")}</p>
            </div>
            <div className="rounded-lg bg-indigo-50 p-3 dark:bg-indigo-950/30">
              <p className="text-xl font-bold text-indigo-800 dark:text-indigo-200">
                {profile.paternity_leave_balance}
              </p>
              <p className="text-xs text-indigo-600 dark:text-indigo-400">{t("paternityLeave")}</p>
            </div>
          </div>
        </div>

        {/* Leave Requests */}
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)] lg:col-span-2">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
              <CalendarCheck className="h-5 w-5" />
              {t("leaveRequests")}
            </h2>
            <Link
              href="/hr/leave"
              className="text-sm font-medium text-primary hover:underline"
            >
              {t("manageLeave")}
            </Link>
          </div>
          {!employeeId ? (
            <p className="text-sm text-muted-foreground">
              {t("notLinkedToPayroll")}
            </p>
          ) : !staffLeave?.items?.length ? (
            <p className="text-sm text-muted-foreground">
              {t("noLeaveRequests")}
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2">{t("leaveType")}</th>
                    <th className="px-3 py-2">{t("dates")}</th>
                    <th className="px-3 py-2">{t("days")}</th>
                    <th className="px-3 py-2">{t("status")}</th>
                    <th className="px-3 py-2">{t("reason")}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {staffLeave.items.map((leave) => (
                    <tr key={leave.id}>
                      <td className="px-3 py-2 font-medium text-foreground">
                        {leave.leave_type_name ?? "-"}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground">
                        {formatDate(leave.start_date)} — {formatDate(leave.end_date)}
                      </td>
                      <td className="px-3 py-2 text-foreground">
                        {leave.days_requested}
                      </td>
                      <td className="px-3 py-2">
                        <span className="inline-block rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-foreground">
                          {t(`leaveStatus_${leave.status}`)}
                        </span>
                      </td>
                      <td className="max-w-xs truncate px-3 py-2 text-muted-foreground">
                        {leave.reason ?? "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Work Schedule / Current Availability */}
        <StaffAvailabilityPanel staffId={staffId} />

        {/* Emergency Contact */}
        {profile.emergency_contact_name && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
              <Heart className="h-5 w-5" />
              {t("emergencyContact")}
            </h2>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-muted-foreground">{t("name")}</dt>
                <dd className="font-medium text-foreground">
                  {profile.emergency_contact_name}
                </dd>
              </div>
              {profile.emergency_contact_phone && (
                <div>
                  <dt className="text-muted-foreground">{t("phone")}</dt>
                  <dd className="font-medium text-foreground">
                    {profile.emergency_contact_phone}
                  </dd>
                </div>
              )}
              {profile.emergency_contact_relationship && (
                <div>
                  <dt className="text-muted-foreground">{t("relationship")}</dt>
                  <dd className="font-medium text-foreground">
                    {profile.emergency_contact_relationship}
                  </dd>
                </div>
              )}
            </dl>
          </div>
        )}

        {/* Qualifications */}
        {profile.qualifications && profile.qualifications.length > 0 && (
          <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground">
              <GraduationCap className="h-5 w-5" />
              {t("qualifications")}
            </h2>
            <div className="space-y-3">
              {profile.qualifications.map((q, idx) => (
                <div
                  key={idx}
                  className="rounded-lg bg-muted/30 p-3"
                >
                  <p className="font-medium text-foreground">
                    {q.degree || q.name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {q.institution} {q.year ? `(${q.year})` : ""}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <StaffAccessDialog
        staff={accessOpen ? member ?? null : null}
        onClose={() => setAccessOpen(false)}
      />
    </div>
  );
}
