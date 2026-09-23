"use client";

import { useEffect, useRef } from "react";
import { apiFetch } from "@/lib/api";
import type { TelemetryPayload } from "@aifya/shared";

const TELEMETRY_INTERVAL_MS = 24 * 60 * 60 * 1000; // 24 hours
const TELEMETRY_STORAGE_KEY = "aifya_last_telemetry";

/**
 * Hook that sends daily usage telemetry to Aifya HQ.
 * Runs once per day per browser session. No PII collected.
 * Silently fails — telemetry is best-effort.
 *
 * @param enabled - Whether telemetry collection is enabled
 */
export function useTelemetry(enabled: boolean = true) {
  const sentRef = useRef(false);

  useEffect(() => {
    if (!enabled || sentRef.current) return;

    const lastSent = localStorage.getItem(TELEMETRY_STORAGE_KEY);
    const now = Date.now();

    if (lastSent && now - parseInt(lastSent, 10) < TELEMETRY_INTERVAL_MS) {
      return; // Already sent within 24h
    }

    const sendTelemetry = async () => {
      try {
        const payload: TelemetryPayload = {
          active_users: 1, // This session counts as 1
          total_patients: 0, // Server will fill from DB
          encounters_today: 0,
          prescriptions_today: 0,
          lab_orders_today: 0,
          admissions_today: 0,
          billing_total_cents: 0,
          ai_requests_today: 0,
          modules_used: collectModulesUsed(),
          app_version: process.env.NEXT_PUBLIC_APP_VERSION ?? "0.1.0",
        };

        await apiFetch("/api/v1/licensing/telemetry", {
          method: "POST",
          body: JSON.stringify(payload),
        });

        localStorage.setItem(TELEMETRY_STORAGE_KEY, String(now));
        sentRef.current = true;
      } catch {
        // Silently fail
      }
    };

    // Delay 30s to not impact page load
    const timer = setTimeout(sendTelemetry, 30_000);
    return () => clearTimeout(timer);
  }, [enabled]);
}

/**
 * Collect which modules the user has visited in this session.
 * Reads from sessionStorage breadcrumbs.
 */
function collectModulesUsed(): string[] {
  try {
    const visited = sessionStorage.getItem("aifya_modules_visited");
    return visited ? JSON.parse(visited) : [];
  } catch {
    return [];
  }
}

/**
 * Record that a module was visited (called from navigation).
 *
 * @param module - Module name
 */
export function recordModuleVisit(module: string) {
  try {
    const visited = sessionStorage.getItem("aifya_modules_visited");
    const set = new Set<string>(visited ? JSON.parse(visited) : []);
    set.add(module);
    sessionStorage.setItem("aifya_modules_visited", JSON.stringify([...set]));
  } catch {
    // Silently fail
  }
}
