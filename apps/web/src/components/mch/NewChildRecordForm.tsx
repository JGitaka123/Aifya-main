"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import type {
  ChildRecordCreate,
  ChildRecordResponse,
  FeedingMethod,
  Patient,
} from "@aifya/shared";
import { PatientLookup } from "@/components/patients/PatientLookup";
import { useANCProfiles, useCreateChildRecord } from "@/hooks/useMCH";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";

/** Bounds the API enforces on birth weight, in grams. */
const BIRTH_WEIGHT_MIN = 200;
const BIRTH_WEIGHT_MAX = 7000;

/**
 * Parse the birth weight, mirroring the API's integer-only bounds so a decimal
 * (e.g. a weight typed in kilograms) is caught before the round trip.
 *
 * @param raw - Raw input value
 * @returns Parsed whole grams, null when blank, or the reason it was rejected
 */
function parseBirthWeight(raw: string): number | null | "range" | "fraction" {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value)) return "range";
  if (!Number.isInteger(value)) return "fraction";
  if (value < BIRTH_WEIGHT_MIN || value > BIRTH_WEIGHT_MAX) return "range";
  return value;
}

/**
 * Today as a YYYY-MM-DD string in local time.
 *
 * @returns Local ISO date
 */
function todayIso(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset() * 60 * 1000;
  return new Date(now.getTime() - offset).toISOString().slice(0, 10);
}

/** Feeding methods recorded on the child health card. */
const FEEDING_METHODS: FeedingMethod[] = [
  "exclusive_breastfeeding",
  "mixed",
  "replacement",
];

type FeedingKey =
  | "feeding_exclusive_breastfeeding"
  | "feeding_mixed"
  | "feeding_replacement";

interface NewChildRecordFormProps {
  /** Child to start from, e.g. the one booked into the vaccination clinic. */
  patient?: Patient | null;
  /** Called after the record is saved so the host can collapse the form. */
  onDone: () => void;
  /** Called with the new child so the host can open its immunization panel. */
  onCreated: (child: ChildRecordResponse) => void;
}

/**
 * Child health card registration: which child, when they were born, and the
 * HIV-exposure and feeding fields the CWC register tracks.
 *
 * @param props - Component props
 * @returns Child record creation form
 */
export function NewChildRecordForm({
  patient: preselected = null,
  onDone,
  onCreated,
}: NewChildRecordFormProps) {
  const t = useTranslations("mch");
  const tc = useTranslations("common");
  const createChild = useCreateChildRecord();
  const { data: ancProfiles } = useANCProfiles();

  const [patient, setPatient] = useState<Patient | null>(preselected);
  const [motherPatientId, setMotherPatientId] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [sex, setSex] = useState("");
  const [birthWeight, setBirthWeight] = useState("");
  const [placeOfBirth, setPlaceOfBirth] = useState("");
  const [birthNotification, setBirthNotification] = useState("");
  const [hivExposed, setHivExposed] = useState(false);
  const [feedingMethod, setFeedingMethod] = useState<FeedingMethod | "">("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  /** Validate the form and open the child health card. */
  const handleSubmit = async () => {
    if (!patient) {
      setError(t("childRequired"));
      return;
    }
    if (!dateOfBirth) {
      setError(t("dobRequired"));
      return;
    }
    if (dateOfBirth > todayIso()) {
      setError(t("futureDate", { field: t("dateOfBirth") }));
      return;
    }
    if (sex !== "male" && sex !== "female") {
      setError(t("sexRequired"));
      return;
    }
    const weight = parseBirthWeight(birthWeight);
    if (weight === "fraction") {
      setError(t("wholeNumber", { field: t("birthWeightGrams") }));
      return;
    }
    if (weight === "range") {
      setError(
        t("outOfRange", {
          field: t("birthWeightGrams"),
          min: BIRTH_WEIGHT_MIN,
          max: BIRTH_WEIGHT_MAX,
        })
      );
      return;
    }
    setError("");

    const payload: ChildRecordCreate = {
      patient_id: patient.id,
      mother_patient_id: motherPatientId || null,
      date_of_birth: dateOfBirth,
      birth_weight_grams: weight,
      sex,
      place_of_birth: placeOfBirth || null,
      birth_notification_number: birthNotification || null,
      hiv_exposed: hivExposed,
      feeding_method: feedingMethod || null,
      notes: notes || null,
    };

    try {
      const created = await createChild.mutateAsync(payload);
      onCreated(created);
      onDone();
    } catch (error) {
      setError(
        error instanceof ApiError && error.message
          ? error.message
          : tc("retrySync")
      );
    }
  };

  const inputClass =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm";
  const labelClass = "mb-1 block text-sm font-medium text-foreground";
  const cellClass = "rounded-lg border border-border bg-muted/20 p-3";

  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
      <h2 className="mb-4 text-sm font-semibold text-foreground">
        {t("registerChild")}
      </h2>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        <div className={cn(cellClass, "md:col-span-2 lg:col-span-3")}>
          <PatientLookup value={patient} onSelect={setPatient} required />
        </div>

        <div className={cellClass}>
          <label className={labelClass}>{t("dateOfBirth")} *</label>
          <input
            type="date"
            value={dateOfBirth}
            onChange={(event) => setDateOfBirth(event.target.value)}
            className={inputClass}
          />
        </div>
        <div className={cellClass}>
          <label className={labelClass}>{t("sex")} *</label>
          <select
            value={sex}
            onChange={(event) => setSex(event.target.value)}
            className={inputClass}
          >
            <option value="">{t("sexPlaceholder")}</option>
            <option value="male">{t("male")}</option>
            <option value="female">{t("female")}</option>
          </select>
        </div>
        <div className={cellClass}>
          <label className={labelClass}>{t("birthWeightGrams")}</label>
          <input
            type="number"
            min={200}
            max={7000}
            value={birthWeight}
            onChange={(event) => setBirthWeight(event.target.value)}
            className={inputClass}
          />
        </div>

        <div className={cellClass}>
          <label className={labelClass}>{t("placeOfBirth")}</label>
          <input
            value={placeOfBirth}
            maxLength={30}
            onChange={(event) => setPlaceOfBirth(event.target.value)}
            className={inputClass}
          />
        </div>
        <div className={cellClass}>
          <label className={labelClass}>{t("birthNotificationNumber")}</label>
          <input
            value={birthNotification}
            maxLength={50}
            onChange={(event) => setBirthNotification(event.target.value)}
            className={inputClass}
          />
        </div>
        <div className={cellClass}>
          <label className={labelClass}>{t("feedingMethod")}</label>
          <select
            value={feedingMethod}
            onChange={(event) =>
              setFeedingMethod(event.target.value as FeedingMethod | "")
            }
            className={inputClass}
          >
            <option value="">{t("feedingPlaceholder")}</option>
            {FEEDING_METHODS.map((method) => (
              <option key={method} value={method}>
                {t(`feeding_${method}` as FeedingKey)}
              </option>
            ))}
          </select>
        </div>

        <div className={cellClass}>
          <label className={labelClass}>{t("motherOptional")}</label>
          <select
            value={motherPatientId}
            onChange={(event) => setMotherPatientId(event.target.value)}
            className={inputClass}
          >
            <option value="">{t("motherNone")}</option>
            {(ancProfiles?.items ?? []).map((profile) => (
              <option key={profile.id} value={profile.patient_id}>
                {profile.patient_name ?? profile.anc_number}
              </option>
            ))}
          </select>
        </div>
        <div className={cn(cellClass, "flex items-center gap-2 md:pt-8")}>
          <input
            id="child-hiv-exposed"
            type="checkbox"
            checked={hivExposed}
            onChange={(event) => setHivExposed(event.target.checked)}
            className="h-4 w-4 rounded border-input"
          />
          <label
            htmlFor="child-hiv-exposed"
            className="text-sm font-medium text-foreground"
          >
            {t("hivExposed")}
          </label>
        </div>
        <div className={cn(cellClass, "md:col-span-2 lg:col-span-3")}>
          <label className={labelClass}>{tc("notes")}</label>
          <textarea
            value={notes}
            maxLength={2000}
            onChange={(event) => setNotes(event.target.value)}
            rows={2}
            className={inputClass}
          />
        </div>
      </div>

      <div className="mt-4 flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onDone}
          className="rounded-lg border border-border px-3 py-2 text-sm font-medium text-foreground hover:bg-muted"
        >
          {tc("cancel")}
        </button>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={createChild.isPending}
          className={cn(
            "rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90",
            createChild.isPending && "cursor-not-allowed opacity-60"
          )}
        >
          {createChild.isPending ? tc("saving") : t("saveChild")}
        </button>
      </div>

      {error && (
        <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
      )}
    </div>
  );
}