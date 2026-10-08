"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  UserPlus,
  CheckCircle2,
  Users,
  Loader2,
  ShieldCheck,
} from "lucide-react";
import { useStaffInvite } from "@/hooks/useOnboarding";
import { useStaffDirectory, useSetStaffActive } from "@/hooks/useSettings";
import { StaffAccessDialog } from "@/components/hr/StaffAccessDialog";
import type { StaffDirectoryItem } from "@aifya/shared";

const ROLES = [
  "facility_admin",
  "doctor",
  "nurse",
  "midwife",
  "clinician",
  "pharmacist",
  "lab_tech",
  "cashier",
  "billing_officer",
  "records",
  "receptionist",
  "radiologist",
] as const;

const inviteSchema = z.object({
  first_name: z.string().min(1).max(100),
  last_name: z.string().min(1).max(100),
  email: z.string().email().max(255),
  role: z.enum(ROLES),
});

type InviteFormData = z.infer<typeof inviteSchema>;

/**
 * Staff invite (QA auth): a facility admin invites a colleague; the backend
 * provisions the Keycloak user (role + facility) and emails a set-password link.
 *
 * @returns Team / staff-invite page
 */
export default function TeamPage() {
  const t = useTranslations("team");
  const tc = useTranslations("common");
  const invite = useStaffInvite();
  const [invited, setInvited] = useState<string[]>([]);
  const directory = useStaffDirectory();
  const setActive = useSetStaffActive();
  // HR issues the credentials, so the row opens the same access dialog the HR
  // directory uses: role, activation and password in one place.
  const [accessStaff, setAccessStaff] = useState<StaffDirectoryItem | null>(
    null,
  );
  // Confirmation shown after switching an account on or off. Activation is
  // where the employee is emailed, so HR is told whether that message went out.
  const [statusNotice, setStatusNotice] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<InviteFormData>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { role: "nurse" },
  });

  const onSubmit = async (data: InviteFormData) => {
    try {
      const res = await invite.mutateAsync(data);
      setInvited((prev) => [res.email, ...prev]);
      reset({ role: "nurse" });
    } catch {
      // surfaced below
    }
  };

  const toggleActive = async (member: StaffDirectoryItem) => {
    setStatusNotice(null);
    try {
      const updated = await setActive.mutateAsync({
        staffId: member.id,
        isActive: !member.is_active,
      });
      if (updated.activation_email_sent) {
        setStatusNotice(t("activationEmailSent", { email: member.email }));
      }
    } catch {
      // surfaced below
    }
  };

  const inputClass =
    "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border dark:bg-background";

  return (
    <div className="mx-auto max-w-4xl p-6 lg:p-8">
      <h1 className="mb-1 flex items-center gap-2 text-2xl font-bold text-foreground">
        <UserPlus className="h-6 w-6 text-primary" />
        {t("title")}
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">{t("subtitle")}</p>

      <form
        onSubmit={handleSubmit(onSubmit)}
        className="space-y-4 rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]"
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("firstName")} *
            </label>
            <input {...register("first_name")} className={inputClass} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("lastName")} *
            </label>
            <input {...register("last_name")} className={inputClass} />
          </div>
        </div>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("email")} *
            </label>
            <input {...register("email")} type="email" className={inputClass} />
            {errors.email && (
              <p className="mt-0.5 text-xs text-red-500">{t("invalidEmail")}</p>
            )}
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("role")} *
            </label>
            <select {...register("role")} className={inputClass}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </div>
        </div>

        {invite.isError && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {invite.error?.message || t("inviteError")}
          </div>
        )}

        <button
          type="submit"
          disabled={isSubmitting || invite.isPending}
          className="rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-50"
        >
          {invite.isPending ? t("sending") : t("sendInvite")}
        </button>
      </form>

      {invited.length > 0 && (
        <div className="mt-6 rounded-xl border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-950">
          <p className="mb-2 text-sm font-medium text-green-800 dark:text-green-200">
            {t("invitedHeading")}
          </p>
          <ul className="space-y-1 text-sm text-green-700 dark:text-green-300">
            {invited.map((email, i) => (
              <li key={i} className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4" />
                {email}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Staff directory: every account in the facility, active or not, so an
          administrator can deactivate a leaver or restore an account. */}
      <div className="mt-8">
        <h2 className="mb-1 flex items-center gap-2 text-lg font-semibold text-foreground">
          <Users className="h-5 w-5 text-primary" />
          {t("directoryTitle")}
        </h2>
        <p className="mb-4 text-sm text-muted-foreground">
          {t("directorySubtitle")}
        </p>

        {directory.isLoading ? (
          <div className="flex items-center gap-2 rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            {tc("loading")}
          </div>
        ) : directory.isError ? (
          <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
            {t("directoryError")}
          </div>
        ) : (directory.data?.items?.length ?? 0) === 0 ? (
          <p className="rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
            {t("directoryEmpty")}
          </p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
            <table className="w-full text-sm">
              <thead className="border-b border-border bg-muted/30">
                <tr>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t("colName")}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t("colRole")}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t("colDepartment")}
                  </th>
                  <th className="px-4 py-3 text-left font-medium text-muted-foreground">
                    {t("colStatus")}
                  </th>
                  <th className="px-4 py-3 text-right font-medium text-muted-foreground">
                    {t("colActions")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {(directory.data?.items ?? []).map((member) => (
                  <tr key={member.id} className="border-b border-border last:border-0">
                    <td className="px-4 py-3">
                      <div className="font-medium text-foreground">
                        {[member.title, member.first_name, member.last_name]
                          .filter(Boolean)
                          .join(" ")}
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {member.employee_number} &middot; {member.email}
                      </div>
                    </td>
                    <td className="px-4 py-3 capitalize text-foreground">
                      {member.role.replace(/_/g, " ")}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {member.department_name ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={
                          member.is_active
                            ? "rounded-md bg-green-100 px-2 py-0.5 text-xs font-medium text-green-800 dark:bg-green-950 dark:text-green-200"
                            : "rounded-md bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground"
                        }
                      >
                        {member.is_active ? t("statusActive") : t("statusInactive")}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setAccessStaff(member)}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
                        >
                          <ShieldCheck className="h-3.5 w-3.5" />
                          {t("manageAccess")}
                        </button>
                        <button
                          type="button"
                          disabled={setActive.isPending}
                          onClick={() => toggleActive(member)}
                          className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted disabled:opacity-50"
                        >
                          {member.is_active ? t("deactivate") : t("activate")}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {statusNotice && (
          <div className="mt-3 rounded-lg border border-green-300 bg-green-50 p-3 text-sm text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200">
            {statusNotice}
          </div>
        )}

        {setActive.isError && (
          <div className="mt-3 rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {t("statusError")}
          </div>
        )}
      </div>

      <StaffAccessDialog
        staff={accessStaff}
        onClose={() => setAccessStaff(null)}
      />
    </div>
  );
}
