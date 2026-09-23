"""
Clinical CDS rules for vitals, lab results, sepsis screening,
duplicate orders, and trend analysis.
"""

from datetime import date, datetime, timedelta
from typing import Any

from structlog import get_logger

from app.services.cds.models import (
    AlertAction,
    AlertCategory,
    AlertSeverity,
    CDSAlert,
    SepsisScore,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Age-adjusted vital thresholds
# ---------------------------------------------------------------------------

PEDIATRIC_VITAL_THRESHOLDS: dict[str, dict[str, dict[str, float]]] = {
    "neonate": {  # 0-28 days
        "heart_rate_high": {"value": 190},
        "heart_rate_low": {"value": 100},
        "respiratory_rate_high": {"value": 60},
        "respiratory_rate_low": {"value": 30},
        "systolic_bp_low": {"value": 60},
        "temperature_high": {"value": 38.0},
    },
    "infant": {  # 1-12 months
        "heart_rate_high": {"value": 180},
        "heart_rate_low": {"value": 80},
        "respiratory_rate_high": {"value": 50},
        "respiratory_rate_low": {"value": 25},
        "systolic_bp_low": {"value": 70},
    },
    "child": {  # 1-5 years
        "heart_rate_high": {"value": 160},
        "heart_rate_low": {"value": 70},
        "respiratory_rate_high": {"value": 40},
        "respiratory_rate_low": {"value": 20},
        "systolic_bp_low": {"value": 75},
    },
    "school_age": {  # 6-12 years
        "heart_rate_high": {"value": 140},
        "heart_rate_low": {"value": 60},
        "respiratory_rate_high": {"value": 30},
        "respiratory_rate_low": {"value": 14},
        "systolic_bp_low": {"value": 80},
    },
}


def _get_age_group(dob: date | str | None) -> str:
    """
    Determine age group for threshold selection.

    @param dob: Date of birth
    @returns Age group string
    """
    if dob is None:
        return "adult"
    if isinstance(dob, str):
        try:
            dob = datetime.fromisoformat(dob).date()
        except (ValueError, TypeError):
            return "adult"

    today = date.today()
    age_days = (today - dob).days
    age_years = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    if age_days <= 28:
        return "neonate"
    elif age_years < 1:
        return "infant"
    elif age_years < 6:
        return "child"
    elif age_years < 13:
        return "school_age"
    return "adult"


def check_vitals_age_adjusted(
    vitals: dict[str, Any],
    patient_dob: date | str | None,
) -> list[CDSAlert]:
    """
    Check vital signs against age-adjusted thresholds.
    Augments the existing CRITICAL_THRESHOLDS with pediatric ranges.

    @param vitals: Vital sign values dict
    @param patient_dob: Patient date of birth
    @returns List of vital sign alerts
    """
    alerts: list[CDSAlert] = []
    age_group = _get_age_group(patient_dob)

    if age_group == "adult":
        return alerts  # Adult thresholds handled by existing vitals_service

    thresholds = PEDIATRIC_VITAL_THRESHOLDS.get(age_group, {})

    hr = vitals.get("heart_rate")
    if hr is not None:
        hr_high = thresholds.get("heart_rate_high", {}).get("value")
        hr_low = thresholds.get("heart_rate_low", {}).get("value")
        if hr_high and hr > hr_high:
            alerts.append(CDSAlert(
                severity=AlertSeverity.HIGH,
                category=AlertCategory.VITAL_CRITICAL,
                action=AlertAction.WARN,
                title=f"Pediatric Tachycardia: HR {hr} bpm ({age_group})",
                message=f"Heart rate {hr} exceeds {age_group} threshold of {hr_high}. Evaluate for fever, pain, dehydration, or cardiac cause.",
                source_rule="pediatric_vital_hr_high",
                affected_items=["heart_rate"],
                evidence={"value": hr, "threshold": hr_high, "age_group": age_group},
            ))
        if hr_low and hr < hr_low:
            alerts.append(CDSAlert(
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.VITAL_CRITICAL,
                action=AlertAction.WARN,
                title=f"Pediatric Bradycardia: HR {hr} bpm ({age_group})",
                message=f"Heart rate {hr} below {age_group} threshold of {hr_low}. Immediate evaluation needed.",
                source_rule="pediatric_vital_hr_low",
                affected_items=["heart_rate"],
                evidence={"value": hr, "threshold": hr_low, "age_group": age_group},
            ))

    rr = vitals.get("respiratory_rate")
    if rr is not None:
        rr_high = thresholds.get("respiratory_rate_high", {}).get("value")
        thresholds.get("respiratory_rate_low", {}).get("value")
        if rr_high and rr > rr_high:
            alerts.append(CDSAlert(
                severity=AlertSeverity.HIGH,
                category=AlertCategory.VITAL_CRITICAL,
                action=AlertAction.WARN,
                title=f"Pediatric Tachypnea: RR {rr} ({age_group})",
                message=f"Respiratory rate {rr} exceeds {age_group} threshold of {rr_high}.",
                source_rule="pediatric_vital_rr_high",
                affected_items=["respiratory_rate"],
                evidence={"value": rr, "threshold": rr_high, "age_group": age_group},
            ))

    sbp = vitals.get("systolic_bp")
    if sbp is not None:
        sbp_low = thresholds.get("systolic_bp_low", {}).get("value")
        if sbp_low and sbp < sbp_low:
            alerts.append(CDSAlert(
                severity=AlertSeverity.CRITICAL,
                category=AlertCategory.VITAL_CRITICAL,
                action=AlertAction.WARN,
                title=f"Pediatric Hypotension: SBP {sbp} mmHg ({age_group})",
                message=f"Systolic BP {sbp} below {age_group} threshold of {sbp_low}. Consider fluid resuscitation.",
                source_rule="pediatric_vital_sbp_low",
                affected_items=["systolic_bp"],
                evidence={"value": sbp, "threshold": sbp_low, "age_group": age_group},
            ))

    return alerts


def check_sepsis_risk(
    vitals: dict[str, Any],
    lab_results: list[dict[str, Any]] | None = None,
    has_suspected_infection: bool = False,
) -> tuple[list[CDSAlert], SepsisScore | None]:
    """
    Evaluate sepsis risk using qSOFA and SIRS criteria.

    qSOFA (≥2 = high risk):
    - Altered mentation (GCS < 15)
    - Respiratory rate ≥ 22
    - Systolic BP ≤ 100 mmHg

    SIRS (≥2 = SIRS criteria met):
    - Temperature > 38°C or < 36°C
    - Heart rate > 90
    - Respiratory rate > 20
    - WBC > 12 or < 4 x10^9/L

    @param vitals: Current vital signs
    @param lab_results: Recent lab results
    @param has_suspected_infection: Whether infection is suspected
    @returns Tuple of (alerts, SepsisScore)
    """
    alerts: list[CDSAlert] = []

    gcs_total = None
    gcs_e = vitals.get("gcs_eye")
    gcs_v = vitals.get("gcs_verbal")
    gcs_m = vitals.get("gcs_motor")
    if gcs_e is not None and gcs_v is not None and gcs_m is not None:
        gcs_total = gcs_e + gcs_v + gcs_m

    rr = vitals.get("respiratory_rate")
    sbp = vitals.get("systolic_bp")
    hr = vitals.get("heart_rate")
    temp = vitals.get("temperature")

    # qSOFA
    qsofa = 0
    components: dict[str, bool] = {}

    if gcs_total is not None and gcs_total < 15:
        qsofa += 1
        components["altered_mentation"] = True
    else:
        components["altered_mentation"] = False

    if rr is not None and rr >= 22:
        qsofa += 1
        components["tachypnea_qsofa"] = True
    else:
        components["tachypnea_qsofa"] = False

    if sbp is not None and sbp <= 100:
        qsofa += 1
        components["hypotension_qsofa"] = True
    else:
        components["hypotension_qsofa"] = False

    # SIRS
    sirs = 0
    if temp is not None and (temp > 38.0 or temp < 36.0):
        sirs += 1
        components["temperature_sirs"] = True
    else:
        components["temperature_sirs"] = False

    if hr is not None and hr > 90:
        sirs += 1
        components["tachycardia_sirs"] = True
    else:
        components["tachycardia_sirs"] = False

    if rr is not None and rr > 20:
        sirs += 1
        components["tachypnea_sirs"] = True
    else:
        components["tachypnea_sirs"] = False

    wbc_abnormal = False
    if lab_results:
        for result in lab_results:
            if result.get("test_code") == "WBC" and result.get("result_numeric") is not None:
                wbc = result["result_numeric"]
                if wbc > 12.0 or wbc < 4.0:
                    wbc_abnormal = True
                    sirs += 1
                break
    components["wbc_abnormal"] = wbc_abnormal

    # Risk level
    if qsofa >= 2:
        risk_level = "critical" if has_suspected_infection else "high"
    elif sirs >= 2 and has_suspected_infection:
        risk_level = "high"
    elif sirs >= 2 or qsofa >= 1:
        risk_level = "moderate"
    else:
        risk_level = "low"

    score = SepsisScore(
        qsofa_score=qsofa,
        sirs_criteria_met=sirs,
        risk_level=risk_level,
        components=components,
    )

    if risk_level in ("high", "critical"):
        alerts.append(CDSAlert(
            severity=AlertSeverity.CRITICAL if risk_level == "critical" else AlertSeverity.HIGH,
            category=AlertCategory.SEPSIS_RISK,
            action=AlertAction.WARN,
            title=f"Sepsis Risk: {risk_level.upper()} (qSOFA={qsofa}, SIRS={sirs})",
            message=(
                f"qSOFA score {qsofa}/3, SIRS criteria {sirs}/4. "
                f"{'Suspected infection present. ' if has_suspected_infection else ''}"
                f"Consider blood cultures, lactate, and early antibiotics per Surviving Sepsis Guidelines."
            ),
            source_rule="sepsis_screening",
            affected_items=["sepsis"],
            evidence={
                "qsofa": qsofa,
                "sirs": sirs,
                "components": components,
                "suspected_infection": has_suspected_infection,
            },
            overridable=True,
            requires_reason=True,
        ))
    elif risk_level == "moderate":
        alerts.append(CDSAlert(
            severity=AlertSeverity.MODERATE,
            category=AlertCategory.SEPSIS_RISK,
            action=AlertAction.INFORM,
            title=f"Sepsis Screening: Moderate risk (qSOFA={qsofa}, SIRS={sirs})",
            message="Some sepsis criteria met. Monitor closely and reassess if clinical status changes.",
            source_rule="sepsis_screening",
            affected_items=["sepsis"],
            evidence={"qsofa": qsofa, "sirs": sirs, "components": components},
        ))

    return alerts, score


def check_lab_trends(
    current_result: dict[str, Any],
    historical_results: list[dict[str, Any]],
) -> list[CDSAlert]:
    """
    Analyze lab result trends for clinically significant changes.

    @param current_result: Current lab result with test_code, result_numeric
    @param historical_results: Previous results for the same test (ordered by date desc)
    @returns List of trend alerts
    """
    alerts: list[CDSAlert] = []

    test_code = current_result.get("test_code", "")
    current_value = current_result.get("result_numeric")
    if current_value is None:
        return alerts

    recent = [r for r in historical_results if r.get("result_numeric") is not None]
    if len(recent) < 2:
        return alerts

    prev_value = recent[0].get("result_numeric")
    if prev_value is None or prev_value == 0:
        return alerts

    pct_change = abs((current_value - prev_value) / prev_value) * 100

    # Significant change thresholds by test
    significant_changes: dict[str, dict[str, float | str]] = {
        "CREAT": {"threshold": 50, "desc": "Creatinine change >50% may indicate acute kidney injury (KDIGO criteria)"},
        "K": {"threshold": 20, "desc": "Potassium change >20% — check for hemolysis, medications, renal function"},
        "HGB": {"threshold": 25, "desc": "Hemoglobin drop >25% — evaluate for bleeding or hemolysis"},
        "PLT": {"threshold": 50, "desc": "Platelet change >50% — evaluate for DIC, HIT, or bone marrow pathology"},
        "GLU": {"threshold": 40, "desc": "Glucose change >40% — review insulin/OHA dosing"},
        "TROP": {"threshold": 100, "desc": "Rising troponin — evaluate for acute coronary syndrome"},
        "INR": {"threshold": 30, "desc": "INR change >30% — review anticoagulation dosing"},
        "ALT": {"threshold": 100, "desc": "ALT doubling — evaluate for hepatotoxicity"},
        "LACTATE": {"threshold": 50, "desc": "Lactate rising >50% — evaluate tissue perfusion and sepsis"},
    }

    if test_code in significant_changes and pct_change >= significant_changes[test_code]["threshold"]:
        direction = "increased" if current_value > prev_value else "decreased"
        info = significant_changes[test_code]

        alerts.append(CDSAlert(
            severity=AlertSeverity.HIGH,
            category=AlertCategory.LAB_TREND,
            action=AlertAction.WARN,
            title=f"Lab Trend: {test_code} {direction} {pct_change:.0f}%",
            message=f"{test_code} {direction} from {prev_value} to {current_value} ({pct_change:.0f}% change). {info['desc']}",
            source_rule="lab_trend_analysis",
            affected_items=[test_code],
            evidence={
                "current": current_value,
                "previous": prev_value,
                "pct_change": round(pct_change, 1),
                "direction": direction,
                "threshold": info["threshold"],
            },
        ))

    # Check for organ dysfunction patterns
    if len(recent) >= 3:
        values = [current_value] + [r["result_numeric"] for r in recent[:2]]
        if test_code == "CREAT" and all(v > values[-1] for v in values[:-1]):
            alerts.append(CDSAlert(
                severity=AlertSeverity.HIGH,
                category=AlertCategory.LAB_ORGAN_DYSFUNCTION,
                action=AlertAction.WARN,
                title=f"Progressive Renal Decline: {test_code} trending up",
                message=f"Creatinine has progressively increased over last 3 results: {list(reversed(values))}. Evaluate for AKI staging.",
                source_rule="progressive_organ_decline",
                affected_items=[test_code],
                evidence={"values": list(reversed(values))},
            ))

    return alerts


def check_duplicate_orders(
    order_type: str,
    test_codes: list[str],
    recent_orders: list[dict[str, Any]],
    window_hours: int = 48,
) -> list[CDSAlert]:
    """
    Check for duplicate lab/imaging orders within a time window.

    @param order_type: 'lab' or 'imaging'
    @param test_codes: Tests/studies being ordered
    @param recent_orders: Recent orders for this patient
    @param window_hours: Lookback window in hours
    @returns List of duplicate order alerts
    """
    alerts: list[CDSAlert] = []
    cutoff = datetime.utcnow() - timedelta(hours=window_hours)

    for order in recent_orders:
        order_date = order.get("created_at")
        if order_date and isinstance(order_date, str):
            try:
                order_date = datetime.fromisoformat(order_date)
            except ValueError:
                continue

        if order_date and order_date < cutoff:
            continue

        order_status = order.get("status", "")
        if order_status in ("cancelled",):
            continue

        existing_tests = order.get("test_codes", [])
        if isinstance(existing_tests, str):
            existing_tests = [existing_tests]

        duplicates = set(test_codes) & set(existing_tests)
        if duplicates:
            alerts.append(CDSAlert(
                severity=AlertSeverity.MODERATE,
                category=AlertCategory.DUPLICATE_ORDER,
                action=AlertAction.WARN,
                title=f"Duplicate {order_type} order: {', '.join(duplicates)}",
                message=f"Tests {', '.join(duplicates)} were already ordered within the last {window_hours}h (Order: {order.get('order_number', 'unknown')}).",
                source_rule="duplicate_order_check",
                affected_items=list(duplicates),
                evidence={
                    "existing_order": order.get("order_number"),
                    "window_hours": window_hours,
                },
                overridable=True,
            ))

    return alerts
