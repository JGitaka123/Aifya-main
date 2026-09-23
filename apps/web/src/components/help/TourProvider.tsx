"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useTranslations } from "next-intl";
import { driver, type Driver, type DriveStep } from "driver.js";
import "driver.js/dist/driver.css";
import { useAuth } from "@/components/providers/AuthProvider";
import {
  ALL_TOURS,
  DEFAULT_DRIVER_CONFIG,
  pickTourForRoles,
  type Tour,
  type TourStep,
} from "./tour-steps";

/** localStorage key for completion state per user. */
const STORAGE_PREFIX = "aifya:tour:completed:";

interface TourContextValue {
  /** Start a specific tour by id. */
  startTour: (tourId: string) => void;
  /** Restart the recommended tour for the current user. */
  startRecommended: () => void;
  /** True while a tour is actively running. */
  active: boolean;
  /** All available tours (for menus). */
  available: readonly Tour[];
}

const TourContext = createContext<TourContextValue | null>(null);

/** Hook to access tour controls from any component. */
export function useTour(): TourContextValue {
  const ctx = useContext(TourContext);
  if (!ctx) {
    throw new Error("useTour must be used inside <TourProvider>");
  }
  return ctx;
}

/**
 * Provider that manages the onboarding tour lifecycle.
 *
 * On first login (per user, tracked in localStorage), automatically
 * launches the role-appropriate tour 800ms after mount. Re-running the
 * tour is always available via `useTour().startRecommended()`.
 *
 * Skipping the tour also marks it as completed (so users aren't nagged).
 */
export function TourProvider({ children }: { children: ReactNode }) {
  const t = useTranslations("tour");
  const { user } = useAuth();
  const [active, setActive] = useState(false);
  const driverRef = useRef<Driver | null>(null);

  /**
   * Check localStorage to see if this user has completed/skipped the
   * welcome tour already.
   */
  const hasCompleted = useCallback(
    (tourId: string, userId: string | undefined): boolean => {
      if (typeof window === "undefined" || !userId) return true;
      try {
        return window.localStorage.getItem(`${STORAGE_PREFIX}${userId}:${tourId}`) === "1";
      } catch {
        return true; // localStorage blocked → treat as completed (no nagging)
      }
    },
    [],
  );

  /** Persist completion state. */
  const markCompleted = useCallback(
    (tourId: string, userId: string | undefined): void => {
      if (typeof window === "undefined" || !userId) return;
      try {
        window.localStorage.setItem(`${STORAGE_PREFIX}${userId}:${tourId}`, "1");
      } catch {
        // Silently ignore storage failures
      }
    },
    [],
  );

  /**
   * Resolve a tour step's target into a real DOM selector that exists.
   * Returns null if the element isn't currently in the DOM (skip step).
   */
  const resolveStep = useCallback(
    (step: TourStep): DriveStep | null => {
      if (typeof document === "undefined") return null;
      const el = document.querySelector(step.target);
      if (!el) return null;
      return {
        element: step.target,
        popover: {
          title: t(`steps.${step.key}.title`),
          description: t(`steps.${step.key}.description`),
          side: step.side,
          align: step.align,
        },
      };
    },
    [t],
  );

  /** Start a tour by id. Tear down any existing driver instance first. */
  const startTour = useCallback(
    (tourId: string): void => {
      const tour = ALL_TOURS[tourId];
      if (!tour) {
        console.warn(`Unknown tour: ${tourId}`);
        return;
      }
      // Destroy any prior driver so we can rebuild with fresh config
      if (driverRef.current) {
        driverRef.current.destroy();
        driverRef.current = null;
      }
      const steps = tour.steps
        .map(resolveStep)
        .filter((s): s is DriveStep => s !== null);

      if (steps.length === 0) {
        console.warn(`Tour "${tourId}" has no resolvable steps on this page`);
        return;
      }

      const drv = driver({
        ...DEFAULT_DRIVER_CONFIG,
        steps,
        nextBtnText: t("controls.next"),
        prevBtnText: t("controls.previous"),
        doneBtnText: t("controls.done"),
        progressText: t("controls.progress", {
          current: "{{current}}",
          total: "{{total}}",
        }),
        onDestroyed: () => {
          setActive(false);
          markCompleted(tourId, user?.id);
        },
      });

      driverRef.current = drv;
      setActive(true);
      drv.drive();
    },
    [resolveStep, t, markCompleted, user?.id],
  );

  /** Restart the recommended tour based on current user's roles. */
  const startRecommended = useCallback((): void => {
    const tour = pickTourForRoles(user?.roles ?? []);
    startTour(tour.id);
  }, [startTour, user?.roles]);

  // Auto-launch on first login
  useEffect(() => {
    if (!user?.id) return;
    const tour = pickTourForRoles(user.roles ?? []);
    if (hasCompleted(tour.id, user.id)) return;
    // Wait for the page to mount fully (sidebar etc.)
    const timer = window.setTimeout(() => startTour(tour.id), 800);
    return () => window.clearTimeout(timer);
  }, [user?.id, user?.roles, hasCompleted, startTour]);

  // Cleanup driver on unmount
  useEffect(() => {
    return () => {
      if (driverRef.current) {
        driverRef.current.destroy();
        driverRef.current = null;
      }
    };
  }, []);

  const value = useMemo<TourContextValue>(
    () => ({
      startTour,
      startRecommended,
      active,
      available: Object.values(ALL_TOURS),
    }),
    [startTour, startRecommended, active],
  );

  return <TourContext.Provider value={value}>{children}</TourContext.Provider>;
}
