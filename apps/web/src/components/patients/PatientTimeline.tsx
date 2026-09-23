"use client";

import { useTranslations } from "next-intl";
import {
  Stethoscope,
  Pill,
  FlaskConical,
  FileText,
  Activity,
  AlertTriangle,
} from "lucide-react";
import { formatDateTime } from "@/lib/utils";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";
import { apiClient } from "@/lib/api-client";

interface TimelineEvent {
  id: string;
  event_type: string;
  event_data: Record<string, unknown>;
  created_at: string;
  stream_type: string;
}

interface TimelineResponse {
  items: TimelineEvent[];
  total: number;
}

const EVENT_ICONS: Record<string, React.ReactNode> = {
  PatientRegistered: <FileText className="h-4 w-4" />,
  PatientUpdated: <FileText className="h-4 w-4" />,
  EncounterCreated: <Stethoscope className="h-4 w-4" />,
  EncounterCompleted: <Stethoscope className="h-4 w-4" />,
  PrescriptionCreated: <Pill className="h-4 w-4" />,
  PrescriptionDispensed: <Pill className="h-4 w-4" />,
  VitalsRecorded: <Activity className="h-4 w-4" />,
  LabOrderCreated: <FlaskConical className="h-4 w-4" />,
  LabResultReceived: <FlaskConical className="h-4 w-4" />,
  DiagnosisCreated: <FileText className="h-4 w-4" />,
  AdverseEventReported: <AlertTriangle className="h-4 w-4 text-destructive" />,
};

const EVENT_COLORS: Record<string, string> = {
  PatientRegistered: "bg-primary/10 text-primary",
  EncounterCreated: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  PrescriptionCreated: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
  VitalsRecorded: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
  LabOrderCreated: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
  AdverseEventReported: "bg-destructive/10 text-destructive",
};

/**
 * Patient timeline showing event-sourced clinical history.
 * @param props.patientId - Patient UUID
 * @returns Timeline component
 */
export function PatientTimeline({ patientId }: { patientId: string }) {
  const t = useTranslations("patients");

  const { data, isLoading } = useOfflineQuery<TimelineResponse>({
    queryKey: ["patients", patientId, "timeline"],
    queryFn: () =>
      apiClient.get<TimelineResponse>(`/patients/${patientId}/timeline`),
    enabled: !!patientId,
  });

  if (isLoading) {
    return (
      <div className="py-8 text-center text-sm text-muted-foreground">
        Loading timeline...
      </div>
    );
  }

  if (!data?.items.length) {
    return (
      <div className="rounded-lg border border-border bg-card p-8 text-center text-muted-foreground dark:border-border dark:bg-card">
        {t("noEncounters")}
      </div>
    );
  }

  return (
    <div className="relative space-y-0">
      {/* Vertical line */}
      <div className="absolute left-5 top-0 bottom-0 w-px bg-border dark:bg-border" />

      {data.items.map((event) => {
        const icon = EVENT_ICONS[event.event_type] ?? <FileText className="h-4 w-4" />;
        const colorClass = EVENT_COLORS[event.event_type] ?? "bg-muted text-muted-foreground";

        return (
          <div key={event.id} className="relative flex items-start gap-4 py-3 pl-2">
            {/* Icon dot */}
            <div
              className={`z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${colorClass}`}
            >
              {icon}
            </div>

            {/* Content */}
            <div className="flex-1 rounded-lg border border-border bg-card p-3 shadow-sm dark:border-border dark:bg-card">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-foreground dark:text-foreground">
                  {formatEventType(event.event_type)}
                </p>
                <time className="text-xs text-muted-foreground">
                  {formatDateTime(event.created_at)}
                </time>
              </div>
              {event.event_data && (
                <p className="mt-1 text-xs text-muted-foreground">
                  {summarizeEventData(event.event_type, event.event_data)}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function formatEventType(eventType: string): string {
  return eventType
    .replace(/([A-Z])/g, " $1")
    .trim();
}

function summarizeEventData(
  eventType: string,
  data: Record<string, unknown>
): string {
  switch (eventType) {
    case "PatientRegistered":
      return `${data.first_name ?? ""} ${data.last_name ?? ""} registered`;
    case "EncounterCreated":
      return `${data.encounter_type ?? "Visit"} — ${data.chief_complaint ?? ""}`;
    case "PrescriptionCreated":
      return `${data.drug_name ?? ""} ${data.dosage ?? ""} ${data.frequency ?? ""}`;
    case "DiagnosisCreated":
      return `${data.icd10_code ?? ""}: ${data.icd10_description ?? ""}`;
    case "VitalsRecorded":
      return `BP: ${data.systolic_bp ?? "—"}/${data.diastolic_bp ?? "—"}, HR: ${data.heart_rate ?? "—"}, Temp: ${data.temperature ?? "—"}°C`;
    case "LabOrderCreated":
      return `${data.order_number ?? ""} — ${data.priority ?? "routine"}`;
    default:
      return "";
  }
}
