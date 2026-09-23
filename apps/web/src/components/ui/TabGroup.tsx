"use client";

import { cn } from "@/lib/utils";

interface Tab {
  key: string;
  label: string;
  count?: number;
}

/**
 * Premium tab group with two style variants: pills and underline.
 * Used for section switching across dashboard and detail pages.
 *
 * @param tabs - Array of tab definitions
 * @param activeTab - Currently selected tab key
 * @param onTabChange - Callback when tab changes
 * @param variant - Visual style: "pills" or "underline"
 * @returns Tab group component
 */
export function TabGroup({
  tabs,
  activeTab,
  onTabChange,
  variant = "pills",
}: {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (key: string) => void;
  variant?: "pills" | "underline";
}) {
  if (variant === "underline") {
    return (
      <div className="border-b border-border">
        <nav className="-mb-px flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => onTabChange(tab.key)}
              className={cn(
                "relative flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors",
                activeTab === tab.key
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:border-muted-foreground/30 hover:text-foreground",
              )}
            >
              {tab.label}
              {tab.count !== undefined && (
                <span
                  className={cn(
                    "inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-semibold",
                    activeTab === tab.key
                      ? "bg-primary/10 text-primary"
                      : "bg-muted text-muted-foreground",
                  )}
                >
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-1.5 rounded-xl bg-muted/50 p-1">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => onTabChange(tab.key)}
          className={cn(
            "relative flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-all duration-200",
            activeTab === tab.key
              ? "bg-card text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {tab.label}
          {tab.count !== undefined && (
            <span
              className={cn(
                "inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 text-[10px] font-semibold",
                activeTab === tab.key
                  ? "bg-primary/10 text-primary"
                  : "bg-muted text-muted-foreground",
              )}
            >
              {tab.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}

/**
 * Filter chip group for status/type filtering.
 *
 * @param options - Filter options
 * @param selected - Currently selected value
 * @param onSelect - Callback when filter changes
 * @param accentColor - Active chip color
 * @returns Filter chip group
 */
export function FilterChips({
  options,
  selected,
  onSelect,
  accentColor = "primary",
}: {
  options: { value: string; label: string }[];
  selected: string;
  onSelect: (value: string) => void;
  accentColor?: "primary" | "red" | "blue";
}) {
  const activeStyles: Record<string, string> = {
    primary: "bg-primary text-primary-foreground",
    red: "bg-red-600 text-white",
    blue: "bg-blue-600 text-white",
  };

  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onSelect(opt.value)}
          className={cn(
            "rounded-full px-3.5 py-1.5 text-xs font-medium transition-all duration-200",
            selected === opt.value
              ? activeStyles[accentColor]
              : "bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground",
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
