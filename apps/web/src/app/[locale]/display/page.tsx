"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useQueryClient } from "@tanstack/react-query";
import { MonitorPlay } from "lucide-react";

import { AudioAnnouncer } from "@/components/queue/AudioAnnouncer";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  reducePublicBoard,
  usePublicQueueBoard,
  useQueueStream,
  type PublicQueueBoard as PublicBoardData,
  type PublicQueueStreamEvent,
  type QueueSpeech,
} from "@/hooks/useQueue";

/**
 * The corridor wall.
 *
 * It shows a ticket number and a room, never a name, and it never asks for a
 * staff login: the display token in the URL is the whole credential. Voice
 * comes from the API, so the TTS key stays on the server.
 *
 * @returns The public display board
 */
export default function DisplayPage() {
  const t = useTranslations("display");
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [speech, setSpeech] = useState<QueueSpeech | null>(null);
  const [speechNumber, setSpeechNumber] = useState<string | undefined>(undefined);

  useEffect(() => {
    const fromQuery = new URLSearchParams(window.location.search).get("token");
    setToken(fromQuery ?? process.env.NEXT_PUBLIC_QUEUE_DISPLAY_TOKEN ?? null);
    setReady(true);
  }, []);

  const board = usePublicQueueBoard(token);

  const onTicket = useCallback(
    (event: PublicQueueStreamEvent) => {
      queryClient.setQueriesData<PublicBoardData>(
        { queryKey: ["queue", "public-board"] },
        (current) => reducePublicBoard(current, event),
      );
      if (event.speech && event.ticket) {
        setSpeech(event.speech);
        setSpeechNumber(event.ticket.ticket_number);
      }
    },
    [queryClient],
  );

  useQueueStream<PublicQueueStreamEvent>({
    enabled: Boolean(token),
    publicToken: token ?? undefined,
    onTicket,
    onSnapshot: () => {
      void queryClient.invalidateQueries({ queryKey: ["queue", "public-board"] });
    },
  });

  const rows = board.data?.items ?? [];

  if (!ready) {
    return <div className="min-h-screen bg-background" />;
  }

  if (!token) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <EmptyState
          icon={MonitorPlay}
          title={t("notConfiguredTitle")}
          description={t("notConfiguredDescription")}
        />
      </div>
    );
  }

  if (board.isError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-6">
        <EmptyState
          icon={MonitorPlay}
          title={t("unauthorisedTitle")}
          description={t("unauthorisedDescription")}
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background p-6 lg:p-10">
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground lg:text-4xl">
            {t("title")}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">{t("subtitle")}</p>
        </div>
        <AudioAnnouncer
          speech={speech}
          ticketNumber={speechNumber}
          publicToken={token}
        />
      </header>

      {rows.length === 0 ? (
        <div className="flex min-h-[50vh] items-center justify-center">
          <EmptyState icon={MonitorPlay} title={t("emptyTitle")} description={t("emptyDescription")} />
        </div>
      ) : (
        <ul
          aria-live="polite"
          aria-relevant="additions text"
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
        >
          {/* A newly called number is read out to screen-reader users. */}
          {rows.map((row) => (
            <li
              key={row.ticket_number}
              className="rounded-2xl border border-border bg-card p-6 text-center shadow-sm"
            >
              <p className="font-mono text-5xl font-bold tracking-tight text-primary lg:text-6xl">
                {row.ticket_number}
              </p>
              <p className="mt-3 text-lg font-semibold text-foreground">
                {row.service_point_label ?? t("unassignedRoom")}
              </p>
            </li>
          ))}
        </ul>
      )}

      {board.data && (
        <footer className="mt-8 flex flex-wrap gap-6 text-sm text-muted-foreground">
          <span>{t("countWaiting", { count: board.data.waiting })}</span>
          <span>{t("countCalled", { count: board.data.called })}</span>
          <span>{t("countInService", { count: board.data.in_service })}</span>
        </footer>
      )}
    </div>
  );
}
