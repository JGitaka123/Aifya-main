"use client";

import { useEffect, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { ArrowRight, Building2, Loader2, Save } from "lucide-react";
import { Link } from "@/i18n/routing";
import { useFacilityProfile, useUpdateFacility } from "@/hooks/useSettings";

/** Editable single-line fields, in the order they appear on the form. */
const TEXT_FIELDS = [
  { key: "name", labelKey: "name" },
  { key: "facility_type", labelKey: "facilityType" },
  { key: "keph_level", labelKey: "kephLevel" },
  { key: "mfl_code", labelKey: "mflCode" },
  { key: "county", labelKey: "county" },
  { key: "sub_county", labelKey: "subCounty" },
  { key: "ward", labelKey: "ward" },
  { key: "phone", labelKey: "phone" },
  { key: "email", labelKey: "email" },
  { key: "website", labelKey: "website" },
  { key: "timezone", labelKey: "timezone" },
  { key: "currency", labelKey: "currency" },
] as const;

type EditableKey = (typeof TEXT_FIELDS)[number]["key"];

const inputClass =
  "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:border-border dark:bg-background";

/**
 * Settings -> Facility: read and edit the facility identity, location and
 * contact details. The facility code stays read-only because other records
 * reference it.
 *
 * @returns Facility settings page
 */
export default function FacilitySettingsPage() {
  const t = useTranslations("settings.facility");
  const profile = useFacilityProfile();
  const update = useUpdateFacility();
  const [form, setForm] = useState<Record<EditableKey, string> | null>(null);
  const [address, setAddress] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!profile.data) return;
    const next = {} as Record<EditableKey, string>;
    for (const field of TEXT_FIELDS) {
      next[field.key] = (profile.data[field.key] as string | null) ?? "";
    }
    setForm(next);
    setAddress(profile.data.physical_address ?? "");
  }, [profile.data]);

  const handleChange = (key: EditableKey, value: string) => {
    setSaved(false);
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!form || form.name.trim().length === 0) return;
    setSaved(false);
    update.mutate(
      { ...form, physical_address: address },
      { onSuccess: () => setSaved(true) },
    );
  };

  return (
    <div className="mx-auto max-w-3xl p-6 lg:p-8">
      <h1 className="mb-1 flex items-center gap-2 text-2xl font-bold text-foreground">
        <Building2 className="h-6 w-6 text-primary" />
        {t("title")}
      </h1>
      <p className="mb-6 text-sm text-muted-foreground">{t("description")}</p>

      {profile.isLoading ? (
        <div className="flex items-center gap-2 rounded-xl border border-border bg-card p-6 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t("loading")}
        </div>
      ) : profile.isError || !form ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-4 text-sm text-destructive">
          {t("loadFailed")}
        </div>
      ) : (
        <form
          onSubmit={onSubmit}
          className="space-y-5 rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]"
        >
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("code")}
            </label>
            <input
              value={profile.data?.code ?? ""}
              readOnly
              disabled
              className={inputClass + " opacity-60"}
            />
            <p className="mt-1 text-xs text-muted-foreground">{t("codeLocked")}</p>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {TEXT_FIELDS.map((field) => (
              <div
                key={field.key}
                className={field.key === "name" ? "sm:col-span-2" : undefined}
              >
                <label className="mb-1 block text-xs font-medium text-muted-foreground">
                  {t(field.labelKey)}
                  {field.key === "name" ? " *" : ""}
                </label>
                <input
                  value={form[field.key]}
                  onChange={(event) => handleChange(field.key, event.target.value)}
                  className={inputClass}
                />
              </div>
            ))}
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("physicalAddress")}
            </label>
            <textarea
              value={address}
              onChange={(event) => {
                setSaved(false);
                setAddress(event.target.value);
              }}
              rows={3}
              className={inputClass}
            />
          </div>

          {update.isError && (
            <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              {update.error?.message || t("saveFailed")}
            </div>
          )}

          {saved && (
            <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm text-green-800 dark:border-green-800 dark:bg-green-950/40 dark:text-green-200">
              {t("saved")}
            </div>
          )}

          <button
            type="submit"
            disabled={update.isPending || form.name.trim().length === 0}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-50"
          >
            {update.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            {update.isPending ? t("saving") : t("save")}
          </button>
        </form>
      )}

      <div className="mt-6 rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <h2 className="text-sm font-semibold text-foreground">
          {t("departmentsTitle")}
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">{t("departmentsHint")}</p>
        <Link
          href="/hr/employees"
          className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-blue-600 hover:underline dark:text-blue-400"
        >
          {t("manageDepartments")}
          <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
