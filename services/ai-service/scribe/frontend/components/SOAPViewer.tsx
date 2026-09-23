"use client";

import { useConsultationStore, ClinicalExtraction } from "@/store/useConsultationStore";
import CopyButton from "./CopyButton";

interface SectionHeaderProps {
  title: string;
  count?: number;
}

const SectionHeader = ({ title, count }: SectionHeaderProps) => (
  <div className="flex items-center gap-2 mb-2">
    <h3 className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">{title}</h3>
    {count !== undefined && (
      <span className="bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 text-[10px] px-1.5 py-0.5 rounded-full font-bold">
        {count}
      </span>
    )}
  </div>
);

const ConfidenceBadge = ({ value }: { value: number }) => {
  const color = value > 0.8 ? "text-green-500" : value > 0.5 ? "text-orange-500" : "text-red-500";
  return (
    <div className={`flex items-center gap-1 text-[10px] font-medium ${color}`}>
      <div className={`h-1.5 w-1.5 rounded-full bg-current`} />
      {Math.round(value * 100)}% Match
    </div>
  );
};

export default function SOAPViewer({ extraction }: { extraction: ClinicalExtraction }) {
  const { scrubResult, scrubClaim, transcript } = useConsultationStore();

  const isEmpty = !extraction.chief_complaint && !extraction.reporting_problem && !extraction.symptoms &&
    !extraction.hpi && !extraction.physical_exam &&
    extraction.vitals.length === 0 && extraction.diagnoses.length === 0 &&
    extraction.medications.length === 0 && extraction.lab_orders.length === 0 &&
    (extraction.suggested_tests?.length || 0) === 0;

  return (
    <div className="space-y-6 animate-fade-in print:text-black">
      {isEmpty && (
        <div className="bg-slate-50 dark:bg-slate-800/50 border border-dashed border-slate-200 dark:border-slate-700 rounded-lg p-8 text-center italic text-slate-500 dark:text-slate-400">
          No clinical entities were identified in this transcript.
        </div>
      )}

      {/* 1. Core Issue & Symptoms */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {extraction.reporting_problem && (
          <div className="md:col-span-1">
            <SectionHeader title="Reporting Problem" />
            <div className="bg-medical-blue/5 dark:bg-medical-blue/10 p-3 rounded-lg border border-medical-blue/20">
              <p className="text-sm font-medium text-slate-800 dark:text-slate-200">{extraction.reporting_problem}</p>
            </div>
          </div>
        )}
        {extraction.symptoms && (
          <div className="md:col-span-1">
            <SectionHeader title="Extracted Symptoms" />
            <div className="bg-slate-50 dark:bg-slate-800/50 p-3 rounded-lg border border-slate-200 dark:border-slate-700">
              <p className="text-sm text-slate-700 dark:text-slate-300">{extraction.symptoms}</p>
            </div>
          </div>
        )}
      </div>

      {/* 2. Vitals & HPI */}
      {extraction.vitals.length > 0 && (
        <div>
          <SectionHeader title="Vitals" count={extraction.vitals.length} />
          <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2 text-xs">
            {extraction.vitals.map((v, i) => (
              <div key={i} className="bg-slate-50 dark:bg-slate-800/50 p-2 rounded border border-slate-100 dark:border-slate-700">
                <span className="text-slate-500 block mb-0.5">{v.name}</span>
                <span className="font-mono font-bold text-slate-800 dark:text-slate-200">{v.value}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {extraction.hpi && (
        <div>
          <SectionHeader title="History of Present Illness (HPI)" />
          <p className="text-slate-700 dark:text-slate-300 text-sm leading-relaxed whitespace-pre-wrap rounded-lg bg-slate-50/50 dark:bg-slate-800/30 p-3">
            {extraction.hpi}
          </p>
        </div>
      )}

      {/* 3. Diagnoses */}
      {extraction.diagnoses.length > 0 && (
        <div>
          <SectionHeader title="Clinical Assessment / Diagnoses" count={extraction.diagnoses.length} />
          <div className="space-y-2 text-sm">
            {extraction.diagnoses.map((dx, i) => (
              <div key={i} className="flex items-center justify-between p-2.5 rounded border bg-slate-50 dark:bg-slate-800/50 border-slate-100 dark:border-slate-700">
                <div className="flex flex-col">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-800 dark:text-slate-200">{dx.name}</span>
                    {dx.is_primary && <span className="text-[10px] bg-medical-blue text-white px-1.5 py-0.5 rounded font-bold">PRIMARY</span>}
                  </div>
                  {dx.icd11_validated && (
                    <span className="text-[10px] font-mono text-green-600 dark:text-green-400 mt-0.5">ICD-11: {dx.icd11_validated}</span>
                  )}
                </div>
                <ConfidenceBadge value={dx.confidence} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. Medications & Tests */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
        {/* Medications */}
        <div className="md:col-span-7">
          <SectionHeader title="Prescribed Medications" count={extraction.medications.length} />
          {extraction.medications.length > 0 ? (
            <div className="space-y-2">
              {extraction.medications.map((m, i) => (
                <div key={i} className="p-3 bg-green-50/50 dark:bg-green-900/10 border border-green-100 dark:border-green-900/30 rounded-lg text-sm">
                  <div className="flex justify-between font-medium text-slate-800 dark:text-slate-200">
                    <span className="flex items-center gap-2">
                      {m.name}
                      {m.is_new && <span className="text-[10px] text-green-600 font-bold uppercase">New</span>}
                    </span>
                    <span className="text-xs text-slate-500">{m.route}</span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 mt-2 text-[11px] text-slate-500 dark:text-slate-400 font-medium">
                    <span>{m.dose}</span>
                    <span>{m.frequency}</span>
                    <span>{m.duration}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-4 border border-dashed border-slate-200 dark:border-slate-800 rounded-lg text-center text-xs text-slate-400 italic">
              No medications prescribed in this session.
            </div>
          )}
        </div>

        {/* Tests & Suggestions */}
        <div className="md:col-span-5">
          <SectionHeader title="Tests (Ordered / Suggested)" />
          <div className="space-y-3">
            {/* Lab Orders */}
            {extraction.lab_orders.map((lab, i) => (
              <div key={i} className="p-2.5 border border-blue-100 dark:border-blue-900/30 rounded-lg bg-blue-50/30 dark:bg-blue-900/10 text-xs flex justify-between items-center group">
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-1.5 rounded-full bg-medical-blue" />
                  <span className="font-medium text-slate-700 dark:text-slate-300">{lab.test_name}</span>
                </div>
                <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${lab.urgency === "stat" ? "bg-red-100 text-red-700" : "bg-blue-100 text-blue-700"
                  }`}>
                  {lab.urgency.toUpperCase()}
                </span>
              </div>
            ))}

            {/* Proactive Suggestions */}
            {extraction.suggested_tests && extraction.suggested_tests.length > 0 && (
              <div className="space-y-2 mt-4">
                <h4 className="text-[10px] font-bold text-orange-500 uppercase flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path d="M13 10V3L4 14h7v7l9-11h-7z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" /></svg>
                  Proactive Clinical Advice
                </h4>
                {extraction.suggested_tests.map((s, i) => (
                  <div key={i} className="p-2.5 border border-orange-100 dark:border-orange-900/20 rounded-lg bg-orange-50/50 dark:bg-orange-900/5 text-xs italic text-orange-800 dark:text-orange-300 relative pl-7">
                    <span className="absolute left-2.5 top-3 text-orange-400">💡</span>
                    {s}
                  </div>
                ))}
              </div>
            )}

            {extraction.lab_orders.length === 0 && (!extraction.suggested_tests || extraction.suggested_tests.length === 0) && (
              <div className="p-4 border border-dashed border-slate-200 dark:border-slate-800 rounded-lg text-center text-xs text-slate-400 italic">
                No investigations required.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 5. Follow-up & Disposition */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 border-t dark:border-slate-800 pt-6">
        {extraction.follow_up && (
          <div>
            <SectionHeader title="Follow-up Instructions" />
            <div className="p-3 bg-purple-50 dark:bg-purple-900/10 border border-purple-100 dark:border-purple-900/30 rounded-lg text-sm text-slate-700 dark:text-slate-300 font-medium leading-relaxed">
              {extraction.follow_up}
            </div>
          </div>
        )}
        {extraction.disposition && (
          <div>
            <SectionHeader title="Encounter Disposition" />
            <div className="p-3 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg text-sm text-slate-700 dark:text-slate-300">
              {extraction.disposition}
            </div>
          </div>
        )}
      </div>

      {/* Action Sections (Conditional) */}
      {scrubResult && (
        <div className={`rounded-xl p-5 border-2 shadow-sm ${scrubResult.status === "passed"
            ? "bg-green-50/50 dark:bg-green-900/10 border-green-200 dark:border-green-800"
            : scrubResult.status === "blocked"
              ? "bg-red-50/50 dark:bg-red-900/10 border-red-200 dark:border-red-800"
              : "bg-orange-50/50 dark:bg-orange-900/10 border-orange-200 dark:border-orange-800"
          }`}>
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-bold text-xs uppercase tracking-tight text-slate-800 dark:text-slate-200">SHA Revenue Guard Analysis</h3>
            <span className={`px-2 py-1 rounded-full text-[10px] font-black ${scrubResult.status === "passed"
                ? "bg-green-500 text-white"
                : scrubResult.status === "blocked"
                  ? "bg-red-500 text-white"
                  : "bg-orange-500 text-white"
              }`}>
              {scrubResult.status.toUpperCase()}
            </span>
          </div>
          {scrubResult.violations.length > 0 && (
            <div className="space-y-3">
              {scrubResult.violations.map((v: any, i: number) => (
                <div key={i} className="flex gap-3 text-sm">
                  <div className={`mt-1 h-5 w-5 flex-shrink-0 rounded flex items-center justify-center text-[10px] font-bold ${v.severity === "BLOCK" ? "bg-red-100 text-red-600" : "bg-orange-100 text-orange-600"
                    }`}>
                    !
                  </div>
                  <div>
                    <p className="font-bold text-slate-800 dark:text-slate-200 leading-tight">{v.rule_id}: {v.message}</p>
                    {v.suggested_fix && <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 italic">Resolution: {v.suggested_fix}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Final Layout / Footer */}
      <div className="flex flex-col gap-5 pt-6 border-t dark:border-slate-800 print:hidden">
        {transcript && (
          <details className="group">
            <summary className="text-[11px] font-bold text-slate-400 cursor-pointer list-none flex items-center gap-1.5 hover:text-slate-600 transition-colors uppercase tracking-widest">
              <svg className="w-3 h-3 transform group-open:rotate-180 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path d="M19 9l-7 7-7-7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" /></svg>
              View Encounter Transcript
            </summary>
            <div className="mt-3 bg-slate-900 p-4 rounded-xl border border-slate-800 shadow-inner">
              <p className="text-[11px] font-mono text-slate-400 whitespace-pre-wrap leading-relaxed">{transcript}</p>
            </div>
          </details>
        )}

        <div className="flex gap-3">
          <button
            onClick={() => window.print()}
            className="flex-1 btn-secondary flex items-center justify-center gap-2 py-2.5 rounded-lg border-2 hover:bg-slate-50 transition-all font-bold text-sm"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" />
            </svg>
            Print SOAP Note
          </button>

          {extraction.diagnoses.length > 0 && !scrubResult && (
            <button
              onClick={scrubClaim}
              className="flex-[2] py-2.5 bg-medical-blue text-white font-bold rounded-lg hover:shadow-lg hover:shadow-medical-blue/20 transform active:scale-[0.98] transition-all text-sm"
            >
              Run SHA Claims Scrub
            </button>
          )}

          {extraction.diagnoses.some(d => d.icd11_validated) && (
            <CopyButton
              text={extraction.diagnoses.filter(d => d.icd11_validated).map(d => d.icd11_validated).join(", ")}
              label="Copy Codes"
              size="md"
            />
          )}
        </div>
      </div>
    </div>
  );
}
