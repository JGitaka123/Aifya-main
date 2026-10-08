"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { Volume2, VolumeX } from "lucide-react";

import { announcementAudioUrl, type QueueSpeech } from "@/hooks/useQueue";

/** A kiosk should not need a click every morning, so the choice is remembered. */
const UNLOCK_KEY = "aifya.queue.audio-unlocked";

export interface AudioAnnouncerProps {
  /** The announcement to speak, or null when nothing new has been called. */
  speech: QueueSpeech | null;
  /** Staff calls know the ticket id. */
  ticketId?: string;
  /** The public wall only ever knows the printed number. */
  ticketNumber?: string;
  /** Display token, for the public audio route. */
  publicToken?: string;
  /** Notified when the speaker is switched on or off. */
  onEnabledChange?: (enabled: boolean) => void;
}

/**
 * Speak queue announcements.
 *
 * The audio comes from the API, so the TTS key stays on the server. When the
 * API is switched off, slow, or the browser refuses to start audio before a
 * click, the line falls back to the local voice - or to silence. The queue
 * itself never waits for any of this.
 *
 * @param props - See AudioAnnouncerProps
 * @returns The speaker toggle and its blocked hint
 */
export function AudioAnnouncer({
  speech,
  ticketId,
  ticketNumber,
  publicToken,
  onEnabledChange,
}: AudioAnnouncerProps) {
  const t = useTranslations("queue");
  const [enabled, setEnabled] = useState(false);
  const [blocked, setBlocked] = useState(false);
  const spoken = useRef<QueueSpeech | null>(null);

useEffect(() => {
  let stored: string | null = null;
  try {
    stored = window.localStorage.getItem(UNLOCK_KEY);
  } catch {
    // Private mode: the speaker simply starts off.
    return;
  }
  if (stored === "1") {
    setEnabled(true);
    return;
  }
  if (stored === "0") {
    // The desk switched the speaker off on purpose; leave it off.
    return;
  }
  // A fresh browser will not start audio before a gesture, so arm a
  // one-time unlock. The first click - usually "Call next patient" -
  // switches the speaker on in time for the announcement it triggers.
  const unlock = () => {
    setEnabled(true);
    setBlocked(false);
    try {
      window.localStorage.setItem(UNLOCK_KEY, "1");
    } catch {
      // Ignore: the speaker stays on for this session.
    }
    if (typeof window.speechSynthesis !== "undefined") {
      try {
        window.speechSynthesis.resume();
      } catch {
        // Ignore.
      }
    }
  };
  window.addEventListener("pointerdown", unlock, { once: true });
  window.addEventListener("keydown", unlock, { once: true });
  return () => {
    window.removeEventListener("pointerdown", unlock);
    window.removeEventListener("keydown", unlock);
  };
}, []);

  const speakLocally = useCallback((line: QueueSpeech) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    try {
      const utterance = new SpeechSynthesisUtterance(line.normalised || line.text);
      utterance.lang = line.language || "en";
      window.speechSynthesis.speak(utterance);
    } catch {
      // A voice is a courtesy; the ticket is already called in the database.
    }
  }, []);

  useEffect(() => {
    if (!speech || speech === spoken.current) return;
    // Remember it either way, so switching the speaker on does not replay an
    // announcement the room already heard.
    spoken.current = speech;
    if (!enabled) {
      // A call arrived while the speaker is off: prompt the desk to switch it on.
      setBlocked(true);
      return;
    }

    const url = announcementAudioUrl({
      ticketId,
      ticketNumber,
      publicToken,
      recalled: speech.recalled,
    });
    if (!url) {
      speakLocally(speech);
      return;
    }

    let cancelled = false;
    const audio = new Audio(url);
    audio.onerror = () => {
      if (!cancelled) speakLocally(speech);
    };
    audio.play().catch((error: unknown) => {
      if (cancelled) return;
      if (error instanceof DOMException && error.name === "NotAllowedError") {
        setBlocked(true);
        return;
      }
      speakLocally(speech);
    });
    return () => {
      cancelled = true;
      audio.pause();
    };
  }, [enabled, speech, ticketId, ticketNumber, publicToken, speakLocally]);

  const toggle = () => {
    const next = !enabled;
    setEnabled(next);
    setBlocked(false);
    try {
      window.localStorage.setItem(UNLOCK_KEY, next ? "1" : "0");
    } catch {
      // Ignore: the toggle still works for this visit.
    }
    onEnabledChange?.(next);
    if (next && typeof window !== "undefined" && "speechSynthesis" in window) {
      // Unlock inside the click that asked for sound.
      try {
        window.speechSynthesis.resume();
      } catch {
        // Ignore.
      }
    }
  };

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={toggle}
        aria-pressed={enabled}
        title={t("audioHelp")}
        className={
          "inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition-colors " +
          (enabled
            ? "border-primary/40 bg-primary/10 text-primary"
            : "border-border bg-card text-muted-foreground hover:text-foreground")
        }
      >
        {enabled ? <Volume2 className="h-4 w-4" /> : <VolumeX className="h-4 w-4" />}
        <span>{enabled ? t("audioOn") : t("audioOff")}</span>
      </button>
      {blocked && enabled && (
        <span className="text-xs font-medium text-amber-600 dark:text-amber-400">
          {t("audioBlocked")}
        </span>
      )}
    </div>
  );
}
