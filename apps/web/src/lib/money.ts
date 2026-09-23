/**
 * Cent-safe money helpers for values the finance API returns as decimal
 * strings (e.g. "1234.50"). Per CLAUDE.md money is integer KES cents —
 * summing floats accumulates rounding error, so all arithmetic here
 * converts to integer cents first.
 */

export type MoneyInput = string | number | null | undefined;

/**
 * Convert a decimal-string/number money value to integer KES cents.
 *
 * @param value - Decimal money value ("1234.50", 1234.5, null)
 * @returns Integer cents (0 for null/invalid input)
 */
export function toCents(value: MoneyInput): number {
  if (value == null) return 0;
  const n = typeof value === "string" ? Number(value) : value;
  if (!Number.isFinite(n)) return 0;
  return Math.round(n * 100);
}

/**
 * Sum decimal money values without float drift (integer-cent addition).
 *
 * @param values - Decimal money values
 * @returns Total in integer cents
 */
export function sumCents(values: MoneyInput[]): number {
  return values.reduce<number>((total, v) => total + toCents(v), 0);
}

/**
 * Convert integer cents back to a decimal number for display components
 * that expect KES units.
 *
 * @param cents - Integer KES cents
 * @returns KES units (cents / 100)
 */
export function centsToUnits(cents: number): number {
  return cents / 100;
}

/**
 * Exact equality check for two decimal money values (compares cents).
 *
 * @param a - First value
 * @param b - Second value
 * @returns Whether the values represent the same amount
 */
export function moneyEquals(a: MoneyInput, b: MoneyInput): boolean {
  return toCents(a) === toCents(b);
}
