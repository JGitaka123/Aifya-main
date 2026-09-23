"use client";

interface SessionTimeoutModalProps {
  remainingSeconds: number;
  onExtend: () => void;
  onDismiss: () => void;
  onLogout: () => void;
}

export default function SessionTimeoutModal({
  remainingSeconds,
  onExtend,
  onDismiss,
  onLogout,
}: SessionTimeoutModalProps) {
  const minutes = Math.floor(remainingSeconds / 60);
  const seconds = remainingSeconds % 60;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[100] p-4" role="alertdialog" aria-modal="true" aria-label="Session expiring">
      <div className="bg-white rounded-xl shadow-2xl max-w-sm w-full overflow-hidden">
        <div className="bg-orange-500 p-4 text-white text-center">
          <div className="text-3xl mb-1">&#9201;</div>
          <h2 className="text-lg font-semibold">Session Expiring</h2>
        </div>

        <div className="p-6 text-center">
          <p className="text-slate-600 mb-3">
            Your session will expire in
          </p>
          <div className="text-4xl font-mono font-bold text-orange-600 mb-4">
            {String(minutes).padStart(2, "0")}:{String(seconds).padStart(2, "0")}
          </div>
          <p className="text-sm text-slate-500">
            Any unsaved work may be lost. Extend your session or save your progress.
          </p>
        </div>

        <div className="p-4 border-t flex gap-3">
          <button
            onClick={onLogout}
            className="px-4 py-2 border border-slate-300 text-slate-600 rounded-md text-sm hover:bg-slate-50 transition-colors"
          >
            Sign Out
          </button>
          <button
            onClick={onDismiss}
            className="px-4 py-2 border border-slate-300 text-slate-600 rounded-md text-sm hover:bg-slate-50 transition-colors"
          >
            Dismiss
          </button>
          <button
            onClick={onExtend}
            className="flex-1 px-4 py-2 bg-medical-blue text-white rounded-md text-sm font-medium hover:bg-medical-blue/90 transition-colors"
            autoFocus
          >
            Extend Session
          </button>
        </div>
      </div>
    </div>
  );
}
