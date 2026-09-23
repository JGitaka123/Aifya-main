"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

function DashboardStats() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [claimsStats, health] = await Promise.allSettled([
          api.claims.stats(),
          api.health(),
        ]);
        setStats({
          claims: claimsStats.status === "fulfilled" ? claimsStats.value : null,
          health: health.status === "fulfilled" ? health.value : null,
        });
      } catch {
        // Silently fail - stats are optional
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full max-w-5xl">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="card p-4 animate-pulse">
            <div className="h-3 bg-slate-200 dark:bg-slate-700 rounded w-20 mb-2" />
            <div className="h-7 bg-slate-200 dark:bg-slate-700 rounded w-16" />
          </div>
        ))}
      </div>
    );
  }

  const items = [
    {
      label: "Total Claims",
      value: stats?.claims?.total ?? "-",
      color: "text-medical-blue",
      bg: "bg-medical-blue/10",
    },
    {
      label: "Pending Review",
      value: stats?.claims?.by_status?.pending ?? stats?.claims?.pending ?? "-",
      color: "text-orange-600",
      bg: "bg-orange-50 dark:bg-orange-900/20",
    },
    {
      label: "Approved",
      value: stats?.claims?.by_status?.approved ?? stats?.claims?.approved ?? "-",
      color: "text-green-600",
      bg: "bg-green-50 dark:bg-green-900/20",
    },
    {
      label: "System Status",
      value: stats?.health?.status === "ok" || stats?.health?.status === "healthy" ? "Healthy" : "Degraded",
      color: stats?.health?.status === "ok" || stats?.health?.status === "healthy" ? "text-green-600" : "text-orange-600",
      bg: stats?.health?.status === "ok" || stats?.health?.status === "healthy" ? "bg-green-50 dark:bg-green-900/20" : "bg-orange-50 dark:bg-orange-900/20",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full max-w-5xl animate-fade-in">
      {items.map((item) => (
        <div key={item.label} className={`card p-4 ${item.bg}`}>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">{item.label}</p>
          <p className={`text-2xl font-bold mt-1 ${item.color}`}>{item.value}</p>
        </div>
      ))}
    </div>
  );
}

const modules = [
  {
    href: "/clinician",
    title: "Clinician Console",
    description: "Start an ambient scribe encounter, review SOAP notes, and authorize discharge summaries.",
    roles: ["clinician", "superadmin"],
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
      </svg>
    ),
  },
  {
    href: "/billing",
    title: "Billing Dashboard",
    description: "Review claims queue, fix rules engine violations, and track SHA claim approvals.",
    roles: ["billing_admin", "facility_admin", "superadmin"],
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    ),
  },
  {
    href: "/analytics",
    title: "Analytics",
    description: "Track claims trends, scrub pass rates, revenue insights, and violation patterns.",
    roles: ["billing_admin", "facility_admin", "superadmin"],
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    href: "/admin",
    title: "Admin Panel",
    description: "Manage user access, supervise audit logs, and monitor infrastructure health.",
    roles: ["facility_admin", "superadmin"],
    icon: (
      <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
];

export default function Home() {
  const { isAuthenticated, user } = useAuth();

  const visibleModules = isAuthenticated
    ? modules.filter((m) => user && m.roles.includes(user.role))
    : modules;

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-8">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-slate-800 dark:text-white mb-4">Aifya Health Platform</h1>
        <p className="text-xl text-slate-500 dark:text-slate-400 max-w-2xl">
          {isAuthenticated
            ? `Welcome back, ${user?.full_name}. Select a module to continue.`
            : "AI-powered clinical documentation and claims intelligence for Kenyan healthcare."}
        </p>
      </div>

      {/* Quick Stats for authenticated users */}
      {isAuthenticated && <DashboardStats />}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 w-full max-w-5xl">
        {visibleModules.map((mod) => (
          <Link
            key={mod.href}
            href={isAuthenticated ? mod.href : "/login"}
            className="group p-6 bg-white dark:bg-slate-800 rounded-xl shadow-sm border border-slate-200 dark:border-slate-700 hover:shadow-md hover:border-medical-blue dark:hover:border-medical-blue transition-all"
          >
            <div className="text-medical-blue mb-3 opacity-60 group-hover:opacity-100 transition-opacity">
              {mod.icon}
            </div>
            <h2 className="text-xl font-semibold text-medical-blue mb-2 group-hover:underline">
              {mod.title} &rarr;
            </h2>
            <p className="text-slate-600 dark:text-slate-400 text-sm">{mod.description}</p>
          </Link>
        ))}
      </div>

      {!isAuthenticated && (
        <p className="text-sm text-slate-400">
          <a href="/login" className="text-medical-blue hover:underline font-medium">
            Sign in
          </a>{" "}
          to access your modules.
        </p>
      )}
    </div>
  );
}
