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
import { useMySchedule, useUpdateMySchedule } from "@/hooks/useAvailability";

/**
 * The clinician's own working week.
 *
 * HR owns the role, department and specialty; this screen only lets a
 * clinician keep their days and hours honest, so the patient picker knows
 * whether they are on duty today. The staff row is resolved from the token,
 * so there is no id here to point at somebody else.
 *
 * @returns Weekly availability editor
 */
export default function MyAvailabilityPage() {
  const t = useTranslations("availability");
  const tc = useTranslations("common");
  const { data, isLoading, isError } = useMySchedule();
  const update = useUpdateMySchedule();
  const [drafts, setDrafts] = useState<ClinicSessionDraft[]>([]);

  useEffect(() => {
    if (data) setDrafts(scheduleToDrafts(data.slots));
  }, [data]);

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        {tc("loading")}
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        {t("notLinked")}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl animate-[fade-in_0.3s_ease-out] space-y-6 p-5 sm:p-6 lg:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold text-foreground">
            <CalendarClock className="h-6 w-6" />
            {t("title")}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <WorkStatusBadge status={data.work_status} />
      </div>

      <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-foreground">
            {t("currentStatus")}
          </h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {data.scheduled_today
              ? t("scheduledToday")
              : t("notScheduledToday")}
          </p>
        </div>

        <ClinicScheduleFields
          drafts={drafts}
          onChange={setDrafts}
          showClinicDetails={false}
        />

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">{t("saveHint")}</p>
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
      </div>
    </div>
  );
}