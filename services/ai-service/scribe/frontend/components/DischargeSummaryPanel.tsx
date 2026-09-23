"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useToast } from "@/components/Toast";
import { format } from "date-fns";

export default function DischargeSummaryPanel() {
  const [admissionId, setAdmissionId] = useState("");
  const [patientId, setPatientId] = useState("");
  const [summary, setSummary] = useState<any>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const { toast } = useToast();

  const handleGenerate = async () => {
    if (!admissionId || !patientId) return;
    setIsGenerating(true);
    try {
      const result = await api.discharge.generate(admissionId, patientId);
      setSummary(result);
      toast("Discharge summary generated successfully", "success");
    } catch (err: any) {
      toast(err.message || "Failed to generate discharge summary", "error");
    } finally {
      setIsGenerating(false);
    }
  };

  const handleStatusUpdate = async (newStatus: string) => {
    if (!summary?.id && !summary?.admission_id) return;
    const id = summary.id || summary.admission_id;
    try {
      await api.discharge.updateStatus(id, newStatus);
      setSummary({ ...summary, status: newStatus });
      toast(`Discharge summary ${newStatus}`, "success");
    } catch (err: any) {
      toast(err.message || "Status update failed", "error");
    }
  };

  const handlePrint = () => {
    window.print();
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return "-";
    try {
      return format(new Date(dateStr), "dd/MM/yyyy");
    } catch {
      return dateStr;
    }
  };

  return (
    <div className={`card overflow-hidden transition-all duration-500 ${summary ? 'ring-2 ring-slate-200 shadow-2xl' : ''}`}>
      {/* Header Controls (Hidden on Print) */}
      <div className="bg-slate-50 dark:bg-slate-800/50 p-4 border-b border-slate-200 dark:border-slate-700 flex justify-between items-center print:hidden">
        <h3 className="font-semibold text-slate-800 dark:text-slate-200">Discharge Summary Generator</h3>
        {summary && (
          <button
            onClick={() => setSummary(null)}
            className="text-xs text-slate-400 hover:text-red-500 flex items-center gap-1"
          >
            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path d="M6 18L18 6M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" /></svg>
            Reset
          </button>
        )}
      </div>

      {!summary ? (
        <div className="p-6 space-y-4 print:hidden">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-400 uppercase ml-1">Admission ID</label>
              <input
                type="text"
                placeholder="e.g. ADM-1001"
                value={admissionId}
                onChange={(e) => setAdmissionId(e.target.value)}
                className="w-full px-3 py-2 border rounded-md text-sm focus:ring-2 focus:ring-medical-blue"
              />
            </div>
            <div className="space-y-1">
              <label className="text-[10px] font-bold text-slate-400 uppercase ml-1">Patient ID / SHA</label>
              <input
                type="text"
                placeholder="e.g. SHA-1001"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                className="w-full px-3 py-2 border rounded-md text-sm focus:ring-2 focus:ring-medical-blue"
              />
            </div>
          </div>
          <button
            onClick={handleGenerate}
            disabled={isGenerating || !admissionId || !patientId}
            className="w-full py-3 bg-medical-blue text-white rounded-md text-sm font-bold shadow-sm hover:shadow-md active:scale-[0.98] transition-all disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {isGenerating ? (
              <>
                <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                Synthesizing Inpatient Record...
              </>
            ) : (
              "Generate AI Discharge Summary"
            )}
          </button>
          <p className="text-[10px] text-center text-slate-400 italic">
            AI will synthesize history, labs, and medications from the EMR.
          </p>
        </div>
      ) : (
        <div className="bg-white text-black p-4 sm:p-12 font-serif animate-fade-in relative min-h-screen">
          {/* Paper Form Look */}
          <div className="max-w-[800px] mx-auto space-y-4">
            {/* Header */}
            <div className="text-center space-y-0.5 border-b border-black pb-4 mb-6">
              <h1 className="text-xl font-bold uppercase tracking-tight">Mary Help of the Sick Mission Hospital</h1>
              <p className="italic underline text-sm font-bold">MOTTO: YOUR HEALTH, OUR CONCERN</p>
              <p className="text-[10px]">P.O. BOX 792 - 01000, THIKA - KENYA</p>
              <p className="text-[10px]">TELEPHONE: 020 800 8257/ MOBILE 0724 936 177/ EMAIL: info@maryhelphospital.org</p>
            </div>

            {/* Title Row */}
            <div className="flex justify-between items-baseline mb-6">
              <h2 className="text-sm font-bold underline uppercase">Discharge Summary and Clinical Abstract Sheet</h2>
              <div className="flex items-baseline gap-2">
                <span className="text-[11px] font-bold">IP NO</span>
                <span className="min-w-[120px] border-b border-black text-xs px-1">{summary.ip_no || summary.id}</span>
              </div>
            </div>

            {/* Demographic Grid */}
            <div className="space-y-3">
              <div className="flex gap-4">
                <div className="flex-[2] flex items-baseline gap-2">
                  <span className="text-[11px] whitespace-nowrap">SURNAME:</span>
                  <span className="flex-1 border-b border-dotted border-slate-400 text-xs py-0.5 uppercase font-bold min-h-[20px]">
                    {summary.patient_name?.split(" ").pop() || ""}
                  </span>
                </div>
                <div className="flex-[3] flex items-baseline gap-2">
                  <span className="text-[11px] whitespace-nowrap">OTHER NAMES:</span>
                  <span className="flex-1 border-b border-dotted border-slate-400 text-xs py-0.5 uppercase min-h-[20px]">
                    {summary.patient_name?.split(" ").slice(0, -1).join(" ") || summary.patient_name}
                  </span>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="flex-1 flex items-baseline gap-2">
                  <span className="text-[11px] whitespace-nowrap">AGE:</span>
                  <span className="flex-1 border-b border-dotted border-slate-400 text-xs py-0.5 min-h-[20px]">{summary.age}</span>
                </div>
                <div className="flex-1 flex items-baseline gap-2">
                  <span className="text-[11px] whitespace-nowrap">SEX:</span>
                  <span className="flex-1 border-b border-dotted border-slate-400 text-xs py-0.5 min-h-[20px]">{summary.sex}</span>
                </div>
                <div className="flex-[2] flex items-baseline gap-2">
                  <span className="text-[11px] whitespace-nowrap">WARD:</span>
                  <span className="flex-1 border-b border-dotted border-slate-400 text-xs py-0.5 min-h-[20px]">{summary.ward}</span>
                </div>
              </div>

              <div className="flex gap-4">
                <div className="flex-1 flex items-baseline gap-2">
                  <span className="text-[11px] whitespace-nowrap">D.O.A:</span>
                  <span className="flex-1 border-b border-dotted border-slate-400 text-xs py-0.5 min-h-[20px]">{formatDate(summary.admission_date)}</span>
                </div>
                <div className="flex-1 flex items-baseline gap-2">
                  <span className="text-[11px] whitespace-nowrap">D.O.D:</span>
                  <span className="flex-1 border-b border-dotted border-slate-400 text-xs py-0.5 min-h-[20px]">{formatDate(summary.discharge_date)}</span>
                </div>
              </div>
            </div>

            {/* Clinical Fields */}
            <div className="space-y-2 mt-6">
              {[
                { label: "ATTENDING DOCTORS", value: summary.attending_doctors },
                { label: "FINAL DIAGNOSIS", value: summary.final_diagnosis, bold: true },
                { label: "OTHER ILLNESS", value: summary.other_illness },
                { label: "COMPLICATIONS", value: summary.complications },
              ].map((field, idx) => (
                <div key={idx} className="flex items-baseline gap-2">
                  <span className="text-[11px] font-bold whitespace-nowrap">{field.label}:</span>
                  <span className={`flex-1 border-b border-dotted border-slate-400 text-xs py-0.5 min-h-[20px] ${field.bold ? 'font-bold' : ''}`}>
                    {field.value || "None recorded"}
                  </span>
                </div>
              ))}

              <div className="space-y-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-[11px] font-bold whitespace-nowrap">OPERATIONS 1.</span>
                  <span className="flex-1 border-b border-dotted border-slate-400 text-xs py-0.5 min-h-[20px]">
                    {summary.procedures?.[0]?.name || ""}
                  </span>
                </div>
                <div className="flex items-baseline gap-2">
                  <span className="text-[11px] font-bold whitespace-nowrap opacity-0">OPERATIONS</span>
                  <span className="text-[11px] font-bold mr-2">2.</span>
                  <span className="flex-1 border-b border-dotted border-slate-400 text-xs py-0.5 min-h-[20px]">
                    {summary.procedures?.[1]?.name || ""}
                  </span>
                </div>
              </div>
            </div>

            {/* Big Sections with Lines */}
            {[
              { label: "CLINICAL SUMMARY", value: `${summary.history_of_present_illness}\n${summary.hospital_course}` },
              { label: "LAB INVESTIGATIONS", value: summary.key_investigations?.map((i: any) => `- ${i.name || i.test_name}: ${i.value || i.result}`).join("\n") },
              { label: "DISCHARGE PRESCRIPTION", value: summary.discharge_medications?.map((m: any) => `- ${m.name} ${m.dose} ${m.frequency} x ${m.duration}`).join("\n") },
              { label: "FURTHER INSTRUCTIONS / RECOMMENDATIONS", value: `${summary.condition_at_discharge}\nPLAN: ${summary.follow_up_plan}\nRED FLAGS: ${summary.red_flags}` },
            ].map((section, idx) => (
              <div key={idx} className="mt-6">
                <h3 className="text-[11px] font-bold underline mb-1">{section.label}</h3>
                <div
                  className="w-full min-h-[100px] text-xs leading-[1.8] whitespace-pre-wrap p-1 font-sans"
                  style={{
                    backgroundImage: 'linear-gradient(rgba(0,0,0,0.1) 1px, transparent 1px)',
                    backgroundSize: '100% 1.8em'
                  }}
                >
                  {section.value}
                </div>
              </div>
            ))}

            {/* Signature Block */}
            <div className="mt-12 grid grid-cols-3 gap-8">
              <div className="text-center space-y-8">
                <div className="border-t border-black pt-1 text-[10px] font-bold">DOCTOR'S NAME</div>
                <div className="text-xs uppercase font-bold">{summary.doctor_name || "Dr. Scribe Aifya"}</div>
              </div>
              <div className="text-center space-y-8">
                <div className="border-t border-black pt-1 text-[10px] font-bold">DOCTOR'S SIGNATURE</div>
              </div>
              <div className="text-center space-y-8">
                <div className="border-t border-black pt-1 text-[10px] font-bold">DATE</div>
                <div className="text-xs">{new Date().toLocaleDateString('en-GB')}</div>
              </div>
            </div>

            <div className="flex items-baseline gap-2 mt-4 pb-20">
              <span className="text-[11px] font-bold">QUALIFICATION:</span>
              <span className="flex-1 border-b border-dotted border-slate-400 text-xs px-2 min-h-[20px]">{summary.doctor_qualification}</span>
            </div>
          </div>

          {/* Floating Action Bar (Hidden on Print) */}
          <div className="fixed bottom-6 left-1/2 -translate-x-1/2 flex gap-3 print:hidden z-50">
            <button
              onClick={() => handleStatusUpdate("reviewed")}
              className="px-6 py-2.5 bg-blue-600 text-white rounded-full text-xs font-bold shadow-xl hover:bg-blue-700 transition-all flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" /></svg>
              Finalize & Approve
            </button>
            <button
              onClick={handlePrint}
              className="px-6 py-2.5 bg-slate-900 text-white rounded-full text-xs font-bold shadow-xl hover:bg-black transition-all flex items-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path d="M17 17h2a2 2 0 002-2v-4a2 2 0 00-2-2H5a2 2 0 00-2 2v4a2 2 0 002 2h2m2 4h6a2 2 0 002-2v-4a2 2 0 00-2-2H9a2 2 0 00-2 2v4a2 2 0 002 2zm8-12V5a2 2 0 00-2-2H9a2 2 0 00-2 2v4h10z" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" /></svg>
              Print Report
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
