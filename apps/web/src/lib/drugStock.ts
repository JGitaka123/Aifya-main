import type { PharmacyItem } from "@aifya/shared";

/** How much of a prescribed drug the pharmacy actually holds. */
export type DrugStockLevel = "in-stock" | "low-stock" | "out-of-stock" | "not-stocked";

/**
 * Reduce a drug label to a single comparable keyword.
 *
 * Prescribers and the pharmacy catalogue rarely spell a drug the same way
 * ("Amoxicillin 500mg caps" against "Amoxicillin"), so the leading word is the
 * most reliable coarse join between the two sides.
 *
 * @param value - Drug or generic name
 * @returns Lower-cased leading word, or "" when there is nothing to match on
 */
export function drugLookupKey(value?: string | null): string {
  const cleaned = (value ?? "").trim().toLowerCase();
  if (!cleaned) return "";
  return cleaned.split(/[\s,;:./()-]+/)[0] ?? "";
}

/** Score awarded when the inventory name is exactly the prescribed drug. */
const EXACT_MATCH = 4000;
/** Score base for the inventory name being a prefix of the prescribed drug. */
const PRESCRIBED_PREFIX = 3000;
/** Score base for the inventory name being exactly the prescribed keyword. */
const KEYWORD_MATCH = 2000;
/** Score base for the inventory name starting with the prescribed drug. */
const NAME_PREFIX = 1500;
/** Score base for the inventory name starting with the prescribed keyword. */
const KEYWORD_PREFIX = 1000;
/** Score base for an exact generic-name match. */
const GENERIC_MATCH = 500;
/** Score base for a generic-name prefix match. */
const GENERIC_PREFIX = 250;
/** Score for the prescribed keyword appearing somewhere in the name. */
const NAME_CONTAINS = 100;
/** Score for the generic keyword appearing somewhere in the generic name. */
const GENERIC_CONTAINS = 50;

/**
 * Score how well one inventory row matches a prescribed drug.
 *
 * Higher is better, and the row's name length breaks ties inside a tier. That
 * ordering matters clinically: prescribing "Amoxicillin Syrup" must report the
 * syrup on hand, not the plain tablets, while a plain "Amoxicillin"
 * prescription still resolves to the exact tablet row.
 *
 * @param item - Inventory row
 * @param drugName - Prescribed drug name
 * @param genericName - Prescribed generic name
 * @returns Match score; 0 means the row is unrelated
 */
export function scoreStockMatch(
  item: PharmacyItem,
  drugName?: string | null,
  genericName?: string | null,
): number {
  const prescribed = (drugName ?? "").trim().toLowerCase();
  const prescribedGeneric = (genericName ?? "").trim().toLowerCase();
  const key = drugLookupKey(prescribed);
  const genericKey = drugLookupKey(prescribedGeneric);
  if (!key && !genericKey) return 0;

  const itemName = item.drug_name.trim().toLowerCase();
  const itemGeneric = (item.generic_name ?? "").trim().toLowerCase();
  const nameLength = itemName.length;

  if (itemName && itemName === prescribed) return EXACT_MATCH;
  if (prescribed && itemName && prescribed.startsWith(itemName)) {
    return PRESCRIBED_PREFIX + nameLength;
  }
  if (key && itemName === key) return KEYWORD_MATCH + nameLength;
  if (prescribed && itemName.startsWith(prescribed)) {
    return NAME_PREFIX + nameLength;
  }
  if (key && itemName.startsWith(key)) return KEYWORD_PREFIX + nameLength;
  if (genericKey && itemGeneric && itemGeneric === prescribedGeneric) {
    return GENERIC_MATCH + nameLength;
  }
  if (genericKey && itemGeneric.startsWith(genericKey)) {
    return GENERIC_PREFIX + nameLength;
  }
  if (key && itemName.includes(key)) return NAME_CONTAINS + nameLength;
  if (genericKey && itemGeneric.includes(genericKey)) {
    return GENERIC_CONTAINS + nameLength;
  }
  return 0;
}

/**
 * Find every inventory row that could stand in for a prescribed drug.
 *
 * @param items - Inventory rows to search
 * @param drugName - Prescribed drug name
 * @param genericName - Prescribed generic name
 * @returns Matching rows, best match first
 */
export function findStockMatches(
  items: PharmacyItem[] | undefined,
  drugName?: string | null,
  genericName?: string | null,
): PharmacyItem[] {
  return (items ?? [])
    .map((item) => ({
      item,
      score: scoreStockMatch(item, drugName, genericName),
    }))
    .filter((candidate) => candidate.score > 0)
    .sort(
      (a, b) =>
        b.score - a.score || a.item.drug_name.localeCompare(b.item.drug_name),
    )
    .map((candidate) => candidate.item);
}

/**
 * Pick the single inventory row an availability badge should report on.
 *
 * @param items - Inventory rows to search
 * @param drugName - Prescribed drug name
 * @param genericName - Prescribed generic name
 * @returns Best match, or null when the drug is not in the catalogue
 */
export function pickStockMatch(
  items: PharmacyItem[] | undefined,
  drugName?: string | null,
  genericName?: string | null,
): PharmacyItem | null {
  return findStockMatches(items, drugName, genericName)[0] ?? null;
}

/**
 * Classify an inventory row into a stock level.
 *
 * @param item - Inventory row, or null when nothing matched
 * @returns Stock level used to colour the availability badge
 */
export function drugStockLevel(item?: PharmacyItem | null): DrugStockLevel {
  if (!item) return "not-stocked";
  if (item.current_quantity <= 0) return "out-of-stock";
  if (item.reorder_level > 0 && item.current_quantity <= item.reorder_level) {
    return "low-stock";
  }
  return "in-stock";
}