"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { ArrowLeft, Siren } from "lucide-react";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useRouter } from "@/i18n/routing";
import { useRegisterEmergencyVisit } from "@/hooks/useEmergency";
import { useRegisterPatient } from "@/hooks/usePatients";
import { PatientLookup } from "@/components/patients/PatientLookup";
import type { ArrivalMode, Patient } from "@aifya/shared";

/** Zod schema for emergency visit registration form. */
const emergencyRegisterSchema = z.object({
  patient_id: z.string().uuid("Must be a valid UUID"),
  chief_complaint: z.string().min(3, "Chief complaint must be at least 3 characters"),
  arrival_mode: z.enum(["walk_in", "ambulance", "referral", "police", "other"]).optional(),
  brought_by: z.string().optional(),
  is_trauma: z.boolean().optional(),
  allergies_noted: z.string().optional(),
  notes: z.string().optional(),
  referred_from_facility_name: z.string().optional(),
  referred_from_facility_mfl: z.string().optional(),
  referral_reason: z.string().optional(),
  referral_urgency: z.enum(["emergency", "urgent", "routine"]).optional(),
});

type EmergencyRegisterFormValues = z.infer<typeof emergencyRegisterSchema>;

/** Minimal details used to register a brand-new visitor before the visit. */
const quickPatientSchema = z.object({
  first_name: z.string().min(1, "First name is required").max(100),
  last_name: z.string().min(1, "Last name is required").max(100),
  date_of_birth: z
    .string()
    .min(1, "Date of birth is required")
    .refine((value) => {
      const dob = new Date(value);
      return !Number.isNaN(dob.getTime()) && dob <= new Date();
    }, "Enter a valid date of birth"),
  gender: z.enum(["male", "female", "other"]),
  phone_number: z
    .string()
    .min(9)
    .max(20)
    .refine(
      (value) => /^(?:\+?254|0)?[17]\d{8}$/.test(value.replace(/[\s-]/g, "")),
      "Enter a valid Kenyan phone number, e.g. 0712345678"
    ),
  national_id: z.string().max(50).optional(),
});

type QuickPatientValues = z.infer<typeof quickPatientSchema>;

export default function RegisterEmergencyPage() {
  const t = useTranslations("emergency");
  const tp = useTranslations("patients");
  const router = useRouter();
  const registerMutation = useRegisterEmergencyVisit();
  const registerPatient = useRegisterPatient();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [showNewPatient, setShowNewPatient] = useState(false);
  const [quickError, setQuickError] = useState<string | null>(null);
  const quickInputClass =
    "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground";
  const quickForm = useForm<QuickPatientValues>({
    resolver: zodResolver(quickPatientSchema),
    defaultValues: { gender: "male" },
  });

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors, isValid },
  } = useForm<EmergencyRegisterFormValues>({
    resolver: zodResolver(emergencyRegisterSchema),
    defaultValues: {
      patient_id: "",
      chief_complaint: "",
      arrival_mode: "walk_in",
      brought_by: "",
      is_trauma: false,
      allergies_noted: "",
      notes: "",
      referred_from_facility_name: "",
      referred_from_facility_mfl: "",
      referral_reason: "",
      referral_urgency: "urgent",
    },
    mode: "onChange",
  });

  const handleQuickRegister = async (values: QuickPatientValues) => {
    setQuickError(null);
    try {
      const created = await registerPatient.mutateAsync({
        first_name: values.first_name.trim(),
        last_name: values.last_name.trim(),
        date_of_birth: values.date_of_birth,
        gender: values.gender,
        phone_number: values.phone_number.trim(),
        national_id: values.national_id?.trim() || null,
      });
      setPatient(created);
      setValue("patient_id", created.id, { shouldDirty: true, shouldValidate: true });
      setShowNewPatient(false);
      quickForm.reset();
    } catch (err) {
      setQuickError(
        err instanceof Error ? err.message : "Could not register the patient."
      );
    }
  };

  const arrivalModes: ArrivalMode[] = ["walk_in", "ambulance", "referral", "police", "other"];
  const referralUrgencies = ["emergency", "urgent", "routine"] as const;
  const arrivalMode = watch("arrival_mode");
  const isReferral = arrivalMode === "referral";

  const onSubmit = (data: EmergencyRegisterFormValues) => {
    const referred = (data.arrival_mode ?? "walk_in") === "referral";
    registerMutation.mutate(
      {
        patient_id: data.patient_id,
        arrival_mode: data.arrival_mode ?? "walk_in",
        brought_by: data.brought_by || null,
        chief_complaint: data.chief_complaint,
        is_trauma: data.is_trauma ?? false,
        allergies_noted: data.allergies_noted || null,
        notes: data.notes || null,
        referred_from_facility_name: referred
          ? data.referred_from_facility_name?.trim() || null
          : null,
        referred_from_facility_mfl: referred
          ? data.referred_from_facility_mfl?.trim() || null
          : null,
        referral_reason: referred ? data.referral_reason?.trim() || null : null,
        referral_urgency: referred ? data.referral_urgency : "urgent",
      },
      {
        onSuccess: (visit) => {
          router.push(`/emergency/${visit.id}`);
        },
      }
    );
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6 lg:p-8 animate-[fade-in_0.3s_ease-out]">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/emergency"
          className="rounded-md p-2 hover:bg-muted/50"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-foreground">{t("registerVisit")}</h1>
          <p className="text-sm text-muted-foreground">{t("registerSubtitle")}</p>
        </div>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <div className="mb-4">
            <input type="hidden" {...register("patient_id")} />
            <PatientLookup
              value={patient}
              required
              error={errors.patient_id?.message}
              onSelect={(selectedPatient) => {
                setPatient(selectedPatient);
                setValue("patient_id", selectedPatient?.id ?? "", {
                  shouldDirty: true,
                  shouldValidate: true,
                });
              }}
            />
          </div>

          {/* Quick new-patient registration */}
          <div className="mb-4">
            {!showNewPatient ? (
              <button
                type="button"
                onClick={() => setShowNewPatient(true)}
                className="text-xs font-medium text-primary hover:underline"
              >
                + {tp("newPatient")} &middot; {t("newPatientHint")}
              </button>
            ) : (
              <div className="rounded-lg border border-border bg-muted/30 p-4">
                <div className="mb-3 flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {tp("newPatient")}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {t("newPatientHint")}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => setShowNewPatient(false)}
                    className="text-xs text-muted-foreground hover:text-foreground"
                  >
                    {t("cancel")}
                  </button>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <label>
                    <span className="mb-1 block text-xs font-medium text-muted-foreground">
                      {tp("firstName")} *
                    </span>
                    <input type="text" {...quickForm.register("first_name")} className={quickInputClass} />
                    {quickForm.formState.errors.first_name && (
                      <span className="mt-1 block text-xs text-red-600">
                        {quickForm.formState.errors.first_name.message}
                      </span>
                    )}
                  </label>
                  <label>
                    <span className="mb-1 block text-xs font-medium text-muted-foreground">
                      {tp("lastName")} *
                    </span>
                    <input type="text" {...quickForm.register("last_name")} className={quickInputClass} />
                    {quickForm.formState.errors.last_name && (
                      <span className="mt-1 block text-xs text-red-600">
                        {quickForm.formState.errors.last_name.message}
                      </span>
                    )}
                  </label>
                  <label>
                    <span className="mb-1 block text-xs font-medium text-muted-foreground">
                      {tp("dateOfBirth")} *
                    </span>
                    <input type="date" {...quickForm.register("date_of_birth")} className={quickInputClass} />
                    {quickForm.formState.errors.date_of_birth && (
                      <span className="mt-1 block text-xs text-red-600">
                        {quickForm.formState.errors.date_of_birth.message}
                      </span>
                    )}
                  </label>
                  <label>
                    <span className="mb-1 block text-xs font-medium text-muted-foreground">
                      {tp("gender")} *
                    </span>
                    <select {...quickForm.register("gender")} className={quickInputClass}>
                      <option value="male">{tp("male")}</option>
                      <option value="female">{tp("female")}</option>
                      <option value="other">{tp("other")}</option>
                    </select>
                  </label>
                  <label>
                    <span className="mb-1 block text-xs font-medium text-muted-foreground">
                      {tp("phoneNumber")} *
                    </span>
                    <input type="tel" {...quickForm.register("phone_number")} className={quickInputClass} placeholder="0712345678" />
                    {quickForm.formState.errors.phone_number && (
                      <span className="mt-1 block text-xs text-red-600">
                        {quickForm.formState.errors.phone_number.message}
                      </span>
                    )}
                  </label>
                  <label>
                    <span className="mb-1 block text-xs font-medium text-muted-foreground">
                      {tp("nationalId")}
                    </span>
                    <input type="text" {...quickForm.register("national_id")} className={quickInputClass} />
                  </label>
                </div>
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
                  {quickError && <p className="text-xs text-red-600">{quickError}</p>}
                  <div className="ml-auto flex gap-2">
                    <button
                      type="button"
                      onClick={() => setShowNewPatient(false)}
                      className="rounded-md border border-input px-3 py-1.5 text-xs font-medium text-foreground hover:bg-muted"
                    >
                      {t("cancel")}
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        quickForm.handleSubmit(handleQuickRegister)();
                      }}
                      disabled={registerPatient.isPending}
                      className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                    >
                      {registerPatient.isPending ? t("saving") : tp("register")}
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Arrival Mode */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-foreground">{t("arrivalMode")}</label>
            <select
              {...register("arrival_mode")}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
            >
              {arrivalModes.map((m) => (
                <option key={m} value={m}>
                  {t(`mode.${m}`)}
                </option>
              ))}
            </select>
          </div>

          {/* Referral intake: the patient was sent here */}
          {isReferral && (
            <div className="mb-4 rounded-lg border border-border bg-muted/30 p-4">
              <p className="text-sm font-semibold text-foreground">{t("referralIntake")}</p>
              <p className="mb-3 text-xs text-muted-foreground">{t("referralIntakeHint")}</p>
              <div className="grid gap-3 sm:grid-cols-2">
                <label>
                  <span className="mb-1 block text-xs font-medium text-muted-foreground">
                    {t("referringFacility")}
                  </span>
                  <input
                    type="text"
                    {...register("referred_from_facility_name")}
                    className={quickInputClass}
                    placeholder={t("referringFacilityPlaceholder")}
                  />
                </label>
                <label>
                  <span className="mb-1 block text-xs font-medium text-muted-foreground">
                    {t("referringFacilityMfl")}
                  </span>
                  <input
                    type="text"
                    {...register("referred_from_facility_mfl")}
                    className={quickInputClass}
                    placeholder={t("mflPlaceholder")}
                  />
                </label>
                <label>
                  <span className="mb-1 block text-xs font-medium text-muted-foreground">
                    {t("referralUrgency")}
                  </span>
                  <select {...register("referral_urgency")} className={quickInputClass}>
                    {referralUrgencies.map((urgency) => (
                      <option key={urgency} value={urgency}>
                        {t(`urgency.${urgency}`)}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="sm:col-span-2">
                  <span className="mb-1 block text-xs font-medium text-muted-foreground">
                    {t("referralReason")}
                  </span>
                  <textarea
                    {...register("referral_reason")}
                    rows={2}
                    className={quickInputClass}
                    placeholder={t("referralReasonPlaceholder")}
                  />
                </label>
              </div>
            </div>
          )}

          {/* Brought By */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-foreground">{t("broughtBy")}</label>
            <input
              type="text"
              {...register("brought_by")}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              placeholder={t("broughtByPlaceholder")}
            />
          </div>

          {/* Chief Complaint */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-foreground">{t("chiefComplaint")} *</label>
            <textarea
              {...register("chief_complaint")}
              rows={3}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              placeholder={t("complaintPlaceholder")}
            />
            {errors.chief_complaint && (
              <p className="mt-1 text-xs text-red-600">{errors.chief_complaint.message}</p>
            )}
          </div>

          {/* Trauma Flag */}
          <div className="mb-4 flex items-center gap-2">
            <input
              type="checkbox"
              id="is_trauma"
              {...register("is_trauma")}
              className="h-4 w-4 rounded border-input"
            />
            <label htmlFor="is_trauma" className="flex items-center gap-1 text-sm font-medium text-red-600">
              <Siren className="h-4 w-4" /> {t("traumaCase")}
            </label>
          </div>

          {/* Allergies */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-foreground">{t("allergies")}</label>
            <input
              type="text"
              {...register("allergies_noted")}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              placeholder={t("allergiesPlaceholder")}
            />
          </div>

          {/* Notes */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-foreground">{t("notes")}</label>
            <textarea
              {...register("notes")}
              rows={2}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
            />
          </div>
        </div>

        {/* Submit */}
        <div className="flex gap-3">
          <button
            type="submit"
            disabled={registerMutation.isPending || !isValid}
            className="rounded-md bg-red-600 px-6 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
          >
            {registerMutation.isPending ? t("saving") : t("registerVisit")}
          </button>
          <Link
            href="/emergency"
            className="rounded-md border border-input px-6 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
          >
            {t("cancel")}
          </Link>
        </div>
      </form>
    </div>
  );
}
