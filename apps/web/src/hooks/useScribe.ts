"use client";

import { useState, useRef, useCallback } from "react";
import type {
  ClinicalExtraction,
  ScribeProcessResponse,
} from "@aifya/shared";

/** State machine states for the ScribeAI recording pipeline. */
export type ScribeState =
  | "idle"
  | "recording"
  | "uploading"
  | "extracting"
  | "review"
  | "signed_off";

/** Return type of the useScribe hook. */
export interface UseScribeReturn {
  /** Current state machine state. */
  state: ScribeState;
  /** Whether the microphone is actively recording. */
  isRecording: boolean;
  /** Whether audio is being uploaded or clinical data extracted. */
  isProcessing: boolean;
  /** Raw transcript text from the AI service. */
  transcript: string | null;
  /** Structured clinical extraction for clinician review. */
  extraction: ClinicalExtraction | null;
  /** Error message if any step failed. */
  error: string | null;
  /** Elapsed recording time in seconds. */
  elapsedSeconds: number;
  /** Start recording audio from the microphone. */
  startRecording: () => Promise<void>;
  /** Stop recording and submit audio for processing. */
  stopRecording: () => void;
  /** Clear all results and reset to idle state. */
  clearResults: () => void;
}

// Same-origin proxy that swaps the httpOnly session cookie for the
// Bearer header the scribe service expects (see app/api/scribe).
const SCRIBE_API_URL = "/api/scribe";

/**
 * Custom hook that manages the full ScribeAI ambient recording pipeline.
 * Records consultation audio via MediaRecorder, sends to AI service for
 * transcription and clinical extraction, then holds results for clinician review.
 *
 * Per CLAUDE.md: AI NEVER auto-commits to patient records. Always clinician sign-off.
 *
 * @param encounterId - The encounter ID to associate with the recording
 * @returns ScribeAI state, controls, and extracted data
 */
export function useScribe(encounterId: string): UseScribeReturn {
  const [state, setState] = useState<ScribeState>("idle");
  const [transcript, setTranscript] = useState<string | null>(null);
  const [extraction, setExtraction] = useState<ClinicalExtraction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  /**
   * Determine the best supported MIME type for audio recording.
   * @returns Supported MIME type string
   */
  const getSupportedMimeType = useCallback((): string => {
    const types = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4",
      "audio/ogg;codecs=opus",
    ];
    for (const type of types) {
      if (MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }
    return "audio/webm";
  }, []);

  /**
   * Start the elapsed time counter.
   */
  const startTimer = useCallback(() => {
    setElapsedSeconds(0);
    timerRef.current = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
  }, []);

  /**
   * Stop the elapsed time counter.
   */
  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  /**
   * Send audio blob to the ScribeAI backend for full pipeline processing.
   * @param audioBlob - Recorded audio data
   */
  const processAudio = useCallback(
    async (audioBlob: Blob): Promise<void> => {
      setState("uploading");
      setError(null);

      try {
        // Step 1: transcribe the audio (backend expects field name "audio").
        const formData = new FormData();
        const extension = audioBlob.type.includes("mp4") ? "mp4" : "webm";
        formData.append("audio", audioBlob, `recording.${extension}`);
        formData.append("encounter_id", encounterId);

        const transcribeResponse = await fetch(
          `${SCRIBE_API_URL}/scribe/transcribe`,
          {
            method: "POST",
            credentials: "include",
            body: formData,
          }
        );

        if (!transcribeResponse.ok) {
          const errorData: { detail?: string } = await transcribeResponse
            .json()
            .catch(() => ({ detail: transcribeResponse.statusText }));
          throw new Error(
            errorData.detail ?? `Server error: ${transcribeResponse.status}`
          );
        }

        const { transcript: transcriptText } =
          (await transcribeResponse.json()) as { transcript: string };
        setTranscript(transcriptText);
        setState("extracting");

        // Step 2: run clinical extraction over the transcript.
        const processResponse = await fetch(
          `${SCRIBE_API_URL}/scribe/process`,
          {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ transcript: transcriptText }),
          }
        );

        if (!processResponse.ok) {
          const errorData: { detail?: string } = await processResponse
            .json()
            .catch(() => ({ detail: processResponse.statusText }));
          throw new Error(
            errorData.detail ?? `Server error: ${processResponse.status}`
          );
        }

        const result = (await processResponse.json()) as ScribeProcessResponse;
        setExtraction(result.extraction);
        setState("review");
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to process audio";
        setError(message);
        setState("idle");
      }
    },
    [encounterId]
  );

  /**
   * Start recording audio from the user's microphone.
   * Requests microphone permission and begins capturing audio data.
   */
  const startRecording = useCallback(async (): Promise<void> => {
    try {
      setError(null);
      setTranscript(null);
      setExtraction(null);

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 16000,
        },
      });

      streamRef.current = stream;
      chunksRef.current = [];

      const mimeType = getSupportedMimeType();
      const mediaRecorder = new MediaRecorder(stream, { mimeType });

      mediaRecorder.ondataavailable = (event: BlobEvent) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(chunksRef.current, { type: mimeType });
        stopTimer();

        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => track.stop());
          streamRef.current = null;
        }

        void processAudio(audioBlob);
      };

      mediaRecorderRef.current = mediaRecorder;
      mediaRecorder.start(1000);
      setState("recording");
      startTimer();
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Failed to access microphone";
      setError(message);
      setState("idle");
    }
  }, [getSupportedMimeType, processAudio, startTimer, stopTimer]);

  /**
   * Stop the current recording and trigger audio processing.
   */
  const stopRecording = useCallback((): void => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      mediaRecorderRef.current.stop();
    }
  }, []);

  /**
   * Clear all results and reset to idle state.
   */
  const clearResults = useCallback((): void => {
    setTranscript(null);
    setExtraction(null);
    setError(null);
    setElapsedSeconds(0);
    setState("idle");
    stopTimer();

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }, [stopTimer]);

  return {
    state,
    isRecording: state === "recording",
    isProcessing: state === "uploading" || state === "extracting",
    transcript,
    extraction,
    error,
    elapsedSeconds,
    startRecording,
    stopRecording,
    clearResults,
  };
}
