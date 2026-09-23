"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Heart,
  ArrowLeft,
  Baby,
  Calendar,
  Activity,
  Stethoscope,
  CheckCircle,
} from "lucide-react";
import { Link } from "@/i18n/routing";
import {
  useANCProfileDetail,
  useAddANCVisit,
  useRecordDelivery,
} from "@/hooks/useMCH";
import { ApiError } from "@/lib/api-client";
import { formatDateTime } from "@/lib/utils";
import { cn } from "@/lib/utils";

/**
 * Read a numeric field and check it against the bounds the API enforces.
 *
 * @param raw - Raw input value
 * @param min - Smallest value the API accepts
 * @param max - Largest value the API accepts
 * @returns Parsed number, null when the field is blank, or "invalid"
 */
function parseBounded(
  raw: string,
  min: number,
  max: number
): number | null | "invalid" {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const value = Number(trimmed);
  if (!Number.isFinite(value) || value < min || value > max) return "invalid";
  return value;
}

/**
 * ANC profile detail page — shows pregnancy info, ANC visits timeline,
 * ANC visit form, delivery form, and delivery record.
 *
 * @returns ANC profile detail page
 */
export default function ANCProfileDetailPage() {
  const params = useParams();
  const profileId = params.profileId as string;
  const t = useTranslations("mch");
  const tc = useTranslations("common");

  const { data: detail, isLoading } = useANCProfileDetail(profileId);
  const addVisit = useAddANCVisit();
  const recordDelivery = useRecordDelivery();

  // Visit form state
  const [showVisitForm, setShowVisitForm] = useState(false);
  const [visitDate, setVisitDate] = useState("");
  const [gestationWeeks, setGestationWeeks] = useState("");
  const [weightKg, setWeightKg] = useState("");
  const [bpSystolic, setBpSystolic] = useState("");
  const [bpDiastolic, setBpDiastolic] = useState("");
  const [fundalHeight, setFundalHeight] = useState("");
  const [fetalHR, setFetalHR] = useState("");
  const [fetalPresentation, setFetalPresentation] = useState("");
  const [hbLevel, setHbLevel] = useState("");
  const [urineProtein, setUrineProtein] = useState("");
  const [ironFolate, setIronFolate] = useState(false);
  const [tetanusDose, setTetanusDose] = useState("");
  const [iptDose, setIptDose] = useState("");
  const [birthPlan, setBirthPlan] = useState(false);
  const [dangerSigns, setDangerSigns] = useState(false);
  const [nextVisitDate, setNextVisitDate] = useState("");
  const [visitNotes, setVisitNotes] = useState("");
  const [visitError, setVisitError] = useState("");

  // Delivery form state
  const [showDeliveryForm, setShowDeliveryForm] = useState(false);
  const [deliveryDate, setDeliveryDate] = useState("");
  const [deliveryMode, setDeliveryMode] = useState("svd");
  const [deliveryGestation, setDeliveryGestation] = useState("");
  const [babyOutcome, setBabyOutcome] = useState("live_birth");
  const [babySex, setBabySex] = useState("");
  const [birthWeight, setBirthWeight] = useState("");
  const [apgar1, setApgar1] = useState("");
  const [apgar5, setApgar5] = useState("");
  const [skinToSkin, setSkinToSkin] = useState(false);
  const [breastfed1hr, setBreastfed1hr] = useState(false);
  const [vitaminK, setVitaminK] = useState(false);
  const [deliveryNotes, setDeliveryNotes] = useState("");
  const [deliveryError, setDeliveryError] = useState("");

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        {tc("loading")}
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
        <p>{t("profileNotFound")}</p>
        <Link href="/mch" className="mt-4 text-primary hover:underline">
          {t("backToDashboard")}
        </Link>
      </div>
    );
  }

  const { profile, visits, delivery } = detail;

  /**
   * Validate the ANC visit form and record the visit.
   * Keeps the form open and shows the reason when the API rejects a value.
   */
  const handleAddVisit = async () => {
    if (!visitDate) return;

    const gestation = parseBounded(gestationWeeks, 1, 45);
    if (gestation === "invalid") {
      setVisitError(
        t("outOfRange", { field: t("gestationWeeks"), min: 1, max: 45 })
      );
      return;
    }
    const weight = parseBounded(weightKg, 20, 300);
    if (weight === "invalid") {
      setVisitError(t("outOfRange", { field: t("weight"), min: 20, max: 300 }));
      return;
    }
    const systolic = parseBounded(bpSystolic, 50, 300);
    const diastolic = parseBounded(bpDiastolic, 20, 200);
    if (systolic === "invalid" || diastolic === "invalid") {
      setVisitError(t("bloodPressureRange"));
      return;
    }
    const fundal = parseBounded(fundalHeight, 0, 50);
    if (fundal === "invalid") {
      setVisitError(
        t("outOfRange", { field: t("fundalHeight"), min: 0, max: 50 })
      );
      return;
    }
    const fetalHeart = parseBounded(fetalHR, 60, 220);
    if (fetalHeart === "invalid") {
      setVisitError(
        t("outOfRange", { field: t("fetalHeartRate"), min: 60, max: 220 })
      );
      return;
    }
    const haemoglobin = parseBounded(hbLevel, 1, 25);
    if (haemoglobin === "invalid") {
      setVisitError(
        t("outOfRange", { field: t("haemoglobin"), min: 1, max: 25 })
      );
      return;
    }

    setVisitError("");
    try {
      await addVisit.mutateAsync({
        anc_profile_id: profile.id,
        visit_date: visitDate,
        gestation_weeks: gestation ?? undefined,
        weight_kg: weight ?? undefined,
        bp_systolic: systolic ?? undefined,
        bp_diastolic: diastolic ?? undefined,
        fundal_height_cm: fundal ?? undefined,
        fetal_heart_rate: fetalHeart ?? undefined,
        fetal_presentation: (fetalPresentation as "cephalic" | "breech" | "transverse" | "oblique") || undefined,
        hb_level: haemoglobin ?? undefined,
        urine_protein: (urineProtein as "nil" | "trace" | "1+" | "2+" | "3+" | "4+") || undefined,
        iron_folate_given: ironFolate,
        tetanus_dose: (tetanusDose as "TT1" | "TT2" | "TT3" | "TT4" | "TT5") || undefined,
        ipt_malaria_dose: (iptDose as "IPT1" | "IPT2" | "IPT3") || undefined,
        birth_plan_discussed: birthPlan,
        danger_signs_counselled: dangerSigns,
        next_visit_date: nextVisitDate || undefined,
        clinical_notes: visitNotes || undefined,
      });
      setShowVisitForm(false);
    } catch (error) {
      setVisitError(
        error instanceof ApiError && error.message
          ? error.message
          : tc("retrySync")
      );
    }
  };

  /**
   * Validate the delivery form and record the delivery.
   * Keeps the form open and shows the reason when the API rejects a value.
   */
  const handleRecordDelivery = async () => {
    if (!deliveryDate || !babyOutcome) return;

    const gestation = parseBounded(deliveryGestation, 20, 45);
    if (gestation === "invalid") {
      setDeliveryError(
        t("outOfRange", { field: t("gestationWeeks"), min: 20, max: 45 })
      );
      return;
    }
    const weight = parseBounded(birthWeight, 200, 7000);
    if (weight === "invalid") {
      setDeliveryError(
        t("outOfRange", { field: t("birthWeight"), min: 200, max: 7000 })
      );
      return;
    }
    const apgarOne = parseBounded(apgar1, 0, 10);
    const apgarFive = parseBounded(apgar5, 0, 10);
    if (apgarOne === "invalid" || apgarFive === "invalid") {
      setDeliveryError(t("outOfRange", { field: t("apgar"), min: 0, max: 10 }));
      return;
    }

    setDeliveryError("");
    try {
      await recordDelivery.mutateAsync({
        anc_profile_id: profile.id,
        delivery_date: new Date(deliveryDate).toISOString(),
        gestation_weeks: gestation ?? undefined,
        mode_of_delivery: deliveryMode as "svd" | "assisted_vaginal" | "elective_cs" | "emergency_cs" | "breech",
        baby_outcome: babyOutcome as "live_birth" | "fresh_stillbirth" | "macerated_stillbirth",
        baby_sex: (babySex as "male" | "female") || undefined,
        birth_weight_grams: weight ?? undefined,
        apgar_1min: apgarOne ?? undefined,
        apgar_5min: apgarFive ?? undefined,
        skin_to_skin: skinToSkin,
        breastfed_within_1hr: breastfed1hr,
        vitamin_k_given: vitaminK,
        notes: deliveryNotes || undefined,
      });
      setShowDeliveryForm(false);
    } catch (error) {
      setDeliveryError(
        error instanceof ApiError && error.message
          ? error.message
          : tc("retrySync")
      );
    }
  };

  return (
    <div className="mx-auto max-w-4xl animate-[fade-in_0.3s_ease-out] p-6 lg:p-8">
      {/* Back link */}
      <Link
        href="/mch"
        className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("backToDashboard")}
      </Link>

      {/* Profile header */}
      <div className="mb-6 rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
        <div className="flex items-center gap-3">
          <Heart className="h-6 w-6 text-pink-500" />
          <h1 className="text-xl font-bold text-foreground">
            {profile.anc_number}
          </h1>
          <span
            className={cn(
              "rounded-full px-2.5 py-0.5 text-xs font-medium",
              profile.risk_level === "high"
                ? "bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200"
                : profile.risk_level === "moderate"
                  ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200"
                  : "bg-green-100 text-green-800 dark:bg-green-950 dark:text-green-200"
            )}
          >
            {t(`risk_${profile.risk_level}` as "risk_low" | "risk_moderate" | "risk_high")}
          </span>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
          <div>
            <span className="text-muted-foreground">{t("patient")}:</span>{" "}
            <span className="font-medium text-foreground">{detail.patient_name ?? "—"}</span>
            {detail.patient_mrn && (
              <span className="ml-2 font-mono text-xs text-muted-foreground">{detail.patient_mrn}</span>
            )}
          </div>
          <div>
            <span className="text-muted-foreground">{t("obstetricHistory")}:</span>{" "}
            <span className="font-medium text-foreground">
              G{profile.gravida}P{profile.parity} L{profile.living_children}
            </span>
          </div>
          {profile.expected_delivery_date && (
            <div>
              <span className="text-muted-foreground">{t("edd")}:</span>{" "}
              <span className="font-medium text-foreground">{profile.expected_delivery_date}</span>
            </div>
          )}
          {profile.lmp_date && (
            <div>
              <span className="text-muted-foreground">{t("lmp")}:</span>{" "}
              <span className="text-foreground">{profile.lmp_date}</span>
            </div>
          )}
          {profile.blood_group && (
            <div>
              <span className="text-muted-foreground">{t("bloodGroup")}:</span>{" "}
              <span className="text-foreground">{profile.blood_group}</span>
            </div>
          )}
          {profile.hiv_status && (
            <div>
              <span className="text-muted-foreground">{t("hivStatus")}:</span>{" "}
              <span className={cn("text-foreground", profile.hiv_status === "positive" && "text-red-600 dark:text-red-400")}>
                {t(`hiv_${profile.hiv_status}` as "hiv_positive" | "hiv_negative" | "hiv_unknown")}
              </span>
              {profile.on_art && (
                <span className="ml-1 text-xs text-green-600 dark:text-green-400">({t("onART")})</span>
              )}
            </div>
          )}
          {profile.rhesus && (
            <div>
              <span className="text-muted-foreground">{t("rhesus")}:</span>{" "}
              <span className={cn("text-foreground", profile.rhesus === "negative" && "text-amber-600")}>
                Rh {profile.rhesus}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Delivery record (if exists) */}
      {delivery && (
        <div className="mb-6 rounded-lg border border-green-300 bg-green-50 p-6 dark:border-green-800 dark:bg-green-950">
          <h2 className="mb-3 flex items-center gap-2 font-semibold text-green-800 dark:text-green-200">
            <Baby className="h-5 w-5" />
            {t("deliveryRecord")}
          </h2>
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
            <div>
              <span className="text-muted-foreground">{t("deliveryDate")}:</span>{" "}
              <span className="text-foreground">{formatDateTime(delivery.delivery_date)}</span>
            </div>
            <div>
              <span className="text-muted-foreground">{t("modeOfDelivery")}:</span>{" "}
              <span className="text-foreground">{t(`delivery_${delivery.mode_of_delivery}` as "delivery_svd" | "delivery_elective_cs" | "delivery_emergency_cs")}</span>
            </div>
            <div>
              <span className="text-muted-foreground">{t("babyOutcome")}:</span>{" "}
              <span className="text-foreground">{t(`outcome_${delivery.baby_outcome}` as "outcome_live_birth" | "outcome_fresh_stillbirth")}</span>
            </div>
            {delivery.baby_sex && (
              <div>
                <span className="text-muted-foreground">{t("babySex")}:</span>{" "}
                <span className="text-foreground">{t(delivery.baby_sex as "male" | "female")}</span>
              </div>
            )}
            {delivery.birth_weight_grams && (
              <div>
                <span className="text-muted-foreground">{t("birthWeight")}:</span>{" "}
                <span className="text-foreground">{delivery.birth_weight_grams}g</span>
              </div>
            )}
            {delivery.apgar_1min != null && (
              <div>
                <span className="text-muted-foreground">APGAR:</span>{" "}
                <span className="text-foreground">
                  {delivery.apgar_1min}/{delivery.apgar_5min}
                  {delivery.apgar_10min != null && `/${delivery.apgar_10min}`}
                </span>
              </div>
            )}
          </div>
          {/* Immediate newborn care checklist */}
          <div className="mt-3 flex flex-wrap gap-2">
            {delivery.skin_to_skin && <Badge label={t("skinToSkin")} />}
            {delivery.breastfed_within_1hr && <Badge label={t("breastfed1hr")} />}
            {delivery.vitamin_k_given && <Badge label={t("vitaminK")} />}
            {delivery.bcg_given && <Badge label="BCG" />}
            {delivery.opv_0_given && <Badge label="OPV-0" />}
          </div>
        </div>
      )}

      {/* Action buttons */}
      {profile.status === "active" && (
        <div className="mb-6 flex gap-3">
          <button
            onClick={() => setShowVisitForm(!showVisitForm)}
            className="rounded-lg bg-pink-600 px-4 py-2 text-sm font-medium text-white hover:bg-pink-700"
          >
            {t("addVisit")}
          </button>
          <button
            onClick={() => setShowDeliveryForm(!showDeliveryForm)}
            className="rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
          >
            {t("recordDelivery")}
          </button>
        </div>
      )}

      {/* ANC Visit form */}
      {showVisitForm && (
        <div className="mb-6 rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 flex items-center gap-2 font-semibold text-foreground">
            <Stethoscope className="h-5 w-5 text-pink-500" />
            {t("newANCVisit")}
          </h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("visitDate")} *</label>
              <input type="date" value={visitDate} onChange={(e) => setVisitDate(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("gestationWeeks")}</label>
              <input type="number" value={gestationWeeks} onChange={(e) => setGestationWeeks(e.target.value)} min="1" max="45"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("weight")} (kg)</label>
              <input type="number" value={weightKg} onChange={(e) => setWeightKg(e.target.value)} step="0.1"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("bpSystolic")}</label>
              <input type="number" value={bpSystolic} onChange={(e) => setBpSystolic(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("bpDiastolic")}</label>
              <input type="number" value={bpDiastolic} onChange={(e) => setBpDiastolic(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("fundalHeight")} (cm)</label>
              <input type="number" value={fundalHeight} onChange={(e) => setFundalHeight(e.target.value)} step="0.5"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("fetalHeartRate")}</label>
              <input type="number" value={fetalHR} onChange={(e) => setFetalHR(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("presentation")}</label>
              <select value={fetalPresentation} onChange={(e) => setFetalPresentation(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground">
                <option value="">—</option>
                <option value="cephalic">{t("cephalic")}</option>
                <option value="breech">{t("breechPresentation")}</option>
                <option value="transverse">{t("transverse")}</option>
                <option value="oblique">{t("oblique")}</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("haemoglobin")} (g/dL)</label>
              <input type="number" value={hbLevel} onChange={(e) => setHbLevel(e.target.value)} step="0.1"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("urineProtein")}</label>
              <select value={urineProtein} onChange={(e) => setUrineProtein(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground">
                <option value="">—</option>
                <option value="nil">Nil</option>
                <option value="trace">Trace</option>
                <option value="1+">1+</option>
                <option value="2+">2+</option>
                <option value="3+">3+</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("tetanus")}</label>
              <select value={tetanusDose} onChange={(e) => setTetanusDose(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground">
                <option value="">—</option>
                <option value="TT1">TT1</option>
                <option value="TT2">TT2</option>
                <option value="TT3">TT3</option>
                <option value="TT4">TT4</option>
                <option value="TT5">TT5</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("iptMalaria")}</label>
              <select value={iptDose} onChange={(e) => setIptDose(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground">
                <option value="">—</option>
                <option value="IPT1">IPT1</option>
                <option value="IPT2">IPT2</option>
                <option value="IPT3">IPT3</option>
              </select>
            </div>
          </div>
          {/* Checkboxes */}
          <div className="mt-4 flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input type="checkbox" checked={ironFolate} onChange={(e) => setIronFolate(e.target.checked)} className="h-4 w-4 rounded border-input" />
              {t("ironFolate")}
            </label>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input type="checkbox" checked={birthPlan} onChange={(e) => setBirthPlan(e.target.checked)} className="h-4 w-4 rounded border-input" />
              {t("birthPlanDiscussed")}
            </label>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input type="checkbox" checked={dangerSigns} onChange={(e) => setDangerSigns(e.target.checked)} className="h-4 w-4 rounded border-input" />
              {t("dangerSignsCounselled")}
            </label>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("nextVisitDate")}</label>
              <input type="date" value={nextVisitDate} onChange={(e) => setNextVisitDate(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{tc("notes")}</label>
              <textarea value={visitNotes} onChange={(e) => setVisitNotes(e.target.value)} rows={2}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
          </div>
          <button onClick={handleAddVisit} disabled={!visitDate || addVisit.isPending}
            className="mt-4 rounded-lg bg-pink-600 px-4 py-2 text-sm font-medium text-white hover:bg-pink-700 disabled:opacity-50">
            {addVisit.isPending ? tc("saving") : t("saveVisit")}
          </button>
          {visitError && (
            <p className="mt-3 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
              {visitError}
            </p>
          )}
        </div>
      )}

      {/* Delivery form */}
      {showDeliveryForm && (
        <div className="mb-6 rounded-xl border border-border bg-card p-6 shadow-[var(--shadow-card)]">
          <h2 className="mb-4 flex items-center gap-2 font-semibold text-foreground">
            <Baby className="h-5 w-5 text-green-500" />
            {t("recordDelivery")}
          </h2>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("deliveryDate")} *</label>
              <input type="datetime-local" value={deliveryDate} onChange={(e) => setDeliveryDate(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("modeOfDelivery")} *</label>
              <select value={deliveryMode} onChange={(e) => setDeliveryMode(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground">
                <option value="svd">{t("delivery_svd")}</option>
                <option value="assisted_vaginal">{t("delivery_assisted")}</option>
                <option value="elective_cs">{t("delivery_elective_cs")}</option>
                <option value="emergency_cs">{t("delivery_emergency_cs")}</option>
                <option value="breech">{t("delivery_breech")}</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("gestationWeeks")}</label>
              <input type="number" value={deliveryGestation} onChange={(e) => setDeliveryGestation(e.target.value)} min="20" max="45"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("babyOutcome")} *</label>
              <select value={babyOutcome} onChange={(e) => setBabyOutcome(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground">
                <option value="live_birth">{t("outcome_live_birth")}</option>
                <option value="fresh_stillbirth">{t("outcome_fresh_stillbirth")}</option>
                <option value="macerated_stillbirth">{t("outcome_macerated_stillbirth")}</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("babySex")}</label>
              <select value={babySex} onChange={(e) => setBabySex(e.target.value)}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground">
                <option value="">—</option>
                <option value="male">{t("male")}</option>
                <option value="female">{t("female")}</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">{t("birthWeight")} (g)</label>
              <input type="number" value={birthWeight} onChange={(e) => setBirthWeight(e.target.value)} min="200" max="7000"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">APGAR 1min</label>
              <input type="number" value={apgar1} onChange={(e) => setApgar1(e.target.value)} min="0" max="10"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
            <div>
              <label className="mb-1 block text-sm text-muted-foreground">APGAR 5min</label>
              <input type="number" value={apgar5} onChange={(e) => setApgar5(e.target.value)} min="0" max="10"
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input type="checkbox" checked={skinToSkin} onChange={(e) => setSkinToSkin(e.target.checked)} className="h-4 w-4 rounded border-input" />
              {t("skinToSkin")}
            </label>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input type="checkbox" checked={breastfed1hr} onChange={(e) => setBreastfed1hr(e.target.checked)} className="h-4 w-4 rounded border-input" />
              {t("breastfed1hr")}
            </label>
            <label className="flex items-center gap-2 text-sm text-foreground">
              <input type="checkbox" checked={vitaminK} onChange={(e) => setVitaminK(e.target.checked)} className="h-4 w-4 rounded border-input" />
              {t("vitaminK")}
            </label>
          </div>
          <div className="mt-4">
            <label className="mb-1 block text-sm text-muted-foreground">{tc("notes")}</label>
            <textarea value={deliveryNotes} onChange={(e) => setDeliveryNotes(e.target.value)} rows={2}
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground" />
          </div>
          <button onClick={handleRecordDelivery} disabled={!deliveryDate || recordDelivery.isPending}
            className="mt-4 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50">
            {recordDelivery.isPending ? tc("saving") : t("saveDelivery")}
          </button>
          {deliveryError && (
            <p className="mt-3 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
              {deliveryError}
            </p>
          )}
        </div>
      )}

      {/* Visits timeline */}
      <h2 className="mb-3 flex items-center gap-2 font-semibold text-foreground">
        <Activity className="h-5 w-5 text-pink-500" />
        {t("ancVisits")} ({visits.length})
      </h2>
      {visits.length === 0 ? (
        <p className="py-8 text-center text-muted-foreground">{t("noVisits")}</p>
      ) : (
        <div className="space-y-3">
          {visits.map((visit) => (
            <div
              key={visit.id}
              className={cn(
                "rounded-xl border border-border bg-card p-4 shadow-[var(--shadow-card)]",
                visit.bp_systolic && visit.bp_systolic >= 140 && "border-amber-400 dark:border-amber-700"
              )}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-foreground">
                  {t("visit")} #{visit.visit_number} — {visit.visit_date}
                </span>
                {visit.gestation_weeks && (
                  <span className="text-sm text-muted-foreground">
                    {visit.gestation_weeks} {t("weeks")}
                  </span>
                )}
              </div>
              <div className="mt-2 flex flex-wrap gap-4 text-sm text-muted-foreground">
                {visit.bp_systolic && (
                  <span className={cn(visit.bp_systolic >= 140 && "font-medium text-amber-600 dark:text-amber-400")}>
                    BP: {visit.bp_systolic}/{visit.bp_diastolic}
                  </span>
                )}
                {visit.weight_kg && <span>{t("weight")}: {visit.weight_kg}kg</span>}
                {visit.fundal_height_cm && <span>FH: {visit.fundal_height_cm}cm</span>}
                {visit.fetal_heart_rate && <span>FHR: {visit.fetal_heart_rate}bpm</span>}
                {visit.hb_level && (
                  <span className={cn(visit.hb_level < 10 && "text-amber-600 dark:text-amber-400")}>
                    Hb: {visit.hb_level}g/dL
                  </span>
                )}
                {visit.fetal_presentation && (
                  <span>{t("presentation")}: {t(visit.fetal_presentation as "cephalic" | "breech")}</span>
                )}
              </div>
              {/* Interventions */}
              <div className="mt-2 flex flex-wrap gap-2">
                {visit.iron_folate_given && <Badge label={t("ironFolate")} />}
                {visit.tetanus_dose && <Badge label={visit.tetanus_dose} />}
                {visit.ipt_malaria_dose && <Badge label={visit.ipt_malaria_dose} />}
                {visit.birth_plan_discussed && <Badge label={t("birthPlan")} />}
                {visit.danger_signs_counselled && <Badge label={t("dangerSigns")} />}
              </div>
              {visit.clinical_notes && (
                <p className="mt-2 text-xs text-muted-foreground">{visit.clinical_notes}</p>
              )}
              {visit.next_visit_date && (
                <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                  <Calendar className="h-3 w-3" />
                  {t("nextVisit")}: {visit.next_visit_date}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Small badge for interventions/checklist items.
 *
 * @param props - Badge props
 * @returns Badge component
 */
function Badge({ label }: { label: string }) {
  return (
    <span className="flex items-center gap-1 rounded bg-green-100 px-1.5 py-0.5 text-xs text-green-700 dark:bg-green-950 dark:text-green-300">
      <CheckCircle className="h-3 w-3" />
      {label}
    </span>
  );
}
