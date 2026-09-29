"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  FlaskConical,
  Loader2,
  Printer,
  Save,
} from "lucide-react";
import {
  useEncounterTests,
  useEncounterVitals,
  useRecordPointOfCareTest,
  useRecordVitals,
  useUpdateEncounter,
} from "@/hooks/useEncounters";
import { formatDateTime, receiptHref } from "@/lib/utils";
import type {
  Encounter,
  PointOfCareCategory,
  PointOfCareInterpretation,
  TriageCategory,
} from "@aifya/shared";

/** Bedside screening tests the OPD nurse commonly runs before the doctor. */
const POC_TESTS: readonly {
  code: string;
  nameKey: string;
  category: PointOfCareCategory;
  specimen: string | null;
}[] = [
  { code: "HIV", nameKey: "testsPocHiv", category: "rapid_diagnostic", specimen: "blood" },
  { code: "MRDT", nameKey: "testsPocMalaria", category: "rapid_diagnostic", specimen: "blood" },
  { code: "URIN", nameKey: "testsPocUrinalysis", category: "urinalysis", specimen: "urine" },
  { code: "PREG", nameKey: "testsPocPregnancy", category: "rapid_diagnostic", specimen: "urine" },
  { code: "GLU", nameKey: "testsPocGlucose", category: "screening", specimen: "blood" },
  { code: "HBSAG", nameKey: "testsPocHbsag", category: "rapid_diagnostic", specimen: "blood" },
];

const INTERPRETATIONS: readonly PointOfCareInterpretation[] = [
  "normal",
  "abnormal",
  "positive",
  "negative",
  "reactive",
  "non_reactive",
  "inconclusive",
];

const INTERPRETATION_LABEL_KEYS = {
  normal: "testsInterpretationNormal",
  abnormal: "testsInterpretationAbnormal",
  positive: "testsInterpretationPositive",
  negative: "testsInterpretationNegative",
  reactive: "testsInterpretationReactive",
  non_reactive: "testsInterpretationNonReactive",
  inconclusive: "testsInterpretationInconclusive",
} as const;

/** Triage categories the nurse can put a patient in, in queue order. */
const TRIAGE_OPTIONS = [
  { value: "emergency", labelKey: "triageEmergency" },
  { value: "urgent", labelKey: "triageUrgent" },
  { value: "standard", labelKey: "triageStandard" },
  { value: "non_urgent", labelKey: "triageNonUrgent" },
  { value: "dead", labelKey: "triageDead" },
] as const;

/**
 * The nurse's OPD assessment - everything taken before a doctor sees the patient.
 *
 * Two halves, neither of which diagnoses anything: the observations every OPD
 * visit takes (blood pressure, temperature, pulse, SpO2, height, weight,
 * respiratory rate, pain score, blood glucose), saved as the visit's vitals,
 * and the bedside screening tests (HIV, malaria RDT, urinalysis, pregnancy...)
 * which never touch the laboratory worklist.
 *
 * @param props - The encounter being assessed
 * @returns The OPD testing content
 */
export function OpdTestsPanel({ encounter }: { encounter: Encounter }) {
  const t = useTranslations("opd");
  const tv = useTranslations("vitals");
  const tc = useTranslations("common");

  // -- Measurements (written through the vitals endpoint) --
  const [systolic, setSystolic] = useState("");
  const [diastolic, setDiastolic] = useState("");
  const [pulse, setPulse] = useState("");
  const [temperature, setTemperature] = useState("");
  const [oxygen, setOxygen] = useState("");
  const [weight, setWeight] = useState("");
  const [height, setHeight] = useState("");
  const [respiratory, setRespiratory] = useState("");
  const [painScore, setPainScore] = useState("");
  const [glucose, setGlucose] = useState("");
  const [measureError, setMeasureError] = useState("");
  const [measureSaved, setMeasureSaved] = useState(false);

  // -- Screening test (point-of-care) --
  const [testCode, setTestCode] = useState("");
  const [customName, setCustomName] = useState("");
  const [result, setResult] = useState("");
  const [unit, setUnit] = useState("");
  const [interpretation, setInterpretation] = useState("");
  const [testNotes, setTestNotes] = useState("");
  const [testError, setTestError] = useState("");
  const [testSaved, setTestSaved] = useState(false);

  const { data: vitals } = useEncounterVitals(encounter.id);
  const { data: tests } = useEncounterTests(encounter.id);
  const recordVitals = useRecordVitals(encounter.id);
  const recordTest = useRecordPointOfCareTest(encounter.id);

  // -- Triage category (written through the encounter endpoint) --
  const [triage, setTriage] = useState<TriageCategory>(
    encounter.triage_category ?? "non_urgent",
  );
  const [triageError, setTriageError] = useState("");
  const [triageSaved, setTriageSaved] = useState(false);
  const updateEncounter = useUpdateEncounter(encounter.id);

  // The queue refetch replaces the encounter prop, so follow what the server
  // holds rather than keeping a stale local choice.
  useEffect(() => {
    setTriage(encounter.triage_category ?? "non_urgent");
  }, [encounter.triage_category]);

  /** Store the nurse triage decision so the queue shows the right priority. */
  const handleSaveTriage = () => {
    setTriageError("");
    setTriageSaved(false);
    updateEncounter.mutate(
      { triage_category: triage },
      {
        onSuccess: () => setTriageSaved(true),
        onError: (err: Error) =>
          setTriageError(err.message || t("triageFailed")),
      },
    );
  };

  const toNumber = (value: string): number | null => {
    const parsed = Number(value);
    return value.trim() !== "" && Number.isFinite(parsed) ? parsed : null;
  };

  const handleSaveMeasurements = () => {
    const payload = {
      encounter_id: encounter.id,
      patient_id: encounter.patient_id,
      systolic_bp: toNumber(systolic),
      diastolic_bp: toNumber(diastolic),
      heart_rate: toNumber(pulse),
      temperature: toNumber(temperature),
      oxygen_saturation: toNumber(oxygen),
      weight_kg: toNumber(weight),
      height_cm: toNumber(height),
      respiratory_rate: toNumber(respiratory),
      pain_score: toNumber(painScore),
      blood_glucose: toNumber(glucose),
    };
    const hasValue = [
      "systolic_bp",
      "diastolic_bp",
      "heart_rate",
      "temperature",
      "oxygen_saturation",
      "weight_kg",
      "height_cm",
      "respiratory_rate",
      "pain_score",
      "blood_glucose",
    ].some((key) => payload[key as keyof typeof payload] !== null);
    if (!hasValue) {
      setMeasureError(t("testsMeasurementsEmpty"));
      return;
    }
    setMeasureError("");
    setMeasureSaved(false);
    recordVitals.mutate(payload, {
      onSuccess: () => {
        setMeasureSaved(true);
        setSystolic("");
        setDiastolic("");
        setPulse("");
        setTemperature("");
        setOxygen("");
        setWeight("");
        setHeight("");
        setRespiratory("");
        setPainScore("");
        setGlucose("");
      },
      onError: (err: Error) => {
        setMeasureError(err.message || t("testsMeasurementsFailed"));
      },
    });
  };

  const handleSaveTest = () => {
    const preset = POC_TESTS.find((item) => item.code === testCode);
    const name = preset ? t(preset.nameKey) : customName.trim();
    if (!name) {
      setTestError(t("testsChooseTest"));
      return;
    }
    if (!result.trim()) {
      setTestError(t("testsResultRequired"));
      return;
    }
    setTestError("");
    setTestSaved(false);
    recordTest.mutate(
      {
        test_code: preset ? preset.code : name.slice(0, 50).toUpperCase().replace(/\s+/g, "_"),
        test_name: name,
        category: preset ? preset.category : "other",
        specimen_type: preset ? preset.specimen : null,
        result_value: result.trim(),
        result_unit: unit.trim() || null,
        interpretation:
          (interpretation as PointOfCareInterpretation) || null,
        notes: testNotes.trim() || null,
      },
      {
        onSuccess: () => {
          setTestSaved(true);
          setTestCode("");
          setCustomName("");
          setResult("");
          setUnit("");
          setInterpretation("");
          setTestNotes("");
        },
        onError: (err: Error) => {
          setTestError(err.message || t("testsFailed"));
        },
      }
    );
  };

  const fieldClasses =
    "w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-sm dark:border-border dark:bg-background disabled:cursor-not-allowed disabled:opacity-60";

  const latestVitals = vitals?.[0];

  return (
    <div className="space-y-4">
      {/* Triage category - the nurse decides how urgently this patient is seen. */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <div className="mb-1 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">
            {t("triage")}
          </h3>
        </div>
        <p className="mb-3 text-xs text-muted-foreground">{t("triageHint")}</p>
        <div className="flex flex-wrap items-center gap-2">
          <div className="w-full sm:w-64">
            <select
              value={triage}
              onChange={(event) => {
                setTriage(event.target.value as TriageCategory);
                setTriageSaved(false);
              }}
              aria-label={t("triage")}
              className={fieldClasses}
            >
              {TRIAGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {t(option.labelKey)}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={handleSaveTriage}
            disabled={updateEncounter.isPending}
            className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            {updateEncounter.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            {updateEncounter.isPending ? tc("loading") : tc("save")}
          </button>
          {triageSaved && (
            <span className="flex items-center gap-1 text-xs font-medium text-green-700 dark:text-green-300">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {t("triageSaved")}
            </span>
          )}
          {triageError && (
            <span className="text-xs text-red-600 dark:text-red-400">{triageError}</span>
          )}
        </div>
      </div>

      {/* Measurements */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <div className="mb-1 flex items-center gap-2">
          <Activity className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">
            {t("testsMeasurementsTitle")}
          </h3>
        </div>
        <p className="mb-4 text-xs text-muted-foreground">
          {t("testsMeasurementsHint")}
        </p>

        {latestVitals && (
          <div className="mb-4 flex flex-wrap gap-x-4 gap-y-1 rounded-lg bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
            <span>
              {t("bloodPressureShort")}: {latestVitals.systolic_bp ?? "-"}/
              {latestVitals.diastolic_bp ?? "-"}
            </span>
            <span>
              {t("heartRate")}: {latestVitals.heart_rate ?? "-"}
            </span>
            <span>
              {t("temperatureShort")}: {latestVitals.temperature ?? "-"}
            </span>
            <span>
              {t("weight")}: {latestVitals.weight_kg ?? "-"}
            </span>
            <span>
              {t("height")}: {latestVitals.height_cm ?? "-"}
            </span>
            <span>{formatDateTime(latestVitals.recorded_at)}</span>
          </div>
        )}

        {latestVitals?.report_url && (
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-green-400 bg-green-50 px-3 py-2 dark:border-green-700 dark:bg-green-950">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-green-800 dark:text-green-200">
                {tv("reportIssued")}: {latestVitals.report_number}
              </p>
              {latestVitals.summary && (
                <p className="mt-0.5 truncate text-xs text-green-800/80 dark:text-green-200/80">
                  {latestVitals.summary}
                </p>
              )}
              <p className="mt-0.5 text-[11px] text-green-800/70 dark:text-green-200/70">
                {tv("reportKept")}
              </p>
            </div>
            <a
              href={receiptHref(latestVitals.report_url)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex flex-shrink-0 items-center gap-1.5 rounded-lg border border-green-600 px-3 py-1.5 text-xs font-semibold text-green-800 hover:bg-green-100 dark:text-green-200"
            >
              <Printer className="h-3.5 w-3.5" />
              {tv("printReport")}
            </a>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("systolicBloodPressure")}
            </label>
            <input
              type="number"
              inputMode="numeric"
              value={systolic}
              onChange={(e) => setSystolic(e.target.value)}
              className={fieldClasses}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("diastolicBloodPressure")}
            </label>
            <input
              type="number"
              inputMode="numeric"
              value={diastolic}
              onChange={(e) => setDiastolic(e.target.value)}
              className={fieldClasses}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("testsPulse")}
            </label>
            <input
              type="number"
              inputMode="numeric"
              value={pulse}
              onChange={(e) => setPulse(e.target.value)}
              className={fieldClasses}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("testsTemperature")}
            </label>
            <input
              type="number"
              step="0.1"
              inputMode="decimal"
              value={temperature}
              onChange={(e) => setTemperature(e.target.value)}
              className={fieldClasses}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("testsOxygen")}
            </label>
            <input
              type="number"
              step="0.1"
              inputMode="decimal"
              value={oxygen}
              onChange={(e) => setOxygen(e.target.value)}
              className={fieldClasses}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("testsWeight")}
            </label>
            <input
              type="number"
              step="0.1"
              inputMode="decimal"
              value={weight}
              onChange={(e) => setWeight(e.target.value)}
              className={fieldClasses}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("testsHeight")}
            </label>
            <input
              type="number"
              step="0.1"
              inputMode="decimal"
              value={height}
              onChange={(e) => setHeight(e.target.value)}
              className={fieldClasses}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("respiratoryRate")}
            </label>
            <input
              type="number"
              inputMode="numeric"
              value={respiratory}
              onChange={(e) => setRespiratory(e.target.value)}
              className={fieldClasses}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("painScore")}
            </label>
            <input
              type="number"
              inputMode="numeric"
              value={painScore}
              onChange={(e) => setPainScore(e.target.value)}
              className={fieldClasses}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("bloodGlucose")}
            </label>
            <input
              type="number"
              step="0.1"
              inputMode="decimal"
              value={glucose}
              onChange={(e) => setGlucose(e.target.value)}
              className={fieldClasses}
            />
          </div>
        </div>

        {measureError && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-red-300 bg-red-50 px-3 py-2 dark:border-red-800 dark:bg-red-950">
            <AlertTriangle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
            <p className="text-sm text-red-800 dark:text-red-200">
              {measureError}
            </p>
          </div>
        )}
        {measureSaved && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-green-300 bg-green-50 px-3 py-2 dark:border-green-800 dark:bg-green-950">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600 dark:text-green-400" />
            <p className="text-sm text-green-800 dark:text-green-200">
              {t("testsMeasurementsSaved")}
            </p>
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={handleSaveMeasurements}
            disabled={recordVitals.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow transition-all hover:opacity-90 disabled:opacity-50"
          >
            {recordVitals.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            {t("testsSaveMeasurements")}
          </button>
        </div>
      </div>

      {/* Screening test */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <div className="mb-1 flex items-center gap-2">
          <FlaskConical className="h-4 w-4 text-primary" />
          <h3 className="text-sm font-semibold text-foreground">
            {t("testsScreeningTitle")}
          </h3>
        </div>
        <p className="mb-4 text-xs text-muted-foreground">
          {t("testsSubtitle")}
        </p>

        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("testsTest")}
            </label>
            <select
              value={testCode}
              onChange={(e) => {
                setTestCode(e.target.value);
                setTestError("");
              }}
              className={fieldClasses}
            >
              <option value="">{t("testsChooseTest")}</option>
              {POC_TESTS.map((item) => (
                <option key={item.code} value={item.code}>
                  {t(item.nameKey)}
                </option>
              ))}
              <option value="OTHER">{t("testsCustomTest")}</option>
            </select>
          </div>

          {testCode === "OTHER" && (
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                {t("testsCustomTest")}
              </label>
              <input
                type="text"
                value={customName}
                onChange={(e) => setCustomName(e.target.value)}
                placeholder={t("testsCustomTestPlaceholder")}
                className={fieldClasses}
              />
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("testsResult")}
            </label>
            <input
              type="text"
              value={result}
              onChange={(e) => setResult(e.target.value)}
              placeholder={t("testsResultPlaceholder")}
              className={fieldClasses}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("testsUnit")}
            </label>
            <input
              type="text"
              value={unit}
              onChange={(e) => setUnit(e.target.value)}
              className={fieldClasses}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("testsInterpretation")}
            </label>
            <select
              value={interpretation}
              onChange={(e) => setInterpretation(e.target.value)}
              className={fieldClasses}
            >
              <option value="">{t("testsInterpretationPlaceholder")}</option>
              {INTERPRETATIONS.map((value) => (
                <option key={value} value={value}>
                  {t(INTERPRETATION_LABEL_KEYS[value])}
                </option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("testsNotes")}
            </label>
            <textarea
              value={testNotes}
              onChange={(e) => setTestNotes(e.target.value)}
              rows={2}
              className={fieldClasses}
            />
          </div>
        </div>

        {testError && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-red-300 bg-red-50 px-3 py-2 dark:border-red-800 dark:bg-red-950">
            <AlertTriangle className="h-4 w-4 shrink-0 text-red-600 dark:text-red-400" />
            <p className="text-sm text-red-800 dark:text-red-200">{testError}</p>
          </div>
        )}
        {testSaved && (
          <div className="mt-3 flex items-center gap-2 rounded-lg border border-green-300 bg-green-50 px-3 py-2 dark:border-green-800 dark:bg-green-950">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-green-600 dark:text-green-400" />
            <p className="text-sm text-green-800 dark:text-green-200">
              {t("testsSaved")}
            </p>
          </div>
        )}

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            onClick={handleSaveTest}
            disabled={recordTest.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground shadow transition-all hover:opacity-90 disabled:opacity-50"
          >
            {recordTest.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            {recordTest.isPending ? t("testsSaving") : t("testsSave")}
          </button>
        </div>
      </div>

      {/* Recorded tests */}
      <div className="rounded-xl border border-border bg-card p-5 shadow-[var(--shadow-card)]">
        <h3 className="mb-3 text-sm font-semibold text-foreground">
          {t("testsHistoryTitle")}
        </h3>
        {!tests || tests.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("testsEmpty")}</p>
        ) : (
          <ul className="space-y-2">
            {tests.map((test) => (
              <li
                key={test.id}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border bg-muted/40 p-3"
              >
                <span className="text-sm font-medium text-foreground">
                  {test.test_name}
                </span>
                <span className="text-sm text-muted-foreground">
                  {test.result_value}
                  {test.result_unit ? ` ${test.result_unit}` : ""}
                </span>
                {test.interpretation && (
                  <span
                    className={
                      test.is_abnormal
                        ? "rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700 dark:bg-red-900 dark:text-red-300"
                        : "rounded-full bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground"
                    }
                  >
                    {t(INTERPRETATION_LABEL_KEYS[test.interpretation])}
                  </span>
                )}
                <span className="ml-auto text-xs text-muted-foreground">
                  {formatDateTime(test.performed_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
