"use client";

import { useCallback, useState } from "react";

import { AudioAnnouncer } from "@/components/queue/AudioAnnouncer";
import {
  useQueueStream,
  type QueueSpeech,
  type QueueStreamEvent,
} from "@/hooks/useQueue";

/**
 * Speak every call made anywhere in the facility.
 *
 * The waiting board owns the stream logic; a room that only needs the
 * audio mounts this instead, so a button pressed in OPD or in the
 * consultation room announces through the same speaker.
 *
 * @returns The speaker toggle and its blocked hint
 */
export function QueueAnnouncer() {
  const [speech, setSpeech] = useState<QueueSpeech | null>(null);
  const [ticketId, setTicketId] = useState<string | undefined>(undefined);

  const onTicket = useCallback((event: QueueStreamEvent) => {
    if (!event.speech) return;
    setSpeech(event.speech);
    setTicketId(event.ticket?.id);
  }, []);

  useQueueStream({ onTicket });

  return <AudioAnnouncer speech={speech} ticketId={ticketId} />;
}
