"use client";

import { useState, useEffect } from "react";
import { getQueueCount, syncPendingActions } from "@/lib/offlineQueue";
import { useToast } from "@/components/Toast";

export default function OfflineIndicator() {
  const [isOnline, setIsOnline] = useState(true);
  const [queueCount, setQueueCount] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    const updateOnline = () => setIsOnline(navigator.onLine);
    window.addEventListener("online", updateOnline);
    window.addEventListener("offline", updateOnline);
    setIsOnline(navigator.onLine);

    const interval = setInterval(async () => {
      try {
        const count = await getQueueCount();
        setQueueCount(count);
      } catch {}
    }, 5000);

    return () => {
      window.removeEventListener("online", updateOnline);
      window.removeEventListener("offline", updateOnline);
      clearInterval(interval);
    };
  }, []);

  // Auto-sync when back online
  useEffect(() => {
    if (isOnline && queueCount > 0 && !isSyncing) {
      handleSync();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOnline, queueCount]);

  const handleSync = async () => {
    setIsSyncing(true);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
      const token = localStorage.getItem("aifya_access_token");
      const result = await syncPendingActions(apiBase, () => token ? { Authorization: `Bearer ${token}` } : {});
      if (result.synced > 0) toast(`Synced ${result.synced} queued action(s)`, "success");
      if (result.failed > 0) toast(`${result.failed} action(s) failed to sync`, "warning");
      const count = await getQueueCount();
      setQueueCount(count);
    } catch {
      toast("Sync failed", "error");
    } finally {
      setIsSyncing(false);
    }
  };

  if (isOnline && queueCount === 0) return null;

  return (
    <div className={`fixed bottom-4 left-4 z-50 px-4 py-2.5 rounded-lg shadow-lg text-sm flex items-center gap-3 ${
      isOnline ? "bg-orange-500 text-white" : "bg-red-600 text-white"
    }`}>
      {!isOnline ? (
        <>
          <div className="h-2.5 w-2.5 bg-white rounded-full animate-pulse" />
          <span>Offline Mode - Actions will be queued</span>
        </>
      ) : (
        <>
          <span>{queueCount} queued action(s)</span>
          <button
            onClick={handleSync}
            disabled={isSyncing}
            className="px-2 py-1 bg-white/20 rounded text-xs hover:bg-white/30 disabled:opacity-50"
          >
            {isSyncing ? "Syncing..." : "Sync Now"}
          </button>
        </>
      )}
    </div>
  );
}
