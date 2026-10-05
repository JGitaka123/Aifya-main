"use client";

import { useEffect, useRef } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { API_BASE_URL, apiClient } from "@/lib/api-client";
import { useOfflineQuery } from "@/hooks/useOfflineQuery";

/**
 * Queue and patient calling.
 *
 * The database is the source of truth: every mutation here invalidates the
 * queue queries and lets the server say what is true. The SSE stream is only a
 * nudge - the board refetches on every reconnect so a dropped connection can
 * never leave a stale name on a wall.
 */

/** Every state a ticket can be in. Mirrors app/services/queue/state_machine.py. */
export type QueueTicketStatus =
  | "WAITING"
  | "CALLED"
  | "IN_SERVICE"
  | "COMPLETED"
  | "NO_SHOW"
  | "CANCELLED"
  | "TRANSFERRED";

/** Statuses that still belong on the live board. */
export const ACTIVE_STATUSES: readonly QueueTicketStatus[] = [
  "WAITING",
  "CALLED",
  "IN_SERVICE",
];

/** One ticket, as the staff board sees it. */
export interface QueueTicket {
  id: string;
  facility_id: string;
  patient_id: string;
  encounter_id: string | null;
  department_id: string | null;
  service_point_id: string | null;
  ticket_number: string;
  issued_on: string | null;
  status: QueueTicketStatus;
  priority: number;
  triage_category: string | null;
  issued_at: string;
  called_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  called_by: string | null;
  recall_count: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
  patient_name: string | null;
  patient_mrn: string | null;
  department_name: string | null;
  service_point_label: string | null;
  waiting_position: number | null;
  waiting_minutes: number | null;
}

/** The live board payload from GET /queue. */
export interface QueueBoard {
  items: QueueTicket[];
  total: number;
  waiting: number;
  called: number;
  in_service: number;
}

/** A room or counter patients can be called into. */
export interface QueueServicePoint {
  id: string;
  facility_id: string;
  department_id: string | null;
  name: string;
  kind: string;
  display_label: string | null;
  is_active: boolean;
  created_at: string;
}

/** Operational counters for the dashboard header. */
export interface QueueStats {
  waiting: number;
  called: number;
  in_service: number;
  completed_today: number;
  no_show_today: number;
  average_wait_minutes: number | null;
  longest_wait_minutes: number | null;
  by_department: unknown[];
}

/** What the speaker should say for one call. */
export interface QueueSpeech {
  text: string;
  normalised: string;
  language: string;
  recalled: boolean;
}

/** A server-sent event on the staff stream. */
export interface QueueStreamEvent {
  type: string;
  action?: string;
  ticket?: QueueTicket;
  speech?: QueueSpeech | null;
  occurred_at?: string;
  server_time?: string;
  facility_id?: string;
}

/** One line on the public wall: a number and where to go, nothing else. */
export interface PublicQueueRow {
  ticket_number: string;
  service_point_label: string | null;
}

/** The public wall payload from GET /queue/public/board. */
export interface PublicQueueBoard {
  items: PublicQueueRow[];
  total: number;
  waiting: number;
  called: number;
  in_service: number;
}

/** A server-sent event on the public stream. */
export interface PublicQueueStreamEvent {
  type: string;
  action?: string;
  ticket?: PublicQueueRow;
  speech?: QueueSpeech | null;
  occurred_at?: string;
}

/** Board filters shared by the board and stats queries. */
export interface QueueFilters {
  departmentId?: string;
  servicePointId?: string;
  includeCompleted?: boolean;
}

function boardParams(filters: QueueFilters): Record<string, string> {
  const params: Record<string, string> = {};
  if (filters.departmentId) params.department_id = filters.departmentId;
  if (filters.servicePointId) params.service_point_id = filters.servicePointId;
  if (filters.includeCompleted) params.include_completed = "true";
  return params;
}

/** Sort a board the way the server does: priority, then arrival. */
export function compareTickets(a: QueueTicket, b: QueueTicket): number {
  if (b.priority !== a.priority) return b.priority - a.priority;
  return a.issued_at.localeCompare(b.issued_at);
}

function countStatus(items: QueueTicket[], status: QueueTicketStatus): number {
  return items.filter((item) => item.status === status).length;
}

/** The live waiting list for this facility. */
export function useQueueBoard(filters: QueueFilters = {}) {
  return useOfflineQuery<QueueBoard>({
    queryKey: [
      "queue",
      "board",
      filters.departmentId ?? "",
      filters.servicePointId ?? "",
      filters.includeCompleted ? "all" : "live",
    ],
    queryFn: () => apiClient.get<QueueBoard>("/queue", boardParams(filters)),
    refetchInterval: 20_000,
  });
}

/** The facility's rooms and counters. */
export function useQueueServicePoints() {
  return useOfflineQuery<QueueServicePoint[]>({
    queryKey: ["queue", "service-points"],
    queryFn: () => apiClient.get<QueueServicePoint[]>("/queue/service-points"),
    refetchInterval: 300_000,
  });
}

/** Today's counters for the dashboard header. */
export function useQueueStats(departmentId?: string) {
  const params: Record<string, string> = {};
  if (departmentId) params.department_id = departmentId;
  return useOfflineQuery<QueueStats>({
    queryKey: ["queue", "stats", departmentId ?? ""],
    queryFn: () => apiClient.get<QueueStats>("/queue/stats", params),
    refetchInterval: 30_000,
  });
}

/** Register a room or counter. Administrators only, per the API. */
export function useCreateServicePoint() {
  const queryClient = useQueryClient();
  return useMutation<
    QueueServicePoint,
    Error,
    { name: string; department_id?: string; kind?: string; display_label?: string }
  >({
    mutationFn: (body) => apiClient.post<QueueServicePoint>("/queue/service-points", body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["queue", "service-points"] });
    },
  });
}

/** Put a patient who is already registered into the waiting list. */
export function useIssueTicket() {
  const queryClient = useQueryClient();
  return useMutation<
    QueueTicket,
    Error,
    {
      patient_id: string;
      encounter_id?: string;
      department_id?: string;
      service_point_id?: string;
      triage_category: string;
      priority?: number;
      notes?: string;
      idempotency_key?: string;
    }
  >({
    mutationFn: (body) => apiClient.post<QueueTicket>("/queue/tickets", body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
  });
}

/** Claim the next waiting patient. The server locks the row, so two callers
 * pressing at the same moment always receive different patients. */
export function useCallNext() {
  const queryClient = useQueryClient();
  return useMutation<
    QueueTicket,
    Error,
    { department_id?: string; service_point_id?: string; triage_category?: string; announce?: boolean }
  >({
    mutationFn: (body) => apiClient.post<QueueTicket>("/queue/call-next", body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
  });
}

/** The one transition a ticket can make from the board. */
export type QueueAction =
  | "call"
  | "recall"
  | "start"
  | "complete"
  | "no-show"
  | "cancel"
  | "priority"
  | "transfer";

/** Run one transition on one ticket. */
export function useTicketAction(action: QueueAction) {
  const queryClient = useQueryClient();
  return useMutation<
    QueueTicket,
    Error,
    { ticketId: string; body?: Record<string, unknown> }
  >({
    mutationFn: ({ ticketId, body }) =>
      apiClient.post<QueueTicket>("/queue/tickets/" + ticketId + "/" + action, body ?? {}),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
  });
}

/** Send a patient to another department. The server issues the new ticket. */
export function useTransferTicket() {
  const queryClient = useQueryClient();
  return useMutation<
    QueueTicket,
    Error,
    { ticketId: string; department_id: string; service_point_id?: string; reason?: string }
  >({
    mutationFn: ({ ticketId, ...body }) =>
      apiClient.post<QueueTicket>("/queue/tickets/" + ticketId + "/transfer", body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
  });
}

/** The immutable history of one ticket. */
export function useTicketEvents(ticketId: string | null) {
  return useOfflineQuery<unknown[]>({
    queryKey: ["queue", "events", ticketId ?? ""],
    queryFn: () => apiClient.get<unknown[]>("/queue/tickets/" + ticketId + "/events"),
    enabled: Boolean(ticketId),
  });
}

/**
 * Subscribe to the live queue stream.
 *
 * On every (re)connect the server sends a hello, and the caller takes a fresh
 * snapshot - that is what makes a reconnect safe. Ticket events are applied
 * afterwards as deltas through onTicket.
 *
 * @param options.enabled - Subscribe at all
 * @param options.publicToken - Display token; switches to the anonymised stream
 * @param options.onTicket - Called for each ticket event
 * @param options.onSnapshot - Called when a fresh snapshot is due
 */
export function useQueueStream<TicketEvent = QueueStreamEvent>(options: {
  enabled?: boolean;
  publicToken?: string;
  onTicket?: (event: TicketEvent) => void;
  onSnapshot?: () => void;
}): void {
  const { enabled = true, publicToken, onTicket, onSnapshot } = options;
  const queryClient = useQueryClient();
  const ticketRef = useRef(onTicket);
  const snapshotRef = useRef(onSnapshot);
  ticketRef.current = onTicket;
  snapshotRef.current = onSnapshot;

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;
    const url = publicToken
      ? API_BASE_URL + "/queue/public/stream?token=" + encodeURIComponent(publicToken)
      : API_BASE_URL + "/queue/stream";
    const source = new EventSource(url, { withCredentials: true });
    source.onmessage = (message: MessageEvent<string>) => {
      let event: QueueStreamEvent;
      try {
        event = JSON.parse(message.data) as QueueStreamEvent;
      } catch {
        return;
      }
      if (event.type === "hello") {
        void queryClient.invalidateQueries({ queryKey: ["queue"] });
        snapshotRef.current?.();
        return;
      }
      if (event.type === "ticket") ticketRef.current?.(event as unknown as TicketEvent);
    };
    return () => source.close();
  }, [enabled, publicToken, queryClient]);
}

/**
 * Fold a ticket event into the cached board without a round trip.
 *
 * A finished ticket leaves the board, a live one is inserted in order. The
 * next refetch still wins, so a missed event costs nothing.
 *
 * @param board - The cached board, if there is one
 * @param event - The event from the stream
 * @returns The updated board, or the original when nothing can be applied
 */
export function reduceBoard(
  board: QueueBoard | undefined,
  event: QueueStreamEvent,
): QueueBoard | undefined {
  const ticket = event.ticket;
  if (!board || !ticket) return board;
  const others = board.items.filter((item) => item.id !== ticket.id);
  const items = (ACTIVE_STATUSES.includes(ticket.status)
    ? [...others, ticket]
    : others
  ).sort(compareTickets);
  return {
    ...board,
    items,
    total: items.length,
    waiting: countStatus(items, "WAITING"),
    called: countStatus(items, "CALLED"),
    in_service: countStatus(items, "IN_SERVICE"),
  };
}

/** Events that take a ticket off the public wall. */
const PUBLIC_TERMINAL_ACTIONS: readonly string[] = [
  "SERVICE_COMPLETED",
  "NO_SHOW",
  "CANCELLED",
  "TRANSFERRED",
];

/**
 * Fold a public event into the cached wall.
 *
 * @param board - The cached wall, if there is one
 * @param event - The event from the public stream
 * @returns The updated wall, or the original when nothing can be applied
 */
export function reducePublicBoard(
  board: PublicQueueBoard | undefined,
  event: PublicQueueStreamEvent,
): PublicQueueBoard | undefined {
  const row = event.ticket;
  if (!board || !row || typeof row.ticket_number !== "string") return board;
  const others = board.items.filter((item) => item.ticket_number !== row.ticket_number);
  const items = PUBLIC_TERMINAL_ACTIONS.includes(event.action ?? "")
    ? others
    : [...others, { ticket_number: row.ticket_number, service_point_label: row.service_point_label ?? null }];
  return { ...board, items, total: items.length };
}

/**
 * The server-proxied audio for one announcement.
 *
 * The browser never holds a TTS key: it asks the API for the bytes, and falls
 * back to the local voice only when the API cannot render them.
 *
 * @param options.ticketId - Staff call: the ticket id is known
 * @param options.ticketNumber - Public wall: only the printed number is known
 * @param options.publicToken - Display token for the public routes
 * @param options.recalled - True for a repeat call
 * @returns An absolute-path URL, or null when neither id nor number is known
 */
export function announcementAudioUrl(options: {
  ticketId?: string;
  ticketNumber?: string;
  publicToken?: string;
  recalled?: boolean;
}): string | null {
  const { ticketId, ticketNumber, publicToken, recalled } = options;
  const suffix = recalled ? "?recalled=true" : "";
  if (publicToken && ticketNumber) {
    const token = "?token=" + encodeURIComponent(publicToken);
    return (
      API_BASE_URL +
      "/voice/public/announcements/by-number/" +
      encodeURIComponent(ticketNumber) +
      "/audio" +
      token +
      (recalled ? "&recalled=true" : "")
    );
  }
  if (publicToken && ticketId) {
    return (
      API_BASE_URL +
      "/voice/public/announcements/" +
      ticketId +
      "/audio?token=" +
      encodeURIComponent(publicToken) +
      (recalled ? "&recalled=true" : "")
    );
  }
  if (ticketId) {
    return API_BASE_URL + "/voice/announcements/" + ticketId + "/audio" + suffix;
  }
  return null;
}

/** The anonymised wall board: ticket numbers and rooms, nothing else. */
export function usePublicQueueBoard(token: string | null) {
  return useOfflineQuery<PublicQueueBoard>({
    queryKey: ["queue", "public-board", token ?? ""],
    queryFn: () =>
      apiClient.get<PublicQueueBoard>(
        "/queue/public/board",
        { token: token ?? "" },
        { skipAuthRedirect: true },
      ),
    enabled: Boolean(token),
    refetchInterval: 20_000,
  });
}
