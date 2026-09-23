"use client";

import { useAuth } from "@/contexts/AuthContext";
import { useConsultationStore } from "@/store/useConsultationStore";
import ScribePanel from "@/components/ScribePanel";
import SOAPViewer from "@/components/SOAPViewer";
import DischargeSummaryPanel from "@/components/DischargeSummaryPanel";
import { useToast } from "@/components/Toast";
import { useKeyboardShortcuts } from "@/hooks/useKeyboardShortcuts";

export default function ClinicianPage() {
  const { user } = useAuth();
  const store = useConsultationStore();
  const { toast } = useToast();

  const handleSyncToEMR = async () => {
    if (!store.extraction) return;
    try {
      await store.finalizeAndSync("enc_" + Date.now());
      toast("Clinical note synced to Q-Afya EMR", "success");
    } catch {
      toast("Sync failed. Note saved locally.", "error");
    }
  };

  // Clinician keyboard shortcuts
  useKeyboardShortcuts([
    {
      key: "ctrl+e",
      description: "Extract structured note",
      handler: () => {
        if (store.transcript && !store.isExtracting) store.extractNote();
      },
      enabled: !!store.transcript || !!store.audioBlobUrl,
    },
    {
      key: "ctrl+shift+s",
      description: "Sync to EMR",
      handler: handleSyncToEMR,
      enabled: !!store.extraction && store.encounterStatus !== "syncing" && store.encounterStatus !== "finalized",
    },
    {
      key: "ctrl+b",
      description: "Run SHA scrub",
      handler: () => {
        if (store.extraction && !store.scrubResult) store.scrubClaim();
      },
      enabled: !!store.extraction && !store.scrubResult,
    },
  ]);

  return (
    <div className="flex flex-col gap-6 print:block">
      {/* Page Header (Hidden in Print) */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-3 border-b dark:border-slate-700 pb-4 print:hidden">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Clinician Console</h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1">Ambient Scribe & AI Consultation Engine</p>
        </div>
        <div className="text-sm text-slate-500 dark:text-slate-400 text-right">
          <p>
            Current facility: <strong className="text-slate-700 dark:text-slate-200">Mary Help Hospital</strong>
          </p>
          <p>
            Signed in as: <strong className="text-slate-700 dark:text-slate-200">{user?.full_name || "Not signed in"}</strong>
          </p>
          <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
            Press <kbd className="px-1 py-0.5 bg-slate-100 dark:bg-slate-700 border dark:border-slate-600 rounded text-xs font-mono">Ctrl+/</kbd> for shortcuts
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start print:block">
        {/* Left Column: Scribe (Hidden) + Discharge (Page 1) */}
        <div className="lg:col-span-5 flex flex-col gap-6 print:block">
          <div className="print:hidden">
            <ScribePanel />
          </div>

          {/* Discharge Summary will be Page 1 */}
          <div className="print:block print:w-full">
            <DischargeSummaryPanel />
          </div>

          {/* Page Break for Print */}
          <div className="hidden print:block print:break-after-page h-0"></div>
        </div>

        {/* Right Column: SOAP Note (Page 2) */}
        <div className="lg:col-span-7 card p-4 md:p-6 min-h-[600px] print:block print:w-full print:mt-8 print:shadow-none print:border-none print:min-h-0">
          <div className="flex justify-between items-center mb-6 print:mb-4">
            <h2 className="text-xl font-bold text-slate-800 dark:text-white uppercase tracking-tight">Clinical Extraction Note</h2>
            <div className="flex gap-2 print:hidden">
              {store.extraction && (
                <button
                  onClick={handleSyncToEMR}
                  disabled={store.encounterStatus === "syncing" || store.encounterStatus === "finalized"}
                  className="btn-primary text-xs"
                  title="Ctrl+Shift+S"
                >
                  {store.encounterStatus === "syncing"
                    ? "Syncing..."
                    : store.encounterStatus === "finalized"
                      ? "Synced ✓"
                      : "Sync to EMR"}
                </button>
              )}
            </div>
          </div>

          {store.extractionError && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-900/30 rounded-lg p-4 mb-4">
              <p className="text-red-700 dark:text-red-400 text-sm">{store.extractionError}</p>
            </div>
          )}

          {store.syncError && (
            <div className="bg-orange-50 dark:bg-orange-900/20 border border-orange-200 dark:border-orange-900/30 rounded-lg p-4 mb-4">
              <p className="text-orange-700 dark:text-orange-400 text-sm">{store.syncError}</p>
            </div>
          )}

          {store.encounterStatus === "finalized" && (
            <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-900/30 rounded-lg p-4 mb-4 flex items-center gap-2">
              <span className="text-green-600 dark:text-green-400 text-lg">&#10003;</span>
              <p className="text-green-700 dark:text-green-400 text-sm font-medium">Note finalized and synced to Q-Afya EMR.</p>
            </div>
          )}

          {store.extraction ? (
            <SOAPViewer extraction={store.extraction} />
          ) : (
            <div className="flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 h-[400px] border-2 border-dashed border-slate-200 dark:border-slate-700 rounded-lg">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-12 w-12 mb-4 text-slate-300 dark:text-slate-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <p className="font-medium">Waiting for consultation recording...</p>
              <p className="text-sm mt-2 text-center max-w-xs">
                The AI structured note will appear here when the extraction engine completes.
              </p>
              <div className="flex gap-4 mt-4 text-xs text-slate-400 dark:text-slate-500">
                <span><kbd className="px-1 py-0.5 bg-slate-100 dark:bg-slate-700 rounded font-mono">Ctrl+E</kbd> Extract</span>
                <span><kbd className="px-1 py-0.5 bg-slate-100 dark:bg-slate-700 rounded font-mono">Ctrl+B</kbd> Scrub</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
