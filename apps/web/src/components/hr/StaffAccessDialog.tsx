"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { KeyRound, ShieldCheck, X } from "lucide-react";
import type { StaffDirectoryItem, StaffRole } from "@aifya/shared";
import {
  useAssignableRoles,
  useSetStaffActive,
  useSetStaffPassword,
  useSetStaffRole,
} from "@/hooks/useHR";
import { StatusBadge } from "@/components/ui/StatusBadge";

interface StaffAccessDialogProps {
  /** The staff member whose access is being edited, or null when closed. */
  staff: StaffDirectoryItem | null;
  /** Close the dialog. */
  onClose: () => void;
}

/**
 * Grant, change and revoke one employee's Aifya access.
 *
 * The three controls map to the three questions HR asks about access: which
 * role does this person hold (what they may open), may they sign in at all
 * (activation), and what is their password (how they get in). The role list
 * comes from the API, so it can never offer a role the server would refuse.
 *
 * @param props.staff - Staff member being edited, or null when closed
 * @param props.onClose - Closes the dialog
 * @returns The access dialog, or null when nothing is selected
 */
export function StaffAccessDialog({ staff, onClose }: StaffAccessDialogProps) {
  const t = useTranslations("hr");
  const tc = useTranslations("common");
  const { data: roles } = useAssignableRoles();
  const setRole = useSetStaffRole();
  const setActive = useSetStaffActive();
  const setLoginPassword = useSetStaffPassword();

  const [role, setRoleValue] = useState<StaffRole | "">("");
  const [password, setPassword] = useState("");
  // Tracked locally as well: the row this dialog was opened from is a
  // snapshot, so after switching access off the badge would otherwise keep
  // reporting the state the employee had when HR clicked.
  const [isActive, setIsActive] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Re-seed the form whenever a different employee is opened.
  useEffect(() => {
    setRoleValue(staff?.role ?? "");
    setPassword("");
    setIsActive(staff?.is_active ?? true);
    setNotice(null);
    setError(null);
  }, [staff]);

  if (!staff) return null;

  const busy =
    setRole.isPending || setActive.isPending || setLoginPassword.isPending;

  const run = async (action: () => Promise<unknown>) => {
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("accessUpdateFailed"));
    }
  };

  const saveRole = () =>
    run(async () => {
      if (!role) return;
      await setRole.mutateAsync({ staffId: staff.id, data: { role } });
      setNotice(t("roleUpdated"));
    });

  const toggleActive = () =>
    run(async () => {
      const next = !isActive;
      const updated = await setActive.mutateAsync({
        staffId: staff.id,
        isActive: next,
      });
      setIsActive(next);
      if (next && updated.activation_email_sent) {
        setNotice(t("activationEmailSent", { email: staff.email }));
      } else {
        setNotice(next ? t("accessGranted") : t("accessRevoked"));
      }
    });

  const savePassword = () =>
    run(async () => {
      const result = await setLoginPassword.mutateAsync({
        staffId: staff.id,
        data: { password },
      });
      setPassword("");
      if (result.activation_email_sent) {
        setNotice(t("activationEmailSent", { email: staff.email }));
      } else {
        setNotice(t("passwordUpdated"));
      }
    });

  const currentLabel =
    (roles?.items ?? []).find((option) => option.role === staff.role)?.label ??
    staff.role;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="staff-access-title"
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-lg overflow-hidden rounded-xl border border-border bg-card shadow-xl"
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <h2
            id="staff-access-title"
            className="flex items-center gap-2 text-lg font-semibold text-foreground"
          >
            <ShieldCheck className="h-5 w-5" />
            {t("systemAccess")}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={tc("cancel")}
            className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted/50"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-5 p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-foreground">
                {staff.first_name} {staff.last_name}
              </p>
              <p className="text-xs text-muted-foreground">
                {staff.email} - {currentLabel}
              </p>
            </div>
            <StatusBadge variant={isActive ? "success" : "default"}>
              {isActive ? t("active") : t("inactive")}
            </StatusBadge>
          </div>

          {(notice || error) && (
            <p
              className={
                error
                  ? "rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-400"
                  : "rounded-lg border border-green-300 bg-green-50 p-3 text-sm text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200"
              }
            >
              {error ?? notice}
            </p>
          )}

          {/* Role */}
          <div>
            <label className="block text-sm">
              <span className="mb-1 block text-muted-foreground">
                {t("role")}
              </span>
              <select
                value={role}
                onChange={(event) =>
                  setRoleValue(event.target.value as StaffRole)
                }
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
              >
                <option value="">{t("selectRole")}</option>
                {(roles?.items ?? []).map((option) => (
                  <option key={option.role} value={option.role}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="mt-2 flex justify-end">
              <button
                type="button"
                onClick={saveRole}
                disabled={busy || !role || role === staff.role}
                className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {t("saveRole")}
              </button>
            </div>
          </div>

          {/* Activation */}
          <div className="flex items-center justify-between gap-3 rounded-lg border border-border p-3">
            <p className="text-sm text-muted-foreground">
              {isActive ? t("deactivateHint") : t("activateHint")}
            </p>
            <button
              type="button"
              onClick={toggleActive}
              disabled={busy}
              className="shrink-0 rounded-lg border border-border bg-card px-3 py-1.5 text-sm font-medium hover:bg-muted/50 disabled:opacity-50"
            >
              {isActive ? t("deactivate") : t("activate")}
            </button>
          </div>

          {/* Password */}
          <div>
            <label className="block text-sm">
              <span className="mb-1 flex items-center gap-1.5 text-muted-foreground">
                <KeyRound className="h-3.5 w-3.5" />
                {t("resetPassword")}
              </span>
              <input
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
              />
            </label>
            <div className="mt-2 flex justify-end">
              <button
                type="button"
                onClick={savePassword}
                disabled={busy || password.length < 8}
                className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
              >
                {t("savePassword")}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
