"use client";

import React, { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Stethoscope,
  Activity,
  FileText,
  Pill,
  FlaskConical,
  Scan,
  CreditCard,
  User,
  Clock,
  AlertTriangle,
  Loader2,
  XCircle,
  Thermometer,
  Heart,
  Wind,
  Droplets,
  Scale,
  Ruler,
  ArrowLeft,
  ChevronRight,
  type LucideIcon,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useEncounter,
  useEncounterVitals,
  useRecordVitals,
  useEncounterDiagnoses,
  useAddDiagnosis,
  useEncounterPrescriptions,
  useCreatePrescription,
  useEncounterLabOrders,
  useCreateLabOrder,
  useUpdateEncounter,
} from "@/hooks/useEncounters";
import { useCreateImagingOrder, useImagingWorklist } from "@/hooks/useRadiology";
import { PageHeader } from "@/components/ui/PageHeader";
import { AdmitToIPDPanel } from "@/components/opd/AdmitToIPDPanel";
import { DrugAutocomplete } from "@/components/opd/DrugAutocomplete";
import { DrugStockBadge } from "@/components/pharmacy/DrugStockBadge";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { PageSkeleton } from "@/components/ui/Skeleton";
import { ConsultationFeePanel } from "@/components/billing/ConsultationFeePanel";
import { EncounterServiceCharges } from "@/components/billing/EncounterServiceCharges";
import { cn, formatDateTime } from "@/lib/utils";
import type {
  DiagnosisCreate,
  DrugInteractionAlert,
  EncounterStatus,
  ImagingModality,
  ImagingOrderCreate,
  ImagingOrderStatus,
  ImagingPriority,
  LabOrderCreate,
  LabTestRequest,
  Laterality,
  PregnancyStatus,
  PrescriptionWithInteractions,
  VitalSignCreate,
} from "@aifya/shared";

// ── Triage color map ──────────────────────────────────────────────────────
const TRIAGE_BORDER: Record<string, string> = {
  emergency: "border-l-red-500",
  urgent: "border-l-orange-500",
  standard: "border-l-yellow-500",
  non_urgent: "border-l-green-500",
  dead: "border-l-blue-500",
};

const TRIAGE_BADGE: Record<string, "red-solid" | "orange-solid" | "yellow-solid" | "green-solid" | "blue-solid"> = {
  emergency: "red-solid",
  urgent: "orange-solid",
  standard: "yellow-solid",
  non_urgent: "green-solid",
  dead: "blue-solid",
};

// ── Status badge map ──────────────────────────────────────────────────────
const STATUS_BADGE: Record<string, "warning" | "info" | "success" | "purple" | "default" | "error"> = {
  waiting: "warning",
  in_consultation: "info",
  completed: "success",
  admitted: "purple",
  discharged: "default",
  cancelled: "error",
};

// ── Tab definitions ───────────────────────────────────────────────────────
const MODALITIES: readonly ImagingModality[] = ["xray", "ultrasound", "ct", "mri", "fluoroscopy", "mammography", "ecg", "echo"];

const MODALITY_LABEL_KEY: Record<ImagingModality, string> = {
  xray: "modalityXray", ultrasound: "modalityUltrasound", ct: "modalityCt", mri: "modalityMri",
  fluoroscopy: "modalityFluoroscopy", mammography: "modalityMammography", ecg: "modalityEcg", echo: "modalityEcho",
};

const LATERALITY_LABEL_KEY: Record<Laterality, string> = {
  left: "left", right: "right", bilateral: "bilateral", na: "notApplicable",
};

const IMAGING_STATUS_LABEL_KEY: Record<ImagingOrderStatus, string> = {
  ordered: "statusOrdered", scheduled: "statusScheduled", in_progress: "statusInProgress",
  completed: "statusCompleted", cancelled: "statusCancelled",
};

const IMAGING_STATUS_STYLE: Record<ImagingOrderStatus, string> = {
  ordered: "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300",
  scheduled: "bg-purple-100 text-purple-700 dark:bg-purple-900 dark:text-purple-300",
  in_progress: "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300",
  completed: "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300",
  cancelled: "bg-muted text-muted-foreground",
};

const TABS = [
  { id: "vitals", labelKey: "vitalsTab", icon: Activity },
  { id: "diagnoses", labelKey: "diagnosesTab", icon: FileText },
  { id: "prescriptions", labelKey: "prescriptionsTab", icon: Pill },
  { id: "lab", labelKey: "labOrdersTab", icon: FlaskConical },
  { id: "imaging", labelKey: "imagingOrdersTab", icon: Scan },
  { id: "billing", labelKey: "billingTab", icon: CreditCard },
] as const;

type TabId = typeof TABS[number]["id"];
type DiagnosisType = DiagnosisCreate["diagnosis_type"];
type LabPriority = NonNullable<LabOrderCreate["priority"]>;

interface PrescriptionFormState {
  drug_name: string;
  dosage: string;
  route: string;
  frequency: string;
  duration_days: string;
  instructions: string;
  quantity: string;
}

interface DiagnosisFormState {
  icd10_code: string;
  icd10_description: string;
  diagnosis_type: DiagnosisType;
  certainty: string;
  notes: string;
}

interface LabFormState {
  test_code: string;
  test_name: string;
  priority: LabPriority;
  clinical_info: string;
  cost_kes: string;
}

interface ImagingFormState {
  modality: ImagingModality;
  body_part: string;
  laterality: Laterality | "";
  views_requested: string;
  study_description: string;
  priority: ImagingPriority;
  clinical_indication: string;
  contrast_required: boolean;
  pregnancy_status: PregnancyStatus;
}

// ── Route & frequency display helpers ────────────────────────────────────
/**
 * OPD Encounter Detail page.
 *
 * Sections:
 *  - Patient header with triage + status
 *  - Vitals recording (critical alert auto-detected by backend)
 *  - ICD-10 Diagnoses
 *  - Prescriptions (drug interaction check by backend)
 *  - Lab Orders (invoice auto-generated, GL auto-posted)
 *  - Billing status (invoice auto-generated on encounter creation)
 *  - Status update (waiting → in_consultation → completed → admitted/discharged)
 */
export default function EncounterDetailPage() {
  const t = useTranslations("opd");
  const td = useTranslations("diagnosis");
  const tp = useTranslations("prescription");
  const tl = useTranslations("lab");
  const tr = useTranslations("radiology");
  const tb = useTranslations("billing");
  const params = useParams();
  const encounterId = params.encounterId as string;
  const router = useRouter();

  const [activeTab, setActiveTab] = useState<TabId>("vitals");
  const [showAdmitForm, setShowAdmitForm] = useState(false);
  const routeLabels: Record<string, string> = {
    oral: tp("oral"), iv: tp("iv"), im: tp("im"), sc: tp("sc"),
    topical: tp("topical"), inhaled: tp("inhaled"), rectal: tp("rectal"),
    sublingual: tp("sublingual"), ophthalmic: tp("ophthalmic"), otic: tp("otic"), nasal: tp("nasal"),
  };
  const frequencyLabels: Record<string, string> = {
    od: tp("od"), bd: tp("bd"), tds: tp("tds"), qds: tp("qds"),
    prn: tp("prn"), stat: tp("stat"), nocte: tp("nocte"), weekly: tp("weekly"), monthly: tp("monthly"),
  };

  // ── Data fetching ─────────────────────────────────────────────────────
  const { data: encounter, isLoading } = useEncounter(encounterId);
  const { data: vitals } = useEncounterVitals(encounterId);
  const { data: diagnoses } = useEncounterDiagnoses(encounterId);
  const { data: prescriptions, refetch: refetchPrescriptions } = useEncounterPrescriptions(encounterId);
  const { data: labOrders } = useEncounterLabOrders(encounterId);
  const { data: imagingWorklist } = useImagingWorklist();
  const imagingOrders = imagingWorklist?.items.filter((item) => item.encounter_id === encounterId) ?? [];

  // ── Mutations ─────────────────────────────────────────────────────────
  const recordVitals = useRecordVitals(encounterId);
  const addDiagnosis = useAddDiagnosis(encounterId);
  const createPrescription = useCreatePrescription(encounterId);
  const createLabOrder = useCreateLabOrder(encounterId);
  const createImagingOrder = useCreateImagingOrder();
  const updateEncounter = useUpdateEncounter(encounterId);

  // ── Vitals form state ─────────────────────────────────────────────────
  const [vitalsForm, setVitalsForm] = useState({
    systolic_bp: "", diastolic_bp: "", heart_rate: "",
    temperature: "", respiratory_rate: "", oxygen_saturation: "",
    weight_kg: "", height_cm: "", pain_score: "", blood_glucose: "",
  });
  const [vitalsSubmitting, setVitalsSubmitting] = useState(false);

  const handleVitalsSubmit = () => {
    if (!encounter) return;
    setVitalsSubmitting(true);

    const payload: VitalSignCreate = {
      encounter_id: encounterId,
      patient_id: encounter.patient_id,
    };

    // Only include filled fields
    if (vitalsForm.systolic_bp) payload.systolic_bp = Number(vitalsForm.systolic_bp);
    if (vitalsForm.diastolic_bp) payload.diastolic_bp = Number(vitalsForm.diastolic_bp);
    if (vitalsForm.heart_rate) payload.heart_rate = Number(vitalsForm.heart_rate);
    if (vitalsForm.temperature) payload.temperature = Number(vitalsForm.temperature);
    if (vitalsForm.respiratory_rate) payload.respiratory_rate = Number(vitalsForm.respiratory_rate);
    if (vitalsForm.oxygen_saturation) payload.oxygen_saturation = Number(vitalsForm.oxygen_saturation);
    if (vitalsForm.weight_kg) payload.weight_kg = Number(vitalsForm.weight_kg);
    if (vitalsForm.height_cm) payload.height_cm = Number(vitalsForm.height_cm);
    if (vitalsForm.pain_score) payload.pain_score = Number(vitalsForm.pain_score);
    if (vitalsForm.blood_glucose) payload.blood_glucose = Number(vitalsForm.blood_glucose);

    recordVitals.mutate(payload, {
      onSettled: () => {
        setVitalsSubmitting(false);
        setVitalsForm({
          systolic_bp: "", diastolic_bp: "", heart_rate: "",
          temperature: "", respiratory_rate: "", oxygen_saturation: "",
          weight_kg: "", height_cm: "", pain_score: "", blood_glucose: "",
        });
      },
    });
  };

  // ── Diagnosis form state ──────────────────────────────────────────────
  const [diagForm, setDiagForm] = useState<DiagnosisFormState>({
    icd10_code: "", icd10_description: "",
    diagnosis_type: "primary", certainty: "confirmed", notes: "",
  });
  const [diagSubmitting, setDiagSubmitting] = useState(false);

  const handleDiagSubmit = () => {
    if (!encounter || !diagForm.icd10_code || !diagForm.icd10_description) return;
    setDiagSubmitting(true);
    addDiagnosis.mutate(
      {
        encounter_id: encounterId,
        patient_id: encounter.patient_id,
        icd10_code: diagForm.icd10_code,
        icd10_description: diagForm.icd10_description,
        diagnosis_type: diagForm.diagnosis_type,
        certainty: diagForm.certainty,
        notes: diagForm.notes || undefined,
        is_chronic: false,
      },
      {
        onSettled: () => {
          setDiagSubmitting(false);
          setDiagForm({ icd10_code: "", icd10_description: "", diagnosis_type: "primary", certainty: "confirmed", notes: "" });
        },
      }
    );
  };

  // ── Prescription form state ───────────────────────────────────────────
  const [rxForm, setRxForm] = useState<PrescriptionFormState>({
    drug_name: "", dosage: "", route: "oral",
    frequency: "bd", duration_days: "", instructions: "", quantity: "",
  });
  // Drug picked from the inventory-backed autocomplete; kept in state so the
  // pharmacy's stock stays on screen while the rest of the form is filled in.
  const [selectedDrug, setSelectedDrug] = useState<{
    name: string;
    generic: string | null;
  } | null>(null);
  const queryClient = useQueryClient();
  const [rxSubmitting, setRxSubmitting] = useState(false);
  const [rxInteractions, setRxInteractions] = useState<DrugInteractionAlert[]>([]);

  const handleRxSubmit = () => {
    if (!encounter || !rxForm.drug_name || !rxForm.dosage) return;
    setRxSubmitting(true);
    setRxInteractions([]);
    createPrescription.mutate(
      {
        encounter_id: encounterId,
        patient_id: encounter.patient_id,
        drug_name: rxForm.drug_name,
        dosage: rxForm.dosage,
        route: rxForm.route,
        frequency: rxForm.frequency,
        duration_days: rxForm.duration_days ? Number(rxForm.duration_days) : undefined,
        quantity: rxForm.quantity ? Number(rxForm.quantity) : undefined,
        instructions: rxForm.instructions || undefined,
      },
      {
        onSuccess: (result: PrescriptionWithInteractions) => {
          if (result.interactions?.length) setRxInteractions(result.interactions);
          setRxForm({ drug_name: "", dosage: "", route: "oral", frequency: "bd", duration_days: "", instructions: "", quantity: "" });
          setSelectedDrug(null);
          queryClient.invalidateQueries({ queryKey: ["encounters", encounterId, "prescriptions"] });
          refetchPrescriptions();
        },
        onSettled: () => setRxSubmitting(false),
      }
    );
  };

  // ── Lab order form state ──────────────────────────────────────────────
  const [labForm, setLabForm] = useState<LabFormState>({ test_code: "", test_name: "", priority: "routine", clinical_info: "", cost_kes: "" });
  const [labSubmitting, setLabSubmitting] = useState(false);

  const handleLabSubmit = () => {
    if (!encounter || !labForm.test_name) return;
    setLabSubmitting(true);
    const payload: LabOrderCreate & { total_cost_cents?: number } = {
        encounter_id: encounterId,
        patient_id: encounter.patient_id,
        priority: labForm.priority,
        clinical_info: labForm.clinical_info || undefined,
        tests: [{ test_code: labForm.test_code || labForm.test_name.toUpperCase().replace(/\s+/g, "_").slice(0, 20), test_name: labForm.test_name }],
        total_cost_cents: labForm.cost_kes ? Math.round(parseFloat(labForm.cost_kes) * 100) : undefined,
      };

    createLabOrder.mutate(
      payload,
      {
        onSettled: () => {
          setLabSubmitting(false);
          setLabForm({ test_code: "", test_name: "", priority: "routine", clinical_info: "", cost_kes: "" });
        },
      }
    );
  };

  // ── Imaging order form state ──
  const emptyImagingForm: ImagingFormState = {
    modality: "xray", body_part: "", laterality: "", views_requested: "",
    study_description: "", priority: "routine", clinical_indication: "",
    contrast_required: false, pregnancy_status: "na",
  };
  const [imagingForm, setImagingForm] = useState<ImagingFormState>(emptyImagingForm);
  const [imagingSubmitting, setImagingSubmitting] = useState(false);

  const handleImagingSubmit = () => {
    if (!encounter || !imagingForm.body_part.trim() || !imagingForm.study_description.trim()) return;
    setImagingSubmitting(true);
    const payload: ImagingOrderCreate = {
      encounter_id: encounterId,
      patient_id: encounter.patient_id,
      modality: imagingForm.modality,
      body_part: imagingForm.body_part.trim(),
      study_description: imagingForm.study_description.trim(),
      priority: imagingForm.priority,
      pregnancy_status: imagingForm.pregnancy_status,
      contrast_required: imagingForm.contrast_required,
    };
    if (imagingForm.laterality) payload.laterality = imagingForm.laterality;
    if (imagingForm.views_requested.trim()) payload.views_requested = imagingForm.views_requested.trim();
    if (imagingForm.clinical_indication.trim()) payload.clinical_indication = imagingForm.clinical_indication.trim();

    createImagingOrder.mutate(payload, {
      onSettled: () => {
        setImagingSubmitting(false);
        setImagingForm(emptyImagingForm);
      },
    });
  };

  // ── Status update ─────────────────────────────────────────────────────
  const handleStatusChange = (newStatus: EncounterStatus) => {
    updateEncounter.mutate({ status: newStatus });
  };

  // ── Loading state ─────────────────────────────────────────────────────
  if (isLoading) return <PageSkeleton />;
  if (!encounter) {
    return (
      <div className="flex flex-col items-center gap-4 p-12 text-center">
        <XCircle className="h-12 w-12 text-muted-foreground" />
        <p className="text-lg font-semibold text-foreground">{t("notFound")}</p>
        <Link href="/opd" className="text-sm text-primary hover:underline">{t("backToQueue")}</Link>
      </div>
    );
  }

  const triageBorder = TRIAGE_BORDER[encounter.triage_category ?? "non_urgent"] ?? TRIAGE_BORDER.non_urgent;
  const triageBadge = TRIAGE_BADGE[encounter.triage_category ?? "non_urgent"] ?? TRIAGE_BADGE.non_urgent;

  return (
    <div className="animate-[fade-in_0.3s_ease-out] space-y-6 p-6 lg:p-8">
      {/* Clinical flow progress bar */}
      <div className="flex flex-wrap items-center gap-1 text-xs">
        <Link href="/opd" className="flex items-center gap-1 text-muted-foreground hover:text-foreground"><ArrowLeft className="h-3 w-3" /> {t("queue")}</Link>
        <span className="text-muted-foreground mx-1">›</span>
        <Link href={`/patients/${encounter.patient_id}`} className="text-muted-foreground hover:text-foreground">{encounter.patient_name}</Link>
        <span className="text-muted-foreground mx-1">›</span>
        {(["vitals","diagnoses","prescriptions","lab","imaging","billing"] as const).map((tab, i) => (
          <span key={tab} className="flex items-center gap-1">
            {i > 0 && <span className="text-muted-foreground mx-1">›</span>}
            <button
              onClick={() => setActiveTab(tab as TabId)}
              className={cn(
                "rounded-full px-2.5 py-0.5 text-[11px] font-semibold transition-colors",
                activeTab === tab
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              )}
            >
              {t(`${tab}Flow`, { step: i + 1 })}
            </button>
          </span>
        ))}
      </div>
      <PageHeader
        icon={Stethoscope}
        title={t("encounterTitle", { patient: encounter.patient_name ?? t("patient") })}
        breadcrumbs={[
          { label: t("queue"), href: "/opd" },
          { label: encounter.patient_name ?? t("encounter") },
        ]}
      />

      {/* ── Patient Header Card ── */}
      <div className={cn(
        "flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)] border-l-4",
        triageBorder
      )}>
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted">
            <User className="h-6 w-6 text-muted-foreground" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-foreground">{encounter.patient_name}</h2>
              <span className="font-mono text-xs text-muted-foreground">{encounter.patient_mrn}</span>
            </div>
            <p className="mt-0.5 text-sm text-muted-foreground">
              {encounter.chief_complaint}
            </p>
            <div className="mt-1 flex items-center gap-2">
              <StatusBadge variant={triageBadge} size="xs">
                {t(`triageStatus.${encounter.triage_category ?? "non_urgent"}`)}
              </StatusBadge>
              <StatusBadge variant={STATUS_BADGE[encounter.status] ?? "warning"} size="xs" dot>
                {t(`status.${encounter.status}`)}
              </StatusBadge>
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="h-3 w-3" />
                {formatDateTime(encounter.created_at)}
              </span>
            </div>
          </div>
        </div>

        {/* Status controls */}
        <div className="flex flex-wrap items-center gap-2">
          {encounter.status === "waiting" && (
            <button
              onClick={() => handleStatusChange("in_consultation")}
              disabled={updateEncounter.isPending}
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {t("startConsultation")}
            </button>
          )}
          {encounter.status === "in_consultation" && !showAdmitForm && (
            <>
              <button
                onClick={() => handleStatusChange("completed")}
                disabled={updateEncounter.isPending}
                className="rounded-lg bg-green-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-green-700 disabled:opacity-50"
              >
                {t("completeConsultation")}
              </button>
              <button
                onClick={() => setShowAdmitForm(true)}
                className="rounded-lg bg-purple-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-purple-700 disabled:opacity-50"
              >
                {t("admitInpatient")}
              </button>
            </>
          )}
          <span className="text-xs text-muted-foreground">{t("queueNumberValue", { number: encounter.queue_number ?? "-" })}</span>
        </div>
      </div>

      {showAdmitForm && (
        <AdmitToIPDPanel
          encounter={encounter}
          onCancel={() => setShowAdmitForm(false)}
          onAdmitted={() => router.push("/ipd")}
        />
      )}

      {/* ── Tabs ── */}
      <div className="border-b border-border">
        <div className="flex gap-0 overflow-x-auto">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors",
                  activeTab === tab.id
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon className="h-4 w-4" />
                {t(tab.labelKey)}
              </button>
            );
          })}
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════════
          TAB: VITALS
      ══════════════════════════════════════════════════════════════════ */}
      {activeTab === "vitals" && (
        <div className="space-y-4">
          {/* Previous vitals */}
          {vitals && vitals.length > 0 && (
            <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
              <h3 className="mb-4 text-sm font-semibold text-foreground">{t("latestVitals")}</h3>
              {(() => {
                const v = vitals[0];
                if (!v) return null;
                return (
                  <>
                    {v.is_critical && (
                      <div className="mb-3 rounded-lg border border-red-300 bg-red-50 px-3 py-2 dark:border-red-800 dark:bg-red-950">
                        <p className="flex items-center gap-2 text-xs font-semibold text-red-600 dark:text-red-400">
                          <AlertTriangle className="h-4 w-4" />
                          {t("criticalLabel")} {v.critical_alerts}
                        </p>
                      </div>
                    )}
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                      {v.systolic_bp && (
                        <VitalCard icon={Heart} label={t("bloodPressureShort")} value={`${v.systolic_bp}/${v.diastolic_bp}`} unit="mmHg" />
                      )}
                      {v.heart_rate && (
                        <VitalCard icon={Activity} label={t("heartRate")} value={String(v.heart_rate)} unit="bpm" />
                      )}
                      {v.temperature && (
                        <VitalCard icon={Thermometer} label={t("temperatureShort")} value={String(v.temperature)} unit="°C" />
                      )}
                      {v.respiratory_rate && (
                        <VitalCard icon={Wind} label={t("respiratoryRateShort")} value={String(v.respiratory_rate)} unit="/min" />
                      )}
                      {v.oxygen_saturation && (
                        <VitalCard icon={Droplets} label={t("oxygenSaturationShort")} value={String(v.oxygen_saturation)} unit="%" />
                      )}
                      {v.weight_kg && (
                        <VitalCard icon={Scale} label={t("weight")} value={String(v.weight_kg)} unit="kg" />
                      )}
                      {v.height_cm && (
                        <VitalCard icon={Ruler} label={t("height")} value={String(v.height_cm)} unit="cm" />
                      )}
                      {v.pain_score !== null && v.pain_score !== undefined && (
                        <VitalCard icon={AlertTriangle} label={t("pain")} value={String(v.pain_score)} unit="/10" />
                      )}
                    </div>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {t("recordedAt", { date: formatDateTime(v.recorded_at) })}
                    </p>
                  </>
                );
              })()}
            </div>
          )}

          {/* Record vitals form */}
          <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
            <h3 className="mb-4 text-sm font-semibold text-foreground">{t("recordVitals")}</h3>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
              <VitalsInput label={t("systolicBloodPressure")} unit="mmHg" value={vitalsForm.systolic_bp}
                onChange={(v) => setVitalsForm((f) => ({ ...f, systolic_bp: v }))} />
              <VitalsInput label={t("diastolicBloodPressure")} unit="mmHg" value={vitalsForm.diastolic_bp}
                onChange={(v) => setVitalsForm((f) => ({ ...f, diastolic_bp: v }))} />
              <VitalsInput label={t("heartRate")} unit="bpm" value={vitalsForm.heart_rate}
                onChange={(v) => setVitalsForm((f) => ({ ...f, heart_rate: v }))} />
              <VitalsInput label={t("temperature")} unit="°C" value={vitalsForm.temperature}
                onChange={(v) => setVitalsForm((f) => ({ ...f, temperature: v }))} />
              <VitalsInput label={t("respiratoryRate")} unit="/min" value={vitalsForm.respiratory_rate}
                onChange={(v) => setVitalsForm((f) => ({ ...f, respiratory_rate: v }))} />
              <VitalsInput label={t("oxygenSaturationShort")} unit="%" value={vitalsForm.oxygen_saturation}
                onChange={(v) => setVitalsForm((f) => ({ ...f, oxygen_saturation: v }))} />
              <VitalsInput label={t("weight")} unit="kg" value={vitalsForm.weight_kg}
                onChange={(v) => setVitalsForm((f) => ({ ...f, weight_kg: v }))} />
              <VitalsInput label={t("height")} unit="cm" value={vitalsForm.height_cm}
                onChange={(v) => setVitalsForm((f) => ({ ...f, height_cm: v }))} />
              <VitalsInput label={t("painScore")} unit="/10" value={vitalsForm.pain_score}
                onChange={(v) => setVitalsForm((f) => ({ ...f, pain_score: v }))} />
              <VitalsInput label={t("bloodGlucose")} unit="mmol/L" value={vitalsForm.blood_glucose}
                onChange={(v) => setVitalsForm((f) => ({ ...f, blood_glucose: v }))} />
            </div>
            <div className="mt-4 flex items-center justify-between">
              <button onClick={() => setActiveTab("diagnoses")} className="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors">
                {t("nextDiagnoses")}
              </button>
              <button
                onClick={handleVitalsSubmit}
                disabled={vitalsSubmitting}
                className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50"
              >
                {vitalsSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Activity className="h-4 w-4" />}
                {t("saveVitals")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          TAB: DIAGNOSES (ICD-10)
      ══════════════════════════════════════════════════════════════════ */}
      {activeTab === "diagnoses" && (
        <div className="space-y-4">
          {/* Existing diagnoses */}
          {diagnoses && diagnoses.length > 0 && (
            <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
              <div className="border-b border-border px-5 py-3">
                <h3 className="text-sm font-semibold text-foreground">{t("diagnosesCount", { count: diagnoses.length })}</h3>
              </div>
              <div className="divide-y divide-border">
                {diagnoses.map((d) => (
                  <div key={d.id} className="flex items-start justify-between gap-3 px-5 py-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-primary">{d.icd10_code}</span>
                        <span className="text-sm font-medium text-foreground">{d.icd10_description}</span>
                      </div>
                      {d.notes && <p className="mt-0.5 text-xs text-muted-foreground">{d.notes}</p>}
                    </div>
                    <div className="flex flex-shrink-0 gap-1">
                      <span className={cn(
                        "rounded px-1.5 py-0.5 text-[10px] font-medium",
                        d.diagnosis_type === "primary" ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300" : "bg-muted text-muted-foreground"
                      )}>
                        {td(d.diagnosis_type === "ruled_out" ? "ruledOut" : d.diagnosis_type)}
                      </span>
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                        {td(d.certainty === "differential" ? "differentialCertainty" : d.certainty)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Add diagnosis form */}
          <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
            <h3 className="mb-4 text-sm font-semibold text-foreground">{t("addDiagnosisIcd10")}</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <FormInput label={td("icd10Code")} placeholder={t("icd10CodePlaceholder")} value={diagForm.icd10_code}
                onChange={(v) => setDiagForm((f) => ({ ...f, icd10_code: v }))} />
              <FormInput label={t("description")} placeholder={t("diagnosisDescriptionPlaceholder")} value={diagForm.icd10_description}
                onChange={(v) => setDiagForm((f) => ({ ...f, icd10_description: v }))} />
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{td("diagnosisType")}</label>
                <select value={diagForm.diagnosis_type} onChange={(e) => setDiagForm((f) => ({ ...f, diagnosis_type: e.target.value as DiagnosisType }))}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30">
                  <option value="primary">{td("primary")}</option>
                  <option value="secondary">{td("secondary")}</option>
                  <option value="differential">{td("differential")}</option>
                  <option value="ruled_out">{td("ruledOut")}</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{td("certainty")}</label>
                <select value={diagForm.certainty} onChange={(e) => setDiagForm((f) => ({ ...f, certainty: e.target.value }))}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30">
                  <option value="confirmed">{td("confirmed")}</option>
                  <option value="provisional">{td("provisional")}</option>
                  <option value="differential">{td("differentialCertainty")}</option>
                  <option value="refuted">{td("refuted")}</option>
                </select>
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{t("clinicalNotes")}</label>
                <textarea value={diagForm.notes} onChange={(e) => setDiagForm((f) => ({ ...f, notes: e.target.value }))}
                  rows={2} placeholder={t("optionalNotesPlaceholder")}
                  className="w-full resize-none rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30" />
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between">
              <button onClick={() => setActiveTab("vitals")} className="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors">
                {t("backVitals")}
              </button>
              <button onClick={() => setActiveTab("prescriptions")} className="flex items-center gap-1.5 rounded-lg border border-primary px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10 transition-colors mr-2">
                {t("nextPrescriptions")} <ChevronRight className="h-4 w-4" />
              </button>
              <button onClick={handleDiagSubmit} disabled={diagSubmitting}
                className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50">
                {diagSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                {td("add")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          TAB: PRESCRIPTIONS
      ══════════════════════════════════════════════════════════════════ */}
      {activeTab === "prescriptions" && (
        <div className="space-y-4">
          {/* Drug interaction alerts */}
          {rxInteractions.length > 0 && (
            <div className="rounded-xl border border-orange-300 bg-orange-50 p-4 dark:border-orange-800 dark:bg-orange-950">
              <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold text-orange-700 dark:text-orange-300">
                <AlertTriangle className="h-4 w-4" /> {tp("interactionWarning")}
              </h4>
              {rxInteractions.map((ix, i) => (
                <div key={i} className={cn("mb-1 rounded px-2 py-1 text-xs",
                  ix.severity === "critical" ? "bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300" :
                  ix.severity === "major" ? "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300" :
                  "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
                )}>
                  <strong>{ix.severity.toUpperCase()}</strong> · {ix.interacting_drug}: {ix.description}
                </div>
              ))}
            </div>
          )}

          {/* Existing prescriptions */}
          {prescriptions && prescriptions.length > 0 && (
            <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
              <div className="border-b border-border px-5 py-3">
                <h3 className="text-sm font-semibold text-foreground">{t("prescriptionsCount", { count: prescriptions.length })}</h3>
              </div>
              <div className="divide-y divide-border">
                {prescriptions.map((rx) => (
                  <div key={rx.id} className="flex items-start justify-between gap-3 px-5 py-3">
                    <div>
                      <p className="font-semibold text-foreground">{rx.drug_name}</p>
                      <DrugStockBadge
                        className="mt-1"
                        drugName={rx.drug_name}
                        genericName={rx.generic_name}
                        requiredQuantity={rx.quantity}
                      />
                      <p className="mt-1 text-xs text-muted-foreground">
                        {rx.dosage} · {routeLabels[rx.route] ?? rx.route} · {frequencyLabels[rx.frequency] ?? rx.frequency}
                        {rx.duration_days && ` · ${t("durationDaysValue", { count: rx.duration_days })}`}
                      </p>
                      {rx.instructions && <p className="mt-0.5 text-xs italic text-muted-foreground">{rx.instructions}</p>}
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {rx.status !== "dispensed" && (
                        <Link href={`/pharmacy?encounter_id=${encounterId}&drug=${encodeURIComponent(rx.drug_name)}&qty=${rx.quantity ?? ""}`}
                          className="inline-flex items-center gap-1 rounded-full bg-green-600 px-3 py-1 text-xs font-semibold text-white shadow animate-pulse hover:animate-none hover:bg-green-700 transition-all">
                          {t("dispense")}
                        </Link>
                      )}
                      <span className={cn("rounded px-2 py-0.5 text-xs font-medium",
                        rx.status === "dispensed" ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300" :
                        "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
                      )}>
                        {t(`prescriptionStatus.${rx.status}`)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* New prescription form */}
          <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
            <h3 className="mb-4 text-sm font-semibold text-foreground">{t("newPrescription")}</h3>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <div className="sm:col-span-2 lg:col-span-3">
                <DrugAutocomplete
                  onSelect={(drugName, genericName, _isKeml, _stock, _unit, strength) => {
                    setRxForm((f) => ({ ...f, drug_name: drugName, dosage: strength || f.dosage }));
                    setSelectedDrug({ name: drugName, generic: genericName });
                  }}
                />
                {selectedDrug && (
                  <DrugStockBadge
                    className="mt-2"
                    drugName={selectedDrug.name}
                    genericName={selectedDrug.generic}
                    requiredQuantity={Number(rxForm.quantity) || null}
                  />
                )}
              </div>
              <FormInput label={tp("dosage")} placeholder={tp("dosagePlaceholder")} value={rxForm.dosage}
                onChange={(v) => setRxForm((f) => ({ ...f, dosage: v }))} />
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{tp("route")}</label>
                <select value={rxForm.route} onChange={(e) => setRxForm((f) => ({ ...f, route: e.target.value }))}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30">
                  {Object.entries(routeLabels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{tp("frequency")}</label>
                <select value={rxForm.frequency} onChange={(e) => {
                  const freq = e.target.value;
                  const fm: Record<string, number> = { od:1, bd:2, tds:3, qds:4, prn:1, stat:1, nocte:1 };
                  const days = Number(rxForm.duration_days) || 0;
                  const qty = days ? Math.ceil((fm[freq] ?? 1) * days) : 0;
                  setRxForm((f) => ({ ...f, frequency: freq, ...(qty ? { quantity: String(qty) } : {}) }));
                }}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30">
                  {Object.entries(frequencyLabels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <FormInput label={tp("duration")} placeholder={t("durationPlaceholder")} value={rxForm.duration_days}
                onChange={(v) => {
                  const fm: Record<string, number> = { od:1, bd:2, tds:3, qds:4, prn:1, stat:1, nocte:1 };
                  const days = Number(v) || 0;
                  const qty = days ? Math.ceil((fm[rxForm.frequency] ?? 1) * days) : 0;
                  setRxForm((f) => ({ ...f, duration_days: v, ...(qty ? { quantity: String(qty) } : {}) }));
                }} />
              <FormInput label={tp("quantity")} placeholder={t("autoCalculated")} value={rxForm.quantity ?? ""}
                onChange={(v) => setRxForm((f) => ({ ...f, quantity: v }))} />
              <div className="sm:col-span-2">
                <FormInput label={tp("instructions")} placeholder={t("instructionsPlaceholder")} value={rxForm.instructions}
                  onChange={(v) => setRxForm((f) => ({ ...f, instructions: v }))} />
              </div>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">{t("interactionCheckNotice")}</p>
            <div className="mt-3 flex items-center justify-between">
              <button onClick={() => setActiveTab("diagnoses")} className="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors">
                {t("backDiagnoses")}
              </button>
              <button onClick={() => setActiveTab("lab")} className="flex items-center gap-1.5 rounded-lg border border-primary px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10 transition-colors mr-2">
                {t("nextLabOrders")} <ChevronRight className="h-4 w-4" />
              </button>
              <button onClick={handleRxSubmit} disabled={rxSubmitting}
                className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50">
                {rxSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Pill className="h-4 w-4" />}
                {t("prescribe")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          TAB: LAB ORDERS
          Automation: order saved → invoice line auto-added → GL DR AR / CR Lab Revenue
      ══════════════════════════════════════════════════════════════════ */}
      {activeTab === "lab" && (
        <div className="space-y-4">
          {labOrders && labOrders.length > 0 && (
            <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
              <div className="border-b border-border px-5 py-3">
                <h3 className="text-sm font-semibold text-foreground">{t("labOrdersCount", { count: labOrders.length })}</h3>
              </div>
              <div className="divide-y divide-border">
                {labOrders.map((order) => {
                  const tests = (order as typeof order & { tests?: LabTestRequest[] }).tests;
                  const testNames = tests?.map((test) => test.test_name).join(", ");

                  return (
                  <div key={order.id} className="flex items-center justify-between px-5 py-3">
                    <div>
                      <p className="font-medium text-foreground">{order.order_number} — {testNames || order.clinical_info || t("labTest")}</p>
                      <p className="text-xs text-muted-foreground">{formatDateTime(order.created_at)}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Link href={`/laboratory/${order.id}`} className="inline-flex items-center gap-1 rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground shadow animate-pulse hover:animate-none hover:bg-primary/90 transition-all">{t("viewInLab")}</Link>
                    <span className={cn("rounded px-2 py-0.5 text-xs font-medium",
                      order.status === "completed" ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300" :
                      order.status === "processing" ? "bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300" :
                      "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300"
                    )}>
                      {tl(order.status ?? "pending")}
                    </span>
                    </div>
                  </div>
                  );
                })}
              </div>
            </div>
          )}

          <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
            <h3 className="mb-1 text-sm font-semibold text-foreground">{t("orderLabTest")}</h3>
            <p className="mb-4 text-xs text-muted-foreground">{t("labAutomationNotice")}</p>
            <div className="grid gap-3 sm:grid-cols-2">
              <FormInput label={t("testNameRequiredLabel")} placeholder={t("testNamePlaceholder")} value={labForm.test_name}
                onChange={(v) => setLabForm((f) => ({ ...f, test_name: v }))} />
              <FormInput label={tl("testCode")} placeholder={t("testCodePlaceholder")} value={labForm.test_code}
                onChange={(v) => setLabForm((f) => ({ ...f, test_code: v }))} />
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{tl("priority")}</label>
                <select value={labForm.priority} onChange={(e) => setLabForm((f) => ({ ...f, priority: e.target.value as LabPriority }))}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30">
                  <option value="routine">{tl("routine")}</option>
                  <option value="urgent">{tl("urgent")}</option>
                  <option value="stat">{tl("stat")}</option>
                </select>
              </div>
              <FormInput label={tl("clinicalInfo")} placeholder={t("clinicalInfoPlaceholder")} value={labForm.clinical_info}
                onChange={(v) => setLabForm((f) => ({ ...f, clinical_info: v }))} />
              <FormInput label={t("costKes")} placeholder={t("costPlaceholder")} value={labForm.cost_kes}
                onChange={(v) => setLabForm((f) => ({ ...f, cost_kes: v }))} />
            </div>
            <div className="mt-3 flex items-center justify-between">
              <button onClick={() => setActiveTab("prescriptions")} className="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors">
                {t("backPrescriptions")}
              </button>
              <button onClick={() => setActiveTab("imaging")} className="flex items-center gap-1.5 rounded-lg border border-primary px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10 transition-colors mr-2">
                {t("nextImaging")} <ChevronRight className="h-4 w-4" />
              </button>
              <button onClick={handleLabSubmit} disabled={labSubmitting}
                className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50">
                {labSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <FlaskConical className="h-4 w-4" />}
                {t("orderTest")}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          TAB: IMAGING ORDERS
          Order saved -> appears in the Radiology worklist (schedule, perform, report)
      ══════════════════════════════════════════════════════════════════ */}
      {activeTab === "imaging" && (
        <div className="space-y-4">
          {imagingOrders.length === 0 ? (
            <p className="rounded-xl border border-border bg-card px-5 py-4 text-sm text-muted-foreground shadow-[var(--shadow-card)]">{t("noImagingOrders")}</p>
          ) : (
            <div className="rounded-xl border border-border bg-card shadow-[var(--shadow-card)]">
              <div className="border-b border-border px-5 py-3">
                <h3 className="text-sm font-semibold text-foreground">{t("imagingOrdersCount", { count: imagingOrders.length })}</h3>
              </div>
              <div className="divide-y divide-border">
                {imagingOrders.map((order) => (
                  <div key={order.id} className="flex items-center justify-between px-5 py-3">
                    <div>
                      <p className="font-medium text-foreground">{order.order_number} — {order.study_description}</p>
                      <p className="text-xs text-muted-foreground">
                        {tr(MODALITY_LABEL_KEY[order.modality])} · {order.body_part}
                        {order.laterality ? " · " + tr(LATERALITY_LABEL_KEY[order.laterality]) : ""}
                        {" · "}{tr(order.priority)}
                      </p>
                      <p className="text-xs text-muted-foreground">{formatDateTime(order.created_at)}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Link href={`/radiology/${order.id}`} className="inline-flex items-center gap-1 rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground shadow hover:bg-primary/90 transition-all">{t("viewInRadiology")}</Link>
                      <span className={cn("rounded px-2 py-0.5 text-xs font-medium", IMAGING_STATUS_STYLE[order.status])}>
                        {tr(IMAGING_STATUS_LABEL_KEY[order.status])}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
            <h3 className="mb-1 text-sm font-semibold text-foreground">{t("orderImagingStudy")}</h3>
            <p className="mb-4 text-xs text-muted-foreground">{t("imagingAutomationNotice")}</p>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{tr("modality")}</label>
                <select value={imagingForm.modality} onChange={(e) => setImagingForm((f) => ({ ...f, modality: e.target.value as ImagingModality }))}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30">
                  {MODALITIES.map((m) => (
                    <option key={m} value={m}>{tr(MODALITY_LABEL_KEY[m])}</option>
                  ))}
                </select>
              </div>
              <FormInput label={tr("bodyPart")} placeholder={tr("bodyPartPlaceholder")} value={imagingForm.body_part}
                onChange={(v) => setImagingForm((f) => ({ ...f, body_part: v }))} />
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{tr("laterality")}</label>
                <select value={imagingForm.laterality} onChange={(e) => setImagingForm((f) => ({ ...f, laterality: e.target.value as Laterality | "" }))}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30">
                  <option value="">{tr("notApplicable")}</option>
                  <option value="left">{tr("left")}</option>
                  <option value="right">{tr("right")}</option>
                  <option value="bilateral">{tr("bilateral")}</option>
                </select>
              </div>
              <FormInput label={tr("study")} placeholder={tr("studyDescriptionPlaceholder")} value={imagingForm.study_description}
                onChange={(v) => setImagingForm((f) => ({ ...f, study_description: v }))} />
              <FormInput label={tr("views")} placeholder={tr("viewsPlaceholder")} value={imagingForm.views_requested}
                onChange={(v) => setImagingForm((f) => ({ ...f, views_requested: v }))} />
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{tr("urgency")}</label>
                <select value={imagingForm.priority} onChange={(e) => setImagingForm((f) => ({ ...f, priority: e.target.value as ImagingPriority }))}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30">
                  <option value="routine">{tr("routine")}</option>
                  <option value="urgent">{tr("urgent")}</option>
                  <option value="stat">{tr("stat")}</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">{tr("pregnancyStatus")}</label>
                <select value={imagingForm.pregnancy_status} onChange={(e) => setImagingForm((f) => ({ ...f, pregnancy_status: e.target.value as PregnancyStatus }))}
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30">
                  <option value="na">{tr("notApplicable")}</option>
                  <option value="not_pregnant">{tr("pregnancy_not_pregnant")}</option>
                  <option value="pregnant">{tr("pregnancy_pregnant")}</option>
                  <option value="unknown">{tr("pregnancy_unknown")}</option>
                </select>
              </div>
              <label className="flex items-center gap-2 self-end pb-2 text-sm text-foreground">
                <input type="checkbox" checked={imagingForm.contrast_required}
                  onChange={(e) => setImagingForm((f) => ({ ...f, contrast_required: e.target.checked }))}
                  className="h-4 w-4 rounded border-border" />
                {tr("contrastRequired")}
              </label>
              <FormInput label={tr("indication")} placeholder={tr("indicationPlaceholder")} value={imagingForm.clinical_indication}
                onChange={(v) => setImagingForm((f) => ({ ...f, clinical_indication: v }))} />
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <button onClick={() => setActiveTab("lab")} className="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors">
                {t("backLabOrders")}
              </button>
              <div className="flex items-center gap-2">
                <button onClick={() => setActiveTab("billing")} className="flex items-center gap-1.5 rounded-lg border border-primary px-4 py-2 text-sm font-medium text-primary hover:bg-primary/10 transition-colors">
                  {t("nextBilling")} <ChevronRight className="h-4 w-4" />
                </button>
                <button onClick={handleImagingSubmit} disabled={imagingSubmitting}
                  className="flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground disabled:opacity-50">
                  {imagingSubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Scan className="h-4 w-4" />}
                  {t("orderImagingStudy")}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════
          TAB: BILLING
          Invoice was auto-generated when encounter was created
      ══════════════════════════════════════════════════════════════════ */}
      {activeTab === "billing" && (
        <div className="rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-foreground">{t("billingTab")}</h3>
            <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-semibold",
              encounter.billing_status === "paid" ? "bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300" :
              encounter.billing_status === "partial" ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300" :
              "bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300"
            )}>
              {t(`billingStatus.${encounter.billing_status ?? "pending"}`)}
            </span>
          </div>
          <p className="mb-4 text-sm text-muted-foreground">
            {t("billingAutomationNotice")}
          </p>

          {/* Consultation fee taken at reception, then the ordered services
              the patient must pay for before lab, x-ray or pharmacy release. */}
          <div className="mb-5">
            <ConsultationFeePanel encounterId={encounterId} />
          </div>
          <div className="mb-5 space-y-3">
            <h4 className="text-sm font-semibold text-foreground">
              {tb("pos.service")}
            </h4>
            <EncounterServiceCharges encounterId={encounterId} />
          </div>
          <div className="mt-4 flex items-center justify-between">
            <button onClick={() => setActiveTab("imaging")} className="flex items-center gap-1.5 rounded-lg border border-border px-4 py-2 text-sm font-medium text-muted-foreground hover:bg-muted transition-colors">
              {t("backImaging")}
            </button>
            <Link href="/billing"
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow animate-pulse hover:animate-none hover:bg-primary/90 transition-all">
              <CreditCard className="h-4 w-4" />
              {t("viewPayInvoice")}
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Reusable sub-components ───────────────────────────────────────────────

function VitalCard({ icon: Icon, label, value, unit }: {
  icon: LucideIcon; label: string; value: string; unit: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-background p-3">
      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <Icon className="h-3 w-3" />
        {label}
      </div>
      <p className="mt-1 text-lg font-bold text-foreground">
        {value} <span className="text-xs font-normal text-muted-foreground">{unit}</span>
      </p>
    </div>
  );
}

function VitalsInput({ label, unit, value, onChange }: {
  label: string; unit: string; value: string; onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-muted-foreground">
        {label} <span className="text-muted-foreground/60">({unit})</span>
      </label>
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
        placeholder="—"
      />
    </div>
  );
}

function FormInput({ label, placeholder, value, onChange }: {
  label: string; placeholder?: string; value: string; onChange: (v: string) => void;
}) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-muted-foreground">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
      />
    </div>
  );
}

