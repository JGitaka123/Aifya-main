"use client";

import { useState, useEffect, useCallback } from "react";
import { useTranslations } from "next-intl";
import {
  Mic,
  MicOff,
  Loader2,
  AlertCircle,
  RotateCcw,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useScribe } from "@/hooks/useScribe";
import { ScribeExtractionPanel } from "./ScribeExtractionPanel";
import type { ClinicalExtraction } from "@aifya/shared";

interface ScribeButtonProps {
  /** Encounter ID for linking the recording. */
  encounterId: string;
  /** Callback when clinician signs off on the AI extraction. */
  onSignOff?: (extraction: ClinicalExtraction) => void;
}

/**
 * Format elapsed seconds into MM:SS display string.
 *
 * @param seconds - Total elapsed seconds
 * @returns Formatted time string (e.g., "02:35")
 */
function formatElapsed(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

/**
 * ScribeAI ambient clinical documentation recorder.
 * Records consultation audio, sends to AI service for transcription and
 * clinical extraction, then displays results for clinician review.
 *
 * Per CLAUDE.md: AI NEVER auto-commits to patient records.
 * Clinician must explicitly sign off on extracted data.
 *
 * @param props - encounterId for linking the recording, optional sign-off callback
 * @returns ScribeAI recorder button with extraction panel
 */
export function ScribeButton({ encounterId, onSignOff }: ScribeButtonProps) {
  const t = useTranslations("scribe");
  const [showPanel, setShowPanel] = useState(false);

  const {
    state,
    isRecording,
    isProcessing,
    extraction,
    error,
    elapsedSeconds,
    startRecording,
    stopRecording,
    clearResults,
  } = useScribe(encounterId);

  /** Show extraction panel when review state is reached. */
  useEffect(() => {
    if (state === "review" && extraction) {
      setShowPanel(true);
    }
  }, [state, extraction]);

  /**
   * Handle the main toggle button click.
   */
  const handleToggle = useCallback(async () => {
    if (isRecording) {
      stopRecording();
    } else if (state === "idle") {
      await startRecording();
    }
  }, [isRecording, state, startRecording, stopRecording]);

  /**
   * Handle clinician sign-off on the extraction.
   * @param data - The signed-off clinical extraction
   */
  const handleSignOff = useCallback(
    (data: ClinicalExtraction) => {
      setShowPanel(false);
      onSignOff?.(data);
      clearResults();
    },
    [onSignOff, clearResults]
  );

  /**
   * Handle discard of the extraction.
   */
  const handleDiscard = useCallback(() => {
    setShowPanel(false);
    clearResults();
  }, [clearResults]);

  /**
   * Handle retry after error.
   */
  const handleRetry = useCallback(() => {
    clearResults();
  }, [clearResults]);

  return (
    <div className="rounded-lg border border-border bg-card p-4 dark:bg-card">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isRecording ? (
            <Mic className="h-5 w-5 animate-pulse text-red-500" />
          ) : (
            <Mic className="h-5 w-5 text-primary" />
          )}
          <h3 className="font-semibold text-foreground">{t("title")}</h3>
        </div>

        <div className="flex items-center gap-2">
          {/* Elapsed time counter during recording */}
          {isRecording && (
            <span className="font-mono text-sm text-red-600 dark:text-red-400">
              {formatElapsed(elapsedSeconds)}
            </span>
          )}

          {/* Main toggle button */}
          <button
            onClick={() => void handleToggle()}
            disabled={isProcessing}
            className={cn(
              "flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors",
              isRecording
                ? "bg-red-500 text-white hover:bg-red-600"
                : isProcessing
                  ? "cursor-not-allowed bg-muted text-muted-foreground"
                  : "bg-primary text-primary-foreground hover:bg-primary/90"
            )}
          >
            {isRecording ? (
              <>
                <MicOff className="h-4 w-4" />
                {t("stopRecording")}
              </>
            ) : isProcessing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {state === "uploading"
                  ? t("transcribing")
                  : t("extracting")}
              </>
            ) : (
              <>
                <Mic className="h-4 w-4" />
                {t("startRecording")}
              </>
            )}
          </button>

          {/* Close / clear button when in review */}
          {state === "review" && (
            <button
              onClick={handleDiscard}
              className="rounded-lg p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Recording indicator with waveform animation */}
      {isRecording && (
        <div className="mt-3 flex items-center gap-3">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-red-500" />
          <span className="text-sm text-red-600 dark:text-red-400">
            {t("recording")}
          </span>
          {/* Simple CSS waveform animation */}
          <div className="flex items-center gap-0.5">
            {[...Array(5)].map((_, i) => (
              <span
                key={i}
                className="inline-block w-1 rounded-full bg-red-400 dark:bg-red-500"
                style={{
                  height: `${8 + Math.random() * 12}px`,
                  animation: `scribe-wave 0.6s ease-in-out ${i * 0.1}s infinite alternate`,
                }}
              />
            ))}
          </div>
          <style>{`
            @keyframes scribe-wave {
              0% { transform: scaleY(0.4); }
              100% { transform: scaleY(1); }
            }
          `}</style>
        </div>
      )}

      {/* Processing indicator */}
      {isProcessing && (
        <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {state === "uploading"
            ? t("transcribing")
            : t("extracting")}
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="mt-3 flex items-center justify-between rounded-md border border-red-200 bg-red-50 p-3 dark:border-red-800 dark:bg-red-950/30">
          <div className="flex items-center gap-2 text-sm text-red-700 dark:text-red-400">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            {error}
          </div>
          <button
            onClick={handleRetry}
            className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-red-700 transition-colors hover:bg-red-100 dark:text-red-400 dark:hover:bg-red-900/30"
          >
            <RotateCcw className="h-3 w-3" />
            {t("retry")}
          </button>
        </div>
      )}

      {/* Disclaimer per CLAUDE.md: AI NEVER auto-commits */}
      <div className="mt-3 flex items-start gap-2 text-xs text-muted-foreground">
        <AlertCircle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
        {t("disclaimer")}
      </div>

      {/* Extraction panel for clinician review */}
      {showPanel && extraction && (
        <ScribeExtractionPanel
          extraction={extraction}
          onSignOff={handleSignOff}
          onDiscard={handleDiscard}
        />
      )}
    </div>
  );
}
