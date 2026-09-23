"use client";

import { useTranslations } from "next-intl";
import { PlayCircle } from "lucide-react";
import type { AppointmentListItem, DentalVisitCreate } from "@aifya/shared";
import { useCreateDentalVisit } from "@/hooks/useDental";
import { useUpdateAppointment } from "@/hooks/useAppointments";

interface StartDentalVisitButtonProps {
  /** Booked dental appointment to convert into a visit. */
  appointment: AppointmentListItem;
}

/**
 * Turns a booked dental appointment into a dental visit and checks the
 * appointment in, so it leaves the scheduled list and appears under Visits.
 *
 * @param props - Component props
 * @returns Start-visit button with inline error state
 */
export function StartDentalVisitButton({
  appointment,
}: StartDentalVisitButtonProps) {
  const t = useTranslations("appointments");
  const createVisit = useCreateDentalVisit();
  const updateAppointment = useUpdateAppointment(appointment.id);

  const isPending = createVisit.isPending || updateAppointment.isPending;
  const hasError = createVisit.isError || updateAppointment.isError;

  const handleStart = async () => {
    const payload: DentalVisitCreate = {
      patient_id: appointment.patient_id,
      dentist_id: appointment.doctor_id,
      chief_complaint: appointment.visit_reason,
    };
    try {
      await createVisit.mutateAsync(payload);
      await updateAppointment.mutateAsync({ status: "checked_in" });
    } catch {
      // Surfaced through the mutation error state below.
    }
  };

  return (
    <div className="flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={handleStart}
        disabled={isPending}
        className="inline-flex items-center gap-1 whitespace-nowrap rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-medium text-foreground shadow-sm transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
      >
        <PlayCircle className="h-3.5 w-3.5" />
        {isPending ? t("startingVisit") : t("startVisit")}
      </button>
      {hasError && (
        <span className="text-xs text-red-600 dark:text-red-400">
          {t("startVisitFailed")}
        </span>
      )}
    </div>
  );
}
