"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/routing";
import type { ANCProfileCreate, MCHRiskLevel, Patient } from "@aifya/shared";
import { PatientLookup } from "@/components/patients/PatientLookup";
import { useCreateANCProfile } from "@/hooks/useMCH";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";

/** Blood groups accepted by the ANC register. */
const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"] as const;

/** HIV statuses accepted by the ANC register. */
const HIV_STATUSES = ["unknown", "negative", "positive", "declined"] as const;

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

/** Pregnancy risk levels, lowest first. */
const RISK_LEVELS: MCHRiskLevel[] = ["low", "moderate", "high"];

/** Naegele's rule: expected delivery date is 280 days after the LMP. */
const GESTATION_DAYS = 280;

type HivKey = "hiv_unknown" | "hiv_negative" | "hiv_positive" | "hiv_declined";
type RiskKey = "risk_low" | "risk_moderate" | "risk_high";

/**
 * Add days to a YYYY-MM-DD date string without timezone drift.
 *
 * @param iso - Source date in YYYY-MM-DD form
 * @param days - Number of days to add
 * @returns Shifted date in YYYY-MM-DD form
 */
function addDays(iso: string, days: number): string {
  const [year = 1970, month = 1, day = 1] = iso.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

interface NewANCProfileFormProps {
  /** Patient to start from, e.g. the one booked into the ANC clinic. */
  patient?: Patient | null;
  /** Called after the profile is saved so the host can collapse the form. */
  onDone: () => void;
}

/**
 * Pregnancy registration form for the ANC register: patient, obstetric
 * history, risk level, and the PMTCT fields the MOH 405 register needs.
 *
 * @param props - Component props
 * @returns ANC profile creation form
 */
export function NewANCProfileForm({
  patient: preselected = null,
  onDone,
}: NewANCProfileFormProps) {
  const t = useTranslations("mch");
  const tc = useTranslations("common");
  const router = useRouter();
  const createProfile = useCreateANCProfile();

  const [patient, setPatient] = useState<Patient | null>(preselected);
  const [gravida, setGravida] = useState("1");
  const [parity, setParity] = useState("0");
  const [livingChildren, setLivingChildren] = useState("0");
  const [lmpDate, setLmpDate] = useState("");
  const [eddDate, setEddDate] = useState("");
  const [bloodGroup, setBloodGroup] = useState("");
  const [hivStatus, setHivStatus] = useState("");
  const [onArt, setOnArt] = useState(false);
  const [riskLevel, setRiskLevel] = useState<MCHRiskLevel>("low");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");

  /**
   * Update the LMP and refresh the derived EDD.
   *
   * @param value - New LMP date in YYYY-MM-DD form
   */
  const handleLmpChange = (value: string) => {
    setLmpDate(value);
    if (value) setEddDate(addDays(value, GESTATION_DAYS));
  };

  /** Validate the form and register the pregnancy. */
  const handleSubmit = async () => {
    if (!patient) {
      setError(t("patientRequired"));
      return;
    }
    const gravidaValue = Number(gravida);
    const parityValue = Number(parity);
    if (!Number.isInteger(gravidaValue) || gravidaValue < 1) {
      setError(t("gravidaRequired"));
      return;
    }
    if (!Number.isInteger(parityValue) || parityValue < 0 || parityValue > gravidaValue) {
      setError(t("parityInvalid"));
      return;
    }
    const livingChildrenValue = Number(livingChildren.trim() === "" ? "0" : livingChildren);
    if (!Number.isInteger(livingChildrenValue) || livingChildrenValue < 0) {
      setError(t("wholeNumber", { field: t("livingChildren") }));
      return;
    }
    if (lmpDate && lmpDate > todayIso()) {
      setError(t("futureDate", { field: t("lmp") }));
      return;
    }
    if (eddDate && lmpDate && eddDate <= lmpDate) {
      setError(t("eddBeforeLmp"));
      return;
    }
    setError("");

    const payload: ANCProfileCreate = {
      patient_id: patient.id,
      gravida: gravidaValue,
      parity: parityValue,
      living_children: livingChildrenValue,
      lmp_date: lmpDate || null,
      expected_delivery_date: eddDate || null,
      blood_group: bloodGroup || null,
      hiv_status: hivStatus || null,
      on_art: onArt,
      risk_level: riskLevel,
      notes: notes || null,
    };

    try {
      const created = await createProfile.mutateAsync(payload);
      onDone();
      router.push(`/mch/${created.id}`);
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
        {t("registerPregnancy")}
      </h2>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
        <div className={cn(cellClass, "md:col-span-2 lg:col-span-3")}>
          <PatientLookup value={patient} onSelect={setPatient} required />
        </div>

        <div className={cellClass}>
          <label className={labelClass}>{t("gravida")} *</label>
          <input
            type="number"
            min={1}
            value={gravida}
            onChange={(event) => setGravida(event.target.value)}
            className={inputClass}
          />
        </div>
        <div className={cellClass}>
          <label className={labelClass}>{t("parity")} *</label>
          <input
            type="number"
            min={0}
            value={parity}
            onChange={(event) => setParity(event.target.value)}
            className={inputClass}
          />
        </div>
        <div className={cellClass}>
          <label className={labelClass}>{t("livingChildren")}</label>
          <input
            type="number"
            min={0}
            value={livingChildren}
            onChange={(event) => setLivingChildren(event.target.value)}
            className={inputClass}
          />
        </div>

        <div className={cellClass}>
          <label className={labelClass}>{t("lmp")}</label>
          <input
            type="date"
            value={lmpDate}
            onChange={(event) => handleLmpChange(event.target.value)}
            className={inputClass}
          />
        </div>
        <div className={cellClass}>
          <label className={labelClass}>{t("edd")}</label>
          <input
            type="date"
            value={eddDate}
            onChange={(event) => setEddDate(event.target.value)}
            className={inputClass}
          />
          <p className="mt-1 text-xs text-muted-foreground">{t("eddAutoHint")}</p>
        </div>
        <div className={cellClass}>
          <label className={labelClass}>{t("bloodGroup")}</label>
          <select
            value={bloodGroup}
            onChange={(event) => setBloodGroup(event.target.value)}
            className={inputClass}
          >
            <option value="">{t("bloodGroupPlaceholder")}</option>
            {BLOOD_GROUPS.map((group) => (
              <option key={group} value={group}>
                {group}
              </option>
            ))}
          </select>
        </div>

        <div className={cellClass}>
          <label className={labelClass}>{t("hivStatus")}</label>
          <select
            value={hivStatus}
            onChange={(event) => setHivStatus(event.target.value)}
            className={inputClass}
          >
            <option value="">{t("hivStatusPlaceholder")}</option>
            {HIV_STATUSES.map((status) => (
              <option key={status} value={status}>
                {t(`hiv_${status}` as HivKey)}
              </option>
            ))}
          </select>
        </div>
        <div className={cellClass}>
          <label className={labelClass}>{t("riskLevel")}</label>
          <select
            value={riskLevel}
            onChange={(event) => setRiskLevel(event.target.value as MCHRiskLevel)}
            className={inputClass}
          >
            {RISK_LEVELS.map((level) => (
              <option key={level} value={level}>
                {t(`risk_${level}` as RiskKey)}
              </option>
            ))}
          </select>
        </div>
        <div className={cn(cellClass, "flex items-center gap-2 md:pt-8")}>
          <input
            id="anc-on-art"
            type="checkbox"
            checked={onArt}
            onChange={(event) => setOnArt(event.target.checked)}
            className="h-4 w-4 rounded border-input"
          />
          <label htmlFor="anc-on-art" className="text-sm font-medium text-foreground">
            {t("onART")}
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
          disabled={createProfile.isPending}
          className={cn(
            "rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90",
            createProfile.isPending && "cursor-not-allowed opacity-60"
          )}
        >
          {createProfile.isPending ? tc("saving") : t("saveProfile")}
        </button>
      </div>

      {error && (
        <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
      )}
    </div>
  );
}