"""
Server-side vitals / triage report rendering (A4, ReportLab).

The nurse takes the vitals; the patient keeps a numbered slip and the same
report sits in the patient's history. Per CLAUDE.md printing rules: facility
name in the header, QR code on the document, "Powered by Aifya" in the footer
only.
"""

import textwrap
import uuid
from datetime import datetime
from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

REPORT_TITLE = "VITALS / TRIAGE REPORT"


def _measurement_rows(vital: dict) -> list[tuple[str, str]]:
    """
    Build the measurement rows printed on the report.

    Only what the nurse actually took is listed: a blank row would read as a
    measurement of zero to whoever is holding the slip.

    @param vital: Report fields from `vitals_report_payload`
    @returns (label, value) pairs in clinical reading order
    """
    rows: list[tuple[str, str]] = []

    systolic, diastolic = vital.get("systolic_bp"), vital.get("diastolic_bp")
    if systolic is not None or diastolic is not None:
        rows.append(
            (
                "Blood pressure",
                f"{systolic if systolic is not None else '-'}"
                f"/{diastolic if diastolic is not None else '-'} mmHg",
            )
        )
    if vital.get("heart_rate") is not None:
        rows.append(("Heart rate", f"{vital['heart_rate']} bpm"))
    if vital.get("temperature") is not None:
        site = vital.get("temperature_site")
        suffix = f" ({site})" if site else ""
        rows.append(("Temperature", f"{vital['temperature']}\u00b0C{suffix}"))
    if vital.get("respiratory_rate") is not None:
        rows.append(("Respiratory rate", f"{vital['respiratory_rate']} /min"))
    if vital.get("oxygen_saturation") is not None:
        o2 = " on supplemental O2" if vital.get("on_supplemental_o2") else ""
        rows.append(("Oxygen saturation", f"{vital['oxygen_saturation']}%{o2}"))
    if vital.get("o2_flow_rate") is not None:
        rows.append(("O2 flow rate", f"{vital['o2_flow_rate']} L/min"))
    if vital.get("blood_glucose") is not None:
        timing = vital.get("glucose_timing")
        suffix = f" ({timing})" if timing else ""
        rows.append(("Blood glucose", f"{vital['blood_glucose']} mmol/L{suffix}"))
    if vital.get("pain_score") is not None:
        rows.append(("Pain score", f"{vital['pain_score']} / 10"))
    if vital.get("gcs_total") is not None:
        rows.append(("Glasgow Coma Scale", f"{vital['gcs_total']} / 15"))
    if vital.get("weight_kg") is not None:
        rows.append(("Weight", f"{vital['weight_kg']} kg"))
    if vital.get("height_cm") is not None:
        rows.append(("Height", f"{vital['height_cm']} cm"))
    if vital.get("bmi") is not None:
        rows.append(("BMI", str(vital["bmi"])))
    if vital.get("muac_cm") is not None:
        rows.append(("MUAC", f"{vital['muac_cm']} cm"))
    if vital.get("head_circumference_cm") is not None:
        rows.append(("Head circumference", f"{vital['head_circumference_cm']} cm"))

    return rows


def render_vitals_report_pdf(
    facility_name: str,
    vital: dict,
    patient_name: str | None,
    patient_mrn: str | None,
    recorded_by_name: str | None,
) -> bytes:
    """
    Render the vitals / triage report a nurse issues after taking observations.

    @param facility_name: Facility display name for the header
    @param vital: Report fields from `vitals_report_payload`
    @param patient_name: Patient display name
    @param patient_mrn: Patient MRN
    @param recorded_by_name: Nurse who took the observations
    @returns PDF bytes
    """
    buf = BytesIO()
    page_w, page_h = A4
    pdf = canvas.Canvas(buf, pagesize=A4)
    margin = 20 * mm
    y = page_h - margin

    # Header
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(margin, y, facility_name)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(page_w - margin, y, REPORT_TITLE)
    y -= 8 * mm
    pdf.setFont("Helvetica", 9)
    pdf.drawString(margin, y, f"Report {vital['report_number']}")
    pdf.drawRightString(
        page_w - margin, y, datetime.now().strftime("Printed %Y-%m-%d %H:%M")
    )
    y -= 4 * mm
    pdf.line(margin, y, page_w - margin, y)
    y -= 8 * mm

    # Patient block
    pdf.setFont("Helvetica", 10)
    pdf.drawString(margin, y, f"Patient: {patient_name or '\u2014'}")
    pdf.drawRightString(page_w - margin, y, f"MRN: {patient_mrn or '\u2014'}")
    y -= 5 * mm
    pdf.drawString(margin, y, f"Vitals taken: {vital.get('recorded_at') or '\u2014'}")
    pdf.drawRightString(
        page_w - margin, y, f"Recorded by: {recorded_by_name or '\u2014'}"
    )
    y -= 10 * mm

    # Measurements
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(margin, y, "Measurement")
    pdf.drawRightString(page_w - margin, y, "Value")
    y -= 2 * mm
    pdf.line(margin, y, page_w - margin, y)
    y -= 6 * mm

    rows = _measurement_rows(vital)
    pdf.setFont("Helvetica", 10)
    if not rows:
        pdf.drawString(margin, y, "No measurements were recorded on this report.")
        y -= 6 * mm
    for label, value in rows:
        pdf.drawString(margin, y, label)
        pdf.drawRightString(page_w - margin, y, value)
        y -= 6 * mm
        if y < 60 * mm:
            pdf.showPage()
            y = page_h - margin
            pdf.setFont("Helvetica", 10)

    # Critical findings, so the paper carries the same warning as the screen
    if vital.get("is_critical"):
        y -= 4 * mm
        pdf.setFont("Helvetica-Bold", 10)
        pdf.setFillColorRGB(0.7, 0, 0)
        pdf.drawString(margin, y, "CRITICAL VALUES \u2014 immediate attention required")
        y -= 5 * mm
        pdf.setFont("Helvetica", 9)
        for alert in str(vital.get("critical_alerts") or "").split("; "):
            if alert.strip():
                pdf.drawString(margin, y, alert.strip()[:95])
                y -= 5 * mm
        pdf.setFillColorRGB(0, 0, 0)

    # Summary line mirrors what the patient's history shows. Wrapped rather
    # than cut: a sentence that stops mid-word reads as a printing fault on a
    # slip the patient keeps.
    y -= 6 * mm
    pdf.setFont("Helvetica-Oblique", 9)
    summary = str(vital.get("summary") or "\u2014")
    for line in textwrap.wrap(summary, width=100) or ["\u2014"]:
        if y < 40 * mm:
            pdf.showPage()
            y = page_h - margin
            pdf.setFont("Helvetica-Oblique", 9)
        pdf.drawString(margin, y, line)
        y -= 4 * mm

    # QR: report number + id, so the slip can be verified at the desk
    qr_code = qr.QrCodeWidget(
        f"AIFYA:VR:{vital['report_number']}:{vital['id']}"
    )
    bounds = qr_code.getBounds()
    size = 25 * mm
    drawing = Drawing(
        size,
        size,
        transform=[
            size / (bounds[2] - bounds[0]), 0, 0,
            size / (bounds[3] - bounds[1]), 0, 0,
        ],
    )
    drawing.add(qr_code)
    renderPDF.draw(drawing, pdf, margin, 25 * mm)

    pdf.setFont("Helvetica", 7)
    pdf.drawCentredString(page_w / 2, 15 * mm, "Powered by Aifya")

    pdf.showPage()
    pdf.save()
    return buf.getvalue()


def vitals_report_filename(report_number: str) -> str:
    """Build a safe download filename for a vitals report.

    @param report_number: Report number
    @returns Filename like vitals-VR-20260927-0001.pdf
    """
    safe = "".join(c for c in report_number if c.isalnum() or c in "-_")
    return f"vitals-{safe or uuid.uuid4().hex}.pdf"
