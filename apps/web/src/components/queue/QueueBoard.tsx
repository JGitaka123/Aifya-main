"use client";

import { useTranslations } from "next-intl";
import {
  ArrowRightLeft,
  BellRing,
  Check,
  Clock,
  Megaphone,
  Play,
  TriangleAlert,
  UserX,
  X,
} from "lucide-react";

import { EmptyState } from "@/components/ui/EmptyState";
import { StatusBadge } from "@/components/ui/StatusBadge";
import type {
  QueueAction,
  QueueBoard as QueueBoardData,
  QueueTicket,
  QueueTicketStatus,
} from "@/hooks/useQueue";

/** Triage colours, matching the OPD workspace. */
const TRIAGE_VARIANT: Record<
  string,
  "red-solid" | "orange-solid" | "yellow-solid" | "green-solid" | "blue-solid"
> = {
  emergency: "red-solid",
  urgent: "orange-solid",
  standard: "yellow-solid",
  "non-urgent": "green-solid",
  non_urgent: "green-solid",
  dead: "blue-solid",
};

/** Where each state sits in the room. */
const STATUS_VARIANT: Record<
  string,
  "warning" | "info" | "success" | "purple" | "default" | "error"
> = {
  WAITING: "warning",
  CALLED: "info",
  IN_SERVICE: "success",
  COMPLETED: "default",
  NO_SHOW: "error",
  CANCELLED: "error",
  TRANSFERRED: "purple",
};

const ACTION_ICON: Record<QueueAction, typeof BellRing> = {
  call: Megaphone,
  recall: BellRing,
  start: Play,
  complete: Check,
  "no-show": UserX,
  cancel: X,
  priority: TriangleAlert,
  transfer: ArrowRightLeft,
} as Record<QueueAction, typeof BellRing>;

/** The moves a ticket allows, from the state machine's point of view. */
export function actionsFor(status: QueueTicketStatus): QueueAction[] {
  switch (status) {
    case "WAITING":
      return ["call", "priority", "transfer", "cancel"];
    case "CALLED":
      return ["recall", "start", "no-show", "transfer", "cancel"];
    case "IN_SERVICE":
      return ["complete", "transfer"];
    default:
      return [];
  }
}

export interface QueueBoardProps {
  board: QueueBoardData;
  /** Runs a state transition on one ticket. */
  onAction: (action: QueueAction, ticket: QueueTicket) => void;
  /** Ticket currently being mutated, so its buttons can be disabled. */
  pendingTicketId?: string | null;
}

/**
 * The live waiting list, as the person calling patients sees it.
 *
 * @param props - See QueueBoardProps
 * @returns The board, or an empty state when nobody is waiting
 */
export function QueueBoard({ board, onAction, pendingTicketId }: QueueBoardProps) {
  const t = useTranslations("queue");

  if (board.items.length === 0) {
    return (
      <EmptyState
        icon={Clock}
        title={t("emptyTitle")}
        description={t("emptyDescription")}
      />
    );
  }

  return (
    <ul className="space-y-3">
      {board.items.map((ticket) => {
        const busy = pendingTicketId === ticket.id;
        return (
          <li
            key={ticket.id}
            className="rounded-xl border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary/30"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0 space-y-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-2xl font-bold tracking-tight text-foreground">
                    {ticket.ticket_number}
                  </span>
                  <StatusBadge variant={STATUS_VARIANT[ticket.status] ?? "default"} size="sm">
                    {t(ticketStatusKey(ticket.status))}
                  </StatusBadge>
                  {ticket.triage_category && (
                    <StatusBadge
                      variant={TRIAGE_VARIANT[ticket.triage_category] ?? "default"}
                      size="sm"
                    >
                      {t(triageKey(ticket.triage_category))}
                    </StatusBadge>
                  )}
                  {ticket.recall_count > 0 && (
                    <span className="text-xs font-medium text-muted-foreground">
                      {t("recalledTimes", { count: ticket.recall_count })}
                    </span>
                  )}
                </div>
                <p className="truncate text-sm font-semibold text-foreground">
                  {ticket.patient_name ?? t("unknownPatient")}
                  {ticket.patient_mrn && (
                    <span className="ml-2 font-mono text-xs font-normal text-muted-foreground">
                      {ticket.patient_mrn}
                    </span>
                  )}
                </p>
                <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <Megaphone className="h-3.5 w-3.5" />
                    {ticket.service_point_label ?? t("unassignedRoom")}
                  </span>
                  <span>{ticket.department_name ?? t("unassignedDepartment")}</span>
                  {ticket.waiting_minutes !== null && (
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5" />
                      {t("waitedMinutes", { minutes: ticket.waiting_minutes })}
                    </span>
                  )}
                  {ticket.waiting_position !== null && (
                    <span>{t("position", { position: ticket.waiting_position })}</span>
                  )}
                </p>
                {ticket.notes && (
                  <p className="truncate text-xs text-muted-foreground">{ticket.notes}</p>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {actionsFor(ticket.status).map((action) => {
                  const Icon = ACTION_ICON[action];
                  const primary = action === "call" || action === "recall" || action === "start";
                  return (
                    <button
                      key={action}
                      type="button"
                      disabled={busy}
                      onClick={() => onAction(action, ticket)}
                      className={
                        "inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 " +
                        (primary
                          ? "border-primary bg-primary text-primary-foreground hover:bg-primary/90"
                          : "border-border bg-background text-foreground hover:bg-muted")
                      }
                    >
                      <Icon className="h-3.5 w-3.5" />
                      {t(actionKey(action))}
                    </button>
                  );
                })}
              </div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

/** Translation key for a ticket status. */
export function ticketStatusKey(status: QueueTicketStatus): string {
  switch (status) {
    case "WAITING":
      return "statusWaiting";
    case "CALLED":
      return "statusCalled";
    case "IN_SERVICE":
      return "statusInService";
    case "COMPLETED":
      return "statusCompleted";
    case "NO_SHOW":
      return "statusNoShow";
    case "CANCELLED":
      return "statusCancelled";
    default:
      return "statusTransferred";
  }
}

function triageKey(triage: string): string {
  return "triage_" + triage.replace(/-/g, "_");
}

function actionKey(action: QueueAction): string {
  return "action_" + action.replace(/-/g, "");
}
