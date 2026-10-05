"use client";

import { useCallback, useMemo, useState } from "react";
import { useTranslations } from "next-intl";
import { useQueryClient, type UseMutationResult } from "@tanstack/react-query";
import { ListOrdered, Megaphone } from "lucide-react";

import { PageHeader } from "@/components/ui/PageHeader";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { useToast } from "@/components/ui/Toast";
import { AudioAnnouncer } from "@/components/queue/AudioAnnouncer";
import { QueueBoard } from "@/components/queue/QueueBoard";
import { useDepartments } from "@/hooks/useEncounters";
import { ApiError, isServerUnavailable } from "@/lib/api-client";
import {
  reduceBoard,
  useCallNext,
  useQueueBoard,
  useQueueServicePoints,
  useQueueStats,
  useQueueStream,
  useTicketAction,
  useTransferTicket,
  type QueueAction,
  type QueueBoard as QueueBoardData,
  type QueueSpeech,
  type QueueStreamEvent,
  type QueueTicket,
} from "@/hooks/useQueue";

/** One ticket mutation, as every action button sees it. */
type TicketMutation = UseMutationResult<
  QueueTicket,
  Error,
  { ticketId: string; body?: Record<string, unknown> }
>;

/**
 * The waiting room desk.
 *
 * Anyone signed in at reception or in nursing can see the board and call the
 * next patient. Every button here is a courteous shortcut for one API call -
 * the server decides who may do what, and the database decides what is true.
 *
 * @returns The staff queue dashboard
 */
export default function QueuePage() {
  const t = useTranslations("queue");
  const toast = useToast();
  const queryClient = useQueryClient();

  const [departmentId, setDepartmentId] = useState("");
  const [servicePointId, setServicePointId] = useState("");
  const [includeCompleted, setIncludeCompleted] = useState(false);
  const [pendingTicketId, setPendingTicketId] = useState<string | null>(null);
  const [speech, setSpeech] = useState<QueueSpeech | null>(null);
  const [speechTicketId, setSpeechTicketId] = useState<string | undefined>(undefined);
  const [transferFrom, setTransferFrom] = useState<QueueTicket | null>(null);
  const [transferTarget, setTransferTarget] = useState("");

  const departments = useDepartments();
  const servicePoints = useQueueServicePoints();

  const filters = useMemo(
    () => ({
      departmentId: departmentId || undefined,
      servicePointId: servicePointId || undefined,
      includeCompleted,
    }),
    [departmentId, servicePointId, includeCompleted],
  );

  const board = useQueueBoard(filters);
  const stats = useQueueStats(filters.departmentId);

  const callNext = useCallNext();
  const callTicket = useTicketAction("call");
  const recallTicket = useTicketAction("recall");
  const startTicket = useTicketAction("start");
  const completeTicket = useTicketAction("complete");
  const noShowTicket = useTicketAction("no-show");
  const cancelTicket = useTicketAction("cancel");
  const priorityTicket = useTicketAction("priority");
  const transferTicket = useTransferTicket();

  const errorMessage = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 409) return t("illegalMove");
      if (error instanceof ApiError && error.status === 403) return t("notAllowed");
      if (isServerUnavailable(error)) return t("serverUnavailable");
      return t("actionFailed");
    },
    [t],
  );

  // Live updates: apply the delta to every cached board, and speak the call.
  const onStreamTicket = useCallback(
    (event: QueueStreamEvent) => {
      queryClient.setQueriesData<QueueBoardData>({ queryKey: ["queue", "board"] }, (current) =>
        reduceBoard(current, event),
      );
      if (event.speech) {
        setSpeech(event.speech);
        setSpeechTicketId(event.ticket?.id);
      }
    },
    [queryClient],
  );

  // A dropped stream reconnects and the hello forces a fresh snapshot, so the
  // wall can never be left showing a call that already finished.
  const onSnapshot = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["queue", "board"] });
  }, [queryClient]);

  useQueueStream({ onTicket: onStreamTicket, onSnapshot });

  const perform = (
    mutation: TicketMutation,
    ticket: QueueTicket,
    body?: Record<string, unknown>,
  ) => {
    setPendingTicketId(ticket.id);
    mutation.mutate(
      { ticketId: ticket.id, body },
      {
        onSuccess: () => toast.success(t("actionDone")),
        onError: (error) => toast.error(errorMessage(error)),
        onSettled: () => setPendingTicketId(null),
      },
    );
  };

  const handleAction = (action: QueueAction, ticket: QueueTicket) => {
    if (action === "transfer") {
      setTransferFrom(ticket);
      setTransferTarget("");
      return;
    }
    if (action === "priority") {
      perform(priorityTicket, ticket, {
        priority: ticket.priority + 1,
        triage_category: ticket.triage_category ?? undefined,
      });
      return;
    }
    const byAction: Record<string, TicketMutation> = {
      call: callTicket,
      recall: recallTicket,
      start: startTicket,
      complete: completeTicket,
      "no-show": noShowTicket,
      cancel: cancelTicket,
    };
    const mutation = byAction[action];
    if (mutation) perform(mutation, ticket);
  };

  const handleCallNext = () => {
    callNext.mutate(
      {
        department_id: filters.departmentId,
        service_point_id: filters.servicePointId,
        announce: true,
      },
      {
        onSuccess: (ticket) =>
          toast.success(t("calledNext", { number: ticket.ticket_number })),
        onError: (error) => {
          if (error instanceof ApiError && error.status === 404) {
            toast.info(t("nobodyWaiting"));
            return;
          }
          toast.error(errorMessage(error));
        },
      },
    );
  };

  const confirmTransfer = () => {
    if (!transferFrom || !transferTarget) return;
    setPendingTicketId(transferFrom.id);
    transferTicket.mutate(
      { ticketId: transferFrom.id, department_id: transferTarget },
      {
        onSuccess: (created) => {
          toast.success(t("transferredTo", { number: created.ticket_number }));
          setTransferFrom(null);
        },
        onError: (error) => toast.error(errorMessage(error)),
        onSettled: () => setPendingTicketId(null),
      },
    );
  };

  const data = board.data;
  const counters = stats.data;

  return (
    <div className="space-y-6 p-4 lg:p-6">
      <PageHeader
        icon={ListOrdered}
        title={t("title")}
        subtitle={t("subtitle")}
        badge={data?.total}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <AudioAnnouncer speech={speech} ticketId={speechTicketId} />
            <button
              type="button"
              onClick={handleCallNext}
              disabled={callNext.isPending}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <Megaphone className="h-4 w-4" />
              {callNext.isPending ? t("callingNext") : t("callNext")}
            </button>
          </div>
        }
      />

      {counters && (
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          {[
            { label: t("statWaiting"), value: counters.waiting },
            { label: t("statCalled"), value: counters.called },
            { label: t("statInService"), value: counters.in_service },
            { label: t("statCompleted"), value: counters.completed_today },
            { label: t("statNoShow"), value: counters.no_show_today },
          ].map((counter) => (
            <div
              key={counter.label}
              className="rounded-xl border border-border bg-card p-3 shadow-sm"
            >
              <dt className="text-xs font-medium text-muted-foreground">{counter.label}</dt>
              <dd className="mt-1 text-2xl font-bold text-foreground">{counter.value}</dd>
            </div>
          ))}
        </dl>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
          {t("filterDepartment")}
          <select
            value={departmentId}
            onChange={(event) => setDepartmentId(event.target.value)}
            className="min-w-44 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="">{t("allDepartments")}</option>
            {(departments.data ?? []).map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
          {t("filterRoom")}
          <select
            value={servicePointId}
            onChange={(event) => setServicePointId(event.target.value)}
            className="min-w-44 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="">{t("allRooms")}</option>
            {(servicePoints.data ?? []).map((point) => (
              <option key={point.id} value={point.id}>
                {point.display_label ?? point.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex items-center gap-2 pb-2 text-xs font-medium text-muted-foreground">
          <input
            type="checkbox"
            checked={includeCompleted}
            onChange={(event) => setIncludeCompleted(event.target.checked)}
            className="h-4 w-4 rounded border-border"
          />
          {t("showFinished")}
        </label>
      </div>

      {transferFrom && (
        <div className="flex flex-wrap items-end gap-3 rounded-xl border border-primary/30 bg-primary/5 p-4">
          <p className="text-sm font-medium text-foreground">
            {t("transferPrompt", { number: transferFrom.ticket_number })}
          </p>
          <select
            value={transferTarget}
            onChange={(event) => setTransferTarget(event.target.value)}
            className="min-w-44 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="">{t("chooseDepartment")}</option>
            {(departments.data ?? []).map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={confirmTransfer}
            disabled={!transferTarget || transferTicket.isPending}
            className="rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-60"
          >
            {t("transfer")}
          </button>
          <button
            type="button"
            onClick={() => setTransferFrom(null)}
            className="rounded-lg border border-border bg-background px-3 py-2 text-sm font-medium text-foreground"
          >
            {t("cancelAction")}
          </button>
        </div>
      )}

      {board.isLoading && !data ? (
        <PageSkeleton />
      ) : data ? (
        <QueueBoard
          board={data}
          onAction={handleAction}
          pendingTicketId={pendingTicketId}
        />
      ) : (
        <EmptyState
          icon={ListOrdered}
          title={t("unavailableTitle")}
          description={t("serverUnavailable")}
        />
      )}
    </div>
  );
}
