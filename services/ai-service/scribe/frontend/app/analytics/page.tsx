"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, Legend, AreaChart, Area,
} from "recharts";
import { api } from "@/lib/api";
import { useToast } from "@/components/Toast";
import ExportButton from "@/components/ExportButton";

interface ClaimStats {
  total: number;
  blocked: number;
  passed: number;
  warnings_only: number;
  overridden: number;
  today_count: number;
  total_billed: number;
  total_approved: number;
}

const COLORS = {
  passed: "#22c55e",
  blocked: "#ef4444",
  warnings_only: "#f97316",
  overridden: "#3b82f6",
  pending: "#94a3b8",
};

export default function AnalyticsPage() {
  const [stats, setStats] = useState<ClaimStats | null>(null);
  const [claims, setClaims] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [dateRange, setDateRange] = useState<"7d" | "30d" | "90d">("30d");
  const { toast } = useToast();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, claimsRes] = await Promise.all([
        api.claims.stats(),
        api.claims.list({ limit: 500 }),
      ]);
      setStats(statsRes);
      setClaims(claimsRes.claims || []);
    } catch (err: any) {
      toast(err.message || "Failed to load analytics data", "error");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat("en-KE", { style: "currency", currency: "KES", minimumFractionDigits: 0 }).format(amount);

  // Pie chart data for scrub status distribution
  const pieData = useMemo(() => {
    if (!stats) return [];
    return [
      { name: "Passed", value: stats.passed, color: COLORS.passed },
      { name: "Blocked", value: stats.blocked, color: COLORS.blocked },
      { name: "Warnings", value: stats.warnings_only, color: COLORS.warnings_only },
      { name: "Overridden", value: stats.overridden, color: COLORS.overridden },
    ].filter((d) => d.value > 0);
  }, [stats]);

  // Daily claims trend data
  const trendData = useMemo(() => {
    const days = dateRange === "7d" ? 7 : dateRange === "30d" ? 30 : 90;
    const now = new Date();
    const dailyMap = new Map<string, { passed: number; blocked: number; warnings: number; total_billed: number }>();

    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      const key = d.toISOString().slice(0, 10);
      dailyMap.set(key, { passed: 0, blocked: 0, warnings: 0, total_billed: 0 });
    }

    claims.forEach((c) => {
      const key = new Date(c.created_at).toISOString().slice(0, 10);
      const entry = dailyMap.get(key);
      if (entry) {
        if (c.scrub_status === "passed") entry.passed++;
        else if (c.scrub_status === "blocked") entry.blocked++;
        else entry.warnings++;
        entry.total_billed += c.amount_billed || 0;
      }
    });

    return Array.from(dailyMap.entries()).map(([date, data]) => ({
      date: new Date(date).toLocaleDateString("en-KE", { month: "short", day: "numeric" }),
      ...data,
    }));
  }, [claims, dateRange]);

  // Revenue trend
  const revenueData = useMemo(() => {
    const days = dateRange === "7d" ? 7 : dateRange === "30d" ? 30 : 90;
    const now = new Date();
    const map = new Map<string, number>();

    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      map.set(d.toISOString().slice(0, 10), 0);
    }

    claims.forEach((c) => {
      const key = new Date(c.created_at).toISOString().slice(0, 10);
      if (map.has(key)) map.set(key, (map.get(key) || 0) + (c.amount_billed || 0));
    });

    let cumulative = 0;
    return Array.from(map.entries()).map(([date, value]) => {
      cumulative += value;
      return {
        date: new Date(date).toLocaleDateString("en-KE", { month: "short", day: "numeric" }),
        daily: value,
        cumulative,
      };
    });
  }, [claims, dateRange]);

  const passRate = stats && stats.total > 0
    ? (((stats.passed + stats.overridden) / stats.total) * 100).toFixed(1)
    : "0";

  const approvalRate = stats && stats.total_billed > 0
    ? ((stats.total_approved / stats.total_billed) * 100).toFixed(1)
    : "0";

  // Analytics export data
  const analyticsExportData = useMemo(() => {
    return trendData.map((d) => ({
      date: d.date,
      passed: d.passed,
      blocked: d.blocked,
      warnings: d.warnings,
      total_billed: d.total_billed,
    }));
  }, [trendData]);

  const analyticsExportColumns = [
    { key: "date", label: "Date" },
    { key: "passed", label: "Passed" },
    { key: "blocked", label: "Blocked" },
    { key: "warnings", label: "Warnings" },
    { key: "total_billed", label: "Total Billed (KES)" },
  ];

  // Dark-mode-aware chart text color
  const chartTextColor = typeof document !== "undefined" && document.documentElement.classList.contains("dark") ? "#94a3b8" : "#64748b";
  const chartGridColor = typeof document !== "undefined" && document.documentElement.classList.contains("dark") ? "#334155" : "#e2e8f0";

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <div className="border-b dark:border-slate-700 pb-4">
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Analytics</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">Claims Intelligence & Revenue Insights</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="card p-6 animate-pulse">
              <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-24 mb-3"></div>
              <div className="h-8 bg-slate-200 dark:bg-slate-700 rounded w-16"></div>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[1, 2].map((i) => (
            <div key={i} className="card p-6 animate-pulse h-80">
              <div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-32 mb-4"></div>
              <div className="h-full bg-slate-100 dark:bg-slate-700/50 rounded"></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-3 border-b dark:border-slate-700 pb-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Analytics</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">Claims Intelligence & Revenue Insights</p>
        </div>
        <div className="flex gap-2 items-center">
          <ExportButton data={analyticsExportData} filename="aifya_analytics" columns={analyticsExportColumns} />
          <div className="flex gap-1 bg-slate-100 dark:bg-slate-800 rounded-lg p-0.5">
            {(["7d", "30d", "90d"] as const).map((range) => (
              <button
                key={range}
                onClick={() => setDateRange(range)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                  dateRange === range
                    ? "bg-white dark:bg-slate-700 text-slate-800 dark:text-white shadow-sm"
                    : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                }`}
              >
                {range === "7d" ? "7 Days" : range === "30d" ? "30 Days" : "90 Days"}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card p-5">
          <p className="text-slate-500 dark:text-slate-400 text-sm font-medium">Total Claims</p>
          <p className="text-3xl font-bold text-slate-800 dark:text-white mt-1">{stats?.total ?? 0}</p>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">{stats?.today_count ?? 0} today</p>
        </div>
        <div className="card p-5 bg-green-50 dark:bg-green-900/20 border-green-100 dark:border-green-900/30">
          <p className="text-green-700 dark:text-green-400 text-sm font-medium">Scrub Pass Rate</p>
          <p className="text-3xl font-bold text-green-700 dark:text-green-400 mt-1">{passRate}%</p>
          <p className="text-xs text-green-600 dark:text-green-500 mt-1">{(stats?.passed ?? 0) + (stats?.overridden ?? 0)} passed/overridden</p>
        </div>
        <div className="card p-5 bg-blue-50 dark:bg-blue-900/20 border-blue-100 dark:border-blue-900/30">
          <p className="text-blue-700 dark:text-blue-400 text-sm font-medium">Total Billed</p>
          <p className="text-2xl font-bold text-blue-700 dark:text-blue-400 mt-1">{stats ? formatCurrency(stats.total_billed) : "KES 0"}</p>
        </div>
        <div className="card p-5 bg-emerald-50 dark:bg-emerald-900/20 border-emerald-100 dark:border-emerald-900/30">
          <p className="text-emerald-700 dark:text-emerald-400 text-sm font-medium">Approval Rate</p>
          <p className="text-3xl font-bold text-emerald-700 dark:text-emerald-400 mt-1">{approvalRate}%</p>
          <p className="text-xs text-emerald-600 dark:text-emerald-500 mt-1">{stats ? formatCurrency(stats.total_approved) : "KES 0"} approved</p>
        </div>
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Claims Trend */}
        <div className="lg:col-span-2 card p-6">
          <h3 className="text-lg font-semibold text-slate-800 dark:text-white mb-4">Claims Volume Trend</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={trendData} barGap={0} barCategoryGap="20%">
              <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: chartTextColor }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: chartTextColor }} />
              <Tooltip
                contentStyle={{
                  borderRadius: "8px",
                  border: "1px solid var(--chart-border, #e2e8f0)",
                  boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
                  backgroundColor: "var(--chart-bg, #fff)",
                }}
              />
              <Legend iconType="circle" />
              <Bar dataKey="passed" name="Passed" fill={COLORS.passed} radius={[2, 2, 0, 0]} />
              <Bar dataKey="blocked" name="Blocked" fill={COLORS.blocked} radius={[2, 2, 0, 0]} />
              <Bar dataKey="warnings" name="Warnings" fill={COLORS.warnings_only} radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Scrub Distribution Pie */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-slate-800 dark:text-white mb-4">Scrub Distribution</h3>
          <ResponsiveContainer width="100%" height={260}>
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={95}
                paddingAngle={3}
                dataKey="value"
                label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {pieData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
          <div className="flex flex-wrap gap-3 justify-center mt-2">
            {pieData.map((entry) => (
              <div key={entry.name} className="flex items-center gap-1.5 text-xs text-slate-600 dark:text-slate-400">
                <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: entry.color }}></span>
                {entry.name}: {entry.value}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Trend */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-slate-800 dark:text-white mb-4">Revenue Trend (Billed)</h3>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={revenueData}>
              <defs>
                <linearGradient id="revenueGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: chartTextColor }} />
              <YAxis
                tick={{ fontSize: 11, fill: chartTextColor }}
                tickFormatter={(v) => `${(v / 1000).toFixed(0)}K`}
              />
              <Tooltip formatter={(value: number) => formatCurrency(value)} />
              <Legend />
              <Area
                type="monotone"
                dataKey="cumulative"
                name="Cumulative"
                stroke="#3b82f6"
                fill="url(#revenueGradient)"
                strokeWidth={2}
              />
              <Line type="monotone" dataKey="daily" name="Daily" stroke="#22c55e" dot={false} strokeWidth={1.5} />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Top Violations */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold text-slate-800 dark:text-white mb-4">Top Scrub Violations</h3>
          <ViolationsTable claims={claims} />
        </div>
      </div>
    </div>
  );
}

function ViolationsTable({ claims }: { claims: any[] }) {
  const violationCounts = useMemo(() => {
    const counts = new Map<string, { rule_id: string; message: string; count: number }>();

    claims.forEach((c) => {
      if (Array.isArray(c.scrub_violations)) {
        c.scrub_violations.forEach((v: any) => {
          const key = v.rule_id || v.message || "unknown";
          const existing = counts.get(key);
          if (existing) {
            existing.count++;
          } else {
            counts.set(key, { rule_id: v.rule_id || "-", message: v.message || key, count: 1 });
          }
        });
      }
    });

    return Array.from(counts.values())
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }, [claims]);

  if (violationCounts.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-slate-400 dark:text-slate-500 text-sm">
        No violation data available
      </div>
    );
  }

  const maxCount = violationCounts[0]?.count || 1;

  return (
    <div className="space-y-3">
      {violationCounts.map((v) => (
        <div key={v.rule_id} className="flex items-center gap-3">
          <span className="px-2 py-0.5 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 text-xs font-mono rounded w-16 text-center flex-shrink-0">
            {v.rule_id}
          </span>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-slate-700 dark:text-slate-300 truncate">{v.message}</p>
            <div className="mt-1 w-full bg-slate-100 dark:bg-slate-700 rounded-full h-1.5">
              <div
                className="bg-red-400 dark:bg-red-500 h-1.5 rounded-full transition-all"
                style={{ width: `${(v.count / maxCount) * 100}%` }}
              ></div>
            </div>
          </div>
          <span className="text-sm font-bold text-slate-600 dark:text-slate-300 flex-shrink-0">{v.count}</span>
        </div>
      ))}
    </div>
  );
}
