"use client";

import { useTranslations } from "next-intl";
import type { DentalTreatmentPlanResponse, TreatmentPlanStatus } from "@aifya/shared";
import { useUpdateTreatmentPlanStatus } from "@/hooks/useDental";
import { cn } from "@/lib/utils";

/** The single onward move available from each plan status. */
const NEXT_STEP: Record<
  string,
  { status: TreatmentPlanStatus; labelKey: string; style: string }
> = {
  draft: {
    status: "approved",
    labelKey: "actionApprove",
    style: "bg-blue-100 text-blue-800 hover:bg-blue-200 dark:bg-blue-950 dark:text-blue-200",
  },
  approved: {
    status: "in_progress",
    labelKey: "actionStart",
    style: "bg-purple-100 text-purple-800 hover:bg-purple-200 dark:bg-purple-950 dark:text-purple-200",
  },
  in_progress: {
    status: "completed",
    labelKey: "actionComplete",
    style: "bg-green-100 text-green-800 hover:bg-green-200 dark:bg-green-950 dark:text-green-200",
  },
};

interface TreatmentPlanActionsProps {
  /** Treatment plan the buttons act on. */
  plan: DentalTreatmentPlanResponse;
}

/**
 * Lifecycle buttons for one treatment plan row. Moving a plan to completed
 * removes it from the "Pending treatments" summary count.
 *
 * @param props - Component props
 * @returns Status transition controls
 */
export function TreatmentPlanActions({ plan }: TreatmentPlanActionsProps) {
  const t = useTranslations("dental");
  const tc = useTranslations("common");
  const mutation = useUpdateTreatmentPlanStatus();

  const next = NEXT_STEP[plan.status];
  const canCancel = plan.status !== "completed" && plan.status !== "cancelled";

  /**
   * Apply a status transition.
   *
   * @param status - Target plan status
   */
  const apply = async (status: TreatmentPlanStatus) => {
    try {
      await mutation.mutateAsync({ planId: plan.id, status });
    } catch {
      // Surfaced through the mutation error state below.
    }
  };

  return (
    <div className="flex flex-col items-start gap-1">
      <div className="flex flex-wrap items-center gap-1.5">
        {next && (
          <button
            type="button"
            disabled={mutation.isPending}
            onClick={() => apply(next.status)}
            className={cn(
              "whitespace-nowrap rounded-lg px-2.5 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
              next.style
            )}
          >
            {t(next.labelKey)}
          </button>
        )}
        {canCancel && (
          <button
            type="button"
            disabled={mutation.isPending}
            onClick={() => apply("cancelled")}
            className="whitespace-nowrap rounded-lg border border-border px-2.5 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
          >
            {t("actionCancelPlan")}
          </button>
        )}
      </div>
      {mutation.isError && (
        <span className="text-xs text-red-600 dark:text-red-400">
          {tc("retrySync")}
        </span>
      )}
    </div>
  );
}
