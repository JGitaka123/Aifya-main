"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  FlaskConical,
  Plus,
  ChevronDown,
  ChevronUp,
  Trash2,
} from "lucide-react";
import { useEncounterLabOrders, useCreateLabOrder } from "@/hooks/useEncounters";
import type { LabCatalogItem } from "@/hooks/useLaboratory";
import { LabTestAutocomplete } from "@/components/opd/LabTestAutocomplete";
import { cn } from "@/lib/utils";
import { formatDateTime } from "@/lib/utils";

const createLabOrderSchema = (
  testCodeRequired: string,
  testNameRequired: string,
  atLeastOneTestRequired: string,
) => z.object({
  priority: z.enum(["stat", "urgent", "routine"]),
  specimen_type: z.string().nullable().optional(),
  clinical_info: z.string().nullable().optional(),
  fasting: z.boolean().optional(),
  tests: z.array(
    z.object({
      test_code: z.string().min(1, testCodeRequired),
      test_name: z.string().min(1, testNameRequired),
      loinc_code: z.string().nullable().optional(),
      panel_name: z.string().nullable().optional(),
    })
  ).min(1, atLeastOneTestRequired),
});

type LabOrderFormData = z.infer<ReturnType<typeof createLabOrderSchema>>;

interface LabOrderPanelProps {
  encounterId: string;
  patientId: string;
}

/**
 * Lab order panel for the consultation page.
 *
 * @param props - encounterId and patientId
 * @returns Lab order panel component
 */
export function LabOrderPanel({ encounterId, patientId }: LabOrderPanelProps) {
  const t = useTranslations("lab");
  const tc = useTranslations("common");
  const labOrderSchema = createLabOrderSchema(
    t("testCodeRequired"),
    t("testNameRequired"),
    t("atLeastOneTestRequired"),
  );
  const [showForm, setShowForm] = useState(false);
  const [expanded, setExpanded] = useState(true);

  const { data: orders, isLoading } = useEncounterLabOrders(encounterId);
  const createOrder = useCreateLabOrder(encounterId);

  const { register, handleSubmit, reset, control, getValues, setValue, formState: { errors } } = useForm<LabOrderFormData>({
    resolver: zodResolver(labOrderSchema),
    defaultValues: {
      priority: "routine",
      fasting: false,
      tests: [{ test_code: "", test_name: "", loinc_code: null, panel_name: null }],
    },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "tests" });

  /**
   * Fill a test row from a catalog selection (D6). Reuses the first blank row
   * so the default empty row isn't left dangling, otherwise appends a new one.
   */
  const handleCatalogSelect = (test: LabCatalogItem) => {
    const rows = getValues("tests") ?? [];
    const blankIndex = rows.findIndex(
      (r) => !r.test_code?.trim() && !r.test_name?.trim(),
    );
    const row = {
      test_code: test.test_code,
      test_name: test.test_name,
      loinc_code: null,
      panel_name: test.panel_name ?? null,
    };
    if (blankIndex >= 0) {
      setValue(`tests.${blankIndex}`, row, { shouldValidate: true });
    } else {
      append(row);
    }
  };

  const onSubmit = (data: LabOrderFormData) => {
    createOrder.mutate(
      {
        encounter_id: encounterId,
        patient_id: patientId,
        ...data,
      },
      {
        onSuccess: () => {
          setShowForm(false);
          reset();
        },
      }
    );
  };

  const priorityColors: Record<string, string> = {
    stat: "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200",
    urgent: "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200",
    routine: "bg-muted text-foreground",
  };

  return (
    <div className="rounded-lg border border-border bg-card dark:bg-card">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-4 py-3"
      >
        <div className="flex items-center gap-2">
          <FlaskConical className="h-5 w-5 text-purple-500" />
          <h3 className="font-semibold text-foreground">{t("title")}</h3>
          {orders && orders.length > 0 && (
            <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
              {orders.length}
            </span>
          )}
        </div>
        {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
      </button>

      {expanded && (
        <div className="border-t border-border px-4 pb-4 pt-3">
          {/* Existing orders */}
          {isLoading ? (
            <p className="text-sm text-muted-foreground">{tc("loading")}</p>
          ) : orders && orders.length > 0 ? (
            <div className="mb-3 space-y-2">
              {orders.map((order) => (
                <div
                  key={order.id}
                  className="flex items-start gap-3 rounded-lg border border-border p-3"
                >
                  <FlaskConical className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-medium text-primary">
                        {order.order_number}
                      </span>
                      <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", priorityColors[order.priority])}>
                        {t(order.priority as Parameters<typeof t>[0])}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {order.status}
                      </span>
                    </div>
                    {order.specimen_type && (
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {t("specimenType")}: {order.specimen_type}
                      </p>
                    )}
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {formatDateTime(order.created_at)}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="mb-3 text-sm text-muted-foreground">{t("noOrders")}</p>
          )}

          {/* Add lab order form */}
          {!showForm ? (
            <button
              onClick={() => setShowForm(true)}
              className="flex items-center gap-1 text-sm font-medium text-primary hover:underline"
            >
              <Plus className="h-4 w-4" />
              {t("order")}
            </button>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-3">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("priority")}</label>
                  <select
                    {...register("priority")}
                    className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                  >
                    <option value="routine">{t("routine")}</option>
                    <option value="urgent">{t("urgent")}</option>
                    <option value="stat">{t("stat")}</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("specimenType")}</label>
                  <select
                    {...register("specimen_type")}
                    className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                  >
                    <option value="">—</option>
                    <option value="blood">{t("blood")}</option>
                    <option value="urine">{t("urine")}</option>
                    <option value="csf">{t("csf")}</option>
                    <option value="stool">{t("stool")}</option>
                    <option value="sputum">{t("sputum")}</option>
                    <option value="swab">{t("swab")}</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <label className="flex items-center gap-2 pb-1.5 text-sm text-foreground">
                    <input type="checkbox" {...register("fasting")} className="rounded border-input" />
                    {t("fastingRequired")}
                  </label>
                </div>
              </div>

              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("clinicalInfo")}</label>
                <input
                  {...register("clinical_info")}
                  className="w-full rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                />
              </div>

              {/* Tests */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-xs font-medium text-muted-foreground">{t("tests")}</label>
                  <button
                    type="button"
                    onClick={() => append({ test_code: "", test_name: "", loinc_code: null, panel_name: null })}
                    className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                  >
                    <Plus className="h-3 w-3" />
                    {t("addTest")}
                  </button>
                </div>
                {/* Catalog type-ahead (D6): fills code/name/price from the
                    managed catalog. The rows below remain a free-text fallback. */}
                <div className="mb-2">
                  <LabTestAutocomplete onSelect={handleCatalogSelect} />
                </div>
                <div className="space-y-2">
                  {fields.map((field, index) => (
                    <div key={field.id} className="flex items-start gap-2">
                      <input
                        {...register(`tests.${index}.test_code`)}
                        placeholder={t("testCode")}
                        className="w-28 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                      />
                      <input
                        {...register(`tests.${index}.test_name`)}
                        placeholder={t("testName")}
                        className="flex-1 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                      />
                      <input
                        {...register(`tests.${index}.panel_name`)}
                        placeholder={t("panel")}
                        className="w-24 rounded-md border border-input bg-background px-2.5 py-1.5 text-sm text-foreground dark:border-border dark:bg-background"
                      />
                      {fields.length > 1 && (
                        <button
                          type="button"
                          onClick={() => remove(index)}
                          className="rounded p-1.5 text-muted-foreground hover:bg-muted hover:text-red-500"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                {errors.tests && (
                  <p className="mt-1 text-xs text-red-500">
                    {errors.tests.root?.message ?? errors.tests.message}
                  </p>
                )}
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="submit"
                  disabled={createOrder.isPending}
                  className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {createOrder.isPending ? t("ordering") : t("order")}
                </button>
                <button
                  type="button"
                  onClick={() => { setShowForm(false); reset(); }}
                  className="rounded-lg border border-input px-4 py-2 text-sm font-medium text-foreground hover:bg-muted"
                >
                  {tc("cancel")}
                </button>
              </div>
            </form>
          )}
        </div>
      )}
    </div>
  );
}
