"use client";

import { useEffect } from "react";
import CopyButton from "@/components/CopyButton";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Application error:", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] text-center">
      <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-900/30 rounded-xl p-8 max-w-md animate-fade-in">
        <div className="text-4xl mb-4">&#9888;</div>
        <h2 className="text-xl font-semibold text-red-700 dark:text-red-400 mb-2">Something went wrong</h2>
        <p className="text-red-600 dark:text-red-400/80 text-sm mb-4">
          An unexpected error occurred. Our team has been notified.
        </p>
        {error.digest && (
          <div className="flex items-center justify-center gap-1 mb-4">
            <p className="text-xs text-red-400 dark:text-red-500 font-mono">Error ID: {error.digest}</p>
            <CopyButton text={error.digest} size="sm" />
          </div>
        )}
        <div className="flex gap-3 justify-center">
          <button
            onClick={reset}
            className="px-4 py-2 bg-red-600 text-white rounded-md text-sm hover:bg-red-700 transition-colors"
          >
            Try Again
          </button>
          <a
            href="/"
            className="px-4 py-2 border border-red-300 dark:border-red-800 text-red-600 dark:text-red-400 rounded-md text-sm hover:bg-red-50 dark:hover:bg-red-900/30 transition-colors"
          >
            Go Home
          </a>
        </div>
      </div>
    </div>
  );
}
