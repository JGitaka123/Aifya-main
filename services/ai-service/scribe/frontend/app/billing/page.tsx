"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/components/Toast";
import Pagination from "@/components/Pagination";
import ExportButton from "@/components/ExportButton";
import ConfirmDialog from "@/components/ConfirmDialog";
import CopyButton from "@/components/CopyButton";
import { useDebounce } from "@/hooks/useDebounce";

interface Claim {
  id: string;
  encounter_id: string;
  qafya_patient_id: string;
  amount_billed: number;
  scrub_status: string;
  claim_status: string | null;
  scrub_violations: any;
  created_at: string;
  sha_submission_ref: string | null;
  override_reason: string | null;
}

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

const PAGE_SIZE_OPTIONS = [10, 25, 50];

export default function BillingPage() {
  const [claims, setClaims] = useState<Claim[]>([]);
  const [stats, setStats] = useState<ClaimStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedClaim, setSelectedClaim] = useState<Claim | null>(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [totalClaims, setTotalClaims] = useState(0);
  const [confirmSubmit, setConfirmSubmit] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sortField, setSortField] = useState<"created_at" | "amount_billed">("created_at");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const { toast } = useToast();

  const debouncedSearch = useDebounce(searchQuery, 300);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const offset = (currentPage - 1) * pageSize;
      const [claimsRes, statsRes] = await Promise.all([
        api.claims.list({ status: statusFilter || undefined, limit: pageSize, offset }),
        api.claims.stats(),
      ]);
      setClaims(claimsRes.claims || []);
      setTotalClaims(claimsRes.total || 0);
      setStats(statsRes);
    } catch (err: any) {
      toast(err.message || "Failed to load claims data", "error");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, currentPage, pageSize, toast]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Reset to page 1 when filter changes
  useEffect(() => {
    setCurrentPage(1);
  }, [statusFilter]);

  const handleOverride = async () => {
    if (!selectedClaim || overrideReason.length < 10) return;
    try {
      await api.claims.override(selectedClaim.id, overrideReason);
      toast("Claim overridden successfully", "success");
      setSelectedClaim(null);
      setOverrideReason("");
      loadData();
    } catch (err: any) {
      toast(err.message || "Override failed", "error");
    }
  };

  const handleSubmit = async (claimId: string) => {
    setSubmitting(true);
    try {
      const res = await api.claims.submit(claimId);
      toast(`Claim submitted. Ref: ${res.sha_submission_ref}`, "success");
      setConfirmSubmit(null);
      loadData();
    } catch (err: any) {
      toast(err.message || "Submission failed", "error");
    } finally {
      setSubmitting(false);
    }
  };

  const formatCurrency = (amount: number) =>
    new Intl.NumberFormat("en-KE", { style: "currency", currency: "KES", minimumFractionDigits: 0 }).format(amount);

  const statusColor = (status: string) => {
    switch (status) {
      case "blocked": return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
      case "passed": return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400";
      case "warnings_only": return "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400";
      case "overridden": return "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400";
      default: return "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400";
    }
  };

  const statusLabel = (status: string) => {
    switch (status) {
      case "warnings_only": return "WARNINGS";
      default: return status.toUpperCase();
    }
  };

  // Client-side search & sort
  const filteredClaims = useMemo(() => {
    let result = [...claims];

    // Search filter
    if (debouncedSearch) {
      const q = debouncedSearch.toLowerCase();
      result = result.filter(
        (c) =>
          c.id.toLowerCase().includes(q) ||
          c.qafya_patient_id?.toLowerCase().includes(q) ||
          c.sha_submission_ref?.toLowerCase().includes(q)
      );
    }

    // Sort
    result.sort((a, b) => {
      const aVal = sortField === "amount_billed" ? a.amount_billed : new Date(a.created_at).getTime();
      const bVal = sortField === "amount_billed" ? b.amount_billed : new Date(b.created_at).getTime();
      return sortDir === "asc" ? aVal - bVal : bVal - aVal;
    });

    return result;
  }, [claims, debouncedSearch, sortField, sortDir]);

  const toggleSort = (field: "created_at" | "amount_billed") => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  const SortIcon = ({ field }: { field: string }) => {
    if (sortField !== field) return <span className="text-slate-300 dark:text-slate-600 ml-1">&#8645;</span>;
    return <span className="text-medical-blue ml-1">{sortDir === "asc" ? "&#8593;" : "&#8595;"}</span>;
  };

  const totalPages = Math.ceil(totalClaims / pageSize);

  const exportColumns = [
    { key: "id", label: "Claim ID" },
    { key: "qafya_patient_id", label: "Patient ID" },
    { key: "created_at", label: "Date" },
    { key: "amount_billed", label: "Amount Billed (KES)" },
    { key: "scrub_status", label: "Scrub Status" },
    { key: "claim_status", label: "Claim Status" },
    { key: "sha_submission_ref", label: "SHA Reference" },
    { key: "override_reason", label: "Override Reason" },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-3 border-b dark:border-slate-700 pb-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Billing Dashboard</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">Intelligent Claims Scrubbing and SHA Submission</p>
        </div>
        <div className="flex gap-2">
          <ExportButton data={filteredClaims} filename="aifya_claims" columns={exportColumns} />
          <button onClick={loadData} className="btn-secondary" aria-label="Refresh claims">
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card p-4 flex flex-col">
          <span className="text-slate-500 dark:text-slate-400 text-sm font-medium">Claims Today</span>
          <span className="text-3xl font-bold text-slate-800 dark:text-slate-100">{stats?.today_count ?? "-"}</span>
        </div>
        <div className="card p-4 flex flex-col bg-red-50 dark:bg-red-900/20 border-red-100 dark:border-red-900/30">
          <span className="text-red-700 dark:text-red-400 text-sm font-medium">Blocked</span>
          <span className="text-3xl font-bold text-red-700 dark:text-red-400">{stats?.blocked ?? "-"}</span>
        </div>
        <div className="card p-4 flex flex-col bg-green-50 dark:bg-green-900/20 border-green-100 dark:border-green-900/30">
          <span className="text-green-700 dark:text-green-400 text-sm font-medium">Auto-Passed</span>
          <span className="text-3xl font-bold text-green-700 dark:text-green-400">{stats?.passed ?? "-"}</span>
        </div>
        <div className="card p-4 flex flex-col bg-medical-blue/10 dark:bg-medical-blue/20 border-medical-blue/20 dark:border-medical-blue/30">
          <span className="text-medical-blue text-sm font-medium">Total Billed</span>
          <span className="text-2xl font-bold text-medical-blue">{stats ? formatCurrency(stats.total_billed) : "-"}</span>
        </div>
      </div>

      {/* Filter Bar + Search */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex flex-wrap gap-2">
          {["", "blocked", "passed", "warnings_only", "overridden"].map((f) => (
            <button
              key={f}
              onClick={() => setStatusFilter(f)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                statusFilter === f
                  ? "bg-medical-blue text-white"
                  : "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-600"
              }`}
            >
              {f ? statusLabel(f) : "All"}
            </button>
          ))}
        </div>
        <div className="sm:ml-auto relative">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search claims..."
            className="input w-full sm:w-64 pl-9"
            aria-label="Search claims by ID, patient, or SHA ref"
          />
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
      </div>

      {/* Claims Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="table-header">
              <tr>
                <th className="px-4 md:px-6 py-3">Claim ID</th>
                <th className="px-4 md:px-6 py-3">Patient</th>
                <th className="px-4 md:px-6 py-3 hidden sm:table-cell cursor-pointer select-none" onClick={() => toggleSort("created_at")}>
                  Date <SortIcon field="created_at" />
                </th>
                <th className="px-4 md:px-6 py-3 cursor-pointer select-none" onClick={() => toggleSort("amount_billed")}>
                  Amount <SortIcon field="amount_billed" />
                </th>
                <th className="px-4 md:px-6 py-3">Scrub Status</th>
                <th className="px-4 md:px-6 py-3 hidden md:table-cell">SHA Ref</th>
                <th className="px-4 md:px-6 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i} className="animate-pulse border-b dark:border-slate-700">
                    <td className="px-4 md:px-6 py-4"><div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-20"></div></td>
                    <td className="px-4 md:px-6 py-4"><div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-16"></div></td>
                    <td className="px-4 md:px-6 py-4 hidden sm:table-cell"><div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-20"></div></td>
                    <td className="px-4 md:px-6 py-4"><div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-24"></div></td>
                    <td className="px-4 md:px-6 py-4"><div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-16"></div></td>
                    <td className="px-4 md:px-6 py-4 hidden md:table-cell"><div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-20"></div></td>
                    <td className="px-4 md:px-6 py-4"><div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-12 ml-auto"></div></td>
                  </tr>
                ))
              ) : filteredClaims.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-400 dark:text-slate-500">
                    <div className="flex flex-col items-center gap-2">
                      <svg className="w-10 h-10 text-slate-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                      <p className="font-medium">No claims found</p>
                      <p className="text-xs">{searchQuery ? "Try adjusting your search query" : "Claims will appear here once created"}</p>
                    </div>
                  </td>
                </tr>
              ) : (
                filteredClaims.map((claim) => (
                  <tr key={claim.id} className="table-row">
                    <td className="px-4 md:px-6 py-4 font-mono font-medium text-slate-900 dark:text-slate-200 text-xs">
                      <span className="inline-flex items-center gap-0.5">
                        {claim.id.slice(0, 8)}...
                        <CopyButton text={claim.id} size="sm" />
                      </span>
                    </td>
                    <td className="px-4 md:px-6 py-4 text-xs font-mono text-slate-600 dark:text-slate-400">{claim.qafya_patient_id || "-"}</td>
                    <td className="px-4 md:px-6 py-4 text-xs text-slate-600 dark:text-slate-400 hidden sm:table-cell">{new Date(claim.created_at).toLocaleDateString()}</td>
                    <td className="px-4 md:px-6 py-4 font-mono text-slate-800 dark:text-slate-200">{formatCurrency(claim.amount_billed)}</td>
                    <td className="px-4 md:px-6 py-4">
                      <span className={`px-2 py-1 rounded text-xs font-bold ${statusColor(claim.scrub_status)}`}>
                        {statusLabel(claim.scrub_status)}
                      </span>
                    </td>
                    <td className="px-4 md:px-6 py-4 text-xs font-mono text-slate-500 hidden md:table-cell">{claim.sha_submission_ref || "-"}</td>
                    <td className="px-4 md:px-6 py-4 text-right space-x-2">
                      {(claim.scrub_status === "blocked" || claim.scrub_status === "warnings_only") && (
                        <button onClick={() => setSelectedClaim(claim)} className="text-medical-blue hover:underline font-medium text-xs">
                          Review
                        </button>
                      )}
                      {(claim.scrub_status === "passed" || claim.scrub_status === "overridden" || claim.scrub_status === "warnings_only") && !claim.sha_submission_ref && (
                        <button onClick={() => setConfirmSubmit(claim.id)} className="text-green-600 dark:text-green-400 hover:underline font-medium text-xs">
                          Submit
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="px-4 md:px-6 border-t dark:border-slate-700">
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={setCurrentPage}
            pageSize={pageSize}
            pageSizeOptions={PAGE_SIZE_OPTIONS}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setCurrentPage(1);
            }}
            totalItems={totalClaims}
          />
        </div>
      </div>

      {/* Submit Confirmation */}
      <ConfirmDialog
        isOpen={!!confirmSubmit}
        title="Submit Claim to SHA"
        message="This will submit the claim to the Social Health Authority for processing. This action cannot be undone. Are you sure you want to proceed?"
        confirmLabel="Submit to SHA"
        cancelLabel="Cancel"
        variant="info"
        onConfirm={() => confirmSubmit && handleSubmit(confirmSubmit)}
        onCancel={() => setConfirmSubmit(null)}
        loading={submitting}
      />

      {/* Override Modal */}
      {selectedClaim && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4 animate-fade-in" role="dialog" aria-modal="true">
          <div className="card shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b dark:border-slate-700">
              <h3 className="text-lg font-semibold text-slate-800 dark:text-white">Review Claim</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Claim: {selectedClaim.id.slice(0, 12)}...</p>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1">Amount Billed</p>
                <p className="text-xl font-bold text-slate-800 dark:text-white">{formatCurrency(selectedClaim.amount_billed)}</p>
              </div>

              <div>
                <p className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-2">Violations</p>
                {Array.isArray(selectedClaim.scrub_violations) && selectedClaim.scrub_violations.length > 0 ? (
                  <div className="space-y-2">
                    {selectedClaim.scrub_violations.map((v: any, i: number) => (
                      <div key={i} className="bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-900/30 rounded-lg p-3">
                        <div className="flex items-center gap-2">
                          <span className="px-1.5 py-0.5 bg-red-200 dark:bg-red-800 text-red-800 dark:text-red-200 text-xs rounded font-mono">{v.rule_id}</span>
                          <span className="text-sm text-slate-700 dark:text-slate-300">{v.message}</span>
                        </div>
                        {v.suggested_fix && <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">Fix: {v.suggested_fix}</p>}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-400">No violation details available</p>
                )}
              </div>

              <div>
                <label htmlFor="override-reason" className="text-sm font-medium text-slate-600 dark:text-slate-400 mb-1 block">
                  Override Justification (min 10 characters)
                </label>
                <textarea
                  id="override-reason"
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  rows={3}
                  placeholder="Clinical justification for overriding this claim..."
                  className="input w-full resize-y"
                />
                <p className={`text-xs mt-1 ${overrideReason.length >= 10 ? "text-green-600 dark:text-green-400" : "text-slate-400"}`}>
                  {overrideReason.length}/10 min characters {overrideReason.length >= 10 && "✓"}
                </p>
              </div>
            </div>

            <div className="p-6 border-t dark:border-slate-700 flex gap-3 justify-end">
              <button
                onClick={() => { setSelectedClaim(null); setOverrideReason(""); }}
                className="btn-secondary"
              >
                Cancel
              </button>
              <button
                onClick={handleOverride}
                disabled={overrideReason.length < 10}
                className="px-4 py-2 bg-orange-500 text-white rounded-md text-sm font-medium hover:bg-orange-600 disabled:opacity-50 transition-colors"
              >
                Override Claim
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
