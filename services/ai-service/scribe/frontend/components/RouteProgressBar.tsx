"use client";

import { useEffect, useState, useRef } from "react";
import { usePathname } from "next/navigation";

/**
 * NProgress-style loading bar that shows during route transitions.
 * Detects route changes via pathname and animates a blue bar at top of viewport.
 */
export default function RouteProgressBar() {
  const pathname = usePathname();
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);
  const prevPathname = useRef(pathname);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (pathname !== prevPathname.current) {
      // Start progress
      setVisible(true);
      setProgress(30);

      // Simulate progress increments
      timerRef.current = setTimeout(() => setProgress(60), 100);
      const t2 = setTimeout(() => setProgress(80), 200);
      const t3 = setTimeout(() => {
        setProgress(100);
        // Hide after animation completes
        setTimeout(() => {
          setVisible(false);
          setProgress(0);
        }, 300);
      }, 400);

      prevPathname.current = pathname;

      return () => {
        if (timerRef.current) clearTimeout(timerRef.current);
        clearTimeout(t2);
        clearTimeout(t3);
      };
    }
  }, [pathname]);

  if (!visible && progress === 0) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[100] pointer-events-none">
      <div
        className="h-[3px] bg-gradient-to-r from-medical-blue via-blue-400 to-medical-blue transition-all duration-300 ease-out shadow-sm shadow-medical-blue/30"
        style={{
          width: `${progress}%`,
          opacity: visible ? 1 : 0,
          transition: progress === 100 ? "width 200ms ease-out, opacity 300ms ease-out 200ms" : "width 300ms ease-out",
        }}
      />
    </div>
  );
}
