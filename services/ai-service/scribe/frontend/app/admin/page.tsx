"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/components/Toast";
import ExportButton from "@/components/ExportButton";
import ConfirmDialog from "@/components/ConfirmDialog";

type Tab = "health" | "users" | "audit";

export default function AdminPage() {
  const [activeTab, setActiveTab] = useState<Tab>("health");
  const { toast } = useToast();

  // Health state
  const [health, setHealth] = useState<any>(null);
  const [syncStatus, setSyncStatus] = useState<any>(null);

  // Users state
  const [users, setUsers] = useState<any[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [newUser, setNewUser] = useState({ email: "", password: "", full_name: "", role: "clinician", license_no: "" });
  const [confirmToggle, setConfirmToggle] = useState<{ user: any; activate: boolean } | null>(null);

  // Audit state
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditFilter, setAuditFilter] = useState("");

  const loadHealth = useCallback(async () => {
    try {
      const [h, s] = await Promise.all([api.health(), api.admin.syncStatus()]);
      setHealth(h);
      setSyncStatus(s);
    } catch {
      toast("Failed to fetch health status", "error");
    }
  }, [toast]);

  const loadUsers = useCallback(async () => {
    setUsersLoading(true);
    try {
      const res = await api.admin.users();
      setUsers(res.users || []);
    } catch (err: any) {
      toast(err.message || "Failed to load users", "error");
    } finally {
      setUsersLoading(false);
    }
  }, [toast]);

  const loadAuditLogs = useCallback(async () => {
    setAuditLoading(true);
    try {
      const res = await api.admin.auditLog({ action: auditFilter || undefined, limit: 100 });
      setAuditLogs(res.logs || []);
    } catch (err: any) {
      toast(err.message || "Failed to load audit logs", "error");
    } finally {
      setAuditLoading(false);
    }
  }, [auditFilter, toast]);

  useEffect(() => {
    if (activeTab === "health") loadHealth();
    else if (activeTab === "users") loadUsers();
    else if (activeTab === "audit") loadAuditLogs();
  }, [activeTab, loadHealth, loadUsers, loadAuditLogs]);

  const handleCreateUser = async () => {
    if (!newUser.email || !newUser.password || !newUser.full_name) return;
    try {
      await api.admin.createUser(newUser);
      toast("User created successfully", "success");
      setShowCreateUser(false);
      setNewUser({ email: "", password: "", full_name: "", role: "clinician", license_no: "" });
      loadUsers();
    } catch (err: any) {
      toast(err.message || "Failed to create user", "error");
    }
  };

  const handleToggleUserStatus = async () => {
    if (!confirmToggle) return;
    try {
      await api.admin.toggleUserStatus(confirmToggle.user.id, confirmToggle.activate);
      toast(`User ${confirmToggle.activate ? "enabled" : "disabled"} successfully`, "success");
      setConfirmToggle(null);
      loadUsers();
    } catch (err: any) {
      toast(err.message || "Failed to update user status", "error");
      setConfirmToggle(null);
    }
  };

  const statusBadge = (status: string) => {
    const colors: Record<string, string> = {
      connected: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
      healthy: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
      ok: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
      closed: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
      configured: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
      disconnected: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
      open: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
      error: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
      not_configured: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
      degraded: "bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400",
      unreachable: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400",
    };
    return (
      <span className={`px-2 py-1 rounded text-xs font-bold uppercase ${colors[status] || "bg-slate-100 text-slate-600 dark:bg-slate-700 dark:text-slate-400"}`}>
        {status}
      </span>
    );
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-between items-end border-b dark:border-slate-700 pb-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Platform Administration</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">System Health, Audit Logs, and User Management</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b dark:border-slate-700">
        {([
          { key: "health", label: "System Health" },
          { key: "users", label: "User Management" },
          { key: "audit", label: "Audit Log" },
        ] as { key: Tab; label: string }[]).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
              activeTab === tab.key
                ? "border-medical-blue text-medical-blue"
                : "border-transparent text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Health Tab */}
      {activeTab === "health" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          <div className="card p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold text-slate-800 dark:text-white">Component Status</h2>
              <button onClick={loadHealth} className="text-xs text-medical-blue hover:underline">Refresh</button>
            </div>
            <div className="space-y-3">
              {health?.components ? (
                Object.entries(health.components).map(([key, value]) => (
                  <div key={key} className="flex justify-between items-center">
                    <span className="text-slate-600 dark:text-slate-400 text-sm capitalize">{key.replace(/_/g, " ")}</span>
                    {statusBadge(value as string)}
                  </div>
                ))
              ) : (
                <p className="text-slate-400 text-sm">Loading...</p>
              )}
            </div>
          </div>

          <div className="card p-6">
            <h2 className="text-lg font-semibold text-slate-800 dark:text-white mb-4">Q-Afya Sync</h2>
            <div className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-slate-600 dark:text-slate-400 text-sm">Connection</span>
                {syncStatus ? statusBadge(syncStatus.qafya_connection) : <span className="text-slate-400">-</span>}
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-600 dark:text-slate-400 text-sm">Circuit Breaker</span>
                {syncStatus ? statusBadge(syncStatus.circuit_breaker_state) : <span className="text-slate-400">-</span>}
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-600 dark:text-slate-400 text-sm">Breaker Failures</span>
                <span className="font-mono text-sm text-slate-800 dark:text-slate-200">{syncStatus?.circuit_breaker_failures ?? "-"}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-600 dark:text-slate-400 text-sm">Latency</span>
                <span className="font-mono text-sm text-slate-800 dark:text-slate-200">{syncStatus?.current_latency_ms ? `${syncStatus.current_latency_ms}ms` : "-"}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-600 dark:text-slate-400 text-sm">Last Success</span>
                <span className="text-xs text-slate-500 dark:text-slate-400">{syncStatus?.last_success_timestamp || "Never"}</span>
              </div>
            </div>
          </div>

          <div className="card p-6">
            <h2 className="text-lg font-semibold text-slate-800 dark:text-white mb-4">Platform Info</h2>
            <div className="space-y-3 text-sm">
              <div className="flex justify-between"><span className="text-slate-600 dark:text-slate-400">API Status</span>{statusBadge(health?.status || "unknown")}</div>
              <div className="flex justify-between"><span className="text-slate-600 dark:text-slate-400">Facility</span><span className="text-slate-800 dark:text-slate-200 font-medium">Mary Help Hospital</span></div>
              <div className="flex justify-between"><span className="text-slate-600 dark:text-slate-400">SHA Code</span><span className="font-mono text-slate-800 dark:text-slate-200">MHH-001</span></div>
              <div className="flex justify-between"><span className="text-slate-600 dark:text-slate-400">Version</span><span className="font-mono text-slate-800 dark:text-slate-200">1.0.0</span></div>
            </div>
          </div>
        </div>
      )}

      {/* Users Tab */}
      {activeTab === "users" && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => setShowCreateUser(!showCreateUser)}
              className="btn-primary"
            >
              {showCreateUser ? "Cancel" : "Create User"}
            </button>
          </div>

          {showCreateUser && (
            <div className="card p-6 animate-slide-up">
              <h3 className="text-lg font-semibold text-slate-800 dark:text-white mb-4">New User</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <input placeholder="Full Name" value={newUser.full_name} onChange={(e) => setNewUser({ ...newUser, full_name: e.target.value })}
                  className="input" />
                <input placeholder="Email" type="email" value={newUser.email} onChange={(e) => setNewUser({ ...newUser, email: e.target.value })}
                  className="input" />
                <input placeholder="Password (min 8 chars)" type="password" value={newUser.password} onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                  className="input" />
                <select value={newUser.role} onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                  className="input">
                  <option value="clinician">Clinician</option>
                  <option value="billing_admin">Billing Admin</option>
                  <option value="facility_admin">Facility Admin</option>
                  <option value="superadmin">Superadmin</option>
                </select>
                <input placeholder="License No (optional)" value={newUser.license_no} onChange={(e) => setNewUser({ ...newUser, license_no: e.target.value })}
                  className="input" />
                <button onClick={handleCreateUser} className="px-4 py-2 bg-green-600 text-white rounded-md text-sm font-medium hover:bg-green-700 transition-colors">
                  Create
                </button>
              </div>
            </div>
          )}

          <div className="card overflow-hidden">
            <table className="w-full text-sm text-left">
              <thead className="table-header">
                <tr>
                  <th className="px-6 py-3">Name</th>
                  <th className="px-6 py-3">Email</th>
                  <th className="px-6 py-3">Role</th>
                  <th className="px-6 py-3 hidden md:table-cell">License</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3 hidden sm:table-cell">Created</th>
                </tr>
              </thead>
              <tbody>
                {usersLoading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <tr key={i} className="animate-pulse border-b dark:border-slate-700">
                      <td className="px-6 py-3"><div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-24"></div></td>
                      <td className="px-6 py-3"><div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-32"></div></td>
                      <td className="px-6 py-3"><div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-16"></div></td>
                      <td className="px-6 py-3 hidden md:table-cell"><div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-20"></div></td>
                      <td className="px-6 py-3"><div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-12"></div></td>
                      <td className="px-6 py-3 hidden sm:table-cell"><div className="h-4 bg-slate-200 dark:bg-slate-700 rounded w-20"></div></td>
                    </tr>
                  ))
                ) : users.length === 0 ? (
                  <tr><td colSpan={6} className="px-6 py-12 text-center text-slate-400 dark:text-slate-500">No users found</td></tr>
                ) : (
                  users.map((u) => (
                    <tr key={u.id} className="table-row">
                      <td className="px-6 py-3 font-medium text-slate-900 dark:text-slate-100">{u.full_name}</td>
                      <td className="px-6 py-3 text-slate-600 dark:text-slate-400">{u.email}</td>
                      <td className="px-6 py-3"><span className="px-2 py-0.5 rounded text-xs font-medium bg-medical-blue/10 text-medical-blue capitalize">{u.role?.replace("_", " ")}</span></td>
                      <td className="px-6 py-3 hidden md:table-cell font-mono text-xs text-slate-500 dark:text-slate-400">{u.license_no || "-"}</td>
                      <td className="px-6 py-3">
                        <button
                          onClick={() => setConfirmToggle({ user: u, activate: u.is_active === false })}
                          className={`px-2.5 py-1 rounded text-xs font-bold transition-colors ${
                            u.is_active !== false
                              ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 hover:bg-red-100 hover:text-red-700 dark:hover:bg-red-900/30 dark:hover:text-red-400"
                              : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400 hover:bg-green-100 hover:text-green-700 dark:hover:bg-green-900/30 dark:hover:text-green-400"
                          }`}
                          title={u.is_active !== false ? "Click to disable" : "Click to enable"}
                        >
                          {u.is_active !== false ? "ACTIVE" : "DISABLED"}
                        </button>
                      </td>
                      <td className="px-6 py-3 hidden sm:table-cell text-xs text-slate-500 dark:text-slate-400">{u.created_at ? new Date(u.created_at).toLocaleDateString() : "-"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Audit Tab */}
      {activeTab === "audit" && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              placeholder="Filter by action (e.g. USER_LOGIN_SUCCESS)"
              value={auditFilter}
              onChange={(e) => setAuditFilter(e.target.value)}
              className="input flex-1"
            />
            <div className="flex gap-2">
              <button onClick={loadAuditLogs} className="px-4 py-2 bg-slate-800 dark:bg-slate-600 text-white rounded-md text-sm hover:bg-slate-700 dark:hover:bg-slate-500 transition-colors">
                Search
              </button>
              <ExportButton
                data={auditLogs}
                filename="aifya_audit_log"
                columns={[
                  { key: "created_at", label: "Timestamp" },
                  { key: "action", label: "Action" },
                  { key: "user_name", label: "User" },
                  { key: "entity_type", label: "Entity Type" },
                  { key: "entity_id", label: "Entity ID" },
                  { key: "details", label: "Details" },
                ]}
              />
            </div>
          </div>

          <div className="card overflow-hidden">
            <div className="max-h-[600px] overflow-y-auto">
              {auditLoading ? (
                <div className="p-12 text-center text-slate-400 dark:text-slate-500">Loading audit logs...</div>
              ) : auditLogs.length === 0 ? (
                <div className="p-12 text-center text-slate-400 dark:text-slate-500">
                  <svg className="w-10 h-10 mx-auto mb-3 text-slate-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  No audit logs found
                </div>
              ) : (
                <div className="divide-y divide-slate-100 dark:divide-slate-700">
                  {auditLogs.map((log, i) => (
                    <div key={log.id || i} className="flex gap-4 text-sm p-3 hover:bg-slate-50 dark:hover:bg-slate-800/50 items-start transition-colors">
                      <span className="text-slate-400 dark:text-slate-500 font-mono flex-shrink-0 text-xs w-20">
                        {log.created_at ? new Date(log.created_at).toLocaleTimeString() : "-"}
                      </span>
                      <span className={`font-medium w-44 flex-shrink-0 text-xs px-2 py-0.5 rounded ${
                        log.action?.includes("FAIL") || log.action?.includes("ERROR")
                          ? "bg-red-50 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                          : log.action?.includes("SUCCESS") || log.action?.includes("CREATED")
                          ? "bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                          : "bg-slate-50 text-slate-700 dark:bg-slate-700 dark:text-slate-300"
                      }`}>
                        {log.action}
                      </span>
                      <span className="text-slate-600 dark:text-slate-400 w-32 flex-shrink-0 text-xs">{log.user_name || "SYSTEM"}</span>
                      <span className="text-slate-500 dark:text-slate-400 flex-1 font-mono text-xs truncate">{log.entity_type}:{log.entity_id}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* User status toggle confirmation */}
      <ConfirmDialog
        isOpen={!!confirmToggle}
        title={confirmToggle?.activate ? "Enable User" : "Disable User"}
        message={confirmToggle?.activate
          ? `Re-enable ${confirmToggle?.user?.full_name}'s account? They will be able to log in again.`
          : `Disable ${confirmToggle?.user?.full_name}'s account? They will be logged out and unable to access the platform.`
        }
        confirmLabel={confirmToggle?.activate ? "Enable" : "Disable"}
        cancelLabel="Cancel"
        variant={confirmToggle?.activate ? "info" : "danger"}
        onConfirm={handleToggleUserStatus}
        onCancel={() => setConfirmToggle(null)}
      />
    </div>
  );
}
