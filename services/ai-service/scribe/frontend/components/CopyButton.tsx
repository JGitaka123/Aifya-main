"use client";

import { useState, useCallback } from "react";

interface CopyButtonProps {
  /** Text to copy to clipboard */
  text: string;
  /** Optional label shown next to the button */
  label?: string;
  /** Size variant */
  size?: "sm" | "md";
  /** Additional CSS classes */
  className?: string;
}

/**
 * Inline copy-to-clipboard button with visual feedback.
 * Shows a checkmark for 2 seconds after copying.
 */
export default function CopyButton({ text, label, size = "sm", className = "" }: CopyButtonProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [text]);

  const iconSize = size === "sm" ? "w-3.5 h-3.5" : "w-4 h-4";
  const padding = size === "sm" ? "p-1" : "p-1.5";

  return (
    <button
      onClick={handleCopy}
      className={`inline-flex items-center gap-1 ${padding} rounded hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors group ${className}`}
      aria-label={`Copy ${label || text}`}
      title={copied ? "Copied!" : `Copy ${label || "to clipboard"}`}
    >
      {label && <span className="text-xs font-mono text-slate-500 dark:text-slate-400 group-hover:text-slate-700 dark:group-hover:text-slate-300">{label}</span>}
      {copied ? (
        <svg className={`${iconSize} text-green-500`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ) : (
        <svg className={`${iconSize} text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-300`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
        </svg>
      )}
    </button>
  );
}
