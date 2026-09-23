"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ROUTE_LABELS: Record<string, string> = {
  "": "Home",
  clinician: "Clinician Console",
  billing: "Billing Dashboard",
  analytics: "Analytics",
  admin: "Administration",
  profile: "Profile & Settings",
  login: "Sign In",
};

export default function Breadcrumbs() {
  const pathname = usePathname();

  if (pathname === "/") return null;

  const segments = pathname.split("/").filter(Boolean);

  const crumbs = segments.map((seg, i) => {
    const href = "/" + segments.slice(0, i + 1).join("/");
    const label = ROUTE_LABELS[seg] || seg.charAt(0).toUpperCase() + seg.slice(1).replace(/-/g, " ");
    const isLast = i === segments.length - 1;
    return { href, label, isLast };
  });

  return (
    <nav aria-label="Breadcrumb" className="mb-4">
      <ol className="flex items-center gap-1.5 text-sm text-slate-500 dark:text-slate-400">
        <li>
          <Link href="/" className="hover:text-medical-blue transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
          </Link>
        </li>
        {crumbs.map((crumb) => (
          <li key={crumb.href} className="flex items-center gap-1.5">
            <svg className="w-3.5 h-3.5 text-slate-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            {crumb.isLast ? (
              <span className="font-medium text-slate-800 dark:text-slate-200" aria-current="page">
                {crumb.label}
              </span>
            ) : (
              <Link href={crumb.href} className="hover:text-medical-blue transition-colors">
                {crumb.label}
              </Link>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
