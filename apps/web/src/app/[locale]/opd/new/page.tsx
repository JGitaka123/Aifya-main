"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Stethoscope,
  Search,
  User,
  AlertTriangle,
  ChevronRight,
  X,
  Loader2,
  CheckCircle2,
  Printer,
} from "lucide-react";
import {
  useCollectConsultationFee,
  useConsultationFee,
  useCreateEncounter,
  useDepartments,
} from "@/hooks/useEncounters";
import { useStaffDirectory } from "@/hooks/useHR";
import { usePatientSearch } from "@/hooks/usePatients";
import { MpesaPaymentPanel } from "@/components/billing/MpesaPaymentPanel";
import { PageHeader } from "@/components/ui/PageHeader";
import { Link } from "@/i18n/routing";
import { cn, receiptHref } from "@/lib/utils";
import type {
  ConsultationPaymentMethod,
  ConsultationPaymentResult,
  Encounter,
  EncounterCreate,
  Patient,
  TriageCategory,
} from "@aifya/shared";

/**
 * Open a receipt through the app's own proxy, not `NEXT_PUBLIC_API_URL`: the
 * PDF is authorised by the session cookie, which the browser only sends back
 * to the app's own origin.
 *
 * @param receiptPath - Path from `receipt_url`
 * @returns Nothing
 */
function openReceipt(receiptPath: string): void {
  window.open(receiptHref(receiptPath), "_blank", "noopener");
}

/**
 * Format integer KES cents for the front desk.
 *
 * @param cents - Amount in KES cents
 * @returns Formatted amount, e.g. "KES 1,000.00"
 */
function formatKes(cents: number): string {
  return `KES ${(cents / 100).toLocaleString("en-KE", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

type SelectedPatient = Pick<
  Patient,
  "id" | "first_name" | "last_name" | "mrn" | "date_of_birth" | "gender"
>;

// ── Triage options (SATS — South African Triage Scale used in Kenya) ──────
const TRIAGE_OPTIONS = [
  {
    value: "emergency",
    labelKey: "triageEmergencyLabel",
    color: "border-red-500 bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-300",
    dot: "bg-red-500",
    descriptionKey: "triageEmergencyDescription",
  },
  {
    value: "urgent",
    labelKey: "triageUrgentLabel",
    color: "border-orange-500 bg-orange-50 dark:bg-orange-950 text-orange-700 dark:text-orange-300",
    dot: "bg-orange-500",
    descriptionKey: "triageUrgentDescription",
  },
  {
    value: "standard",
    labelKey: "triageStandardLabel",
    color: "border-yellow-500 bg-yellow-50 dark:bg-yellow-950 text-yellow-700 dark:text-yellow-300",
    dot: "bg-yellow-500",
    descriptionKey: "triageStandardDescription",
  },
  {
    value: "non_urgent",
    labelKey: "triageNonUrgentLabel",
    color: "border-green-500 bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-300",
    dot: "bg-green-500",
    descriptionKey: "triageNonUrgentDescription",
  },
];

// ── Department options (extend as needed) ─────────────────────────────────
const DEPARTMENTS = [
  { value: "general_opd", labelKey: "departmentGeneral" },
  { value: "paediatrics", labelKey: "departmentPaediatrics" },
  { value: "maternity", labelKey: "departmentMaternity" },
  { value: "surgical", labelKey: "departmentSurgical" },
  { value: "dental", labelKey: "departmentDental" },
  { value: "eye", labelKey: "departmentEye" },
  { value: "ent", labelKey: "departmentEnt" },
  { value: "orthopaedics", labelKey: "departmentOrthopaedics" },
  { value: "mental_health", labelKey: "departmentMentalHealth" },
  { value: "dermatology", labelKey: "departmentDermatology" },
  { value: "nutrition", labelKey: "departmentNutrition" },
  { value: "physiotherapy", labelKey: "departmentPhysiotherapy" },
];

/**
 * OPD New Encounter page.
 *
 * Automation chain on submit:
 *  1. POST /encounters → encounter created, queue number assigned
 *  2. Backend auto-generates consultation fee invoice
 *  3. Backend auto-posts GL: DR Accounts Receivable → CR Consultation Revenue
 *  4. Encounter added to OPD queue with triage priority
 *  5. Patient timeline updated
 *  6. Redirect to encounter detail for vitals + clinical notes
 */
export default function NewEncounterPage() {
  const t = useTranslations("opd");
  const tc = useTranslations("common");
  const router = useRouter();
  const createEncounter = useCreateEncounter();

  // ── Patient search state ──────────────────────────────────────────────
  const searchParams = useSearchParams();
  const prefilledPatientId = searchParams.get("patient_id");
  const prefilledPatientName = searchParams.get("patient_name");

  const [searchQuery, setSearchQuery] = useState(prefilledPatientName ?? "");
  const [selectedPatient, setSelectedPatient] = useState<SelectedPatient | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);

  // Auto-select patient if coming from patient detail page
  useEffect(() => {
    if (prefilledPatientId && prefilledPatientName && !selectedPatient) {
      const [firstName = "", ...lastNameParts] = prefilledPatientName.split(" ");
      setSelectedPatient({
        id: prefilledPatientId,
        first_name: firstName,
        last_name: lastNameParts.join(" "),
        mrn: "",
        date_of_birth: "",
        gender: "other",
      });
    }
  }, [prefilledPatientId, prefilledPatientName, selectedPatient]);

  const { data: patientResults, isLoading: searchLoading } = usePatientSearch(
    searchQuery.length >= 2 ? searchQuery : undefined,
    1,
    8
  );

  const { data: doctorDirectory } = useStaffDirectory("doctor");
  const doctors = (doctorDirectory?.items ?? []).filter((d) => d.is_active);

  // Real departments when the facility has configured them; the static list
  // below is a display-only fallback so a fresh install can still route.
  const { data: departmentDirectory } = useDepartments();
  const liveDepartments = departmentDirectory ?? [];


  // ── Form state ────────────────────────────────────────────────────────
  const [triage, setTriage] = useState<TriageCategory>("non_urgent");
  const [department, setDepartment] = useState("");
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [doctorId, setDoctorId] = useState("");

  // Reception fee collection. The encounter is created first so the backend
  // can raise the consultation invoice; the desk then settles it and prints.
  const [createdEncounter, setCreatedEncounter] = useState<Encounter | null>(
    null
  );
  const [paymentMethod, setPaymentMethod] =
    useState<ConsultationPaymentMethod>("cash");
  const [paymentRef, setPaymentRef] = useState("");
  const [receipt, setReceipt] = useState<ConsultationPaymentResult | null>(null);

  const {
    data: feeQuote,
    isLoading: feeLoading,
    refetch: refetchFee,
  } = useConsultationFee(createdEncounter?.id ?? "", !!createdEncounter);
  const collectFee = useCollectConsultationFee(createdEncounter?.id ?? "");

  // ── Patient selection ─────────────────────────────────────────────────
  const handleSelectPatient = useCallback((patient: SelectedPatient) => {
    setSelectedPatient(patient);
    setSearchQuery(`${patient.first_name} ${patient.last_name}`);
    setShowDropdown(false);
    setErrors((e) => ({ ...e, patient: "" }));
  }, []);

  const handleClearPatient = () => {
    setSelectedPatient(null);
    setSearchQuery("");
    setShowDropdown(false);
  };

  // ── Validation ────────────────────────────────────────────────────────
  const validate = () => {
    const newErrors: Record<string, string> = {};
    if (!selectedPatient) newErrors.patient = t("selectPatientError");
    if (!chiefComplaint.trim()) newErrors.chiefComplaint = t("chiefComplaintRequired");
    if (chiefComplaint.trim().length < 3) newErrors.chiefComplaint = t("chiefComplaintTooShort");
    return newErrors;
  };

  // ── Submit → full automation chain ───────────────────────────────────
  const handleSubmit = () => {
    const newErrors = validate();
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    const payload: EncounterCreate = {
        patient_id: selectedPatient!.id,
        encounter_type: "opd",
        // Only a configured department UUID is sent; the static fallback
        // labels are display-only until departments exist.
        department_id: liveDepartments.some((d) => d.id === department)
          ? department
          : null,
        attending_doctor_id: doctorId || null,
        chief_complaint: chiefComplaint.trim(),
        triage_category: triage,
      };

    createEncounter.mutate(
      payload,
      {
        onSuccess: (encounter) => {
          // Redirect to encounter detail — invoice + GL already posted by backend
          setCreatedEncounter(encounter);
          setReceipt(null);
          setErrors({});
        },
        onError: (err: Error) => {
          setErrors({ submit: err.message || t("createEncounterError") });
        },
      }
    );
  };

  const handleCollectFee = () => {
    if (!createdEncounter) return;
    setErrors((e) => ({ ...e, payment: "" }));
    collectFee.mutate(
      {
        payment_method: paymentMethod,
        reference_number: paymentRef.trim() || null,
      },
      {
        onSuccess: (result) => setReceipt(result),
        onError: (err: Error) =>
          setErrors((e) => ({
            ...e,
            payment: err.message || t("createEncounterError"),
          })),
      }
    );
  };

  return (
    <div className="animate-[fade-in_0.3s_ease-out] p-6 lg:p-8">
      {/* Clinical flow progress bar */}
      <div className="mb-4 flex items-center gap-1 text-xs text-muted-foreground">
        <span className="rounded-full bg-primary px-2.5 py-0.5 text-[11px] font-semibold text-primary-foreground">{t("flowRegister", { step: 1 })}</span>
        <span className="text-muted-foreground">›</span>
        <span className="rounded-full bg-primary px-2.5 py-0.5 text-[11px] font-semibold text-primary-foreground">{t("flowQueue", { step: 2 })}</span>
        <span className="text-muted-foreground">›</span>
        <span className="rounded-full bg-primary/20 px-2.5 py-0.5 text-[11px] font-semibold text-primary">{t("flowEncounter", { step: 3 })}</span>
        <span className="text-muted-foreground">›</span>
        <span className="rounded-full bg-muted px-2.5 py-0.5 text-[11px] font-medium">{t("flowVitals", { step: 4 })}</span>
        <span className="text-muted-foreground">›</span>
        <span className="rounded-full bg-muted px-2.5 py-0.5 text-[11px] font-medium">{t("flowPrescribe", { step: 5 })}</span>
        <span className="text-muted-foreground">›</span>
        <span className="rounded-full bg-muted px-2.5 py-0.5 text-[11px] font-medium">{t("flowBilling", { step: 6 })}</span>
      </div>
      <PageHeader
        icon={Stethoscope}
        title={t("newEncounter")}
        breadcrumbs={[
          { label: t("queue"), href: "/opd" },
          { label: t("newEncounter") },
        ]}
      />

      <div className="mx-auto mt-6 max-w-2xl space-y-6">

        {/* ── STEP 1: Patient Search ── */}
        <section className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">1</span>
            {t("patient")}
          </h2>

          {selectedPatient ? (
            // Selected patient card
            <div className="flex items-center justify-between rounded-lg border border-green-400 bg-green-50 px-4 py-3 dark:border-green-700 dark:bg-green-950">
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-200 text-green-800 dark:bg-green-800 dark:text-green-200">
                  <User className="h-5 w-5" />
                </div>
                <div>
                  <p className="font-semibold text-foreground">
                    {selectedPatient.first_name} {selectedPatient.last_name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {selectedPatient.mrn} · {selectedPatient.date_of_birth ?? "DOB unknown"}
                  </p>
                </div>
              </div>
              <button
                onClick={handleClearPatient}
                className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ) : (
            // Search input with live dropdown
            <div className="relative" ref={searchRef}>
              <div className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 focus-within:ring-2 focus-within:ring-primary/30">
                <Search className="h-4 w-4 flex-shrink-0 text-muted-foreground" />
                <input
                  type="text"
                  placeholder={t("patientSearchPlaceholder")}
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setShowDropdown(true);
                  }}
                  onFocus={() => setShowDropdown(true)}
                  className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
                  autoComplete="off"
                />
                {searchLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
              </div>

              {/* Dropdown results */}
              {showDropdown && searchQuery.length >= 2 && (
                <div className="absolute z-50 mt-1 w-full rounded-lg border border-border bg-card shadow-lg">
                  {patientResults?.items?.length ? (
                    patientResults.items.map((patient) => (
                      <button
                        key={patient.id}
                        onClick={() => handleSelectPatient(patient)}
                        className="flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-muted first:rounded-t-lg last:rounded-b-lg"
                      >
                        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-muted">
                          <User className="h-4 w-4 text-muted-foreground" />
                        </div>
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-foreground">
                            {patient.first_name} {patient.last_name}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {patient.mrn} · {patient.gender ?? ""}
                          </p>
                        </div>
                      </button>
                    ))
                  ) : (
                    <div className="flex flex-col items-center gap-2 px-4 py-6 text-center">
                      <p className="text-sm text-muted-foreground">{t("noPatientsFound")}</p>
                      <Link
                        href="/patients/register"
                        className="text-xs font-medium text-primary hover:underline"
                      >
                        {t("registerNewPatient")}
                      </Link>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          {errors.patient && (
            <p className="mt-1.5 flex items-center gap-1 text-xs text-red-500">
              <AlertTriangle className="h-3 w-3" /> {errors.patient}
            </p>
          )}
        </section>

        {/* ── STEP 2: Triage Category (SATS) ── */}
        <section className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">2</span>
            {t("triageSats")}
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {TRIAGE_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => setTriage(option.value as TriageCategory)}
                className={cn(
                  "flex flex-col items-start rounded-lg border-2 p-3 text-left transition-all",
                  triage === option.value
                    ? option.color + " ring-2 ring-offset-1"
                    : "border-border bg-background hover:bg-muted"
                )}
              >
                <div className="flex items-center gap-2">
                  <span className={cn("h-2.5 w-2.5 rounded-full", option.dot)} />
                  <span className="text-sm font-semibold">{t(option.labelKey)}</span>
                </div>
                <span className="mt-1 text-[11px] text-muted-foreground">
                  {t(option.descriptionKey)}
                </span>
              </button>
            ))}
          </div>
        </section>

        {/* ── STEP 3: Department + Chief Complaint ── */}
        <section className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">3</span>
            {t("clinicalDetails")}
          </h2>

          <div className="space-y-4">
            {/* Department */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-foreground">
                {t("department")}
              </label>
              <select
                value={department}
                onChange={(e) => setDepartment(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="">{t("anyDepartment")}</option>
                {liveDepartments.length > 0
                  ? liveDepartments.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name}
                      </option>
                    ))
                  : DEPARTMENTS.map((d) => (
                      <option key={d.value} value={d.value}>
                        {t(d.labelKey)}
                      </option>
                    ))}
              </select>
            </div>

            {/* Doctor: directing to a named doctor drives that doctor's fee */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-foreground">
                {t("doctor")}
              </label>
              <select
                value={doctorId}
                onChange={(e) => setDoctorId(e.target.value)}
                className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="">{t("anyAvailableDoctor")}</option>
                {doctors.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.first_name} {d.last_name}
                    {d.specialization ? ` - ${d.specialization}` : ""}
                  </option>
                ))}
              </select>
            </div>

            {/* Chief Complaint */}
            <div>
              <label className="mb-1.5 block text-sm font-medium text-foreground">
                {t("chiefComplaint")} <span className="text-red-500">*</span>
              </label>
              <textarea
                value={chiefComplaint}
                onChange={(e) => {
                  setChiefComplaint(e.target.value);
                  if (e.target.value.trim()) setErrors((er) => ({ ...er, chiefComplaint: "" }));
                }}
                placeholder={t("chiefComplaintExample")}
                rows={3}
                className={cn(
                  "w-full resize-none rounded-lg border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30",
                  errors.chiefComplaint ? "border-red-500" : "border-border"
                )}
              />
              {errors.chiefComplaint && (
                <p className="mt-1 flex items-center gap-1 text-xs text-red-500">
                  <AlertTriangle className="h-3 w-3" /> {errors.chiefComplaint}
                </p>
              )}
            </div>
          </div>
        </section>

        {/* ── Automation summary ── */}
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 dark:border-blue-800 dark:bg-blue-950">
          <p className="text-xs font-medium text-blue-700 dark:text-blue-300">
            {t("encounterAutomationNotice")}
          </p>
        </div>

        {/* ── Submit error ── */}
        {errors.submit && (
          <div className="rounded-lg border border-red-300 bg-red-50 px-4 py-3 dark:border-red-800 dark:bg-red-950">
            <p className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400">
              <AlertTriangle className="h-4 w-4" /> {errors.submit}
            </p>
          </div>
        )}

        {/* ── Actions ── */}
        {/* Reception collects the consultation fee before the patient is seen */}
        {createdEncounter && (
          <section className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
            <h2 className="mb-4 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                4
              </span>
              {t("consultationFee")}
            </h2>

            {feeLoading ? (
              <p className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
              </p>
            ) : (
              <div className="space-y-4">
                <div className="flex items-center justify-between rounded-lg border border-border bg-muted/40 px-4 py-3">
                  <div>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      {t("feeDue")}
                    </p>
                    <p className="text-2xl font-semibold text-foreground">
                      {formatKes(feeQuote?.fee_cents ?? 0)}
                    </p>
                  </div>
                  {feeQuote?.paid ? (
                    <span className="flex items-center gap-1.5 rounded-full bg-green-100 px-3 py-1 text-xs font-semibold text-green-800 dark:bg-green-900 dark:text-green-200">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {t("feePaid")}
                    </span>
                  ) : (
                    <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-900 dark:text-amber-200">
                      {feeQuote?.invoice_number ?? "-"}
                    </span>
                  )}
                </div>

                {feeQuote && feeQuote.fee_cents === 0 && (
                  <p className="text-xs text-muted-foreground">
                    {t("feeNotRequired")}
                  </p>
                )}

                {feeQuote && !feeQuote.paid && (
                  <>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <label className="mb-1.5 block text-sm font-medium text-foreground">
                          {t("paymentMethod")}
                        </label>
                        <select
                          value={paymentMethod}
                          onChange={(e) =>
                            setPaymentMethod(
                              e.target.value as ConsultationPaymentMethod
                            )
                          }
                          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
                        >
                          <option value="cash">{t("paymentCash")}</option>
                          <option value="mpesa">{t("paymentMpesa")}</option>
                          <option value="insurance">
                            {t("paymentInsurance")}
                          </option>
                          <option value="exemption">
                            {t("paymentExemption")}
                          </option>
                        </select>
                      </div>
                      <div>
                        <label className="mb-1.5 block text-sm font-medium text-foreground">
                          {t("paymentReference")}
                        </label>
                        <input
                          value={paymentRef}
                          onChange={(e) => setPaymentRef(e.target.value)}
                          placeholder="e.g. SFH4KQ8L2M"
                          className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
                        />
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={handleCollectFee}
                      disabled={collectFee.isPending}
                      className="flex items-center gap-2 rounded-lg bg-primary px-6 py-2 text-sm font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
                    >
                      {collectFee.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Printer className="h-4 w-4" />
                      )}
                      {t("collectPayment")}
                    </button>

                    {feeQuote.invoice_id && (
                      <MpesaPaymentPanel
                        invoiceId={feeQuote.invoice_id}
                        amountCents={feeQuote.balance_cents}
                        onPaid={() => {
                          void refetchFee();
                        }}
                      />
                    )}
                  </>
                )}

                {receipt && (
                  <div className="flex items-center justify-between rounded-lg border border-green-400 bg-green-50 px-4 py-3 dark:border-green-700 dark:bg-green-950">
                    <p className="text-sm font-medium text-green-800 dark:text-green-200">
                      {t("receiptReady")}: {receipt.invoice_number}
                    </p>
                    <button
                      type="button"
                      onClick={() => openReceipt(receipt.receipt_url)}
                      className="flex items-center gap-1.5 rounded-lg border border-green-600 px-3 py-1.5 text-xs font-semibold text-green-800 hover:bg-green-100 dark:text-green-200"
                    >
                      <Printer className="h-3.5 w-3.5" />
                      {t("printReceipt")}
                    </button>
                  </div>
                )}

                {errors.payment && (
                  <p className="flex items-center gap-1 text-xs text-red-500">
                    <AlertTriangle className="h-3 w-3" /> {errors.payment}
                  </p>
                )}

                <button
                  type="button"
                  onClick={() => router.push(`/opd/${createdEncounter.id}`)}
                  className="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
                >
                  {t("continueToEncounter")}
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            )}
          </section>
        )}

        <div className="flex items-center justify-between">
          <Link
            href={prefilledPatientId ? `/patients/${prefilledPatientId}` : "/opd"}
            className="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted"
          >
            {tc("back")}
          </Link>
          <button
            onClick={handleSubmit}
            disabled={createEncounter.isPending || !!createdEncounter}
            className="flex items-center gap-2 rounded-lg bg-primary px-6 py-2 text-sm font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {createEncounter.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {t("creatingEncounter")}
              </>
            ) : (
              <>
                {t("startEncounter")}
                <ChevronRight className="h-4 w-4" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
