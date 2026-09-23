"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Activity,
  AlertTriangle,
  Ambulance,
  ArrowLeft,
  Clock,
  Heart,
  Siren,
  Stethoscope,
  UserCheck,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useEmergencyVisit,
  useTriageVisit,
  useAssignDoctor,
  useRecordDisposition,
  useDoctorsOnDuty,
} from "@/hooks/useEmergency";
import { useStaffDirectory } from "@/hooks/useHR";
import { useBeds, useWards } from "@/hooks/useIPD";
import { cn } from "@/lib/utils";
import type { EmergencyTriageCategory, TreatmentArea, DispositionType } from "@aifya/shared";

const TRIAGE_STYLES: Record<string, string> = {
  red: "bg-red-600 text-white",
  orange: "bg-orange-500 text-white",
  yellow: "bg-yellow-400 text-yellow-900",
  green: "bg-green-500 text-white",
  blue: "bg-blue-600 text-white",
};

export default function EmergencyVisitDetailPage() {
  const { visitId } = useParams<{ visitId: string }>();
  const t = useTranslations("emergency");
  const { data: visit, isLoading } = useEmergencyVisit(visitId);
  const { data: onDutyDoctors, isLoading: onDutyLoading } = useDoctorsOnDuty();
  const { data: staffDirectory } = useStaffDirectory("doctor");
  const { data: wards } = useWards();

  const onDutyList = onDutyDoctors ?? [];
  const onDutyById = new Map(onDutyList.map((doc) => [doc.id, doc]));
  const otherDoctors = (staffDirectory?.items ?? []).filter(
    (staff) => staff.is_active && !onDutyById.has(staff.id)
  );

  // Triage form state
  const [showTriage, setShowTriage] = useState(false);
  const [triageCategory, setEmergencyTriageCategory] = useState<EmergencyTriageCategory>("standard");
  const [triageScore, setTriageScore] = useState("");
  const [treatmentArea, setTreatmentArea] = useState<TreatmentArea | "">("");
  const [triageNotes, setTriageNotes] = useState("");

  // Assign doctor form state
  const [showAssign, setShowAssign] = useState(false);
  const [doctorId, setDoctorId] = useState("");

  // Disposition form state
  const [showDisposition, setShowDisposition] = useState(false);
  const [disposition, setDisposition] = useState<DispositionType>("discharge");
  const [dispositionNotes, setDispositionNotes] = useState("");
  const [wardId, setWardId] = useState("");
  const [bedId, setBedId] = useState("");
  const [admissionReason, setAdmissionReason] = useState("");
  const [receivingFacilityName, setReceivingFacilityName] = useState("");
  const [receivingFacilityMfl, setReceivingFacilityMfl] = useState("");
  const [transferReason, setTransferReason] = useState("");
  const [transferUrgency, setTransferUrgency] = useState<"emergency" | "urgent" | "routine">("urgent");

  const { data: availableBeds, isLoading: bedsLoading } = useBeds(
    wardId || undefined,
    wardId ? "available" : undefined
  );

  const triageMutation = useTriageVisit(visitId);
  const assignMutation = useAssignDoctor(visitId);
  const dispositionMutation = useRecordDisposition(visitId);

  if (isLoading) {
    return <div className="py-12 text-center text-muted-foreground">{t("loading")}</div>;
  }

  if (!visit) {
    return <div className="py-12 text-center text-muted-foreground">{t("notFound")}</div>;
  }

  const handleTriage = () => {
    triageMutation.mutate(
      {
        triage_category: triageCategory,
        triage_score: triageScore ? Number(triageScore) : null,
        treatment_area: treatmentArea || null,
        notes: triageNotes || null,
      },
      { onSuccess: () => setShowTriage(false) }
    );
  };

  const handleAssign = () => {
    if (!doctorId) return;
    assignMutation.mutate({ doctor_id: doctorId }, { onSuccess: () => setShowAssign(false) });
  };

  const handleWardChange = (nextWardId: string) => {
    setWardId(nextWardId);
    setBedId("");
  };

  const handleDisposition = () => {
    if (disposition === "admit" && (!wardId || !bedId)) return;
    if (disposition === "transfer" && !receivingFacilityName.trim()) return;
    dispositionMutation.mutate(
      {
        disposition,
        disposition_notes: dispositionNotes || null,
        admitted_to_ward_id: disposition === "admit" ? wardId : null,
        bed_id: disposition === "admit" ? bedId : null,
        admission_reason:
          disposition === "admit" && admissionReason.trim() ? admissionReason.trim() : null,
        receiving_facility_name:
          disposition === "transfer" && receivingFacilityName.trim()
            ? receivingFacilityName.trim()
            : null,
        receiving_facility_mfl:
          disposition === "transfer" && receivingFacilityMfl.trim()
            ? receivingFacilityMfl.trim()
            : null,
        transfer_reason:
          disposition === "transfer" && transferReason.trim() ? transferReason.trim() : null,
        transfer_urgency: disposition === "transfer" ? transferUrgency : "urgent",
      },
      { onSuccess: () => setShowDisposition(false) }
    );
  };

  const triageCategories: EmergencyTriageCategory[] = ["emergency", "urgent", "standard", "non_urgent", "dead"];
  const areas: TreatmentArea[] = ["resus", "acute", "sub_acute", "fast_track", "observation", "paediatric"];
  const dispositions: DispositionType[] = ["discharge", "admit", "transfer", "deceased", "left_ama"];
  const transferUrgencies = ["emergency", "urgent", "routine"] as const;

  return (
    <div className="space-y-6 p-6 lg:p-8 animate-[fade-in_0.3s_ease-out]">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link
          href="/emergency"
          className="rounded-md p-2 hover:bg-muted/50"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-foreground">
            {visit.visit_number}
          </h1>
          <p className="text-sm text-muted-foreground">{t("visitDetail")}</p>
        </div>
        {visit.triage_color && (
          <span
            className={cn(
              "rounded-full px-4 py-1.5 text-sm font-bold uppercase",
              TRIAGE_STYLES[visit.triage_color] || "bg-muted"
            )}
          >
            {visit.triage_category}
          </span>
        )}
      </div>

      {/* Flags */}
      <div className="flex gap-2">
        {visit.is_trauma && (
          <span className="inline-flex items-center gap-1 rounded-md bg-red-100 px-3 py-1 text-sm font-bold text-red-700 dark:bg-red-950 dark:text-red-300">
            <Ambulance className="h-4 w-4" /> {t("trauma")}
          </span>
        )}
        {visit.is_resuscitation && (
          <span className="inline-flex items-center gap-1 rounded-md bg-rose-100 px-3 py-1 text-sm font-bold text-rose-700 dark:bg-rose-950 dark:text-rose-300">
            <Siren className="h-4 w-4" /> {t("resus")}
          </span>
        )}
        {visit.allergies_noted && (
          <span className="inline-flex items-center gap-1 rounded-md bg-amber-100 px-3 py-1 text-sm font-bold text-amber-700 dark:bg-amber-950 dark:text-amber-300">
            <AlertTriangle className="h-4 w-4" /> {t("allergies")}: {visit.allergies_noted}
          </span>
        )}
      </div>

      {/* Visit Info Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Arrival Info */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 flex items-center gap-2 font-semibold text-foreground">
            <Clock className="h-4 w-4" /> {t("arrivalInfo")}
          </h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">{t("arrivalTime")}</dt>
              <dd className="font-medium">{new Date(visit.arrival_time).toLocaleString()}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">{t("arrivalMode")}</dt>
              <dd className="font-medium">{t(`mode.${visit.arrival_mode}`)}</dd>
            </div>
            {visit.brought_by && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">{t("broughtBy")}</dt>
                <dd className="font-medium">{visit.brought_by}</dd>
              </div>
            )}
            <div className="flex justify-between">
              <dt className="text-muted-foreground">{t("statusLabel")}</dt>
              <dd className="font-medium">{t(`status.${visit.status}`)}</dd>
            </div>
            {visit.referral_id && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">{t("referralLinked")}</dt>
                <dd>
                  <Link href="/referrals" className="font-medium text-primary hover:underline">
                    {t("viewReferral")}
                  </Link>
                </dd>
              </div>
            )}
          </dl>
        </div>

        {/* Chief Complaint */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 flex items-center gap-2 font-semibold text-foreground">
            <Stethoscope className="h-4 w-4" /> {t("chiefComplaint")}
          </h3>
          <p className="text-sm text-foreground">{visit.chief_complaint}</p>
        </div>

        {/* Triage Info */}
        <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
          <h3 className="mb-3 flex items-center gap-2 font-semibold text-foreground">
            <Activity className="h-4 w-4" /> {t("triageInfo")}
          </h3>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">{t("category")}</dt>
              <dd>
                <span
                  className={cn(
                    "rounded-full px-2 py-0.5 text-xs font-bold uppercase",
                    TRIAGE_STYLES[visit.triage_color] || "bg-muted"
                  )}
                >
                  {visit.triage_category}
                </span>
              </dd>
            </div>
            {visit.triage_score != null && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">{t("tewsScore")}</dt>
                <dd className="font-medium">{visit.triage_score}</dd>
              </div>
            )}
            {visit.triage_time && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">{t("triageTime")}</dt>
                <dd className="font-medium">{new Date(visit.triage_time).toLocaleTimeString()}</dd>
              </div>
            )}
            {visit.treatment_area && (
              <div className="flex justify-between">
                <dt className="text-muted-foreground">{t("areaLabel")}</dt>
                <dd className="font-medium">{t(`area.${visit.treatment_area}`)}</dd>
              </div>
            )}
          </dl>
        </div>

        {/* Treatment Info */}
        {visit.treatment_started_at && (
          <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
            <h3 className="mb-3 flex items-center gap-2 font-semibold text-foreground">
              <Heart className="h-4 w-4" /> {t("treatmentInfo")}
            </h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">{t("treatmentStarted")}</dt>
                <dd className="font-medium">
                  {new Date(visit.treatment_started_at).toLocaleTimeString()}
                </dd>
              </div>
            </dl>
          </div>
        )}

        {/* Disposition Info */}
        {visit.disposition && (
          <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
            <h3 className="mb-3 flex items-center gap-2 font-semibold text-foreground">
              <UserCheck className="h-4 w-4" /> {t("dispositionInfo")}
            </h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between">
                <dt className="text-muted-foreground">{t("disposition")}</dt>
                <dd className="font-medium">{t(`dispositionType.${visit.disposition}`)}</dd>
              </div>
              {visit.disposition_time && (
                <div className="flex justify-between">
                  <dt className="text-muted-foreground">{t("dispositionTime")}</dt>
                  <dd className="font-medium">
                    {new Date(visit.disposition_time).toLocaleString()}
                  </dd>
                </div>
              )}
              {visit.disposition_notes && (
                <div>
                  <dt className="text-muted-foreground">{t("notes")}</dt>
                  <dd className="mt-1 text-foreground">
                    {visit.disposition_notes}
                  </dd>
                </div>
              )}
            </dl>
          </div>
        )}

        {/* Notes */}
        {visit.notes && (
          <div className="rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]">
            <h3 className="mb-3 font-semibold text-foreground">{t("notes")}</h3>
            <p className="whitespace-pre-wrap text-sm text-foreground">
              {visit.notes}
            </p>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-3">
        {visit.status === "arrived" && (
          <button
            onClick={() => setShowTriage(true)}
            className="rounded-md bg-orange-600 px-4 py-2 text-sm font-medium text-white hover:bg-orange-700"
          >
            {t("performTriage")}
          </button>
        )}
        {["arrived", "triaged"].includes(visit.status) && (
          <button
            onClick={() => setShowAssign(true)}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            {t("assignDoctor")}
          </button>
        )}
        {["triaged", "in_treatment", "observation"].includes(visit.status) && (
          <button
            onClick={() => setShowDisposition(true)}
            className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
          >
            {t("recordDisposition")}
          </button>
        )}
      </div>

      {/* Triage Form */}
      {showTriage && (
        <div className="rounded-lg border border-orange-200 bg-orange-50 p-4 dark:border-orange-800 dark:bg-orange-950">
          <h3 className="mb-4 font-semibold text-orange-800 dark:text-orange-200">
            {t("performTriage")}
          </h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium">{t("category")}</label>
              <select
                value={triageCategory}
                onChange={(e) => setEmergencyTriageCategory(e.target.value as EmergencyTriageCategory)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              >
                {triageCategories.map((c) => (
                  <option key={c} value={c}>
                    {t(`triageCategory.${c}`)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">{t("tewsScore")}</label>
              <input
                type="number"
                min={0}
                max={17}
                value={triageScore}
                onChange={(e) => setTriageScore(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                placeholder="0-17"
              />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">{t("treatmentArea")}</label>
              <select
                value={treatmentArea}
                onChange={(e) => setTreatmentArea(e.target.value as TreatmentArea)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              >
                <option value="">{t("selectArea")}</option>
                {areas.map((a) => (
                  <option key={a} value={a}>
                    {t(`area.${a}`)}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium">{t("notes")}</label>
              <input
                type="text"
                value={triageNotes}
                onChange={(e) => setTriageNotes(e.target.value)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              />
            </div>
          </div>
          <div className="mt-4 flex gap-2">
            <button
              onClick={handleTriage}
              disabled={triageMutation.isPending}
              className="rounded-md bg-orange-600 px-4 py-2 text-sm font-medium text-white hover:bg-orange-700 disabled:opacity-50"
            >
              {triageMutation.isPending ? t("saving") : t("saveTriage")}
            </button>
            <button
              onClick={() => setShowTriage(false)}
              className="rounded-md border border-input px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
            >
              {t("cancel")}
            </button>
          </div>
        </div>
      )}

      {/* Assign Doctor Form */}
      {showAssign && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-800 dark:bg-blue-950">
          <h3 className="mb-4 font-semibold text-blue-800 dark:text-blue-200">
            {t("assignDoctor")}
          </h3>
          <div>
            <label className="mb-1 block text-sm font-medium">{t("doctor")}</label>
            <select
              value={doctorId}
              onChange={(e) => setDoctorId(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
            >
              <option value="">{t("selectDoctor")}</option>
              {onDutyList.length > 0 && (
                <optgroup label={t("onDutyGroup")}>
                  {onDutyList.map((doc) => (
                    <option key={doc.id} value={doc.id}>
                      {doc.title ? doc.title + " " : ""}{doc.first_name} {doc.last_name}
                      {doc.shift_name ? " (" + doc.shift_name + ")" : ""}
                      {doc.specialization ? " - " + doc.specialization : ""}
                    </option>
                  ))}
                </optgroup>
              )}
              {otherDoctors.length > 0 && (
                <optgroup label={t("otherDoctorsGroup")}>
                  {otherDoctors.map((staff) => (
                    <option key={staff.id} value={staff.id}>
                      {staff.title ? staff.title + " " : ""}{staff.first_name} {staff.last_name}
                      {staff.specialization ? " - " + staff.specialization : ""}
                    </option>
                  ))}
                </optgroup>
              )}
            </select>
            {!onDutyLoading && onDutyList.length === 0 && (
              <p className="mt-2 text-sm text-muted-foreground">{t("noDoctorsOnDuty")}</p>
            )}
          </div>
          <div className="mt-4 flex gap-2">
            <button
              onClick={handleAssign}
              disabled={assignMutation.isPending || !doctorId}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
            >
              {assignMutation.isPending ? t("saving") : t("assign")}
            </button>
            <button
              onClick={() => setShowAssign(false)}
              className="rounded-md border border-input px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
            >
              {t("cancel")}
            </button>
          </div>
        </div>
      )}

      {/* Disposition Form */}
      {showDisposition && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-950">
          <h3 className="mb-4 font-semibold text-green-800 dark:text-green-200">
            {t("recordDisposition")}
          </h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium">{t("disposition")}</label>
              <select
                value={disposition}
                onChange={(e) => setDisposition(e.target.value as DispositionType)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
              >
                {dispositions.map((d) => (
                  <option key={d} value={d}>
                    {t(`dispositionType.${d}`)}
                  </option>
                ))}
              </select>
            </div>
            {disposition === "admit" && (
              <>
                <div>
                  <label className="mb-1 block text-sm font-medium">{t("ward")}</label>
                  <select
                    value={wardId}
                    onChange={(e) => handleWardChange(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                  >
                    <option value="">{t("selectWard")}</option>
                    {wards
                      ?.filter((ward) => ward.is_active && ward.available_beds > 0)
                      .map((ward) => (
                        <option key={ward.id} value={ward.id}>
                          {ward.name} ({t("bedsAvailable", { count: ward.available_beds })})
                        </option>
                      ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">{t("bed")}</label>
                  <select
                    value={bedId}
                    onChange={(e) => setBedId(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                    disabled={!wardId || bedsLoading}
                  >
                    <option value="">{t("selectBed")}</option>
                    {(availableBeds ?? [])
                      .filter((bed) => bed.ward_id === wardId)
                      .map((bed) => (
                        <option key={bed.id} value={bed.id}>
                          {bed.bed_number}
                        </option>
                      ))}
                  </select>
                  {wardId && !bedsLoading &&
                    !(availableBeds ?? []).some((bed) => bed.ward_id === wardId) && (
                      <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
                        {t("noAvailableBeds")}
                      </p>
                    )}
                </div>
                <div className="sm:col-span-2">
                  <label className="mb-1 block text-sm font-medium">{t("admissionReason")}</label>
                  <textarea
                    value={admissionReason}
                    onChange={(e) => setAdmissionReason(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                    rows={2}
                    placeholder={visit.chief_complaint || undefined}
                  />
                </div>
              </>
            )}
            {disposition === "transfer" && (
              <>
                <div>
                  <label className="mb-1 block text-sm font-medium">{t("receivingFacility")}</label>
                  <input
                    type="text"
                    value={receivingFacilityName}
                    onChange={(e) => setReceivingFacilityName(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                    placeholder={t("receivingFacilityPlaceholder")}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">{t("receivingFacilityMfl")}</label>
                  <input
                    type="text"
                    value={receivingFacilityMfl}
                    onChange={(e) => setReceivingFacilityMfl(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                    placeholder={t("mflPlaceholder")}
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="mb-1 block text-sm font-medium">{t("transferUrgency")}</label>
                  <select
                    value={transferUrgency}
                    onChange={(e) =>
                      setTransferUrgency(e.target.value as "emergency" | "urgent" | "routine")
                    }
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                  >
                    {transferUrgencies.map((urgency) => (
                      <option key={urgency} value={urgency}>
                        {t(`urgency.${urgency}`)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="sm:col-span-2">
                  <label className="mb-1 block text-sm font-medium">{t("transferReason")}</label>
                  <textarea
                    value={transferReason}
                    onChange={(e) => setTransferReason(e.target.value)}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                    rows={2}
                    placeholder={visit.chief_complaint || undefined}
                  />
                </div>
              </>
            )}

              <div className="sm:col-span-2">
                <label className="mb-1 block text-sm font-medium">{t("dispositionNotes")}</label>
                <textarea
                  value={dispositionNotes}
                  onChange={(e) => setDispositionNotes(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
                  rows={3}
                />
              </div>
            </div>
          <div className="mt-4 flex gap-2">
            <button
              onClick={handleDisposition}
              disabled={
                dispositionMutation.isPending ||
                (disposition === "admit" && (!wardId || !bedId)) ||
                (disposition === "transfer" && !receivingFacilityName.trim())
              }
              className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
            >
              {dispositionMutation.isPending ? t("saving") : t("saveDisposition")}
            </button>
            <button
              onClick={() => setShowDisposition(false)}
              className="rounded-md border border-input px-4 py-2 text-sm font-medium text-foreground hover:bg-muted/50"
            >
              {t("cancel")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
