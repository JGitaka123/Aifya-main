"use client";

import { useTranslations } from "next-intl";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { formatKES } from "@/lib/utils";

/** Payment state of one ordered service, as the receiving department sees it. */
export type ServiceChargeState =
  | "not_charged"
  | "paid"
  | "partial"
  | "unpaid";

const VARIANT: Record<
  ServiceChargeState,
  "success" | "warning" | "error" | "neutral"
> = {
  paid: "success",
  partial: "warning",
  unpaid: "error",
  not_charged: "neutral",
};

const LABEL_KEY: Record<
  ServiceChargeState,
  "paid" | "partial" | "unpaid" | "notCharged"
> = {
  paid: "paid",
  partial: "partial",
  unpaid: "unpaid",
  not_charged: "notCharged",
};

/**
 * Payment state of one ordered service — a lab test, an imaging study or a
 * prescription — shown on the department worklist.
 *
 * A department must never treat "the patient paid something" as "this request
 * is covered", so the badge names the state of this exact request and, when
 * money is still owed, the amount outstanding.
 *
 * @param props - Charge state and amounts for the request
 * @returns Payment badge
 */
export function ServiceChargeBadge({
  status,
  balanceCents = null,
  totalCents = null,
  className,
}: {
  status: ServiceChargeState;
  balanceCents?: number | null;
  totalCents?: number | null;
  className?: string;
}) {
  const t = useTranslations("serviceCharge");
  const owed = status === "unpaid" || status === "partial";
  const amount = owed ? (balanceCents ?? 0) : (totalCents ?? 0);
  const suffix = amount > 0 ? ` - ${formatKES(amount)}` : "";

  return (
    <StatusBadge
      variant={VARIANT[status]}
      size="xs"
      className={className}
      dot
    >
      {t(LABEL_KEY[status])}
      {suffix}
    </StatusBadge>
  );
}
