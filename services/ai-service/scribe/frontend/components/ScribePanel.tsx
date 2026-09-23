"use client";

import { useState, useRef, useEffect } from "react";
import { useConsultationStore } from "@/store/useConsultationStore";
import { useDebounce } from "@/hooks/useDebounce";

export default function ScribePanel() {
  const store = useConsultationStore();
  const [patientId, setPatientId] = useState("");
  const [manualTranscript, setManualTranscript] = useState("");
  const [showManualEntry, setShowManualEntry] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const [timer, setTimer] = useState(0);

  // Debounced auto-lookup: triggers lookup after 600ms of no typing (min 5 chars)
  const debouncedPatientId = useDebounce(patientId.trim(), 600);

  useEffect(() => {
    if (debouncedPatientId.length >= 5 && !store.patient) {
      store.lookupPatient(debouncedPatientId);
    }
  }, [debouncedPatientId, store.patient]);

  const handlePatientLookup = (e: React.FormEvent) => {
    e.preventDefault();
    if (patientId.trim()) store.lookupPatient(patientId.trim());
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };

      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        const objectUrl = URL.createObjectURL(audioBlob);
        store.stopRecording(objectUrl);
        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorderRef.current.start();
      store.startRecording();
      setTimer(0);
      timerRef.current = setInterval(() => setTimer((t) => t + 1), 1000);
    } catch {
      alert("Microphone permission required for ambient scribe.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
    }
    if (timerRef.current) clearInterval(timerRef.current);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60).toString().padStart(2, "0");
    const secs = (seconds % 60).toString().padStart(2, "0");
    return `${mins}:${secs}`;
  };

  const handleManualExtract = () => {
    if (manualTranscript.trim().length < 10) return;
    store.setTranscript(manualTranscript.trim());
    store.extractNote();
  };

  return (
    <div className="card overflow-hidden">
      {/* Step 1: Patient Context */}
      <div className="bg-slate-50 p-4 border-b border-slate-200">
        <h3 className="font-semibold text-slate-800 dark:text-slate-200">1. Patient Context</h3>
      </div>
      <div className="p-4 border-b border-slate-200">
        {!store.patient ? (
          <div>
            <form onSubmit={handlePatientLookup} className="flex gap-2">
              <input
                type="text"
                placeholder="National ID or SHA Member No"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                className="flex-1 px-3 py-2 border rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-medical-blue focus:border-transparent"
                disabled={store.patientLoading}
                aria-label="Patient identifier"
              />
              <button
                type="submit"
                className="px-4 py-2 bg-slate-800 text-white rounded-md text-sm font-medium hover:bg-slate-700 transition-colors disabled:opacity-50"
                disabled={store.patientLoading || !patientId.trim()}
              >
                {store.patientLoading ? "Looking up..." : "Lookup"}
              </button>
            </form>
            {store.patientError && (
              <p className="text-red-500 text-sm mt-2">{store.patientError}</p>
            )}
          </div>
        ) : (
          <div className="flex justify-between items-center">
            <div>
              <p className="font-medium text-medical-blue">{store.patient.full_name}</p>
              <div className="flex items-center gap-3 mt-1 text-sm text-slate-500">
                <span className="flex items-center gap-1">
                  SHA: <strong className="text-slate-700 font-mono">{store.patient.insurance_no}</strong>
                </span>
                <span
                  className={`px-2 py-0.5 rounded text-xs font-medium ${
                    store.patient.insurance_status === "ACTIVE"
                      ? "bg-green-100 text-green-700"
                      : "bg-red-100 text-red-700"
                  }`}
                >
                  {store.patient.insurance_status}
                </span>
              </div>
            </div>
            <button
              onClick={() => store.reset()}
              className="text-sm text-slate-400 hover:text-red-500"
              aria-label="Clear patient"
            >
              Clear
            </button>
          </div>
        )}
      </div>

      {/* Step 2: Ambient Recording */}
      <div className="bg-slate-50 p-4 border-b border-slate-200">
        <div className="flex justify-between items-center">
          <h3 className="font-semibold text-slate-800 dark:text-slate-200">2. Ambient Recording</h3>
          {store.patient && (
            <button
              onClick={() => setShowManualEntry(!showManualEntry)}
              className="text-xs text-medical-blue hover:underline"
            >
              {showManualEntry ? "Use microphone" : "Manual transcript entry"}
            </button>
          )}
        </div>
      </div>
      <div className={`p-6 flex flex-col items-center justify-center min-h-[200px] ${!store.patient ? "opacity-40 pointer-events-none" : ""}`}>
        {showManualEntry ? (
          <div className="w-full space-y-3">
            <textarea
              placeholder="[CLINICIAN]: Habari yako? Shida ni nini leo?\n[PATIENT]: Kichwa inaniuma sana, na homa..."
              value={manualTranscript}
              onChange={(e) => setManualTranscript(e.target.value)}
              rows={6}
              className="w-full px-3 py-2 border rounded-md text-sm font-mono focus:outline-none focus:ring-2 focus:ring-medical-blue focus:border-transparent resize-y"
              aria-label="Manual transcript entry"
            />
            <button
              onClick={handleManualExtract}
              disabled={store.isExtracting || manualTranscript.trim().length < 10}
              className="w-full py-2 bg-medical-blue text-white rounded-md text-sm font-medium hover:bg-medical-blue/90 transition-colors disabled:opacity-50 flex justify-center items-center gap-2"
            >
              {store.isExtracting ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                  Extracting Intelligence...
                </>
              ) : (
                "Extract Structured Note"
              )}
            </button>
          </div>
        ) : (
          <>
            {store.encounterStatus === "idle" && !store.audioBlobUrl && (
              <button onClick={startRecording} className="group relative flex flex-col items-center gap-3">
                <div className="h-16 w-16 bg-medical-blue rounded-full flex items-center justify-center text-white shadow-lg group-hover:scale-105 transition-all">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                  </svg>
                </div>
                <span className="font-medium text-medical-blue">Start Consultation</span>
              </button>
            )}

            {store.isRecording && (
              <div className="flex flex-col items-center gap-4">
                <div className="flex items-center gap-3 bg-red-50 text-red-600 px-4 py-2 rounded-full font-mono text-xl border border-red-100 animate-pulse">
                  <div className="h-3 w-3 bg-red-600 rounded-full" />
                  {formatTime(timer)}
                </div>
                <button onClick={stopRecording} className="px-6 py-2 bg-slate-800 text-white rounded-md hover:bg-slate-700 transition-colors">
                  Stop & Process Audio
                </button>
              </div>
            )}

            {store.audioBlobUrl && !store.isRecording && (
              <div className="w-full flex flex-col items-center gap-4">
                <audio src={store.audioBlobUrl} controls className="w-full" />
                <div className="flex gap-3 w-full">
                  <button
                    onClick={() => useConsultationStore.setState({ audioBlobUrl: null, encounterStatus: "idle" })}
                    className="flex-1 px-4 py-2 border border-slate-300 text-slate-600 rounded-md hover:bg-slate-50 transition-colors"
                  >
                    Discard
                  </button>
                  <button
                    onClick={store.extractNote}
                    disabled={store.isExtracting}
                    className="flex-[2] px-4 py-2 bg-medical-blue text-white rounded-md hover:bg-medical-blue/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center gap-2"
                  >
                    {store.isExtracting ? (
                      <>
                        <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                        Extracting Intelligence...
                      </>
                    ) : (
                      "Extract Structured Note"
                    )}
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
