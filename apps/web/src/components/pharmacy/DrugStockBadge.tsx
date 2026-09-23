"use client";

import { useTranslations } from "next-intl";
import {
  AlertTriangle,
  CheckCircle2,
  Loader2,
  PackageSearch,
  PackageX,
} from "lucide-react";
import { useDrugStock } from "@/hooks/usePharmacy";
import type { DrugStockLevel } from "@/lib/drugStock";
import { cn } from "@/lib/utils";

interface DrugStockBadgeProps {
  /** Drug being prescribed, or already prescribed. */
  drugName: string;
  /** Generic name, used to widen the inventory search. */
  genericName?: string | null;
  /** Quantity the prescriber intends to give, for an "enough on hand" check. */
  requiredQuantity?: number | null;
  /** Extra classes for spacing where the badge is embedded. */
  className?: string;
}

const LEVEL_STYLES: Record<DrugStockLevel, string> = {
  "in-stock":
    "border-green-300 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200",
  "low-stock":
    "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200",
  "out-of-stock":
    "border-red-300 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200",
  "not-stocked": "border-border bg-muted text-muted-foreground",
};

const LEVEL_ICONS: Record<DrugStockLevel, typeof CheckCircle2> = {
  "in-stock": CheckCircle2,
  "low-stock": AlertTriangle,
  "out-of-stock": PackageX,
  "not-stocked": PackageSearch,
};

/**
 * Live pharmacy-availability indicator for a prescribed medicine.
 *
 * Reports whether the drug sits in the facility inventory, how much is on
 * hand, and whether that covers the quantity being prescribed, so the
 * prescriber sees stock before the medicine is promised and the patient knows
 * what the counter can actually hand over. Matches on the leading word of the
 * drug or generic name.
 *
 * @param props - Drug identity and the quantity being prescribed
 * @returns Availability pill, or nothing when no drug name is supplied
 */
export function DrugStockBadge({
  drugName,
  genericName,
  requiredQuantity,
  className,
}: DrugStockBadgeProps) {
  const t = useTranslations("prescription");
  const { item, level, isChecking } = useDrugStock(drugName, genericName);

  if (!drugName.trim()) return null;

  if (isChecking) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-2.5 py-1 text-xs text-muted-foreground",
          className,
        )}
      >
        <Loader2 className="h-3 w-3 animate-spin" />
        {t("stockChecking")}
      </span>
    );
  }

  const onHand = item?.current_quantity ?? 0;
  const unit = item?.unit_of_measure ?? "";
  const required =
    requiredQuantity && requiredQuantity > 0 ? requiredQuantity : null;
  const shortOfStock =
    required !== null && level !== "not-stocked" && onHand < required;

  const label =
    level === "in-stock"
      ? t("stockInStock")
      : level === "low-stock"
        ? t("stockLow")
        : level === "out-of-stock"
          ? t("outOfStock")
          : t("stockNotStocked");

  const Icon = LEVEL_ICONS[level];

  return (
    <div className={cn("space-y-1", className)}>
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
          LEVEL_STYLES[level],
        )}
      >
        <Icon className="h-3 w-3" />
        {label}
        {level !== "not-stocked" && (
          <span className="font-normal opacity-80">
            {t("stockOnHand", { quantity: onHand, unit })}
          </span>
        )}
      </span>
      {shortOfStock && (
        <p className="text-xs font-medium text-amber-700 dark:text-amber-300">
          {t("stockInsufficient", { quantity: onHand, unit, required })}
        </p>
      )}
      {level === "not-stocked" && (
        <p className="text-xs text-muted-foreground">{t("stockNotStockedHint")}</p>
      )}
    </div>
  );
}