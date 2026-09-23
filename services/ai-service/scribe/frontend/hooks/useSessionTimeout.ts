"use client";

import { useState, useEffect, useCallback, useRef } from "react";

interface SessionTimeoutConfig {
  /** Token expiry time in minutes */
  tokenExpiryMinutes: number;
  /** Show warning this many minutes before expiry */
  warningMinutesBefore: number;
  /** Callback when session expires */
  onExpired: () => void;
  /** Callback to refresh the token */
  onRefresh?: () => Promise<void>;
  /** Whether the user is authenticated */
  isAuthenticated: boolean;
}

export function useSessionTimeout({
  tokenExpiryMinutes,
  warningMinutesBefore,
  onExpired,
  onRefresh,
  isAuthenticated,
}: SessionTimeoutConfig) {
  const [showWarning, setShowWarning] = useState(false);
  const [remainingSeconds, setRemainingSeconds] = useState(0);
  const loginTimeRef = useRef<number>(Date.now());
  const warningTimerRef = useRef<NodeJS.Timeout | null>(null);
  const expiryTimerRef = useRef<NodeJS.Timeout | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  const clearAllTimers = useCallback(() => {
    if (warningTimerRef.current) clearTimeout(warningTimerRef.current);
    if (expiryTimerRef.current) clearTimeout(expiryTimerRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);
  }, []);

  const startTimers = useCallback(() => {
    clearAllTimers();
    loginTimeRef.current = Date.now();

    const warningMs = (tokenExpiryMinutes - warningMinutesBefore) * 60 * 1000;
    const expiryMs = tokenExpiryMinutes * 60 * 1000;

    // Show warning before expiry
    warningTimerRef.current = setTimeout(() => {
      setShowWarning(true);
      setRemainingSeconds(warningMinutesBefore * 60);

      // Start countdown
      countdownRef.current = setInterval(() => {
        setRemainingSeconds((prev) => {
          if (prev <= 1) {
            clearAllTimers();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }, warningMs);

    // Auto-expire
    expiryTimerRef.current = setTimeout(() => {
      clearAllTimers();
      setShowWarning(false);
      onExpired();
    }, expiryMs);
  }, [tokenExpiryMinutes, warningMinutesBefore, onExpired, clearAllTimers]);

  const extendSession = useCallback(async () => {
    setShowWarning(false);
    clearAllTimers();
    if (onRefresh) {
      try {
        await onRefresh();
      } catch {
        onExpired();
        return;
      }
    }
    startTimers();
  }, [onRefresh, onExpired, clearAllTimers, startTimers]);

  const dismissWarning = useCallback(() => {
    setShowWarning(false);
  }, []);

  useEffect(() => {
    if (isAuthenticated) {
      startTimers();
    } else {
      clearAllTimers();
      setShowWarning(false);
    }
    return clearAllTimers;
  }, [isAuthenticated, startTimers, clearAllTimers]);

  return {
    showWarning,
    remainingSeconds,
    extendSession,
    dismissWarning,
  };
}
