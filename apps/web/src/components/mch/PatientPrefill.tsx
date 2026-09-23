"use client";

import { useEffect, useRef } from "react";
import type { Patient } from "@aifya/shared";
import { usePatient } from "@/hooks/usePatients";

interface PatientPrefillProps {
  /** Patient to load, usually taken from the booked appointment. */
  patientId: string;
  /** Called once with the loaded patient so the caller can open a form. */
  onLoaded: (patient: Patient) => void;
}

/**
 * Headless loader that resolves one patient and hands them to the caller.
 *
 * Mounted only while a prefill is pending, so opening a registration form from
 * an appointment costs a single patient request instead of one per table row.
 *
 * @param props - Component props
 * @returns Nothing; the patient is delivered through `onLoaded`
 */
export function PatientPrefill({ patientId, onLoaded }: PatientPrefillProps) {
  const { data: patient } = usePatient(patientId);
  const delivered = useRef(false);

  useEffect(() => {
    if (patient && !delivered.current) {
      delivered.current = true;
      onLoaded(patient);
    }
  }, [patient, onLoaded]);

  return null;
}