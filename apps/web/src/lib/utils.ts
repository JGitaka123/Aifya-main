import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Merge Tailwind CSS classes with proper precedence.
 * @param inputs - Class names or conditional class expressions
 * @returns Merged class string
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Format money in KES from cents to display string.
 * @param cents - Amount in KES cents (integer)
 * @returns Formatted string like "KES 1,234.56"
 */
export function formatKES(cents: number): string {
  const amount = cents / 100;
  return `KES ${amount.toLocaleString("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

/**
 * Format a date to Africa/Nairobi timezone.
 * @param date - ISO date string or Date object
 * @returns Formatted date string
 */
export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat("en-KE", {
    timeZone: "Africa/Nairobi",
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(date));
}

/**
 * Format a datetime to Africa/Nairobi timezone.
 * @param date - ISO date string or Date object
 * @returns Formatted datetime string
 */
export function formatDateTime(date: string | Date): string {
  return new Intl.DateTimeFormat("en-KE", {
    timeZone: "Africa/Nairobi",
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(date));
}

/** Unit an elapsed clinical duration is displayed in. */
export type ElapsedUnit = "minutes" | "hours" | "days";

/** Elapsed time rolled up to a single unit. */
export interface ElapsedDuration {
  /** Whole number of `unit`s elapsed. */
  count: number;
  /** Largest sensible unit for the elapsed time. */
  unit: ElapsedUnit;
  /** `ipd` message key including the number, e.g. "3 days". */
  key: string;
  /** `ipd` message key for the unit alone, e.g. "days". */
  unitKey: string;
}

const MINUTES_PER_HOUR = 60;
const MINUTES_PER_DAY = 60 * 24;

/**
 * Elapsed time since a timestamp, rolled up to the largest sensible unit.
 *
 * Minutes below one hour, whole hours below one day, and whole days from
 * 24 hours onwards, so a long stay reads "3 days" rather than "4320 minutes".
 * Pass `until` for a closed episode so the timer stops instead of running on.
 *
 * @param since - ISO start timestamp (e.g. admitted_at)
 * @param until - ISO end timestamp (e.g. discharged_at); defaults to now
 * @returns Elapsed count with its unit and message keys, or null when unusable
 */
export function elapsedDuration(
  since?: string | null,
  until?: string | null
): ElapsedDuration | null {
  if (!since) return null;
  const startedAt = new Date(since).getTime();
  if (Number.isNaN(startedAt)) return null;
  const endedAt = until ? new Date(until).getTime() : Date.now();
  if (Number.isNaN(endedAt)) return null;

  const minutes = Math.max(0, Math.floor((endedAt - startedAt) / 60_000));
  if (minutes < MINUTES_PER_HOUR) {
    return { count: minutes, unit: "minutes", key: "lengthMinutes", unitKey: "unitMinutes" };
  }
  if (minutes < MINUTES_PER_DAY) {
    return {
      count: Math.floor(minutes / MINUTES_PER_HOUR),
      unit: "hours",
      key: "lengthHours",
      unitKey: "unitHours",
    };
  }
  return {
    count: Math.floor(minutes / MINUTES_PER_DAY),
    unit: "days",
    key: "lengthDays",
    unitKey: "unitDays",
  };
}

/**
 * Generate a UUID v4.
 * @returns UUID string
 */
export function generateId(): string {
  return crypto.randomUUID();
}

/**
 * Build the URL a browser opens to print a receipt PDF.
 *
 * The link always goes through the app's own `/api/v1` proxy rather than
 * `NEXT_PUBLIC_API_URL`: the receipt is authorised by the session cookie,
 * which the browser only sends back to the app's own origin, and next.config
 * rewrites `/api/v1/*` to the API.
 *
 * @param path - Receipt path returned by the payment API
 * @returns Same-origin URL for the receipt
 */
export function receiptHref(path: string): string {
  return "/api/v1" + (path.startsWith("/") ? path : "/" + path);
}
