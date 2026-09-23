"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { BedDouble, Loader2, PlusCircle, Settings2, XCircle } from "lucide-react";
import { useAuth } from "@/components/providers/AuthProvider";
import {
  useWards,
  useBeds,
  useCreateWard,
  useCreateBed,
} from "@/hooks/useIPD";
import type { WardResponse, WardType } from "@aifya/shared";

const WARD_TYPE_OPTIONS: { value: WardType; label: string }[] = [
  { value: "general", label: "General" },
  { value: "icu", label: "ICU" },
  { value: "hdu", label: "HDU" },
  { value: "maternity", label: "Maternity" },
  { value: "paediatric", label: "Paediatric" },
  { value: "nicu", label: "NICU" },
  { value: "psychiatric", label: "Psychiatric" },
  { value: "isolation", label: "Isolation" },
  { value: "surgical", label: "Surgical" },
  { value: "burns", label: "Burns" },
];

const WARD_TYPE_LABELS: Record<string, string> = Object.fromEntries(
  WARD_TYPE_OPTIONS.map((o) => [o.value, o.label])
);

/**
 * Admin panel for creating wards and beds inside the IPD module.
 *
 * Visible to users with an admin role. Without at least one ward and one
 * available bed, no patient can be admitted to IPD.
 */
export function WardSetup() {
  const t = useTranslations("ipd");
  const { user } = useAuth();
  const canManage =
    !!user &&
    user.roles.some((role) => role === "admin" || role === "facility_admin");

  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [wardType, setWardType] = useState<WardType>("general");
  const [bedCount, setBedCount] = useState("2");
  const [error, setError] = useState<string | null>(null);
  const [savingWard, setSavingWard] = useState(false);

  const { data: wards, isLoading: wardsLoading } = useWards();
  const createWard = useCreateWard();
  const createBed = useCreateBed();

  if (!canManage) return null;

  const handleAddWard = async () => {
    if (!name.trim() || !code.trim()) {
      setError(t("wardSetupNameCodeRequired"));
      return;
    }
    const count = Math.min(Math.max(parseInt(bedCount, 10) || 1, 1), 50);
    const wardCode = code.trim().toUpperCase().slice(0, 20);
    setSavingWard(true);
    setError(null);
    try {
      const ward = await createWard.mutateAsync({
        name: name.trim(),
        code: wardCode,
        ward_type: wardType,
        total_beds: count,
      });
      for (let i = 1; i <= count; i += 1) {
        const bedNumber = `${wardCode}-${String(i).padStart(2, "0")}`;
        await createBed.mutateAsync({
          ward_id: ward.id,
          bed_number: bedNumber,
        });
      }
      setName("");
      setCode("");
      setBedCount("2");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("wardSetupError"));
    } finally {
      setSavingWard(false);
    }
  };

  const inputClasses =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background";

  return (
    <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-foreground">
          <Settings2 className="h-4 w-4 text-primary" />
          {t("wardSetupTitle")}
        </h2>
        <button
          onClick={() => setOpen((v) => !v)}
          className="text-xs text-muted-foreground hover:text-foreground"
        >
          {open ? t("wardSetupCollapse") : t("wardSetupExpand")}
        </button>
      </div>

      {open && (
        <>
          <p className="mb-4 mt-1 text-xs text-muted-foreground">
            {t("wardSetupHint")}
          </p>

          {/* New ward form */}
          <div className="grid gap-3 sm:grid-cols-5">
            <label className="sm:col-span-2">
              <span className="mb-1 block text-xs font-medium text-muted-foreground">
                {t("wardSetupName")}
              </span>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("wardSetupName")}
                className={inputClasses}
              />
            </label>
            <label>
              <span className="mb-1 block text-xs font-medium text-muted-foreground">
                {t("wardSetupCode")}
              </span>
              <input
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="MALE-1"
                className={inputClasses}
              />
            </label>
            <label>
              <span className="mb-1 block text-xs font-medium text-muted-foreground">
                {t("wardSetupType")}
              </span>
              <select
                value={wardType}
                onChange={(e) => setWardType(e.target.value as WardType)}
                className={inputClasses}
              >
                {WARD_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span className="mb-1 block text-xs font-medium text-muted-foreground">
                {t("wardSetupBedCount")}
              </span>
              <input
                type="number"
                min={1}
                max={50}
                value={bedCount}
                onChange={(e) => setBedCount(e.target.value)}
                className={inputClasses}
              />
            </label>
          </div>

          <div className="mt-3 flex items-center justify-between gap-3">
            {error && (
              <p className="flex items-center gap-1 text-xs text-red-600 dark:text-red-400">
                <XCircle className="h-3.5 w-3.5" />
                {error}
              </p>
            )}
            <button
              onClick={handleAddWard}
              disabled={savingWard}
              className="ml-auto inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {savingWard ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  {t("wardSetupAdding")}
                </>
              ) : (
                <>
                  <PlusCircle className="h-3.5 w-3.5" />
                  {t("wardSetupAddWard")}
                </>
              )}
            </button>
          </div>

          {/* Existing wards */}
          <div className="mt-5">
            <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              <BedDouble className="h-3.5 w-3.5" />
              {t("wardSetupExisting")}
            </h3>
            {wardsLoading ? (
              <p className="text-xs text-muted-foreground">{t("wardSetupLoading")}</p>
            ) : !wards || wards.length === 0 ? (
              <p className="text-xs text-muted-foreground">{t("wardSetupNoWardsHint")}</p>
            ) : (
              <div className="grid gap-2">
                {wards.map((ward) => (
                  <WardRow key={ward.id} ward={ward} />
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function WardRow({ ward }: { ward: WardResponse }) {
  const t = useTranslations("ipd");
  const { data: beds, isLoading } = useBeds(ward.id);
  const createBed = useCreateBed();
  const [error, setError] = useState<string | null>(null);

  const nextNumber = (beds?.length ?? 0) + 1;
  const bedNumber = `${ward.code}-${String(nextNumber).padStart(2, "0")}`;

  const handleAddBed = () => {
    setError(null);
    createBed.mutate(
      { ward_id: ward.id, bed_number: bedNumber },
      {
        onError: (err) =>
          setError(err instanceof Error ? err.message : t("wardSetupError")),
      }
    );
  };

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-muted/30 px-3 py-2">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium text-foreground">
            {ward.name}
          </span>
          <span className="font-mono text-xs text-muted-foreground">{ward.code}</span>
        </div>
        <p className="text-xs text-muted-foreground">
          {WARD_TYPE_LABELS[ward.ward_type] ?? ward.ward_type} &middot;{" "}
          {ward.available_beds} {t("available")} / {ward.occupied_beds}{" "}
          {t("occupied")}
        </p>
        {error && <p className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</p>}
      </div>
      {isLoading ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
      ) : (
        <span className="text-xs text-muted-foreground">
          {beds?.length ?? 0} {t("wardSetupBedsCreated")}
        </span>
      )}
      <button
        onClick={handleAddBed}
        disabled={createBed.isPending}
        className="inline-flex items-center gap-1 rounded-lg border border-input bg-background px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
      >
        {createBed.isPending && <Loader2 className="h-3 w-3 animate-spin" />}
        {createBed.isPending ? t("wardSetupAddingBed") : t("wardSetupAddBed")}
      </button>
    </div>
  );
}