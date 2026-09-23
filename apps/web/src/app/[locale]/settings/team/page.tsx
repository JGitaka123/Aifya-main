"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { UserPlus, CheckCircle2 } from "lucide-react";
import { useStaffInvite } from "@/hooks/useOnboarding";

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
  const invite = useStaffInvite();
  const [invited, setInvited] = useState<string[]>([]);

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

  const inputClass =
    "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border dark:bg-background";

  return (
    <div className="mx-auto max-w-2xl p-6 lg:p-8">
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
    </div>
  );
}
