"use client";

import { formatShortcutKey } from "@/hooks/useKeyboardShortcuts";

interface ShortcutInfo {
  key: string;
  description: string;
  category?: string;
}

const GLOBAL_SHORTCUTS: ShortcutInfo[] = [
  { key: "ctrl+/", description: "Show keyboard shortcuts", category: "Global" },
  { key: "ctrl+k", description: "Open command palette", category: "Global" },
  { key: "ctrl+h", description: "Go to Home", category: "Navigation" },
  { key: "escape", description: "Close dialogs", category: "Global" },
  { key: "ctrl+p", description: "Print current page", category: "Global" },
];

const CLINICIAN_SHORTCUTS: ShortcutInfo[] = [
  { key: "ctrl+r", description: "Start/stop recording", category: "Clinician" },
  { key: "ctrl+e", description: "Extract structured note", category: "Clinician" },
  { key: "ctrl+shift+s", description: "Sync to EMR", category: "Clinician" },
  { key: "ctrl+b", description: "Run SHA scrub", category: "Clinician" },
];

interface KeyboardShortcutsHelpProps {
  isOpen: boolean;
  onClose: () => void;
  page?: "clinician" | "billing" | "admin" | "analytics";
}

export default function KeyboardShortcutsHelp({ isOpen, onClose, page }: KeyboardShortcutsHelpProps) {
  if (!isOpen) return null;

  const shortcuts = [
    ...GLOBAL_SHORTCUTS,
    ...(page === "clinician" ? CLINICIAN_SHORTCUTS : []),
  ];

  const categories = Array.from(new Set(shortcuts.map((s) => s.category || "Other")));

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[90] p-4" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts">
      <div className="bg-white rounded-xl shadow-2xl max-w-md w-full max-h-[80vh] overflow-y-auto">
        <div className="p-5 border-b flex justify-between items-center">
          <h2 className="text-lg font-semibold text-slate-800">Keyboard Shortcuts</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 text-xl" aria-label="Close">&times;</button>
        </div>

        <div className="p-5 space-y-5">
          {categories.map((cat) => (
            <div key={cat}>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">{cat}</h3>
              <div className="space-y-2">
                {shortcuts
                  .filter((s) => (s.category || "Other") === cat)
                  .map((s) => (
                    <div key={s.key} className="flex items-center justify-between">
                      <span className="text-sm text-slate-600">{s.description}</span>
                      <kbd className="px-2 py-1 bg-slate-100 border border-slate-200 rounded text-xs font-mono text-slate-700">
                        {formatShortcutKey(s.key)}
                      </kbd>
                    </div>
                  ))}
              </div>
            </div>
          ))}
        </div>

        <div className="p-4 border-t bg-slate-50 text-center">
          <p className="text-xs text-slate-400">
            Press <kbd className="px-1.5 py-0.5 bg-white border rounded text-xs font-mono">Ctrl+/</kbd> anytime to toggle this help
          </p>
        </div>
      </div>
    </div>
  );
}
