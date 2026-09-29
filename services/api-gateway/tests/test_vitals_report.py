"""The vitals report a nurse issues after triage.

Recording vitals used to leave a row and an event: nothing the patient could be
handed, and nothing a history could quote by reference. Every recording now
produces a numbered report. These tests pin the two things that can silently
rot - the wording of the summary and the fact that the PDF renders at all, for
a full recording, for a sparse one, and for a critical one.
"""

from types import SimpleNamespace

from app.services.vitals_report_pdf import (
    render_vitals_report_pdf,
    vitals_report_filename,
)
from app.services.vitals_service import build_vitals_summary, vitals_report_payload


def _vital(**overrides) -> SimpleNamespace:
    """Build a vitals row with a full set of measurements.

    @param overrides: Fields to replace
    @returns Stand-in for a persisted VitalSign
    """
    fields = {
        "id": "11111111-1111-1111-1111-111111111111",
        "report_number": "VR-20260927-0001",
        "summary": None,
        "recorded_at": None,
        "systolic_bp": 120,
        "diastolic_bp": 80,
        "heart_rate": 78,
        "temperature": 36.8,
        "temperature_site": "axillary",
        "respiratory_rate": 16,
        "oxygen_saturation": 98.0,
        "on_supplemental_o2": False,
        "o2_flow_rate": None,
        "weight_kg": 70.0,
        "height_cm": 175.0,
        "bmi": 22.9,
        "head_circumference_cm": None,
        "muac_cm": None,
        "pain_score": None,
        "blood_glucose": None,
        "glucose_timing": None,
        "gcs_eye": None,
        "gcs_verbal": None,
        "gcs_motor": None,
        "is_critical": False,
        "critical_alerts": None,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


# ── Summary ─────────────────────────────────────────


def test_summary_lists_the_measurements_that_were_taken():
    """A clinician skimming the history sees only real numbers."""
    summary = build_vitals_summary(_vital())

    assert "BP 120/80 mmHg" in summary
    assert "HR 78 bpm" in summary
    assert "Temp 36.8\u00b0C" in summary
    assert "SpO2 98.0%" in summary
    assert "Weight 70.0 kg" in summary
    assert "BMI 22.9" in summary
    # Nothing was measured for these, so they must not appear at all.
    assert "Glucose" not in summary
    assert "Pain" not in summary
    assert "GCS" not in summary


def test_summary_reports_a_half_taken_blood_pressure():
    """A missing diastolic reads as a dash, never as a zero."""
    summary = build_vitals_summary(_vital(diastolic_bp=None))

    assert "BP 120/\u2014 mmHg" in summary


def test_summary_totals_a_complete_gcs():
    """The coma scale only totals when all three components are present."""
    complete = _vital(gcs_eye=4, gcs_verbal=5, gcs_motor=6)
    assert "GCS 15/15" in build_vitals_summary(complete)

    partial = _vital(gcs_eye=4, gcs_verbal=5, gcs_motor=None)
    assert "GCS" not in build_vitals_summary(partial)


def test_summary_survives_an_empty_recording():
    """A recording with no measurements still has a printable label."""
    blank = _vital(
        systolic_bp=None,
        diastolic_bp=None,
        heart_rate=None,
        temperature=None,
        respiratory_rate=None,
        oxygen_saturation=None,
        weight_kg=None,
        height_cm=None,
        bmi=None,
    )

    assert build_vitals_summary(blank) == "Vitals recorded"


def test_payload_derives_the_summary_when_the_row_has_none():
    """Rows written before the summary column still render a report."""
    payload = vitals_report_payload(_vital(summary=None))

    assert payload["summary"] == build_vitals_summary(_vital(summary=None))
    assert payload["report_number"] == "VR-20260927-0001"


# ── Printed report ──────────────────────────────


def test_report_pdf_renders():
    """The slip the patient keeps is a real PDF."""
    pdf = render_vitals_report_pdf(
        facility_name="Aifya Test Clinic",
        vital=vitals_report_payload(_vital()),
        patient_name="Jane Wanjiru",
        patient_mrn="MRN-0001",
        recorded_by_name="Nurse A. Otieno",
    )

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000


def test_report_pdf_renders_when_nothing_was_measured():
    """An empty recording must not produce a broken page."""
    blank = _vital(
        systolic_bp=None,
        diastolic_bp=None,
        heart_rate=None,
        temperature=None,
        respiratory_rate=None,
        oxygen_saturation=None,
        weight_kg=None,
        height_cm=None,
        bmi=None,
    )

    pdf = render_vitals_report_pdf(
        facility_name="Aifya Test Clinic",
        vital=vitals_report_payload(blank),
        patient_name=None,
        patient_mrn=None,
        recorded_by_name=None,
    )

    assert pdf.startswith(b"%PDF-")


def test_report_pdf_renders_critical_findings():
    """Critical values reach the paper, not only the screen."""
    critical = _vital(
        is_critical=True,
        critical_alerts="Critical high systolic BP: 190 mmHg",
    )

    pdf = render_vitals_report_pdf(
        facility_name="Aifya Test Clinic",
        vital=vitals_report_payload(critical),
        patient_name="John Kamau",
        patient_mrn="MRN-0002",
        recorded_by_name="Nurse B. Achieng",
    )

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000


def test_report_filename_is_safe_and_stable():
    """The download name is derived from the report number."""
    assert vitals_report_filename("VR-20260927-0001") == "vitals-VR-20260927-0001.pdf"
    assert "/" not in vitals_report_filename("VR/2026/0001")

def _pdf_text(pdf: bytes) -> str:
    """Extract the text ReportLab drew on the page.

    @param pdf: Rendered PDF bytes
    @returns Text drawn on the page, in draw order
    """
    import base64
    import re
    import zlib

    drawn: list[str] = []
    for match in re.finditer(rb"(?<!end)stream\r?\n", pdf):
        start = match.end()
        end = pdf.find(b"endstream", start)
        chunk = pdf[start:end].strip()
        if chunk.endswith(b"~>"):
            chunk = chunk[:-2]
        try:
            content = zlib.decompress(base64.a85decode(chunk))
        except Exception:
            continue
        for item in re.finditer(rb"\((?:\\.|[^\\()])*\)\s*Tj", content):
            text = item.group(0)
            text = text[: text.rfind(b")")][1:]
            drawn.append(text.decode("latin-1"))
    return " ".join(drawn)


def test_report_pdf_prints_the_whole_summary():
    """A long summary wraps onto the next line instead of being cut short."""
    summary = (
        "BP 148/92 mmHg HR 96 bpm Temp 37.4C SpO2 96.5% RR 20/min "
        "Glucose 5.6 mmol/L Weight 82.5 kg Height 176.0 cm GCS 15/15"
    )
    pdf = render_vitals_report_pdf(
        facility_name="Aifya Test Clinic",
        vital=vitals_report_payload(_vital(summary=summary)),
        patient_name="Jane Wanjiru",
        patient_mrn="MRN-0001",
        recorded_by_name="Nurse A. Otieno",
    )

    printed = "".join(_pdf_text(pdf).split())
    assert "".join(summary.split()) in printed