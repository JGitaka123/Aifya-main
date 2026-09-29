"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Loader2, Plus, XCircle } from "lucide-react";
import { useCreateTheatre } from "@/hooks/useTheatre";
import type { TheatreType } from "@aifya/shared";

/** Theatre types the backend accepts. */
const THEATRE_TYPES: readonly TheatreType[] = [
  "general",
  "orthopaedic",
  "cardiac",
  "neuro",
  "ophthalmic",
  "obstetric",
  "ent",
  "dental",
  "minor",
];

/**
 * Add an operating theatre to the facility.
 *
 * A facility with no theatres can never book a case, so the board offers this
 * rather than sending an administrator to another screen.
 *
 * @param props.onCreated - Called with the new theatre name
 * @param props.onCancel - Called when the operator closes the form
 * @returns New-theatre form
 */
export function NewTheatrePanel({
  onCreated,
  onCancel,
}: {
  onCreated: (name: string) => void;
  onCancel: () => void;
}) {
  const t = useTranslations("theatre");
  const [name, setName] = useState("");
  const [theatreType, setTheatreType] = useState<TheatreType>("general");
  const [floor, setFloor] = useState("");
  const [error, setError] = useState<string | null>(null);
  const create = useCreateTheatre();

  const handleSubmit = () => {
    if (!name.trim()) {
      setError(t("theatreNameRequired"));
      return;
    }
    setError(null);
    create.mutate(
      {
        name: name.trim(),
        theatre_type: theatreType,
        floor: floor.trim() || null,
      },
      {
        onSuccess: (created) => onCreated(created.name),
        onError: (err) => setError(err.message ?? t("createFailed")),
      }
    );
  };

  const selectClasses =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background";
  const labelClasses = "mb-1 block text-xs font-medium text-muted-foreground";

  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-foreground">{t("theatreFormTitle")}</h3>
          <p className="mt-0.5 text-xs text-muted-foreground">{t("theatreFormSubtitle")}</p>
        </div>
        <button
          onClick={onCancel}
          className="inline-flex shrink-0 items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          <XCircle className="h-3.5 w-3.5" />
          {t("cancel")}
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block">
          <span className={labelClasses}>{t("theatreNameLabel")}</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={t("theatreNamePlaceholder")}
            className={selectClasses}
          />
        </label>

        <label className="block">
          <span className={labelClasses}>{t("theatreTypeLabel")}</span>
          <select
            value={theatreType}
            onChange={(e) => setTheatreType(e.target.value as TheatreType)}
            className={selectClasses}
          >
            {THEATRE_TYPES.map((value) => (
              <option key={value} value={value}>
                {t("theatreType." + value)}
              </option>
            ))}
          </select>
        </label>

        <label className="block sm:col-span-2">
          <span className={labelClasses}>{t("theatreFloorLabel")}</span>
          <input
            value={floor}
            onChange={(e) => setFloor(e.target.value)}
            placeholder={t("theatreFloorPlaceholder")}
            className={selectClasses}
          />
        </label>
      </div>

      {error && <p className="mt-3 text-xs text-red-600 dark:text-red-400">{error}</p>}

      <div className="mt-4 flex items-center justify-end">
        <button
          onClick={handleSubmit}
          disabled={create.isPending}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {create.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Plus className="h-3.5 w-3.5" />
          )}
          {create.isPending ? t("creating") : t("newTheatre")}
        </button>
      </div>
    </div>
  );
}
