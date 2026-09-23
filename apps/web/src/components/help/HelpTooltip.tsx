"use client";

import { HelpCircle } from "lucide-react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

interface HelpTooltipProps {
  /**
   * Tooltip body. Plain string or rich JSX (multiple paragraphs, lists, code spans).
   * Keep it concise — 1-3 short paragraphs at most. For longer guidance, link to docs.
   */
  content: ReactNode;
  /** Visible label near the icon (optional, e.g. for screen-reader context). */
  ariaLabel?: string;
  /** Inline icon size in px. Default 14. */
  size?: number;
  /** Tailwind class overrides for the icon. */
  className?: string;
  /** Tooltip side preference. Default "top". */
  side?: "top" | "right" | "bottom" | "left";
  /** Optional override of the default ? icon — pass any ReactNode trigger. */
  trigger?: ReactNode;
}

/**
 * Inline contextual help icon.
 *
 * Renders a small `?` icon that, on hover or keyboard focus, shows a
 * Radix-powered tooltip with the supplied content. Use next to form
 * fields and section headings to surface guidance without cluttering
 * the UI.
 *
 * @example
 * ```tsx
 * <Label htmlFor="kra_pin">
 *   KRA PIN
 *   <HelpTooltip content="Format: A123456789B (11 chars). Required for PAYE filing." />
 * </Label>
 * ```
 *
 * @returns Help icon with hover/focus tooltip
 */
export function HelpTooltip({
  content,
  ariaLabel,
  size = 14,
  className,
  side = "top",
  trigger,
}: HelpTooltipProps) {
  return (
    <Tooltip.Provider delayDuration={150}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          {trigger ? (
            <span
              tabIndex={0}
              role="button"
              aria-label={ariaLabel ?? "Help"}
              className="inline-flex items-center justify-center align-middle ml-1 cursor-help focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded"
            >
              {trigger}
            </span>
          ) : (
            <button
              type="button"
              aria-label={ariaLabel ?? "Help"}
              className={cn(
                "inline-flex items-center justify-center align-middle ml-1",
                "text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300",
                "focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-full",
                "cursor-help",
                className,
              )}
            >
              <HelpCircle width={size} height={size} aria-hidden="true" />
            </button>
          )}
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            side={side}
            sideOffset={6}
            collisionPadding={12}
            className={cn(
              "z-[60] max-w-xs rounded-md px-3 py-2 text-xs leading-relaxed",
              "bg-gray-900 text-gray-50 shadow-lg",
              "dark:bg-gray-100 dark:text-gray-900",
              "data-[state=delayed-open]:animate-in",
              "data-[state=closed]:animate-out",
              "data-[state=delayed-open]:fade-in-0",
              "data-[state=closed]:fade-out-0",
              "data-[state=delayed-open]:zoom-in-95",
            )}
            role="tooltip"
          >
            {content}
            <Tooltip.Arrow
              className="fill-gray-900 dark:fill-gray-100"
              width={10}
              height={5}
            />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}
