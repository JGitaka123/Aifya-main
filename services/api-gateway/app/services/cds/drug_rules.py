"""
Drug-related CDS rules.
Checks for drug interactions, allergy contraindications, condition conflicts,
age-based warnings, pregnancy risks, duplicate therapies, and dose validation.
"""

import re
from datetime import date, datetime
from typing import Any

from structlog import get_logger

from app.services.cds.models import (
    AlertAction,
    AlertCategory,
    AlertSeverity,
    CDSAlert,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Drug interaction database (critical pairs)
# Based on WHO Essential Medicines & common Kenyan formulary interactions
# ---------------------------------------------------------------------------

DRUG_INTERACTIONS: list[dict[str, Any]] = [
    # Anticoagulants
    {"drugs": ["warfarin", "aspirin"], "severity": "high", "desc": "Increased bleeding risk. Monitor INR closely."},
    {"drugs": ["warfarin", "ibuprofen"], "severity": "critical", "desc": "NSAIDs significantly increase bleeding risk with warfarin. Avoid combination."},
    {"drugs": ["warfarin", "diclofenac"], "severity": "critical", "desc": "NSAIDs significantly increase bleeding risk with warfarin. Avoid combination."},
    {"drugs": ["warfarin", "metronidazole"], "severity": "high", "desc": "Metronidazole inhibits warfarin metabolism. Reduce warfarin dose and monitor INR."},
    {"drugs": ["warfarin", "fluconazole"], "severity": "high", "desc": "Fluconazole inhibits CYP2C9, increasing warfarin effect. Monitor INR."},
    {"drugs": ["heparin", "aspirin"], "severity": "high", "desc": "Increased bleeding risk with concurrent antiplatelet therapy."},
    # Cardiovascular
    {"drugs": ["digoxin", "amiodarone"], "severity": "critical", "desc": "Amiodarone increases digoxin levels by 70-100%. Halve digoxin dose."},
    {"drugs": ["digoxin", "verapamil"], "severity": "high", "desc": "Verapamil increases digoxin levels. Monitor digoxin levels."},
    {"drugs": ["enalapril", "spironolactone"], "severity": "high", "desc": "Risk of severe hyperkalemia. Monitor potassium closely."},
    {"drugs": ["enalapril", "potassium chloride"], "severity": "high", "desc": "ACE inhibitors with potassium supplementation risk hyperkalemia."},
    {"drugs": ["amlodipine", "simvastatin"], "severity": "moderate", "desc": "Amlodipine increases simvastatin levels. Max simvastatin 20mg."},
    {"drugs": ["atenolol", "verapamil"], "severity": "critical", "desc": "Risk of severe bradycardia and heart block. Avoid combination."},
    {"drugs": ["nifedipine", "atenolol"], "severity": "moderate", "desc": "Enhanced hypotension. Monitor blood pressure."},
    # Antibiotics
    {"drugs": ["metronidazole", "alcohol"], "severity": "high", "desc": "Disulfiram-like reaction. Avoid alcohol during treatment."},
    {"drugs": ["ciprofloxacin", "theophylline"], "severity": "high", "desc": "Ciprofloxacin increases theophylline levels. Monitor levels."},
    {"drugs": ["erythromycin", "simvastatin"], "severity": "critical", "desc": "Risk of rhabdomyolysis. Avoid combination."},
    {"drugs": ["rifampicin", "oral contraceptives"], "severity": "critical", "desc": "Rifampicin reduces contraceptive efficacy. Use alternative contraception."},
    {"drugs": ["rifampicin", "warfarin"], "severity": "critical", "desc": "Rifampicin dramatically reduces warfarin effect. Major dose adjustment needed."},
    {"drugs": ["co-trimoxazole", "methotrexate"], "severity": "critical", "desc": "Co-trimoxazole increases methotrexate toxicity. Avoid combination."},
    # Diabetes
    {"drugs": ["metformin", "contrast dye"], "severity": "high", "desc": "Hold metformin 48h before and after IV contrast. Risk of lactic acidosis."},
    {"drugs": ["glibenclamide", "fluconazole"], "severity": "high", "desc": "Fluconazole increases glibenclamide effect. Risk of hypoglycemia."},
    {"drugs": ["insulin", "atenolol"], "severity": "moderate", "desc": "Beta-blockers mask hypoglycemia symptoms. Monitor glucose closely."},
    # Psychiatric
    {"drugs": ["fluoxetine", "tramadol"], "severity": "critical", "desc": "Risk of serotonin syndrome. Avoid combination."},
    {"drugs": ["fluoxetine", "carbamazepine"], "severity": "high", "desc": "Fluoxetine increases carbamazepine levels. Monitor for toxicity."},
    {"drugs": ["diazepam", "opioids"], "severity": "critical", "desc": "Combined CNS depression risk. Respiratory depression possible."},
    {"drugs": ["phenytoin", "fluconazole"], "severity": "high", "desc": "Fluconazole increases phenytoin levels. Monitor levels."},
    # HIV/TB
    {"drugs": ["efavirenz", "rifampicin"], "severity": "moderate", "desc": "Dose adjustment needed. Increase efavirenz to 800mg."},
    {"drugs": ["lopinavir", "rifampicin"], "severity": "critical", "desc": "Rifampicin dramatically reduces lopinavir levels. Contraindicated."},
    {"drugs": ["zidovudine", "stavudine"], "severity": "critical", "desc": "Antagonistic antiretrovirals. Never combine."},
    {"drugs": ["tenofovir", "nsaids"], "severity": "high", "desc": "Increased nephrotoxicity risk. Monitor renal function."},
]

# ---------------------------------------------------------------------------
# Drug-allergy cross-reference classes
# ---------------------------------------------------------------------------

DRUG_ALLERGY_CLASSES: dict[str, list[str]] = {
    "penicillin": ["amoxicillin", "ampicillin", "flucloxacillin", "piperacillin", "benzylpenicillin", "phenoxymethylpenicillin", "co-amoxiclav", "augmentin"],
    "cephalosporin": ["ceftriaxone", "cefuroxime", "cephalexin", "cefixime", "ceftazidime", "cefotaxime"],
    "sulfonamide": ["co-trimoxazole", "sulfadiazine", "sulfasalazine", "dapsone"],
    "nsaid": ["ibuprofen", "diclofenac", "aspirin", "naproxen", "piroxicam", "indomethacin", "mefenamic acid", "ketorolac", "celecoxib"],
    "opioid": ["morphine", "codeine", "tramadol", "pethidine", "fentanyl", "methadone"],
    "macrolide": ["erythromycin", "azithromycin", "clarithromycin"],
    "fluoroquinolone": ["ciprofloxacin", "levofloxacin", "moxifloxacin", "norfloxacin"],
    "aminoglycoside": ["gentamicin", "amikacin", "streptomycin", "tobramycin"],
    "tetracycline": ["doxycycline", "tetracycline", "minocycline"],
}

# Cross-reactivity: penicillin ↔ cephalosporin ~10%
CROSS_REACTIVITY: dict[str, list[str]] = {
    "penicillin": ["cephalosporin"],
    "cephalosporin": ["penicillin"],
}

# ---------------------------------------------------------------------------
# Drug-condition contraindications
# ---------------------------------------------------------------------------

DRUG_CONDITION_RULES: list[dict[str, Any]] = [
    {"drug_class": "nsaid", "conditions": ["peptic ulcer", "gastric ulcer", "gi bleeding", "renal failure", "kidney disease"], "severity": "critical", "desc": "NSAIDs contraindicated in {condition}. Risk of GI bleeding/renal injury."},
    {"drug_class": "nsaid", "conditions": ["asthma"], "severity": "high", "desc": "NSAIDs may trigger bronchospasm in aspirin-sensitive asthma."},
    {"drug_class": "nsaid", "conditions": ["heart failure", "cardiac failure"], "severity": "high", "desc": "NSAIDs cause fluid retention. Worsen heart failure."},
    {"drug_pattern": "metformin", "conditions": ["renal failure", "kidney disease", "hepatic failure", "liver failure"], "severity": "critical", "desc": "Metformin contraindicated in severe renal/hepatic impairment. Risk of lactic acidosis."},
    {"drug_pattern": "atenolol|propranolol|metoprolol", "conditions": ["asthma", "copd"], "severity": "critical", "desc": "Non-selective beta-blockers contraindicated in asthma/COPD. Risk of bronchospasm."},
    {"drug_pattern": "enalapril|lisinopril|ramipril|captopril", "conditions": ["angioedema"], "severity": "critical", "desc": "ACE inhibitors contraindicated with history of angioedema."},
    {"drug_pattern": "enalapril|lisinopril|ramipril|captopril", "conditions": ["bilateral renal artery stenosis"], "severity": "critical", "desc": "ACE inhibitors contraindicated in bilateral renal artery stenosis."},
    {"drug_pattern": "simvastatin|atorvastatin|rosuvastatin", "conditions": ["active liver disease", "hepatitis"], "severity": "high", "desc": "Statins contraindicated in active liver disease. Check LFTs."},
    {"drug_pattern": "warfarin", "conditions": ["active bleeding", "hemorrhagic stroke"], "severity": "critical", "desc": "Anticoagulation contraindicated in active bleeding."},
    {"drug_pattern": "glibenclamide", "conditions": ["renal failure", "kidney disease"], "severity": "high", "desc": "Glibenclamide accumulates in renal impairment. Use gliclazide instead."},
    {"drug_pattern": "chloroquine|hydroxychloroquine", "conditions": ["retinopathy"], "severity": "high", "desc": "Risk of retinal toxicity. Requires ophthalmology monitoring."},
]

# ---------------------------------------------------------------------------
# Pregnancy risk drugs (FDA Category D and X equivalents)
# ---------------------------------------------------------------------------

PREGNANCY_CONTRAINDICATED: list[str] = [
    "warfarin", "methotrexate", "isotretinoin", "thalidomide", "misoprostol",
    "finasteride", "statins", "simvastatin", "atorvastatin", "rosuvastatin",
    "ace inhibitors", "enalapril", "lisinopril", "ramipril", "captopril",
    "arbs", "losartan", "valsartan", "telmisartan",
    "tetracycline", "doxycycline", "ciprofloxacin", "levofloxacin",
    "phenytoin", "carbamazepine", "valproate", "sodium valproate",
    "efavirenz",
]

# ---------------------------------------------------------------------------
# Age-specific warnings
# ---------------------------------------------------------------------------

PEDIATRIC_CONTRAINDICATED: list[dict[str, Any]] = [
    {"drug_pattern": "aspirin", "max_age_years": 16, "desc": "Aspirin contraindicated in children under 16. Risk of Reye's syndrome."},
    {"drug_pattern": "tetracycline|doxycycline", "max_age_years": 8, "desc": "Tetracyclines contraindicated under 8 years. Permanent tooth discoloration."},
    {"drug_pattern": "ciprofloxacin|levofloxacin", "max_age_years": 18, "desc": "Fluoroquinolones avoid in children. Risk of tendon/cartilage damage."},
    {"drug_pattern": "codeine", "max_age_years": 12, "desc": "Codeine contraindicated under 12. Risk of fatal respiratory depression."},
    {"drug_pattern": "loperamide", "max_age_years": 2, "desc": "Loperamide contraindicated in children under 2 years."},
]

# ---------------------------------------------------------------------------
# Weight-based (paediatric) dosing ranges — mg per kg PER DOSE.
# Deterministic, calculator-owned reference (NOT model-generated). Used to
# flag an adult dose entered for a child. `max_single_mg` caps the absolute
# per-dose amount regardless of weight.
# ---------------------------------------------------------------------------

WEIGHT_BASED_DOSING: dict[str, dict[str, float]] = {
    "paracetamol": {"min_mg_per_kg": 10, "max_mg_per_kg": 15, "max_single_mg": 1000},
    "acetaminophen": {"min_mg_per_kg": 10, "max_mg_per_kg": 15, "max_single_mg": 1000},
    "ibuprofen": {"min_mg_per_kg": 5, "max_mg_per_kg": 10, "max_single_mg": 400},
    "amoxicillin": {"min_mg_per_kg": 15, "max_mg_per_kg": 30, "max_single_mg": 500},
    "azithromycin": {"min_mg_per_kg": 10, "max_mg_per_kg": 12, "max_single_mg": 500},
    "ceftriaxone": {"min_mg_per_kg": 20, "max_mg_per_kg": 40, "max_single_mg": 2000},
    "gentamicin": {"min_mg_per_kg": 2.5, "max_mg_per_kg": 7.5, "max_single_mg": 400},
    "metronidazole": {"min_mg_per_kg": 7, "max_mg_per_kg": 10, "max_single_mg": 500},
    "zinc": {"min_mg_per_kg": 0.7, "max_mg_per_kg": 1.5, "max_single_mg": 20},
}

# Age below which weight-based paediatric dosing checks apply.
_PAEDIATRIC_MAX_AGE_YEARS = 12
# Tolerance above the max mg/kg before warning, to avoid nuisance boundary alerts.
_DOSE_TOLERANCE = 1.2

GERIATRIC_WARNINGS: list[dict[str, Any]] = [
    {"drug_pattern": "diazepam|lorazepam|chlordiazepoxide", "min_age_years": 65, "desc": "Long-acting benzodiazepines: increased fall risk in elderly. Consider short-acting alternatives."},
    {"drug_pattern": "amitriptyline|imipramine", "min_age_years": 65, "desc": "Tricyclic antidepressants: anticholinergic effects magnified in elderly. Use SSRIs."},
    {"drug_pattern": "glibenclamide", "min_age_years": 65, "desc": "Glibenclamide: prolonged hypoglycemia risk in elderly. Use gliclazide."},
    {"drug_pattern": "nsaid|ibuprofen|diclofenac", "min_age_years": 65, "desc": "NSAIDs: increased GI bleeding and renal risk in elderly. Use paracetamol first."},
]


def _normalize_drug(name: str) -> str:
    """
    Normalize drug name for matching.

    @param name: Drug name string
    @returns Lowercase, stripped drug name
    """
    return name.strip().lower().replace("-", " ").replace("_", " ")


def _drug_in_class(drug_name: str, drug_class: str) -> bool:
    """
    Check if a drug belongs to a drug class.

    @param drug_name: Normalized drug name
    @param drug_class: Drug class key
    @returns True if drug is in the class
    """
    members = DRUG_ALLERGY_CLASSES.get(drug_class, [])
    return any(member in drug_name for member in members)


def _patient_age_years(dob: date | str | None) -> int | None:
    """
    Calculate patient age in years.

    @param dob: Date of birth
    @returns Age in years or None
    """
    if dob is None:
        return None
    if isinstance(dob, str):
        try:
            dob = datetime.fromisoformat(dob).date()
        except (ValueError, TypeError):
            return None
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def check_drug_interactions(
    drug_name: str,
    current_medications: list[str],
) -> list[CDSAlert]:
    """
    Check for drug-drug interactions.

    @param drug_name: New drug being prescribed
    @param current_medications: List of current medication names
    @returns List of interaction alerts
    """
    alerts: list[CDSAlert] = []
    norm_drug = _normalize_drug(drug_name)

    for med in current_medications:
        norm_med = _normalize_drug(med)
        for rule in DRUG_INTERACTIONS:
            pair = [_normalize_drug(d) for d in rule["drugs"]]
            if ((norm_drug in pair[0] or pair[0] in norm_drug) and \
               (norm_med in pair[1] or pair[1] in norm_med)) or ((norm_drug in pair[1] or pair[1] in norm_drug) and \
                 (norm_med in pair[0] or pair[0] in norm_med)):
                match = True
            else:
                match = False

            if match:
                sev = AlertSeverity.CRITICAL if rule["severity"] == "critical" else \
                      AlertSeverity.HIGH if rule["severity"] == "high" else AlertSeverity.MODERATE
                act = AlertAction.BLOCK if sev == AlertSeverity.CRITICAL else AlertAction.WARN

                alerts.append(CDSAlert(
                    severity=sev,
                    category=AlertCategory.DRUG_INTERACTION,
                    action=act,
                    title=f"Drug Interaction: {drug_name} ↔ {med}",
                    message=rule["desc"],
                    source_rule="drug_interaction_check",
                    affected_items=[drug_name, med],
                    evidence={"pair": rule["drugs"], "severity": rule["severity"]},
                    overridable=sev != AlertSeverity.CRITICAL,
                    requires_reason=sev == AlertSeverity.CRITICAL,
                ))

    return alerts


def check_drug_allergies(
    drug_name: str,
    patient_allergies: list[str | dict],
) -> list[CDSAlert]:
    """
    Check for drug-allergy contraindications and cross-reactivity.

    @param drug_name: Drug being prescribed
    @param patient_allergies: Patient's allergy list (strings or dicts with 'name' key)
    @returns List of allergy alerts
    """
    alerts: list[CDSAlert] = []
    norm_drug = _normalize_drug(drug_name)

    allergy_names: list[str] = []
    for a in patient_allergies:
        if isinstance(a, str):
            allergy_names.append(_normalize_drug(a))
        elif isinstance(a, dict) and "name" in a:
            allergy_names.append(_normalize_drug(str(a["name"])))

    for allergy in allergy_names:
        # Direct match
        if allergy in norm_drug or norm_drug in allergy:
            alerts.append(CDSAlert(
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.DRUG_ALLERGY,
                action=AlertAction.BLOCK,
                title=f"ALLERGY: {drug_name} — Patient allergic to {allergy}",
                message=f"Patient has documented allergy to {allergy}. {drug_name} is contraindicated.",
                source_rule="drug_allergy_direct",
                affected_items=[drug_name],
                evidence={"allergy": allergy, "match_type": "direct"},
                overridable=False,
                requires_reason=True,
            ))
            continue

        # Class match
        for class_name, members in DRUG_ALLERGY_CLASSES.items():
            allergy_is_class = allergy == class_name or any(m in allergy for m in members)
            drug_is_member = any(m in norm_drug for m in members)

            if allergy_is_class and drug_is_member:
                alerts.append(CDSAlert(
                    severity=AlertSeverity.CRITICAL,
                    category=AlertCategory.DRUG_ALLERGY,
                    action=AlertAction.BLOCK,
                    title=f"CLASS ALLERGY: {drug_name} ({class_name}) — Patient allergic",
                    message=f"Patient has {class_name} allergy. {drug_name} belongs to this class.",
                    source_rule="drug_allergy_class",
                    affected_items=[drug_name],
                    evidence={"allergy": allergy, "class": class_name, "match_type": "class"},
                    overridable=False,
                    requires_reason=True,
                ))

        # Cross-reactivity
        for class_name, cross_classes in CROSS_REACTIVITY.items():
            allergy_is_class = allergy == class_name or any(
                m in allergy for m in DRUG_ALLERGY_CLASSES.get(class_name, [])
            )
            if allergy_is_class:
                for cross_class in cross_classes:
                    drug_is_cross = any(
                        m in norm_drug for m in DRUG_ALLERGY_CLASSES.get(cross_class, [])
                    )
                    if drug_is_cross:
                        alerts.append(CDSAlert(
                            severity=AlertSeverity.HIGH,
                            category=AlertCategory.DRUG_ALLERGY,
                            action=AlertAction.WARN,
                            title=f"CROSS-REACTIVITY: {drug_name} — {class_name}/{cross_class}",
                            message=f"Patient has {class_name} allergy. {drug_name} ({cross_class}) has ~10% cross-reactivity risk.",
                            source_rule="drug_allergy_cross_reactivity",
                            affected_items=[drug_name],
                            evidence={"allergy": allergy, "cross_class": cross_class},
                            overridable=True,
                            requires_reason=True,
                        ))

    return alerts


def check_drug_conditions(
    drug_name: str,
    patient_conditions: list[str | dict],
) -> list[CDSAlert]:
    """
    Check for drug-condition contraindications.

    @param drug_name: Drug being prescribed
    @param patient_conditions: Patient's chronic conditions / diagnoses
    @returns List of condition conflict alerts
    """
    alerts: list[CDSAlert] = []
    norm_drug = _normalize_drug(drug_name)

    condition_names: list[str] = []
    for c in patient_conditions:
        if isinstance(c, str):
            condition_names.append(c.strip().lower())
        elif isinstance(c, dict) and "name" in c:
            condition_names.append(str(c["name"]).strip().lower())

    for rule in DRUG_CONDITION_RULES:
        drug_match = False
        if "drug_class" in rule:
            drug_match = _drug_in_class(norm_drug, rule["drug_class"])
        elif "drug_pattern" in rule:
            drug_match = bool(re.search(rule["drug_pattern"], norm_drug, re.IGNORECASE))

        if not drug_match:
            continue

        for condition in condition_names:
            for rule_condition in rule["conditions"]:
                if rule_condition in condition or condition in rule_condition:
                    sev = AlertSeverity.CRITICAL if rule["severity"] == "critical" else AlertSeverity.HIGH
                    desc = rule["desc"].replace("{condition}", condition)
                    alerts.append(CDSAlert(
                        severity=sev,
                        category=AlertCategory.DRUG_CONDITION,
                        action=AlertAction.BLOCK if sev == AlertSeverity.CRITICAL else AlertAction.WARN,
                        title=f"Contraindication: {drug_name} + {condition}",
                        message=desc,
                        source_rule="drug_condition_check",
                        affected_items=[drug_name, condition],
                        evidence={"condition": condition, "rule_condition": rule_condition},
                        overridable=sev != AlertSeverity.CRITICAL,
                        requires_reason=True,
                    ))
                    break

    return alerts


def check_age_safety(
    drug_name: str,
    patient_dob: date | str | None,
) -> list[CDSAlert]:
    """
    Check for age-specific drug contraindications.

    @param drug_name: Drug being prescribed
    @param patient_dob: Patient's date of birth
    @returns List of age-related alerts
    """
    alerts: list[CDSAlert] = []
    age = _patient_age_years(patient_dob)
    if age is None:
        return alerts

    norm_drug = _normalize_drug(drug_name)

    for rule in PEDIATRIC_CONTRAINDICATED:
        if age < rule["max_age_years"] and re.search(
            rule["drug_pattern"], norm_drug, re.IGNORECASE
        ):
                alerts.append(CDSAlert(
                    severity=AlertSeverity.CRITICAL,
                    category=AlertCategory.DRUG_AGE,
                    action=AlertAction.BLOCK,
                    title=f"Pediatric Contraindication: {drug_name} (patient age {age}y)",
                    message=rule["desc"],
                    source_rule="pediatric_drug_check",
                    affected_items=[drug_name],
                    evidence={"patient_age": age, "max_age": rule["max_age_years"]},
                    overridable=False,
                    requires_reason=True,
                ))

    for rule in GERIATRIC_WARNINGS:
        if age >= rule["min_age_years"] and re.search(
            rule["drug_pattern"], norm_drug, re.IGNORECASE
        ):
                alerts.append(CDSAlert(
                    severity=AlertSeverity.MODERATE,
                    category=AlertCategory.DRUG_AGE,
                    action=AlertAction.WARN,
                    title=f"Geriatric Warning: {drug_name} (patient age {age}y)",
                    message=rule["desc"],
                    source_rule="geriatric_drug_check",
                    affected_items=[drug_name],
                    evidence={"patient_age": age, "min_age": rule["min_age_years"]},
                    overridable=True,
                ))

    return alerts


def check_weight_based_dose(
    drug_name: str,
    dosage_value: float | None,
    dosage_unit: str | None,
    weight_kg: float | None,
    age_years: int | None,
) -> list[CDSAlert]:
    """
    Flag a paediatric per-dose amount that exceeds the weight-based range.

    Deterministic mg/kg arithmetic against a curated table — no model output.
    Applies only to children (< 12y) with a recorded weight and an mg dose for
    a drug in the dosing table; otherwise returns no alerts (never a false
    alarm from missing data).

    @param drug_name: Drug being prescribed
    @param dosage_value: Numeric per-dose amount
    @param dosage_unit: Unit of the dose (only mg is dose-range checked)
    @param weight_kg: Patient's most recent recorded weight in kg
    @param age_years: Patient's age in years
    @returns List of dose-range alerts (WARN, overridable)
    """
    alerts: list[CDSAlert] = []
    if dosage_value is None or dosage_value <= 0:
        return alerts
    if weight_kg is None or weight_kg <= 0:
        return alerts
    if age_years is None or age_years >= _PAEDIATRIC_MAX_AGE_YEARS:
        return alerts

    unit = (dosage_unit or "").strip().lower()
    if unit not in ("", "mg", "milligram", "milligrams"):
        return alerts  # cannot derive mg/kg from ml / tablets

    norm_drug = _normalize_drug(drug_name)
    spec: dict[str, float] | None = None
    for key, value in WEIGHT_BASED_DOSING.items():
        if key in norm_drug:
            spec = value
            break
    if spec is None:
        return alerts

    dose_per_kg = dosage_value / weight_kg
    max_per_kg = spec["max_mg_per_kg"]
    over_range = dose_per_kg > max_per_kg * _DOSE_TOLERANCE
    over_absolute = dosage_value > spec["max_single_mg"]

    if over_range or over_absolute:
        alerts.append(CDSAlert(
            severity=AlertSeverity.HIGH,
            category=AlertCategory.DRUG_DOSE,
            action=AlertAction.WARN,
            title=f"Paediatric dose check: {drug_name} ({dose_per_kg:.1f} mg/kg)",
            message=(
                f"{drug_name} {dosage_value:.0f} mg is {dose_per_kg:.1f} mg/kg for a "
                f"{weight_kg:.0f} kg child (age {age_years}); recommended "
                f"{spec['min_mg_per_kg']:g}-{max_per_kg:g} mg/kg/dose "
                f"(max {spec['max_single_mg']:g} mg). Verify the weight-based dose."
            ),
            source_rule="weight_based_dose",
            affected_items=[drug_name],
            evidence={
                "dose_per_kg": round(dose_per_kg, 2),
                "max_mg_per_kg": max_per_kg,
                "max_single_mg": spec["max_single_mg"],
                "weight_kg": weight_kg,
                "age_years": age_years,
            },
            overridable=True,
            requires_reason=True,
        ))

    return alerts


def check_pregnancy_safety(
    drug_name: str,
    is_pregnant: bool,
) -> list[CDSAlert]:
    """
    Check for pregnancy contraindications.

    @param drug_name: Drug being prescribed
    @param is_pregnant: Whether patient is pregnant
    @returns List of pregnancy safety alerts
    """
    if not is_pregnant:
        return []

    alerts: list[CDSAlert] = []
    norm_drug = _normalize_drug(drug_name)

    for contraindicated in PREGNANCY_CONTRAINDICATED:
        if contraindicated in norm_drug or norm_drug in contraindicated:
            alerts.append(CDSAlert(
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.DRUG_PREGNANCY,
                action=AlertAction.BLOCK,
                title=f"PREGNANCY: {drug_name} contraindicated",
                message=f"{drug_name} is contraindicated in pregnancy. Risk of teratogenic effects.",
                source_rule="pregnancy_drug_check",
                affected_items=[drug_name],
                evidence={"pregnancy_status": True},
                overridable=False,
                requires_reason=True,
            ))
            break

    return alerts


def check_duplicate_therapy(
    drug_name: str,
    current_medications: list[str],
) -> list[CDSAlert]:
    """
    Check for duplicate therapeutic class prescriptions.

    @param drug_name: New drug being prescribed
    @param current_medications: Current active medications
    @returns List of duplicate therapy alerts
    """
    alerts: list[CDSAlert] = []
    norm_drug = _normalize_drug(drug_name)

    for med in current_medications:
        norm_med = _normalize_drug(med)
        if norm_drug == norm_med:
            alerts.append(CDSAlert(
                severity=AlertSeverity.HIGH,
                category=AlertCategory.DRUG_DUPLICATE,
                action=AlertAction.WARN,
                title=f"Duplicate: {drug_name} already prescribed",
                message=f"Patient already has an active prescription for {med}.",
                source_rule="duplicate_drug_check",
                affected_items=[drug_name, med],
                overridable=True,
            ))
            continue

        for class_name, members in DRUG_ALLERGY_CLASSES.items():
            drug_in = any(m in norm_drug for m in members)
            med_in = any(m in norm_med for m in members)
            if drug_in and med_in and norm_drug != norm_med:
                alerts.append(CDSAlert(
                    severity=AlertSeverity.MODERATE,
                    category=AlertCategory.DRUG_DUPLICATE,
                    action=AlertAction.WARN,
                    title=f"Same Class: {drug_name} + {med} ({class_name})",
                    message=f"Both {drug_name} and {med} are {class_name}s. Review therapeutic duplication.",
                    source_rule="duplicate_class_check",
                    affected_items=[drug_name, med],
                    evidence={"drug_class": class_name},
                    overridable=True,
                ))

    return alerts
