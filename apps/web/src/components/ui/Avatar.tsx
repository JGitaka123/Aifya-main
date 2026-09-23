"use client";

import { cn } from "@/lib/utils";

/**
 * Generate consistent color from name string.
 *
 * @param name - Person's name
 * @returns Tailwind color classes
 */
function nameToColor(name: string): string {
  const colors = [
    "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
    "bg-green-100 text-green-700 dark:bg-green-950 dark:text-green-300",
    "bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300",
    "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
    "bg-teal-100 text-teal-700 dark:bg-teal-950 dark:text-teal-300",
    "bg-pink-100 text-pink-700 dark:bg-pink-950 dark:text-pink-300",
    "bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300",
    "bg-cyan-100 text-cyan-700 dark:bg-cyan-950 dark:text-cyan-300",
    "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300",
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length] ?? colors[0] ?? "";
}

/**
 * Initials-based avatar for patients and staff.
 * Generates consistent colors from the name.
 *
 * @param name - Full name
 * @param size - Avatar size: sm (32px), md (40px), lg (48px)
 * @param className - Additional classes
 * @returns Avatar circle with initials
 */
export function Avatar({
  name,
  size = "md",
  className,
}: {
  name: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const parts = name.trim().split(/\s+/);
  const initials = parts.length >= 2
    ? `${parts[0]?.[0] ?? ""}${parts[parts.length - 1]?.[0] ?? ""}`
    : name.slice(0, 2);

  const sizeClasses = {
    sm: "h-8 w-8 text-xs",
    md: "h-10 w-10 text-sm",
    lg: "h-12 w-12 text-base",
  };

  return (
    <div
      className={cn(
        "flex flex-shrink-0 items-center justify-center rounded-full font-semibold uppercase",
        sizeClasses[size],
        nameToColor(name),
        className,
      )}
      title={name}
    >
      {initials.toUpperCase()}
    </div>
  );
}
