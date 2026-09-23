"use client";

import { useTranslations } from "next-intl";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import {
  patientCreateSchema,
  type PatientCreateFormData,
} from "@/lib/validations/patient";
import {
  useRegisterPatient,
  useCheckDuplicates,
  type DuplicateMatch,
} from "@/hooks/usePatients";
import { HelpTooltip } from "@/components/help/HelpTooltip";
import { Link } from "@/i18n/routing";
import React from "react";
import { cn } from "@/lib/utils";

/**
 * Provider names stored when the plan is picked from the registration list.
 * Any other insurer is typed by the user, so it is not listed here.
 */
const INSURANCE_PLAN_PROVIDERS: Record<string, string> = {
  sha: "SHA",
  nhif: "NHIF (Legacy)",
};

/**
 * Patient Registration form page.
 * Supports offline submission — mutations queue to IndexedDB when offline.
 * All strings internationalized via next-intl.
 * @returns Registration form page
 */
export default function PatientRegistrationPage() {
  const t = useTranslations("patients");
  const tc = useTranslations("common");
  const router = useRouter();
  const registerMutation = useRegisterPatient();
  const checkDuplicates = useCheckDuplicates();
  const [newPatient, setNewPatient] = React.useState<{id: string, name: string} | null>(null);
  // D7: possible duplicates surfaced before a second record is created.
  const [duplicates, setDuplicates] = React.useState<DuplicateMatch[] | null>(null);
  const [pendingData, setPendingData] = React.useState<PatientCreateFormData | null>(null);
  // F6: allergies + chronic conditions are stored as string lists on the patient;
  // the form captures them as comma-separated text and splits on submit.
  const [allergiesText, setAllergiesText] = React.useState("");
  const [chronicText, setChronicText] = React.useState("");

  // Insurance plan picked at registration. SHA and NHIF are named schemes; any
  // other insurer is captured as free text in `insurance_provider`.
  const [insurancePlan, setInsurancePlan] = React.useState("none");

  /** Split a comma/newline-separated string into a trimmed, de-duplicated list. */
  const parseList = (value: string): string[] => {
    const items = value
      .split(/[,\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
    return Array.from(new Set(items));
  };

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<PatientCreateFormData>({
    resolver: zodResolver(patientCreateSchema),
    defaultValues: {
      gender: "male",
    },
  });

  const doRegister = async (data: PatientCreateFormData) => {
    try {
      const patient = await registerMutation.mutateAsync(data);
      setNewPatient({ id: patient.id, name: `${patient.first_name} ${patient.last_name}` });
      setDuplicates(null);
      setPendingData(null);
    } catch {
      // Error handled by mutation state
    }
  };

  const onSubmit = async (data: PatientCreateFormData) => {
    // F6: attach captured allergies + chronic conditions so downstream
    // allergy checking (CDS) has the data it needs.
    data.allergies = parseList(allergiesText);
    data.chronic_conditions = parseList(chronicText);
    // D7: warn on likely duplicates before creating a second record. A failed
    // check (e.g. offline) must not block registration — fall through.
    try {
      const result = await checkDuplicates.mutateAsync({
        first_name: data.first_name,
        last_name: data.last_name,
        date_of_birth: data.date_of_birth,
        phone_number: data.phone_number,
        national_id: data.national_id ?? null,
        passport_number: data.passport_number ?? null,
      });
      if (result.has_duplicates) {
        setDuplicates(result.matches);
        setPendingData(data);
        return;
      }
    } catch {
      // Duplicate check unavailable — proceed to registration.
    }
    await doRegister(data);
  };

  /** Keep `insurance_provider` in step with the plan picked in the form. */
  const onInsurancePlanChange = (plan: string) => {
    setInsurancePlan(plan);
    setValue("insurance_provider", INSURANCE_PLAN_PROVIDERS[plan] ?? "");
    // Only one identifier is collected per plan, so clear the others.
    if (plan !== "sha") setValue("sha_number", "");
    if (plan === "none" || plan === "sha") setValue("insurance_member_number", "");
  };

  return (
    <div className="mx-auto max-w-4xl p-6 lg:p-8 animate-[fade-in_0.3s_ease-out]">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-foreground">
          {t("register")}
        </h1>
        <Link
          href="/patients/import"
          className="text-sm font-medium text-primary hover:underline"
        >
          {t("bulkImport")} →
        </Link>
      </div>

      {newPatient && (
        <div className="mb-6 rounded-xl border border-green-300 bg-green-50 p-5 dark:border-green-700 dark:bg-green-950">
          <p className="mb-3 font-semibold text-green-700 dark:text-green-300">
            ✅ {t("registrationSuccessNamed", { name: newPatient.name })}
          </p>
          <div className="flex flex-wrap gap-3">
            <Link href={`/opd/new?patient_id=${newPatient.id}&patient_name=${encodeURIComponent(newPatient.name)}`}
              className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2 text-sm font-semibold text-primary-foreground shadow animate-pulse hover:animate-none hover:bg-primary/90 transition-all">
              → {t("startOpdVisit")}
            </Link>
            <Link href={`/patients/${newPatient.id}`}
              className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted transition-colors">
              {t("viewPatientRecord")}
            </Link>
            <button onClick={() => setNewPatient(null)}
              className="inline-flex items-center gap-2 rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors">
              {t("registerAnother")}
            </button>
          </div>
        </div>
      )}

      {/* D7: possible-duplicate prompt shown before a second record is created. */}
      {duplicates && duplicates.length > 0 && (
        <div className="mb-6 rounded-xl border border-amber-300 bg-amber-50 p-5 dark:border-amber-700 dark:bg-amber-950">
          <p className="mb-1 font-semibold text-amber-800 dark:text-amber-200">
            ⚠️ {t("possibleDuplicateTitle")}
          </p>
          <p className="mb-3 text-sm text-amber-700 dark:text-amber-300">
            {t("possibleDuplicateBody")}
          </p>
          <ul className="mb-4 space-y-2">
            {duplicates.map((match) => (
              <li
                key={match.patient.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-200 bg-background px-3 py-2 dark:border-amber-800"
              >
                <div className="text-sm">
                  <span className="font-medium text-foreground">
                    {match.patient.first_name} {match.patient.last_name}
                  </span>
                  <span className="ml-2 text-muted-foreground">
                    {match.patient.mrn} · {match.patient.phone_number}
                  </span>
                  <span className="ml-2 text-xs text-amber-700 dark:text-amber-300">
                    {match.match_reasons
                      .map((r) => t(`matchReason.${r}`))
                      .join(", ")}
                  </span>
                </div>
                <a
                  href={`/en/patients/${match.patient.id}`}
                  className="rounded-lg border border-border px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
                >
                  {t("useExisting")}
                </a>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => pendingData && doRegister(pendingData)}
              disabled={registerMutation.isPending}
              className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
            >
              {t("registerAnyway")}
            </button>
            <button
              type="button"
              onClick={() => {
                setDuplicates(null);
                setPendingData(null);
              }}
              className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted"
            >
              {tc("cancel")}
            </button>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
        {/* Demographics */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("demographics")}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField
              label={t("firstName")}
              error={errors.first_name?.message}
              required
            >
              <input
                {...register("first_name")}
                className={inputClass(!!errors.first_name)}
              />
            </FormField>
            <FormField
              label={t("middleName")}
              error={errors.middle_name?.message}
            >
              <input
                {...register("middle_name")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField
              label={t("lastName")}
              error={errors.last_name?.message}
              required
            >
              <input
                {...register("last_name")}
                className={inputClass(!!errors.last_name)}
              />
            </FormField>
            <FormField
              label={t("dateOfBirth")}
              error={errors.date_of_birth?.message}
              required
            >
              <input
                type="date"
                {...register("date_of_birth")}
                className={inputClass(!!errors.date_of_birth)}
              />
            </FormField>
            <FormField
              label={t("gender")}
              error={errors.gender?.message}
              required
            >
              <select
                {...register("gender")}
                className={inputClass(!!errors.gender)}
              >
                <option value="male">{t("male")}</option>
                <option value="female">{t("female")}</option>
                <option value="other">{t("other")}</option>
              </select>
            </FormField>
            <FormField
              label={t("nationalId")}
              error={errors.national_id?.message}
              help={t("help.nationalId")}
            >
              <input
                {...register("national_id")}
                placeholder="12345678"
                className={inputClass(false)}
              />
            </FormField>
          </div>
        </section>

        {/* Contact Information */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("contactInfo")}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField
              label={t("phoneNumber")}
              error={errors.phone_number?.message}
              required
              help={t("help.phoneNumber")}
            >
              <input
                type="tel"
                {...register("phone_number")}
                placeholder="0712345678"
                className={inputClass(!!errors.phone_number)}
              />
            </FormField>
            <FormField
              label={t("alternatePhone")}
              error={errors.alternate_phone?.message}
            >
              <input
                type="tel"
                {...register("alternate_phone")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField label={t("email")} error={errors.email?.message}>
              <input
                type="email"
                {...register("email")}
                className={inputClass(!!errors.email)}
              />
            </FormField>
          </div>
        </section>

        {/* Address */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("address")}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField label={t("county")} error={errors.county?.message}>
              <input {...register("county")} className={inputClass(false)} />
            </FormField>
            <FormField
              label={t("subCounty")}
              error={errors.sub_county?.message}
            >
              <input
                {...register("sub_county")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField label={t("ward")} error={errors.ward?.message}>
              <input {...register("ward")} className={inputClass(false)} />
            </FormField>
            <FormField label={t("village")} error={errors.village?.message}>
              <input {...register("village")} className={inputClass(false)} />
            </FormField>
            <FormField
              label={t("postalAddress")}
              error={errors.postal_address?.message}
            >
              <input
                {...register("postal_address")}
                className={inputClass(false)}
              />
            </FormField>
          </div>
        </section>

        {/* Next of Kin */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("nextOfKin")}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField
              label={t("nextOfKinName")}
              error={errors.next_of_kin_name?.message}
            >
              <input
                {...register("next_of_kin_name")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField
              label={t("nextOfKinPhone")}
              error={errors.next_of_kin_phone?.message}
            >
              <input
                type="tel"
                {...register("next_of_kin_phone")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField
              label={t("nextOfKinRelationship")}
              error={errors.next_of_kin_relationship?.message}
            >
              <input
                {...register("next_of_kin_relationship")}
                className={inputClass(false)}
              />
            </FormField>
          </div>
        </section>

        {/* Insurance */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("insurance")}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField label={t("insurancePlan")}>
              <select
                value={insurancePlan}
                onChange={(e) => onInsurancePlanChange(e.target.value)}
                className={inputClass(false)}
              >
                <option value="none">{t("insurancePlanNone")}</option>
                <option value="sha">{t("insurancePlanSha")}</option>
                <option value="nhif">{t("insurancePlanNhif")}</option>
                <option value="other">{t("insurancePlanOther")}</option>
              </select>
            </FormField>
            {insurancePlan === "sha" && (
              <FormField
                label={t("shaNumber")}
                error={errors.sha_number?.message}
              >
                <input
                  {...register("sha_number")}
                  className={inputClass(!!errors.sha_number)}
                />
              </FormField>
            )}
            {insurancePlan === "other" && (
              <FormField
                label={t("insuranceProvider")}
                error={errors.insurance_provider?.message}
              >
                <input
                  {...register("insurance_provider")}
                  placeholder={t("insuranceProviderPlaceholder")}
                  className={inputClass(!!errors.insurance_provider)}
                />
              </FormField>
            )}
            {insurancePlan !== "none" && insurancePlan !== "sha" && (
              <FormField
                label={t("insuranceMemberNumber")}
                error={errors.insurance_member_number?.message}
              >
                <input
                  {...register("insurance_member_number")}
                  className={inputClass(!!errors.insurance_member_number)}
                />
              </FormField>
            )}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {t("insuranceHint")}
          </p>
        </section>

        {/* Medical */}
        <section>
          <h2 className="mb-4 text-lg font-semibold text-foreground">
            {t("medicalInfo")}
          </h2>
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <FormField
              label={t("bloodGroup")}
              error={errors.blood_group?.message}
            >
              <select
                {...register("blood_group")}
                className={inputClass(false)}
              >
                <option value="">—</option>
                {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map(
                  (bg) => (
                    <option key={bg} value={bg}>
                      {bg}
                    </option>
                  )
                )}
              </select>
            </FormField>
            {/* F6: allergy capture — enables allergy alerting at prescribing. */}
            <FormField label={t("allergies")}>
              <input
                type="text"
                value={allergiesText}
                onChange={(e) => setAllergiesText(e.target.value)}
                placeholder={t("allergiesHint")}
                className={inputClass(false)}
              />
            </FormField>
            <FormField label={t("chronicConditions")}>
              <input
                type="text"
                value={chronicText}
                onChange={(e) => setChronicText(e.target.value)}
                placeholder={t("chronicHint")}
                className={inputClass(false)}
              />
            </FormField>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            {t("allergyImportanceNote")}
          </p>
        </section>

        {/* Error display */}
        {registerMutation.isError && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {t("registrationError")}
          </div>
        )}

        {/* Submit */}
        <div className="flex gap-4">
          <button
            type="submit"
            disabled={isSubmitting || registerMutation.isPending}
            className="rounded-lg bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90 disabled:opacity-50"
          >
            {registerMutation.isPending ? tc("loading") : t("register")}
          </button>
          <button
            type="button"
            onClick={() => router.back()}
            className="rounded-lg border border-border bg-background px-6 py-2.5 text-sm font-medium text-foreground shadow-sm hover:bg-accent"
          >
            {tc("cancel")}
          </button>
        </div>
      </form>
    </div>
  );
}

function inputClass(hasError: boolean): string {
  return cn(
    "w-full rounded-md border bg-background px-3 py-2 text-sm text-foreground shadow-sm transition-colors",
    "focus:outline-none focus:ring-2 focus:ring-ring",
    hasError
      ? "border-destructive focus:ring-destructive"
      : "border-input"
  );
}

function FormField({
  label,
  error,
  required,
  help,
  children,
}: {
  label: string;
  error?: string;
  required?: boolean;
  /** Optional contextual help shown via a `?` tooltip next to the label. */
  help?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium text-foreground inline-flex items-center">
        {label}
        {required && <span className="ml-1 text-destructive">*</span>}
        {help && <HelpTooltip content={help} />}
      </label>
      {children}
      {error && (
        <p className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
