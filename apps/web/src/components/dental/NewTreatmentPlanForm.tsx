"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Plus, Trash2 } from "lucide-react";
import type { DentalTreatmentPlanCreate, Patient } from "@aifya/shared";
import { PatientLookup } from "@/components/patients/PatientLookup";
import { useStaffDirectory } from "@/hooks/useHR";
import { useDoctorSchedules } from "@/hooks/useAppointments";
import { useCreateTreatmentPlan } from "@/hooks/useDental";
import { cn, formatKES } from "@/lib/utils";

/** Procedure types offered for a plan line item. */
const PROCEDURE_TYPES = [
  "examination",
  "cleaning",
  "filling",
  "extraction",
  "root_canal",
  "crown",
  "bridge",
  "denture",
  "implant",
  "orthodontic",
  "whitening",
  "other",
] as const;

interface PlanItemDraft {
  tooth: string;
  procedure_type: string;
  estimatedCostKes: string;
}

const EMPTY_ITEM: PlanItemDraft = {
  tooth: "",
  procedure_type: "cleaning",
  estimatedCostKes: "",
};

interface NewTreatmentPlanFormProps {
  /** Called after a plan is saved so the host can collapse the form. */
  onDone: () => void;
}

/**
 * Intake form for a dental treatment plan: patient, dentist, diagnosis and the
 * planned line items, with the estimated cost rolled up automatically.
 *
 * @param props - Component props
 * @returns Treatment plan creation form
 */
export function NewTreatmentPlanForm({ onDone }: NewTreatmentPlanFormProps) {
  const t = useTranslations("dental");
  const tc = useTranslations("common");

  const [patient, setPatient] = useState<Patient | null>(null);
  const [dentistId, setDentistId] = useState("");
  const [diagnosis, setDiagnosis] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<PlanItemDraft[]>([{ ...EMPTY_ITEM }]);
  const [error, setError] = useState("");

  const { data: directory } = useStaffDirectory("doctor");
  const { data: dentalSchedules } = useDoctorSchedules(undefined, "dental");
  const createPlan = useCreateTreatmentPlan();

  // A dentist is a doctor who runs a dental clinic. Until the rota is set up
  // on the Dentists tab, fall back to the full doctor list so plans can still
  // be raised.
  const scheduledDentists = Array.from(
    new Map(
      (dentalSchedules ?? []).map((schedule) => [
        schedule.doctor_id,
        schedule.doctor_name ?? schedule.doctor_id,
      ])
    ).entries()
  ).map(([id, name]) => ({ id, name }));

  const allDoctors = (directory?.items ?? [])
    .filter((staff) => staff.is_active)
    .map((staff) => ({
      id: staff.id,
      name: [staff.title, staff.first_name, staff.last_name]
        .filter(Boolean)
        .join(" ")
        .trim(),
    }));

  const usingFallback = scheduledDentists.length === 0;
  const dentists = usingFallback ? allDoctors : scheduledDentists;

  const totalCents = items.reduce((sum, item) => {
    const parsed = Number(item.estimatedCostKes);
    return sum + (Number.isFinite(parsed) ? Math.round(parsed * 100) : 0);
  }, 0);

  /**
   * Replace one line item.
   *
   * @param index - Item index to update
   * @param patch - Fields to merge into the item
   */
  const updateItem = (index: number, patch: Partial<PlanItemDraft>) => {
    setItems((prev) =>
      prev.map((item, i) => (i === index ? { ...item, ...patch } : item))
    );
  };

  /** Append a blank line item. */
  const addItem = () => setItems((prev) => [...prev, { ...EMPTY_ITEM }]);

  /**
   * Remove a line item, keeping at least one row.
   *
   * @param index - Item index to remove
   */
  const removeItem = (index: number) =>
    setItems((prev) =>
      prev.length === 1 ? prev : prev.filter((_, i) => i !== index)
    );

  /** Validate and submit the plan. */
  const handleSubmit = async () => {
    if (!patient) {
      setError(t("patientRequired"));
      return;
    }
    if (!dentistId) {
      setError(t("dentistRequired"));
      return;
    }
    setError("");

    const payload: DentalTreatmentPlanCreate = {
      patient_id: patient.id,
      dentist_id: dentistId,
      diagnosis: diagnosis || null,
      notes: notes || null,
      total_estimated_cost: totalCents,
      plan_items: items.map((item) => ({
        tooth: item.tooth || null,
        procedure_type: item.procedure_type,
        estimated_cost: Math.round(Number(item.estimatedCostKes) * 100) || 0,
      })),
    };

    try {
      await createPlan.mutateAsync(payload);
      onDone();
    } catch {
      setError(tc("retrySync"));
    }
  };

  const inputClass =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm";
  const labelClass = "mb-1 block text-sm font-medium text-foreground";

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <PatientLookup value={patient} onSelect={setPatient} required />
        </div>
        <div>
          <label className={labelClass}>{t("dentist")}</label>
          <select
            value={dentistId}
            onChange={(e) => setDentistId(e.target.value)}
            className={inputClass}
          >
            <option value="">{t("dentistRequired")}</option>
            {dentists.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
          {usingFallback && (
            <p className="mt-1 text-xs text-muted-foreground">
              {t("noDentistRota")}
            </p>
          )}
        </div>
        <div className="lg:col-span-2">
          <label className={labelClass}>{t("diagnosis")}</label>
          <textarea
            value={diagnosis}
            onChange={(e) => setDiagnosis(e.target.value)}
            rows={2}
            className={inputClass}
          />
        </div>
      </div>

      <div className="mt-5">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-foreground">
            {t("planItems")}
          </h3>
          <button
            type="button"
            onClick={addItem}
            className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted"
          >
            <Plus className="h-3.5 w-3.5" />
            {t("addItem")}
          </button>
        </div>

        <div className="space-y-2">
          {items.map((item, index) => (
            <div
              key={index}
              className="grid grid-cols-1 gap-2 sm:grid-cols-[2fr_1fr_1fr_auto]"
            >
              <select
                value={item.procedure_type}
                onChange={(e) =>
                  updateItem(index, { procedure_type: e.target.value })
                }
                className={inputClass}
              >
                {PROCEDURE_TYPES.map((pt) => (
                  <option key={pt} value={pt}>
                    {t(`procedureType.${pt}`)}
                  </option>
                ))}
              </select>
              <input
                value={item.tooth}
                onChange={(e) => updateItem(index, { tooth: e.target.value })}
                placeholder={t("tooth")}
                className={inputClass}
              />
              <input
                value={item.estimatedCostKes}
                onChange={(e) =>
                  updateItem(index, { estimatedCostKes: e.target.value })
                }
                inputMode="decimal"
                placeholder={t("estimatedCost")}
                className={inputClass}
              />
              <button
                type="button"
                onClick={() => removeItem(index)}
                disabled={items.length === 1}
                aria-label={tc("remove")}
                className="inline-flex items-center justify-center rounded-lg border border-border px-2.5 text-muted-foreground hover:bg-muted disabled:opacity-40"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-5">
        <label className={labelClass}>{t("notes")}</label>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          className={inputClass}
        />
      </div>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
        <span className="text-sm text-muted-foreground">
          {t("totalCost")}:{" "}
          <span className="font-semibold text-foreground">
            {formatKES(totalCents)}
          </span>
        </span>
        <div className="flex items-center gap-2">
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
            disabled={createPlan.isPending}
            className={cn(
              "rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground shadow-sm hover:opacity-90",
              createPlan.isPending && "cursor-not-allowed opacity-60"
            )}
          >
            {createPlan.isPending ? tc("saving") : t("savePlan")}
          </button>
        </div>
      </div>

      {error && (
        <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
      )}
    </div>
  );
}
