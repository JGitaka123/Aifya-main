"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { z } from "zod";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertTriangle, CheckCircle2, Loader2, Search, Send, X } from "lucide-react";
import { PatientLookup } from "@/components/patients/PatientLookup";
import { useCreateReferral, useFacilityLookup } from "@/hooks/useReferrals";
import type {
  FacilityLookupItem,
  Patient,
  ReferralUrgency,
} from "@aifya/shared";

/** Validation schema for an outbound referral to another facility. */
const newReferralSchema = z.object({
  patient_id: z.string().min(1),
  receiving_facility_name: z.string().min(2).max(200),
  receiving_facility_mfl: z.string().max(20).optional(),
  urgency: z.enum(["emergency", "urgent", "routine"]),
  reason: z.string().min(3).max(2000),
  diagnosis: z.string().max(500).optional(),
  clinical_notes: z.string().max(5000).optional(),
  send_now: z.boolean(),
});

type NewReferralValues = z.infer<typeof newReferralSchema>;

interface NewReferralFormProps {
  /** Called after a referral is created, or when the form is dismissed. */
  onClose: () => void;
}

/**
 * Form for referring a patient from this hospital to another one.
 *
 * Creates an external, outgoing referral owned by this facility. The letter
 * itself is printed afterwards from the row's "Generate Note" action.
 *
 * @param props - Close callback
 * @returns Referral creation panel
 */
export function NewReferralForm({ onClose }: NewReferralFormProps) {
  const t = useTranslations("referrals");
  const createReferral = useCreateReferral();
  const [patient, setPatient] = useState<Patient | null>(null);
  // Facility-register check, mirroring the pharmacy stock check on prescriptions.
  const [facilityQuery, setFacilityQuery] = useState("");
  const [matchedFacility, setMatchedFacility] =
    useState<FacilityLookupItem | null>(null);
  const { data: facilityMatches, isFetching: facilitySearching } =
    useFacilityLookup(facilityQuery);
  const facilityOptions = facilityMatches?.items ?? [];
  const facilitySearchActive = facilityQuery.trim().length >= 3;

  const inputClass =
    "w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground";

  const {
    register,
    handleSubmit,
    setValue,
    formState: { errors, isValid },
  } = useForm<NewReferralValues>({
    resolver: zodResolver(newReferralSchema),
    defaultValues: {
      patient_id: "",
      receiving_facility_name: "",
      receiving_facility_mfl: "",
      urgency: "urgent",
      reason: "",
      diagnosis: "",
      clinical_notes: "",
      send_now: true,
    },
    mode: "onChange",
  });

  const urgencies: ReferralUrgency[] = ["emergency", "urgent", "routine"];

  /**
   * Adopt a facility from the register.
   *
   * Fills the name and MFL code so the referral is addressed to a known
   * facility rather than free text, and remembers its id for the payload.
   *
   * @param facility - Register match chosen by the user
   */
  const chooseFacility = (facility: FacilityLookupItem) => {
    setMatchedFacility(facility);
    setFacilityQuery("");
    setValue("receiving_facility_name", facility.name, {
      shouldDirty: true,
      shouldValidate: true,
    });
    setValue("receiving_facility_mfl", facility.mfl_code ?? "", {
      shouldDirty: true,
      shouldValidate: true,
    });
  };

  const onSubmit = (values: NewReferralValues) => {
    createReferral.mutate(
      {
        patient_id: values.patient_id,
        referral_type: "external",
        direction: "outgoing",
        receiving_facility_id: matchedFacility?.id ?? null,
        receiving_facility_name: values.receiving_facility_name.trim(),
        receiving_facility_mfl: values.receiving_facility_mfl?.trim() || null,
        urgency: values.urgency,
        reason: values.reason.trim(),
        diagnosis: values.diagnosis?.trim() || null,
        clinical_notes: values.clinical_notes?.trim() || null,
        initial_status: values.send_now ? "sent" : "draft",
      },
      { onSuccess: () => onClose() }
    );
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]"
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-foreground">{t("newReferral")}</h2>
          <p className="text-xs text-muted-foreground">{t("newReferralHint")}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
          aria-label={t("cancel")}
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="mb-4">
        <input type="hidden" {...register("patient_id")} />
        <PatientLookup
          value={patient}
          required
          error={errors.patient_id ? t("patientRequired") : undefined}
          onSelect={(selected) => {
            setPatient(selected);
            setValue("patient_id", selected?.id ?? "", {
              shouldDirty: true,
              shouldValidate: true,
            });
          }}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label
            htmlFor="receiving_facility_name"
            className="mb-1 block text-sm font-medium text-foreground"
          >
            {t("receivingHospital")} *
          </label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <input
              id="receiving_facility_name"
              type="text"
              autoComplete="off"
              {...register("receiving_facility_name", {
                onChange: (event) => {
                  setFacilityQuery(event.target.value);
                  setMatchedFacility(null);
                },
              })}
              className={`${inputClass} pl-8`}
              placeholder={t("receivingHospitalPlaceholder")}
            />
            {facilitySearching && (
              <Loader2 className="absolute right-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 animate-spin text-muted-foreground" />
            )}
            {facilityOptions.length > 0 && (
              <ul className="absolute z-50 mt-1 max-h-56 w-full overflow-auto rounded-md border border-border bg-card shadow-lg dark:bg-card">
                {facilityOptions.map((facility) => (
                  <li key={facility.id}>
                    <button
                      type="button"
                      onClick={() => chooseFacility(facility)}
                      className="flex w-full flex-col items-start px-3 py-2 text-left text-sm hover:bg-muted dark:hover:bg-muted"
                    >
                      <span className="font-medium text-foreground">
                        {facility.name}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {[
                          facility.facility_type,
                          facility.keph_level ? `KEPH ${facility.keph_level}` : null,
                          facility.county,
                          facility.mfl_code ? `MFL ${facility.mfl_code}` : null,
                        ]
                          .filter(Boolean)
                          .join(" \u00b7 ")}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {matchedFacility && (
            <p className="mt-1 flex items-center gap-1 text-xs font-medium text-green-700 dark:text-green-300">
              <CheckCircle2 className="h-3 w-3 flex-shrink-0" />
              {t("facilityInRegister")}
              {" \u00b7 "}
              {matchedFacility.mfl_code
                ? `MFL ${matchedFacility.mfl_code}`
                : matchedFacility.facility_type}
              {matchedFacility.county ? ` \u00b7 ${matchedFacility.county}` : ""}
            </p>
          )}
          {!matchedFacility &&
            facilitySearchActive &&
            facilityMatches !== undefined &&
            facilityOptions.length === 0 && (
              <p className="mt-1 flex items-start gap-1 text-xs text-amber-700 dark:text-amber-300">
                <AlertTriangle className="mt-0.5 h-3 w-3 flex-shrink-0" />
                <span>
                  {t("facilityNotInRegister")} {t("facilityNotInRegisterHint")}
                </span>
              </p>
            )}
          {!matchedFacility && !facilitySearchActive && (
            <p className="mt-1 text-xs text-muted-foreground">
              {t("facilityCheckHint")}
            </p>
          )}
          {errors.receiving_facility_name && (
            <span className="mt-1 block text-xs text-red-600">
              {t("receivingHospitalRequired")}
            </span>
          )}
        </div>

        <label>
          <span className="mb-1 block text-sm font-medium text-foreground">
            {t("receivingFacilityMfl")}
          </span>
          <input
            type="text"
            {...register("receiving_facility_mfl")}
            className={inputClass}
            placeholder={t("mflPlaceholder")}
          />
        </label>

        <label>
          <span className="mb-1 block text-sm font-medium text-foreground">
            {t("urgency")}
          </span>
          <select {...register("urgency")} className={inputClass}>
            {urgencies.map((urgency) => (
              <option key={urgency} value={urgency}>
                {t(`urgencyType.${urgency}`)}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span className="mb-1 block text-sm font-medium text-foreground">
            {t("diagnosis")}
          </span>
          <input
            type="text"
            {...register("diagnosis")}
            className={inputClass}
            placeholder={t("diagnosisPlaceholder")}
          />
        </label>

        <label className="sm:col-span-2">
          <span className="mb-1 block text-sm font-medium text-foreground">
            {t("reason")} *
          </span>
          <textarea
            {...register("reason")}
            rows={2}
            className={inputClass}
            placeholder={t("reasonPlaceholder")}
          />
          {errors.reason && (
            <span className="mt-1 block text-xs text-red-600">{t("reasonRequired")}</span>
          )}
        </label>

        <label className="sm:col-span-2">
          <span className="mb-1 block text-sm font-medium text-foreground">
            {t("clinicalNotes")}
          </span>
          <textarea {...register("clinical_notes")} rows={3} className={inputClass} />
        </label>
      </div>

      <label className="mt-4 flex items-center gap-2 text-sm text-foreground">
        <input type="checkbox" {...register("send_now")} className="h-4 w-4 rounded border-input" />
        {t("sendNow")}
      </label>
      <p className="mt-1 text-xs text-muted-foreground">{t("sendNowHint")}</p>

      <div className="mt-4 flex gap-2">
        <button
          type="submit"
          disabled={createReferral.isPending || !isValid}
          className="inline-flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
          {createReferral.isPending ? t("creating") : t("createReferral")}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="rounded-md border border-input px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
        >
          {t("cancel")}
        </button>
      </div>
    </form>
  );
}