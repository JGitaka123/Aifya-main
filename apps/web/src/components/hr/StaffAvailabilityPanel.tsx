"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { CalendarClock, Check, Save } from "lucide-react";
import {
  ClinicScheduleFields,
  draftsToSlots,
  scheduleToDrafts,
  type ClinicSessionDraft,
} from "@/components/hr/ClinicScheduleFields";
import { WorkStatusBadge } from "@/components/availability/WorkStatusBadge";
import {
  useStaffSchedule,
  useUpdateStaffSchedule,
} from "@/hooks/useAvailability";

/**
 * HR's view of one employee's working week.
 *
 * Shows the effective work status the patient picker would use right now,
 * alongside an editor for the days and hours behind it. HR has this edit
 * because a clinician who is absent or locked out cannot keep their own week
 * truthful, and an out-of-date roster would misroute patients.
 *
 * @param props.staffId - Staff UUID whose week is shown
 * @returns Work schedule and availability card
 */
export function StaffAvailabilityPanel({ staffId }: { staffId: string }) {
  const t = useTranslations("availability");
  const tc = useTranslations("common");
  const { data, isLoading } = useStaffSchedule(staffId);
  const update = useUpdateStaffSchedule(staffId);
  const [drafts, setDrafts] = useState<ClinicSessionDraft[]>([]);

  useEffect(() => {
    if (data) setDrafts(scheduleToDrafts(data.slots));
  }, [data]);

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)] lg:col-span-2">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
          <CalendarClock className="h-5 w-5" />
          {t("hrPanelTitle")}
        </h2>
        {data && <WorkStatusBadge status={data.work_status} />}
      </div>

      {isLoading || !data ? (
        <p className="text-sm text-muted-foreground">{tc("loading")}</p>
      ) : (
        <>
          <p className="mb-3 text-xs text-muted-foreground">
            {data.scheduled_today
              ? t("scheduledToday")
              : t("notScheduledToday")}
          </p>

          <ClinicScheduleFields
            drafts={drafts}
            onChange={setDrafts}
            showClinicDetails={false}
          />

          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted-foreground">
              {t("hrPanelHint")}
            </p>
            <button
              type="button"
              onClick={() => update.mutate({ slots: draftsToSlots(drafts) })}
              disabled={update.isPending}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
            >
              <Save className="h-4 w-4" />
              {update.isPending ? t("saving") : t("save")}
            </button>
          </div>

          {update.isSuccess && (
            <p className="mt-3 flex items-center gap-1.5 text-xs font-medium text-green-700 dark:text-green-300">
              <Check className="h-3.5 w-3.5" />
              {t("saved")}
            </p>
          )}
          {update.isError && (
            <p className="mt-3 text-xs font-medium text-red-700 dark:text-red-300">
              {t("failed")}
            </p>
          )}
        </>
      )}
    </div>
  );
}