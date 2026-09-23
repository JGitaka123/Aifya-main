"""
Standardized referral note PDF generator.
Uses ReportLab to render an A4 referral letter that includes patient
demographics, presenting complaint, clinical history, vitals, recent labs,
current medications, reason for referral, receiving facility, urgency, and
the referring clinician's signature placeholder.
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def generate_referral_note_pdf(
    db: AsyncSession,
    referral_id: uuid.UUID,
    facility_id: uuid.UUID,
) -> bytes:
    """
    Generate a referral note PDF for the given referral.

    @param db: Async database session
    @param referral_id: Referral UUID
    @param facility_id: Tenant facility UUID (multi-tenant scoping)
    @returns PDF document bytes
    @raises ValueError: If the referral is not found
    """
    from app.models.diagnosis import Diagnosis
    from app.models.facility import Facility
    from app.models.lab import LabResult
    from app.models.patient import Patient
    from app.models.prescription import Prescription
    from app.models.referral import Referral
    from app.models.staff import Staff
    from app.models.vital import VitalSign

    # ── Lookups (all multi-tenant scoped) ────────────────────────────────
    ref_q = await db.execute(
        select(Referral).where(
            Referral.id == referral_id,
            Referral.facility_id == facility_id,
            Referral.is_deleted == False,  # noqa: E712
        )
    )
    referral = ref_q.scalar_one_or_none()
    if referral is None:
        raise ValueError("Referral not found")

    pat_q = await db.execute(
        select(Patient).where(
            Patient.id == referral.patient_id,
            Patient.facility_id == facility_id,
        )
    )
    patient = pat_q.scalar_one_or_none()

    fac_q = await db.execute(
        select(Facility).where(Facility.id == facility_id)
    )
    facility = fac_q.scalar_one_or_none()

    doctor = None
    if referral.referring_doctor_id is not None:
        doctor_q = await db.execute(
            select(Staff).where(
                Staff.id == referral.referring_doctor_id,
                Staff.facility_id == facility_id,
            )
        )
        doctor = doctor_q.scalar_one_or_none()

    vital_q = await db.execute(
        select(VitalSign)
        .where(
            VitalSign.patient_id == referral.patient_id,
            VitalSign.facility_id == facility_id,
            VitalSign.is_deleted == False,  # noqa: E712
        )
        .order_by(VitalSign.created_at.desc())
        .limit(1)
    )
    latest_vital = vital_q.scalar_one_or_none()

    rx_q = await db.execute(
        select(Prescription)
        .where(
            Prescription.patient_id == referral.patient_id,
            Prescription.facility_id == facility_id,
            Prescription.is_deleted == False,  # noqa: E712
        )
        .order_by(Prescription.created_at.desc())
        .limit(10)
    )
    prescriptions = list(rx_q.scalars().all())

    dx_q = await db.execute(
        select(Diagnosis)
        .where(
            Diagnosis.patient_id == referral.patient_id,
            Diagnosis.facility_id == facility_id,
            Diagnosis.is_deleted == False,  # noqa: E712
        )
        .order_by(Diagnosis.created_at.desc())
        .limit(5)
    )
    diagnoses = list(dx_q.scalars().all())

    lab_q = await db.execute(
        select(LabResult)
        .where(
            LabResult.patient_id == referral.patient_id,
            LabResult.facility_id == facility_id,
            LabResult.is_deleted == False,  # noqa: E712
        )
        .order_by(LabResult.created_at.desc())
        .limit(8)
    )
    lab_results = list(lab_q.scalars().all())

    # ── PDF assembly ──────────────────────────────────────────────────────
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Referral Note - {referral.referral_number}",
        author="Aifya HMIS",
    )

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontSize=16,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=4,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=11,
        textColor=colors.HexColor("#1e40af"),
        spaceBefore=8,
        spaceAfter=4,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=12,
    )
    small = ParagraphStyle(
        "Small",
        parent=styles["BodyText"],
        fontSize=8,
        textColor=colors.HexColor("#475569"),
    )

    story: list = []

    # Header
    facility_name = facility.name if facility else "Aifya Facility"
    story.append(Paragraph(facility_name, h1))
    story.append(Paragraph("PATIENT REFERRAL LETTER", h2))
    story.append(Paragraph(f"Ref: <b>{referral.referral_number}</b>", body))
    story.append(
        Paragraph(
            f"Date: {referral.referral_date.strftime('%d %B %Y')} &nbsp;&nbsp; "
            f"Urgency: <b>{referral.urgency.upper()}</b>",
            body,
        )
    )
    story.append(Spacer(1, 0.3 * cm))

    # Patient demographics
    story.append(Paragraph("Patient Demographics", h2))
    if patient is not None:
        dob = (
            patient.date_of_birth.strftime("%d %B %Y")
            if getattr(patient, "date_of_birth", None)
            else "—"
        )
        demo = [
            ["Name", f"{patient.first_name} {patient.last_name}"],
            ["MRN / ID", str(patient.id)[:8]],
            ["Date of Birth", dob],
            ["Sex", patient.gender or "—"],
            ["Phone", patient.phone_number or "—"],
        ]
    else:
        demo = [["Patient", "Not on file"]]
    story.append(_two_col_table(demo))
    story.append(Spacer(1, 0.3 * cm))

    # Reason for referral
    story.append(Paragraph("Reason for Referral", h2))
    story.append(Paragraph(_safe(referral.reason), body))
    if referral.diagnosis:
        story.append(Spacer(1, 0.15 * cm))
        story.append(
            Paragraph(f"<b>Working Diagnosis:</b> {_safe(referral.diagnosis)}", body)
        )
    story.append(Spacer(1, 0.2 * cm))

    # Clinical history & notes
    if referral.clinical_notes:
        story.append(Paragraph("Clinical History &amp; Notes", h2))
        story.append(Paragraph(_safe(referral.clinical_notes), body))
        story.append(Spacer(1, 0.2 * cm))

    # Recent diagnoses
    if diagnoses:
        story.append(Paragraph("Recent Diagnoses", h2))
        rows = [["ICD-10", "Description", "Date"]]
        for d in diagnoses:
            rows.append(
                [
                    d.icd10_code or "—",
                    _safe(d.icd10_description or ""),
                    d.created_at.strftime("%Y-%m-%d") if d.created_at else "—",
                ]
            )
        story.append(_data_table(rows, col_widths=[2.5 * cm, 9.5 * cm, 3 * cm]))
        story.append(Spacer(1, 0.2 * cm))

    # Vitals
    story.append(Paragraph("Latest Vital Signs", h2))
    if latest_vital is not None:
        vit_rows = [
            ["BP",
             (
                 f"{latest_vital.systolic_bp}/{latest_vital.diastolic_bp} mmHg"
                 if latest_vital.systolic_bp and latest_vital.diastolic_bp
                 else "—"
             ),
             "HR",
             f"{latest_vital.heart_rate} bpm" if latest_vital.heart_rate else "—",
            ],
            ["Temp",
             f"{latest_vital.temperature} °C" if latest_vital.temperature else "—",
             "RR",
             f"{latest_vital.respiratory_rate} /min" if getattr(latest_vital, "respiratory_rate", None) else "—",
            ],
            ["SpO2",
             (
                 f"{latest_vital.oxygen_saturation}%"
                 if latest_vital.oxygen_saturation
                 else "—"
             ),
             "Recorded",
             latest_vital.created_at.strftime("%Y-%m-%d %H:%M") if latest_vital.created_at else "—",
            ],
        ]
        story.append(_data_table(vit_rows, col_widths=[2 * cm, 4 * cm, 2 * cm, 4 * cm]))
    else:
        story.append(Paragraph("No vitals recorded.", body))
    story.append(Spacer(1, 0.2 * cm))

    # Lab results summary
    if lab_results:
        story.append(Paragraph("Recent Lab Results", h2))
        rows = [["Test", "Result", "Range", "Status"]]
        for r in lab_results:
            rows.append(
                [
                    _safe(r.test_name or ""),
                    f"{r.result_value or '—'} {r.result_unit or ''}".strip(),
                    r.reference_range or "—",
                    (r.interpretation or r.status or "").upper(),
                ]
            )
        story.append(_data_table(rows, col_widths=[5 * cm, 3.5 * cm, 3.5 * cm, 3 * cm]))
        story.append(Spacer(1, 0.2 * cm))

    # Current medications
    if prescriptions:
        story.append(Paragraph("Current Medications", h2))
        rows = [["Drug", "Dose", "Frequency", "Duration"]]
        for p in prescriptions:
            rows.append(
                [
                    _safe(getattr(p, "drug_name", "")),
                    _safe(getattr(p, "dosage", "") or ""),
                    _safe(getattr(p, "frequency", "") or ""),
                    _safe(getattr(p, "duration", "") or ""),
                ]
            )
        story.append(_data_table(rows, col_widths=[6 * cm, 3 * cm, 3 * cm, 3 * cm]))
        story.append(Spacer(1, 0.2 * cm))

    # Receiving facility
    story.append(Paragraph("Receiving Facility", h2))
    recv = [
        ["Facility", referral.receiving_facility_name or "—"],
        ["MFL Code", referral.receiving_facility_mfl or "—"],
    ]
    story.append(_two_col_table(recv))
    story.append(Spacer(1, 0.4 * cm))

    # Signature
    story.append(Paragraph("Referring Clinician", h2))
    doc_name = (
        f"{getattr(doctor, 'first_name', '') or ''} {getattr(doctor, 'last_name', '') or ''}".strip()
        if doctor is not None
        else "Clinician name on file"
    )
    sig_rows = [
        ["Name", doc_name or "—"],
        ["Signature", "________________________________"],
        ["Date", datetime.now(UTC).strftime("%d %B %Y")],
    ]
    story.append(_two_col_table(sig_rows))
    story.append(Spacer(1, 0.4 * cm))

    story.append(
        Paragraph(
            "This referral note was generated by Aifya HMIS — Powered by Aifya.",
            small,
        )
    )

    doc.build(story)
    return buf.getvalue()


def _safe(text: str | None) -> str:
    """Escape minimal HTML for ReportLab Paragraphs."""
    if not text:
        return "—"
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _two_col_table(rows: list[list[str]]) -> Table:
    """Render a label/value table."""
    t = Table(rows, colWidths=[4 * cm, 12 * cm])
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#475569")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return t


def _data_table(rows: list[list[str]], col_widths: list[float]) -> Table:
    """Render a header+data table."""
    t = Table(rows, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
            ]
        )
    )
    return t
