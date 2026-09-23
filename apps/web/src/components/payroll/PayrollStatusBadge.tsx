"use client";

import { useTranslations } from "next-intl";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type { PayrollRunStatus } from "@/hooks/usePayroll";

const STATUS_VARIANT: Record<
  PayrollRunStatus,
  "default" | "success" | "warning" | "error" | "info" | "purple"
> = {
  draft: "default",
  approved: "info",
  posted: "success",
  locked: "purple",
};

/**
 * Status badge for payroll runs.
 *
 * @param status - Run status
 * @returns Color-coded status badge
 */
export function PayrollStatusBadge({ status }: { status: PayrollRunStatus }) {
  const t = useTranslations("payroll");
  return (
    <StatusBadge variant={STATUS_VARIANT[status]} dot>
      {t(`runStatus_${status}`)}
    </StatusBadge>
  );
}
